"""
用户定义模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from database.models.base import BaseModel
import enum


class ModelType(enum.Enum):
    """模型类型枚举"""
    PERFORMANCE = "performance"
    COST = "cost"
    UTILITY = "utility"


class UserModel(BaseModel):
    """用户定义模型表"""
    __tablename__ = "user_models"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 模型信息
    name = Column(String(255), nullable=False, comment="模型名称")
    model_type = Column(
        Enum(ModelType),
        nullable=False,
        comment="模型类型"
    )
    description = Column(Text, comment="模型描述")
    formula = Column(Text, comment="模型公式")
    parameters = Column(JSON, comment="模型参数")
    code = Column(Text, comment="Python代码")

    # 关系定义
    project = relationship("Project", back_populates="user_models")
    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")

    # 约束
    __table_args__ = (
        {'comment': '用户定义模型表'},
    )

    def __repr__(self):
        return f"<UserModel(id={self.id}, name='{self.name}', type={self.model_type})>"
