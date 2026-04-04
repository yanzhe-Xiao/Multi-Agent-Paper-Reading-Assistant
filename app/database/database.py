from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os
load_dotenv()  # Load environment variables from .env file
# 验证 DATABASE_URL 是否正确加载
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

print(f"✓ Using database: {DATABASE_URL}")


# DATABASE_URL = os.getenv("DATABASE_URL") or ""

engine = create_engine(
    DATABASE_URL,
    echo=True
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_session():
    """将生成器转换为上下文管理器"""
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()
