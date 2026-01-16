"""
仿真结果模型
"""
from sqlalchemy import Column, Integer, ForeignKey, JSON, Float, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class SimulationResult(BaseModel):
    """仿真结果表"""
    __tablename__ = "simulation_results"

    # 外键
    design_alternative_id = Column(
        Integer,
        ForeignKey("design_alternatives.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属设计方案ID"
    )

    # 结果数据
    performance_metrics = Column(JSON, comment="性能指标值")
    cost_metrics = Column(JSON, comment="成本指标值")
    utility_score = Column(Float, comment="效用分数")
    normalized_metrics = Column(JSON, comment="归一化指标")

    # 关系定义
    design_alternative = relationship("DesignAlternative", back_populates="simulation_results")

    # 索引
    __table_args__ = (
        Index('idx_sim_result_design', 'design_alternative_id'),
        {'comment': '仿真结果表'},
    )

    def __repr__(self):
        return f"<SimulationResult(id={self.id}, design={self.design_alternative_id}, utility={self.utility_score})>"
