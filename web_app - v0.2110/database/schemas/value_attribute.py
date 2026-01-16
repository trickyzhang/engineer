"""
价值属性 Pydantic Schema
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class ValueAttributeBase(BaseModel):
    """价值属性基础 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="属性名称")
    unit: Optional[str] = Field(None, max_length=50, description="单位")
    ideal_value: Optional[float] = Field(None, description="理想值")
    worst_value: Optional[float] = Field(None, description="最差值")
    optimization_direction: Optional[str] = Field(None, description="优化方向：maximize/minimize")
    weight: float = Field(1.0, ge=0.0, le=1.0, description="权重（0-1之间）")
    definition: Optional[str] = Field(None, description="属性定义")

    @field_validator('optimization_direction')
    @classmethod
    def validate_optimization_direction(cls, v):
        """验证优化方向"""
        if v is not None:
            allowed_directions = ['maximize', 'minimize']
            if v not in allowed_directions:
                raise ValueError(f"优化方向必须是 {allowed_directions} 之一，当前值: {v}")
        return v


class ValueAttributeCreate(ValueAttributeBase):
    """创建价值属性 Schema"""
    project_id: int = Field(..., description="所属项目ID")


class ValueAttributeUpdate(BaseModel):
    """更新价值属性 Schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="属性名称")
    unit: Optional[str] = Field(None, max_length=50, description="单位")
    ideal_value: Optional[float] = Field(None, description="理想值")
    worst_value: Optional[float] = Field(None, description="最差值")
    optimization_direction: Optional[str] = Field(None, description="优化方向")
    weight: Optional[float] = Field(None, ge=0.0, le=1.0, description="权重")
    definition: Optional[str] = Field(None, description="属性定义")


class ValueAttributeResponse(ValueAttributeBase):
    """价值属性响应 Schema"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
