from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from django.conf import settings

def _build_url() -> Optional[str]:
    cfg = settings.DATABASES.get('analytics') or settings.DATABASES.get('default')
    if isinstance(cfg, str):
        return cfg
    if not isinstance(cfg, dict):
        return None
    name = cfg.get('NAME') or ''
    user = cfg.get('USER') or ''
    password = cfg.get('PASSWORD') or ''
    host = cfg.get('HOST') or 'localhost'
    port = cfg.get('PORT') or '5432'
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"

def get_engine() -> Engine:
    url = _build_url()
    if not url:
        raise RuntimeError('Invalid analytics database configuration')
    return create_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={
            'sslmode': 'require',
            'connect_timeout': 30,
        },
        future=True,
    )

def get_sessionmaker():
    eng = get_engine()
    return sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)

