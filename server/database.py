import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Se existir DATABASE_URL, usa Postgres (produção no Railway)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Exemplo de DATABASE_URL:
    # postgres://usuario:senha@host:port/dbname
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )
else:
    # Fallback: SQLite em arquivo (para desenvolvimento local)
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(PROJECT_ROOT, "usuarios.db")

    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
