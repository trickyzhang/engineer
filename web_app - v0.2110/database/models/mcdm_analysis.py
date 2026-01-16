"""
多准则决策分析模型
"""
from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class MCDMAnalysis(BaseModel):
    """多准则决策分析表"""
    __tablename__ = "mcdm_analyses"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 分析信息
    method = Column(String(50), comment="MCDM方法（如：TOPSIS, AHP, SAW）")
    weights = Column(JSON, comment="属性权重")
    rankings = Column(JSON, comment="方案排名结果")
    scores = Column(JSON, comment="综合得分")

    # 关系定义
    project = relationship("Project", back_populates="mcdm_analyses")

    # 索引
    __table_args__ = (
        Index('idx_mcdm_project', 'project_id'),
        {'comment': '多准则决策分析表'},
    )

    def __repr__(self):
        return f"<MCDMAnalysis(id={self.id}, method='{self.method}')>"
