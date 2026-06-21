import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Allow running without python-dotenv installed; environment variables may be set externally.
    pass

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    _db_url = os.getenv("DATABASE_URL", "sqlite:///cliniq.db")
    # SQLAlchemy prefers the scheme 'postgresql://' for PostgreSQL URIs
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
