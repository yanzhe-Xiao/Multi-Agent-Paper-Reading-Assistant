"""
数据库配置模块
负责数据库连接、会话管理和基础配置
"""
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# 加载环境变量（从.env文件读取配置）
load_dotenv()

# 获取数据库连接URL
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

print(f"✓ Using database: {DATABASE_URL}")


# 创建数据库引擎
# echo=True 会在控制台打印所有SQL语句（开发环境使用，生产环境建议设为False）
engine = create_engine(
    DATABASE_URL,
    echo=True
)

# 创建会话工厂
# autocommit=False: 禁用自动提交，需要手动调用commit()
# autoflush=False: 禁用自动刷新，需要手动调用flush()或commit()
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# 创建声明性基类，所有ORM模型都继承自此类
Base = declarative_base()


def get_db():
    """
    数据库会话生成器（用于FastAPI依赖注入）
    
    Yields:
        Session: 数据库会话对象
    
    Usage:
        @app.get("/papers")
        def read_papers(db: Session = Depends(get_db)):
            return db.query(Paper).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # 确保会话被正确关闭，避免资源泄漏
        db.close()


@contextmanager
def get_db_session():
    """
    将生成器转换为上下文管理器（用于非FastAPI场景）
    
    Yields:
        Session: 数据库会话对象
    
    Usage:
        with get_db_session() as db:
            papers = db.query(Paper).all()
    """
    db = next(get_db())
    try:
        yield db
    finally:
        db.close()