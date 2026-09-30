import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from channelscout.app import create_app
from channelscout.config import Settings


def test_health_and_unavailable_readiness():
    class Unavailable:
        async def open(self):
            pass

        async def migrate(self):
            pass

        async def close(self):
            pass

        async def ready(self):
            raise RuntimeError()

    with TestClient(create_app(Settings(_env_file=None), Unavailable())) as client:
        assert client.get("/health").json() == {"status": "alive"}
        assert client.get("/ready").status_code == 503


def test_log_redaction(capsys):
    import logging
    from channelscout.logging_config import configure

    configure(Settings(_env_file=None, telegram_token="secret-token"))
    logging.getLogger("channelscout").info("token=%s", "secret-token")
    output = capsys.readouterr().err
    assert "secret-token" not in output
    assert "[REDACTED]" in output


def test_invalid_config_does_not_expose_secret():
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, telegram_token="canary", mode="webhook")
    assert "canary" not in str(error.value)


def test_secret_redaction_and_mode_validation():
    s = Settings(_env_file=None, telegram_token="private-token", database_url="private-db")
    assert "private-token" not in repr(s)
    assert "private-db" not in repr(s)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode="webhook", telegram_token="x")
    with pytest.raises(ValidationError):
        Settings(_env_file=None, mode="both")
