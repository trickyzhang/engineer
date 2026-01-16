"""
DVM矩阵模型
"""
from sqlalchemy import Column, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class DVMMatrix(BaseModel):
    """DVM矩阵表"""
    __tablename__ = "dvm_matrix"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )
    design_variable_id = Column(
        Integer,
        ForeignKey("design_variables.id", ondelete="CASCADE"),
        nullable=False,
        comment="设计变量ID"
    )
    value_attribute_id = Column(
        Integer,
        ForeignKey("value_attributes.id", ondelete="CASCADE"),
        nullable=False,
        comment="价值属性ID"
    )

    # 评分
    influence_score = Column(
        Integer,
        default=0,
        comment="影响分数（0/1/3/9）"
    )

    # 关系定义
    project = relationship("Project", back_populates="dvm_matrix")
    design_variable = relationship("DesignVariable", back_populates="dvm_entries")
    value_attribute = relationship("ValueAttribute", back_populates="dvm_entries")

    # 索引和约束
    __table_args__ = (
        UniqueConstraint('design_variable_id', 'value_attribute_id', name='uq_dvm_variable_attribute'),
        Index('idx_dvm_project', 'project_id'),
        Index('idx_dvm_variable', 'design_variable_id'),
        Index('idx_dvm_attribute', 'value_attribute_id'),
        {'comment': 'DVM矩阵表'},
    )

    def __repr__(self):
        return f"<DVMMatrix(id={self.id}, variable={self.design_variable_id}, attribute={self.value_attribute_id}, score={self.influence_score})>"