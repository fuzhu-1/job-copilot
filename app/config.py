from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "job-copilot"
    database_url: str = "sqlite:///./data/job_copilot.db"
    chroma_path: str = "./data/chroma"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    upload_dir: str = "./data/uploads"
    search_api_key: str = ""
    search_provider: str = "tavily"
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
