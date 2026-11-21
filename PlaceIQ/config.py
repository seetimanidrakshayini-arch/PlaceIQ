"""Central configuration, read from environment variables / .env file."""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(v, default=False):
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key")
    DEBUG = _bool(os.getenv("FLASK_DEBUG"), False)
    PORT = int(os.getenv("PORT", "5000"))

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "placeiq")

    OFFICER_NAME = os.getenv("OFFICER_NAME", "Placement Officer")
    OFFICER_EMAIL = os.getenv("OFFICER_EMAIL", "officer@example.com")
    OFFICER_PASSWORD = os.getenv("OFFICER_PASSWORD", "ChangeMe@123")
    OFFICER_SIGNUP_CODE = os.getenv("OFFICER_SIGNUP_CODE", "")

    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "resumes")
    MAX_RESUME_MB = int(os.getenv("MAX_RESUME_MB", "5"))
    MAX_CONTENT_LENGTH = (MAX_RESUME_MB + 1) * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours
