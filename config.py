import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'presentearfoz.db'}")
    # Railway/Heroku sometimes expose the old postgres:// prefix.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me-before-production")
    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", 25 * 1024 * 1024))
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(BASE_DIR / "app" / "static" / "uploads"))
    SESSION_COOKIE_NAME = "presentearfoz_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.getenv("SESSION_DAYS", "180")))

    SITE_URL = os.getenv("SITE_URL", "http://localhost:5000").rstrip("/")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@presentearfoz.com.br")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "TroqueEstaSenha123!")
    AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "true").lower() == "true"
    SEED_DEMO = os.getenv("SEED_DEMO", "true").lower() == "true"


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    SERVER_NAME = "localhost"
