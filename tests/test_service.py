import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from channelscout.app import create_app
from channelscout.config import Settings


def test_health_and_unavailable_readiness():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.get('/health').json() == {'status': 'alive'}
        assert client.get('/ready').status_code == 503


def test_secret_redaction_and_mode_validation():
    s = Settings(_env_file=None, telegram_token='private-token', database_url='private-db')
    assert 'private-token' not in repr(s)
    assert 'private-db' not in repr(s)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode='webhook', telegram_token='x')
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode='both')
