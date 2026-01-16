"""
DVM矩阵 Pydantic Schema
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class DVMMatrixBase(BaseModel):
    """DVM矩阵基础 Schema"""
    design_variable_id: int = Field(..., description="设计变量ID")
    value_attribute_id: int = Field(..., description="价值属性ID")
    influence_score: int = Field(0, description="影响分数（0/1/3/9）")

    @field_validator('influence_score')
    @classmethod
    def validate_influence_score(cls, v):
        """验证DVM评分"""
        allowed_scores = [0, 1, 3, 9]
        if v not in allowed_scores:
            raise ValueError(f"影响分数必须是 {allowed_scores} 之一，当前值: {v}")
        return v


class DVMMatrixCreate(DVMMatrixBase):
    """创建DVM矩阵条目 Schema"""
    project_id: int = Field(..., description="所属项目ID")


class DVMMatrixUpdate(BaseModel):
    """更新DVM矩阵条目 Schema"""
    influence_score: int = Field(..., description="影响分数（0/1/3/9）")

    @field_validator('influence_score')
    @classmethod
    def validate_influence_score(cls, v):
        """验证DVM评分"""
        allowed_scores = [0, 1, 3, 9]
        if v not in allowed_scores:
            raise ValueError(f"影响分数必须是 {allowed_scores} 之一，当前值: {v}")
        return v


class DVMMatrixResponse(DVMMatrixBase):
    """DVM矩阵响应 Schema"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
