"""
N-squared图表模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class NSquaredDiagram(BaseModel):
    """N-squared图表"""
    __tablename__ = "n_squared_diagrams"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="所属项目ID"
    )

    # 图表信息
    name = Column(String(255), nullable=False, comment="图表名称")
    description = Column(Text, comment="图表描述")
    diagram_metadata = Column(JSON, comment="图表元数据")

    # 关系定义
    project = relationship("Project", back_populates="n_squared_diagram")
    nodes = relationship("NSquaredNode", back_populates="diagram", cascade="all, delete-orphan")
    edges = relationship("NSquaredEdge", back_populates="diagram", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NSquaredDiagram(id={self.id}, name='{self.name}')>"
