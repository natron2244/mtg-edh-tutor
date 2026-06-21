from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_provider: str = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4:26"

    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    scryfall_base_url: str = "https://api.scryfall.com"
    scryfall_rate_limit_delay: float = 0.1


settings = Settings()
