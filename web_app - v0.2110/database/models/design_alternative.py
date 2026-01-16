"""
设计方案模型
"""
from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class DesignAlternative(BaseModel):
    """设计方案表"""
    __tablename__ = "design_alternatives"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 方案信息
    name = Column(String(255), nullable=False, comment="方案名称")
    design_vector = Column(JSON, nullable=False, comment="设计变量值向量")
    generation_method = Column(String(50), comment="生成方法（如：full_factorial, orthogonal）")

    # 关系定义
    project = relationship("Project", back_populates="design_alternatives")
    simulation_results = relationship("SimulationResult", back_populates="design_alternative", cascade="all, delete-orphan")

    # 索引
    __table_args__ = (
        Index('idx_design_alt_project', 'project_id'),
        {'comment': '设计方案表'},
    )

    def __repr__(self):
        return f"<DesignAlternative(id={self.id}, name='{self.name}')>"
