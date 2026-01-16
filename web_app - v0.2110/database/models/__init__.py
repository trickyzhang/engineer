"""
数据库模型包初始化
"""
from database.models.base import Base, BaseModel, TimestampMixin

# 项目管理相关
from database.models.project import Project, ProjectStatus
from database.models.mission import Mission
from database.models.project_state import ProjectState

# Phase 1: 问题定义
from database.models.design_variable import DesignVariable, VariableType
from database.models.value_attribute import ValueAttribute, OptimizationDirection
from database.models.dvm_matrix import DVMMatrix

# Phase 2: 物理架构
from database.models.n_squared_diagram import NSquaredDiagram
from database.models.n_squared_node import NSquaredNode
from database.models.n_squared_edge import NSquaredEdge

# Phase 3: 效用建模
from database.models.user_model import UserModel, ModelType
from database.models.model_version import ModelVersion

# Phase 4-8: 设计空间与分析
from database.models.design_alternative import DesignAlternative
from database.models.simulation_result import SimulationResult
from database.models.sensitivity_analysis import SensitivityAnalysis
from database.models.pareto_analysis import ParetoAnalysis
from database.models.mcdm_analysis import MCDMAnalysis

__all__ = [
    # 基础类
    "Base",
    "BaseModel",
    "TimestampMixin",

    # 项目管理
    "Project",
    "ProjectStatus",
    "Mission",
    "ProjectState",

    # Phase 1
    "DesignVariable",
    "VariableType",
    "ValueAttribute",
    "OptimizationDirection",
    "DVMMatrix",

    # Phase 2
    "NSquaredDiagram",
    "NSquaredNode",
    "NSquaredEdge",

    # Phase 3
    "UserModel",
    "ModelType",
    "ModelVersion",

    # Phase 4-8
    "DesignAlternative",
    "SimulationResult",
    "SensitivityAnalysis",
    "ParetoAnalysis",
    "MCDMAnalysis",
]
