from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    bot_token: str = "test-token"

    # Хранилища
    database_url: str = "postgresql+asyncpg://bukafit:bukafit@localhost:5432/bukafit"
    redis_url: str = "redis://localhost:6379/0"

    # ИИ-провайдер
    ai_provider: str = "mock"  # mock | codex
    codex_bin: str = "codex"
    codex_timeout: int = 60

    # Режим Telegram
    use_webhook: bool = False
    webhook_url: str = ""
    webhook_path: str = "/webhook"
    web_host: str = "0.0.0.0"
    web_port: int = 8080

    # Прочее
    tz: str = "Asia/Tashkent"


settings = Settings()
