"""
项目状态模型
"""
from sqlalchemy import Column, String, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class ProjectState(BaseModel):
    """项目状态表"""
    __tablename__ = "project_states"

    # 外键
    project_id = Column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="所属项目ID"
    )

    # 状态信息
    current_phase = Column(String(20), comment="当前阶段")
    current_step = Column(Integer, comment="当前步骤")
    step_statuses = Column(JSON, comment="各步骤状态")
    last_accessed = Column(DateTime, comment="最后访问时间")

    # 关系定义
    project = relationship("Project", back_populates="project_state")

    def __repr__(self):
        return f"<ProjectState(id={self.id}, project_id={self.project_id}, phase='{self.current_phase}')>"