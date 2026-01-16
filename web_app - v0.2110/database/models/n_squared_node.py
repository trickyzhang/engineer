"""
N-squared节点模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class NSquaredNode(BaseModel):
    """N-squared节点表"""
    __tablename__ = "n_squared_nodes"

    # 外键
    diagram_id = Column(
        Integer,
        ForeignKey("n_squared_diagrams.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属图表ID"
    )

    # 节点信息
    node_id = Column(String(50), nullable=False, comment="节点标识符")
    name = Column(String(255), nullable=False, comment="节点名称")
    description = Column(Text, comment="节点描述")
    position = Column(Integer, comment="节点位置索引")

    # 关系定义
    diagram = relationship("NSquaredDiagram", back_populates="nodes")
    outgoing_edges = relationship(
        "NSquaredEdge",
        foreign_keys="NSquaredEdge.source_node_id",
        back_populates="source_node",
        cascade="all, delete-orphan"
    )
    incoming_edges = relationship(
        "NSquaredEdge",
        foreign_keys="NSquaredEdge.target_node_id",
        back_populates="target_node",
        cascade="all, delete-orphan"
    )

    # 索引
    __table_args__ = (
        Index('idx_nsq_node_diagram', 'diagram_id'),
        Index('idx_nsq_node_id', 'node_id'),
        {'comment': 'N-squared节点表'},
    )

    def __repr__(self):
        return f"<NSquaredNode(id={self.id}, node_id='{self.node_id}', name='{self.name}')>"
