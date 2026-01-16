"""
数据库配置管理
"""
import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据库文件路径
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f'sqlite:///{BASE_DIR}/project.db'
)

# SQLAlchemy配置
SQLALCHEMY_CONFIG = {
    'echo': os.getenv('DB_ECHO', 'False') == 'True',  # 是否打印SQL语句
    'pool_pre_ping': True,  # 连接池健康检查
    'pool_recycle': 3600,   # 连接回收时间（秒）
}

# Alembic配置
ALEMBIC_CONFIG = {
    'script_location': 'database/migrations',
    'sqlalchemy.url': DATABASE_URL,
}