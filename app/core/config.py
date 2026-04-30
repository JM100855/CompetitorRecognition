from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Competitor Watch"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/competitor_intel.db"
    scrape_time_utc: str = "09:00"
    request_timeout_seconds: int = 20
    default_user_agent: str = "SignalNotebook/0.1 (+personal research)"
    discovery_strategy: str = "hybrid"
    max_discovered_sources: int = 12
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
