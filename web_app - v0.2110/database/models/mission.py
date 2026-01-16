"""
任务定义模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class Mission(BaseModel):
    """任务定义表"""
    __tablename__ = "missions"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属项目ID"
    )

    # 任务信息
    title = Column(String(255), nullable=False, comment="任务标题")
    description = Column(Text, comment="任务描述")
    key_objectives = Column(JSON, comment="关键目标列表")
    value_proposition = Column(Text, comment="价值主张")

    # 关系定义
    project = relationship("Project", back_populates="missions")

    def __repr__(self):
        return f"<Mission(id={self.id}, title='{self.title}')>"