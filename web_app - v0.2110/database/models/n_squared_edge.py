"""
N-squared边模型
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.models.base import BaseModel


class NSquaredEdge(BaseModel):
    """N-squared边表"""
    __tablename__ = "n_squared_edges"

    # 外键
    diagram_id = Column(
        Integer,
        ForeignKey("n_squared_diagrams.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属图表ID"
    )
    source_node_id = Column(
        Integer,
        ForeignKey("n_squared_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="源节点ID"
    )
    target_node_id = Column(
        Integer,
        ForeignKey("n_squared_nodes.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标节点ID"
    )

    # 边信息
    interface_type = Column(String(100), comment="接口类型")
    description = Column(Text, comment="接口描述")

    # 关系定义
    diagram = relationship("NSquaredDiagram", back_populates="edges")
    source_node = relationship(
        "NSquaredNode",
        foreign_keys=[source_node_id],
        back_populates="outgoing_edges"
    )
    target_node = relationship(
        "NSquaredNode",
        foreign_keys=[target_node_id],
        back_populates="incoming_edges"
    )

    # 索引
    __table_args__ = (
        Index('idx_nsq_edge_diagram', 'diagram_id'),
        Index('idx_nsq_edge_source', 'source_node_id'),
        Index('idx_nsq_edge_target', 'target_node_id'),
        {'comment': 'N-squared边表'},
    )

    def __repr__(self):
        return f"<NSquaredEdge(id={self.id}, source={self.source_node_id}, target={self.target_node_id})>"
