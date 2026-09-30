import logging


def configure(settings):
    secrets = [
        settings.telegram_token.get_secret_value(),
        settings.database_url.get_secret_value(),
        settings.webhook_secret.get_secret_value(),
    ]

    class Redact(logging.Filter):
        def filter(self, record):
            text = record.getMessage()
            for secret in secrets:
                if secret:
                    text = text.replace(secret, "[REDACTED]")
            record.msg, record.args = text, ()
            return True

    logger = logging.getLogger("channelscout")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.addFilter(Redact())
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # HTTP libraries may otherwise log Bot API URLs containing tokens.
    for name in ("httpx", "httpcore", "telegram", "psycopg.pool"):
        logging.getLogger(name).setLevel(logging.CRITICAL)
