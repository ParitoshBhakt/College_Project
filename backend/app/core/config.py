from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SentiFace API"
    app_env: str = "development"
    database_url: str = "sqlite:///./sentiface.db"
    jwt_secret_key: str = "change_me_for_production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    rate_limit_per_minute: int = 60
    model_path: str = "app/models_store/emotion_resnet18.pt"
    gan_generator_path: str = "app/models_store/dcgan_generator.pt"
    frontend_origin: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()