"""
基础模型定义
"""
from datetime import datetime
from typing import Any, Dict
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import declared_attr


# 创建Base类
Base = declarative_base()


class TimestampMixin:
    """时间戳混入类"""

    @declared_attr
    def created_at(self):
        return Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")

    @declared_attr
    def updated_at(self):
        return Column(
            DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
            comment="更新时间"
        )


class BaseModel(Base, TimestampMixin):
    """基础模型类"""
    __abstract__ = True

    # 所有模型都有id主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")

    def to_dict(self, exclude: list = None) -> Dict[str, Any]:
        """
        将模型转换为字典

        Args:
            exclude: 要排除的字段列表

        Returns:
            字典格式的模型数据
        """
        exclude = exclude or []
        result = {}

        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                # 处理datetime类型
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value

        return result

    def update_from_dict(self, data: Dict[str, Any], exclude: list = None):
        """
        从字典更新模型

        Args:
            data: 数据字典
            exclude: 要排除的字段列表
        """
        exclude = exclude or ['id', 'created_at', 'updated_at']

        for key, value in data.items():
            if key not in exclude and hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self):
        """字符串表示"""
        return f"<{self.__class__.__name__}(id={self.id})>"