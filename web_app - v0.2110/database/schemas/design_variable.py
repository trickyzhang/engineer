"""
设计变量 Pydantic Schema
"""
from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Any
from datetime import datetime


class DesignVariableBase(BaseModel):
    """设计变量基础 Schema"""
    name: str = Field(..., min_length=1, max_length=100, description="变量名称")
    variable_type: str = Field(..., description="变量类型：continuous/discrete/categorical")
    range_min: Optional[float] = Field(None, description="最小值（连续变量）")
    range_max: Optional[float] = Field(None, description="最大值（连续变量）")
    options: Optional[List[Any]] = Field(None, description="选项列表（离散/分类变量）")
    unit: Optional[str] = Field(None, max_length=50, description="单位")
    description: Optional[str] = Field(None, description="变量描述")

    @field_validator('variable_type')
    @classmethod
    def validate_variable_type(cls, v):
        """验证变量类型"""
        allowed_types = ['continuous', 'discrete', 'categorical']
        if v not in allowed_types:
            raise ValueError(f"变量类型必须是 {allowed_types} 之一，当前值: {v}")
        return v

    @field_validator('range_max')
    @classmethod
    def validate_range(cls, v, info):
        """验证数值范围"""
        # 获取 range_min 的值
        range_min = info.data.get('range_min')
        variable_type = info.data.get('variable_type')

        # 只对连续变量验证范围
        if variable_type == 'continuous':
            if range_min is not None and v is not None:
                if v <= range_min:
                    raise ValueError(f"最大值 ({v}) 必须大于最小值 ({range_min})")
        return v


class DesignVariableCreate(DesignVariableBase):
    """创建设计变量 Schema"""
    project_id: int = Field(..., description="所属项目ID")


class DesignVariableUpdate(BaseModel):
    """更新设计变量 Schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="变量名称")
    variable_type: Optional[str] = Field(None, description="变量类型")
    range_min: Optional[float] = Field(None, description="最小值")
    range_max: Optional[float] = Field(None, description="最大值")
    options: Optional[List[Any]] = Field(None, description="选项列表")
    unit: Optional[str] = Field(None, max_length=50, description="单位")
    description: Optional[str] = Field(None, description="变量描述")


class DesignVariableResponse(DesignVariableBase):
    """设计变量响应 Schema"""
    id: int
    project_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
