from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# 初始化 MySQL 连接池和 ORM 会话管理

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# 创建数据库引擎
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, future=True, pool_pre_ping=True, pool_recycle=1800)
# 创建数据库会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
# 创建ORM基类
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
