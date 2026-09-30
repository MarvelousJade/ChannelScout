from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    database_url: SecretStr = SecretStr("postgresql://scout:scout@localhost:5432/scout")
    telegram_token: SecretStr = SecretStr("")
    mode: Literal["off", "polling", "webhook"] = "off"
    webhook_url: str = ""
    webhook_secret: SecretStr = SecretStr("")
    allowed_chat_ids: str = ""

    @property
    def allowlist(self) -> set[int]:
        return {int(x.strip()) for x in self.allowed_chat_ids.split(",") if x.strip()}

    @model_validator(mode="after")
    def validate_mode(self):
        self.allowlist
        if self.mode != "off" and not self.telegram_token.get_secret_value():
            raise ValueError("Telegram mode requires a token")
        if self.mode == "webhook":
            import re

            secret = self.webhook_secret.get_secret_value()
            if not self.webhook_url.startswith("https://") or not re.fullmatch(
                r"[\w-]{1,256}", secret, re.ASCII
            ):
                raise ValueError("Webhook requires HTTPS URL and valid secret")
        return self
