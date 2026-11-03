import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _g(k, d=""):
    return os.getenv(k, d).strip()


class Settings:
    llm_provider = _g("LLM_PROVIDER", "gemini").lower()
    gemini_key = _g("GEMINI_API_KEY")
    gemini_model = _g("GEMINI_MODEL", "gemini-3.8-flash")
    openai_key = _g("OPENAI_API_KEY")
    openai_base = _g("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model = _g("OPENAI_MODEL", "gpt-4o-mini")
    whisper_model = _g("WHISPER_MODEL", "base.en")
    whisper_language = _g("WHISPER_LANGUAGE", "en")
    jwt_secret = _g("JWT_SECRET", "dev-insecure-secret-change-me")
    jwt_expire_minutes = int(_g("JWT_EXPIRE_MINUTES", "720"))
    admin_email = _g("ADMIN_EMAIL").lower()
    database_url = _g("DATABASE_URL", f"sqlite:///{(BASE_DIR / 'interview.db').as_posix()}")
    max_upload_mb = int(_g("MAX_UPLOAD_MB", "200"))
    retention_days = int(_g("RECORDING_RETENTION_DAYS", "30"))
    cors = [o.strip() for o in _g("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    storage_dir = BASE_DIR / "storage"
    model_dir = BASE_DIR / "models"


settings = Settings()
settings.storage_dir.mkdir(exist_ok=True)
settings.model_dir.mkdir(exist_ok=True)
