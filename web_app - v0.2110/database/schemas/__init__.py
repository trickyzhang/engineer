"""
Pydantic Schemas - Data Validation Layer
"""

from database.schemas.project import (
    ProjectBase,
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse
)

from database.schemas.design_variable import (
    DesignVariableBase,
    DesignVariableCreate,
    DesignVariableUpdate,
    DesignVariableResponse
)

from database.schemas.value_attribute import (
    ValueAttributeBase,
    ValueAttributeCreate,
    ValueAttributeUpdate,
    ValueAttributeResponse
)

from database.schemas.dvm_matrix import (
    DVMMatrixBase,
    DVMMatrixCreate,
    DVMMatrixUpdate,
    DVMMatrixResponse
)

__all__ = [
    # Project schemas
    "ProjectBase",
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",

    # Design Variable schemas
    "DesignVariableBase",
    "DesignVariableCreate",
    "DesignVariableUpdate",
    "DesignVariableResponse",

    # Value Attribute schemas
    "ValueAttributeBase",
    "ValueAttributeCreate",
    "ValueAttributeUpdate",
    "ValueAttributeResponse",

    # DVM Matrix schemas
    "DVMMatrixBase",
    "DVMMatrixCreate",
    "DVMMatrixUpdate",
    "DVMMatrixResponse",
]
