"""Application configuration."""
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'supermart-secure-pos-key-2026-prod-jwt-secret')
    
    # Database configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    USE_SQLITE = os.environ.get('USE_SQLITE', 'false').lower() == 'true'
    IS_VERCEL = os.environ.get('VERCEL') == '1' or 'VERCEL' in os.environ

    if DATABASE_URL:
        if DATABASE_URL.startswith('postgres://'):
            DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    elif USE_SQLITE or IS_VERCEL:
        if IS_VERCEL:
            db_path = os.path.join(tempfile.gettempdir(), 'supermart.db')
        else:
            db_path = os.path.join(os.path.dirname(__file__), 'supermart.db')
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"
    else:
        DB_HOST = os.environ.get('DB_HOST', 'localhost')
        DB_PORT = os.environ.get('DB_PORT', '3306')
        DB_NAME = os.environ.get('DB_NAME', 'supermart_pos')
        DB_USER = os.environ.get('DB_USER', 'root')
        DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
            "?charset=utf8mb4"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    if 'sqlite' in SQLALCHEMY_DATABASE_URI:
        SQLALCHEMY_ENGINE_OPTIONS = {}
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 10,
            'pool_recycle': 3600,
            'pool_pre_ping': True,
        }
    
    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 28800  # 8 hours
    
    # WTF CSRF
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None  # Valid for the entire life of the session (prevents 1-hour expiration)
    
    # Upload
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Application
    DEFAULT_CURRENCY = os.environ.get('DEFAULT_CURRENCY', 'INR')
    DEFAULT_TAX_TYPE = os.environ.get('DEFAULT_TAX_TYPE', 'intra-state')


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    WTF_CSRF_SSL_STRICT = False


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}

