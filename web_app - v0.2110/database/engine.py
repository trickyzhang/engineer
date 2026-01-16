"""
数据库引擎和会话管理
"""
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.engine import Engine
from database.config import DATABASE_URL, SQLALCHEMY_CONFIG


# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    **SQLALCHEMY_CONFIG
)


# 启用SQLite外键约束
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """为SQLite启用外键约束"""
    if "sqlite" in DATABASE_URL:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# 创建会话工厂
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    获取数据库会话的上下文管理器

    Example:
        with get_db_session() as session:
            # 使用session进行数据库操作
            session.query(Project).all()
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库会话（用于FastAPI依赖注入）

    Example:
        @app.get("/projects")
        def get_projects(db: Session = Depends(get_db)):
            return db.query(Project).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """
    初始化数据库
    - 创建所有表
    - 设置初始数据（如果需要）
    """
    from database.models.base import Base

    # 创建所有表
    Base.metadata.create_all(bind=engine)

    print(f"✅ 数据库初始化完成: {DATABASE_URL}")

    # 可选：创建默认项目
    with get_db_session() as session:
        from database.models.project import Project

        # 检查是否已有默认项目
        default_project = session.query(Project).filter_by(
            name="默认项目"
        ).first()

        if not default_project:
            # 创建默认项目
            default_project = Project(
                name="默认项目",
                description="系统自动创建的默认项目",
                created_by="System",
                status="active"
            )
            session.add(default_project)
            session.commit()
            print(f"✅ 创建默认项目: ID={default_project.id}")


def close_database():
    """关闭数据库连接"""
    engine.dispose()
    print("✅ 数据库连接已关闭")


# 健康检查函数
def check_database_connection() -> bool:
    """
    检查数据库连接是否正常

    Returns:
        bool: 连接正常返回True，否则返回False
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False