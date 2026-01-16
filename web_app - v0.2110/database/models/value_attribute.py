"""
价值属性模型
"""
from sqlalchemy import Column, String, Float, Text, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
from database.models.base import BaseModel
import enum


class OptimizationDirection(enum.Enum):
    """优化方向枚举"""
    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ValueAttribute(BaseModel):
    """价值属性表"""
    __tablename__ = "value_attributes"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 属性信息
    name = Column(String(100), nullable=False, comment="属性名称")
    unit = Column(String(50), comment="单位")
    ideal_value = Column(Float, comment="理想值")
    worst_value = Column(Float, comment="最差值")
    optimization_direction = Column(
        Enum(OptimizationDirection),
        comment="优化方向"
    )
    weight = Column(Float, default=1.0, comment="权重")
    definition = Column(Text, comment="属性定义")

    # 关系定义
    project = relationship("Project", back_populates="value_attributes")
    dvm_entries = relationship("DVMMatrix", back_populates="value_attribute", cascade="all, delete-orphan")

    # 唯一约束
    __table_args__ = (
        {'comment': '价值属性表'},
    )

    def __repr__(self):
        return f"<ValueAttribute(id={self.id}, name='{self.name}', weight={self.weight})>"