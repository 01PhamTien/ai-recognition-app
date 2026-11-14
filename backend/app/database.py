from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_engine(url: str):
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    options = {"check_same_thread": False} if url.startswith("sqlite") else {"connect_timeout": 5}
    return create_engine(url, pool_pre_ping=True, connect_args=options)


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
