"""
设计变量模型
"""
from sqlalchemy import Column, String, Float, Text, Integer, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship
from database.models.base import BaseModel
import enum


class VariableType(enum.Enum):
    """变量类型枚举"""
    CONTINUOUS = "continuous"
    DISCRETE = "discrete"
    CATEGORICAL = "categorical"


class DesignVariable(BaseModel):
    """设计变量表"""
    __tablename__ = "design_variables"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 变量信息
    name = Column(String(100), nullable=False, comment="变量名称")
    variable_type = Column(
        Enum(VariableType),
        nullable=False,
        comment="变量类型"
    )
    range_min = Column(Float, comment="最小值（连续变量）")
    range_max = Column(Float, comment="最大值（连续变量）")
    options = Column(JSON, comment="选项列表（离散/分类变量）")
    unit = Column(String(50), comment="单位")
    description = Column(Text, comment="变量描述")

    # 关系定义
    project = relationship("Project", back_populates="design_variables")
    dvm_entries = relationship("DVMMatrix", back_populates="design_variable", cascade="all, delete-orphan")

    # 唯一约束
    __table_args__ = (
        {'comment': '设计变量表'},
    )

    def __repr__(self):
        return f"<DesignVariable(id={self.id}, name='{self.name}', type={self.variable_type})>"