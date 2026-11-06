from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = "postgresql://sinistre:sinistre@127.0.0.1:5433/sinistre"
    embeddings_url: str = "http://127.0.0.1:8081"  # TEI-compatible server (BGE-M3, 1024 dims)
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.8-flash"
    extract_model: str = "gemini-3.5-flash"
    data_dir: Path = ROOT / "data"
    max_analyses_par_jour: int = 300
    max_analyses_par_ip_heure: int = 10
    precompute: bool = True  # warm the cache with the examples at startup


@lru_cache
def get_settings() -> Settings:
    return Settings()
