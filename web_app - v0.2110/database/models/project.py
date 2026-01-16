"""
项目模型定义
"""
from sqlalchemy import Column, String, Text, Enum
from sqlalchemy.orm import relationship
from database.models.base import BaseModel
import enum


class ProjectStatus(enum.Enum):
    """项目状态枚举"""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Project(BaseModel):
    """项目主表"""
    __tablename__ = "projects"

    # 基本信息
    name = Column(String(255), nullable=False, comment="项目名称")
    description = Column(Text, comment="项目描述")
    created_by = Column(String(100), default="System", comment="创建者")
    status = Column(
        Enum(ProjectStatus),
        default=ProjectStatus.DRAFT,
        nullable=False,
        comment="项目状态"
    )

    # 关系定义
    # 一对一关系
    project_state = relationship("ProjectState", back_populates="project", uselist=False, cascade="all, delete-orphan")
    n_squared_diagram = relationship("NSquaredDiagram", back_populates="project", uselist=False, cascade="all, delete-orphan")

    # 一对多关系
    missions = relationship("Mission", back_populates="project", cascade="all, delete-orphan")
    value_attributes = relationship("ValueAttribute", back_populates="project", cascade="all, delete-orphan")
    design_variables = relationship("DesignVariable", back_populates="project", cascade="all, delete-orphan")
    dvm_matrix = relationship("DVMMatrix", back_populates="project", cascade="all, delete-orphan")
    user_models = relationship("UserModel", back_populates="project", cascade="all, delete-orphan")
    design_alternatives = relationship("DesignAlternative", back_populates="project", cascade="all, delete-orphan")
    sensitivity_analyses = relationship("SensitivityAnalysis", back_populates="project", cascade="all, delete-orphan")
    pareto_analyses = relationship("ParetoAnalysis", back_populates="project", cascade="all, delete-orphan")
    mcdm_analyses = relationship("MCDMAnalysis", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name='{self.name}')>"