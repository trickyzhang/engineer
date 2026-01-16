"""
模型版本模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class ModelVersion(BaseModel):
    """模型版本表"""
    __tablename__ = "model_versions"

    # 外键
    model_id = Column(
        Integer,
        ForeignKey("user_models.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属模型ID"
    )

    # 版本信息
    version = Column(String(50), nullable=False, comment="版本号")
    description = Column(Text, comment="版本描述")
    code = Column(Text, nullable=False, comment="代码快照")
    is_active = Column(Boolean, default=False, comment="是否为活动版本")

    # 关系定义
    model = relationship("UserModel", back_populates="versions")

    # 索引
    __table_args__ = (
        Index('idx_model_version', 'model_id', 'version'),
        {'comment': '模型版本表'},
    )

    def __repr__(self):
        return f"<ModelVersion(id={self.id}, model={self.model_id}, version='{self.version}')>"
