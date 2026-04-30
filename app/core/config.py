from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CompetitorRecognition"
    app_env: str = "development"
    database_url: str = "sqlite:///./data/competitor_intel.db"
    scrape_time_utc: str = "09:00"
    request_timeout_seconds: int = 20
    default_user_agent: str = "CompetitorRecognition/0.1 (+research agent)"
    discovery_strategy: str = "hybrid"
    max_discovered_sources: int = 12
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ddg_region: str = "us-en"
    ddg_max_results: int = 10
    gemini_model: str = "gemini-1.5-flash"
    gemini_api_key: str | None = None
    chroma_path: str = "./data/chroma"
    chroma_collection_name: str = "competitive_web_docs"
    kuzu_path: str = "./data/kuzu"
    streamlit_title: str = "CompetitorRecognition"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
