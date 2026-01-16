"""
敏感性分析模型
"""
from sqlalchemy import Column, String, Integer, ForeignKey, JSON, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class SensitivityAnalysis(BaseModel):
    """敏感性分析表"""
    __tablename__ = "sensitivity_analyses"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 分析信息
    analysis_type = Column(String(50), comment="分析类型（如：local, global）")
    variable_name = Column(String(255), comment="分析的变量名")
    results = Column(JSON, comment="分析结果数据")
    tornado_data = Column(JSON, comment="龙卷风图数据")

    # 关系定义
    project = relationship("Project", back_populates="sensitivity_analyses")

    # 索引
    __table_args__ = (
        Index('idx_sensitivity_project', 'project_id'),
        {'comment': '敏感性分析表'},
    )

    def __repr__(self):
        return f"<SensitivityAnalysis(id={self.id}, type='{self.analysis_type}', variable='{self.variable_name}')>"
