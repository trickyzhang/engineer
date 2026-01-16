"""
帕累托分析模型
"""
from sqlalchemy import Column, Integer, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class ParetoAnalysis(BaseModel):
    """帕累托分析表"""
    __tablename__ = "pareto_analyses"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 分析数据
    pareto_front = Column(JSON, comment="帕累托前沿设计方案IDs")
    dominated_solutions = Column(JSON, comment="被支配的方案IDs")
    objective_values = Column(JSON, comment="目标值数据")

    # 关系定义
    project = relationship("Project", back_populates="pareto_analyses")

    # 索引
    __table_args__ = (
        Index('idx_pareto_project', 'project_id'),
        {'comment': '帕累托分析表'},
    )

    def __repr__(self):
        return f"<ParetoAnalysis(id={self.id}, project={self.project_id})>"
