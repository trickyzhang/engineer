"""
Phase 6: 约束评估引擎
支持硬约束/软约束、可行性过滤、Kill分析、边界探索
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional


class Constraint:
    """约束定义"""

    def __init__(self, name: str, expression: str, constraint_type: str = 'hard'):
        """
        Args:
            name: 约束名称
            expression: 约束表达式（如'cost_total <= 500', 'perf_coverage >= 80'）
            constraint_type: 'hard'（硬约束）或'soft'（软约束）
        """
        self.name = name
        self.expression = expression
        self.type = constraint_type
        self.violations = 0
        self.violation_rate = 0.0

    def to_dict(self):
        return {
            'name': self.name,
            'expression': self.expression,
            'type': self.type,
            'violations': self.violations,
            'violation_rate': self.violation_rate
        }


class ConstraintEngine:
    """约束评估和过滤引擎"""

    def __init__(self):
        self.constraints: List[Constraint] = []
        self.feasibility_mask: Optional[pd.Series] = None

    def add_constraint(self, constraint: Constraint) -> None:
        """添加约束"""
        self.constraints.append(constraint)

    def apply_constraints(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        应用所有约束，标记可行性

        Args:
            data: 包含设计和性能数据的DataFrame

        Returns:
            添加了'feasible'列的DataFrame
        """
        n = len(data)
        data = data.copy()

        # 初始化所有设计为可行
        self.feasibility_mask = pd.Series(True, index=data.index)

        # 评估每个约束
        for constraint in self.constraints:
            try:
                # 使用pandas.eval安全评估表达式
                mask = data.eval(constraint.expression)

                # 统计违反情况
                violations = (~mask).sum()
                constraint.violations = violations
                constraint.violation_rate = violations / n * 100

                # 应用硬约束
                if constraint.type == 'hard':
                    self.feasibility_mask &= mask

            except Exception as e:
                print(f"⚠️ 约束'{constraint.name}'评估失败: {str(e)}")
                continue

        # 标记可行性
        data['feasible'] = self.feasibility_mask

        return data

    def get_feasible_designs(self, data: pd.DataFrame) -> pd.DataFrame:
        """获取所有可行设计"""
        if 'feasible' not in data.columns:
            data = self.apply_constraints(data)

        return data[data['feasible']].copy()

    def analyze_constraints(self) -> pd.DataFrame:
        """
        约束瓶颈分析（Kill Analysis）

        识别哪些约束导致了最多的设计被淘汰

        Returns:
            约束分析结果DataFrame
        """
        analysis = []

        for constraint in self.constraints:
            criticality = 'High' if constraint.violation_rate > 50 else \
                         'Medium' if constraint.violation_rate > 20 else 'Low'

            analysis.append({
                '约束名称': constraint.name,
                '约束类型': '硬约束' if constraint.type == 'hard' else '软约束',
                '表达式': constraint.expression,
                '违反数量': constraint.violations,
                '违反率': f"{constraint.violation_rate:.1f}%",
                '严重性': criticality
            })

        df = pd.DataFrame(analysis)

        # 按违反率降序排序
        df = df.sort_values('违反率', ascending=False)

        return df

    def find_boundary_designs(
        self,
        data: pd.DataFrame,
        constraint_name: str,
        n_closest: int = 10
    ) -> pd.DataFrame:
        """
        寻找约束边界附近的设计

        Args:
            data: 设计数据
            constraint_name: 约束名称
            n_closest: 返回最接近边界的前N个设计

        Returns:
            边界附近的设计DataFrame
        """
        # 找到对应的约束
        constraint = next((c for c in self.constraints if c.name == constraint_name), None)

        if constraint is None:
            raise ValueError(f"约束'{constraint_name}'不存在")

        # 解析约束表达式
        # 简化处理：假设表达式为 "variable <= value" 或 "variable >= value"
        expr = constraint.expression

        # 计算每个设计到约束边界的距离
        # 这里使用简化方法：直接评估表达式值
        try:
            # 将约束表达式转换为数值（距离边界的距离）
            if '<=' in expr:
                left, right = expr.split('<=')
                distances = data.eval(f"abs({left.strip()} - ({right.strip()}))")
            elif '>=' in expr:
                left, right = expr.split('>=')
                distances = data.eval(f"abs({left.strip()} - ({right.strip()}))")
            elif '=' in expr and not ('>' in expr or '<' in expr):
                left, right = expr.split('=')
                distances = data.eval(f"abs({left.strip()} - ({right.strip()}))")
            else:
                raise ValueError(f"不支持的约束格式: {expr}")

            # 找到距离最小的设计
            boundary_indices = distances.nsmallest(n_closest).index
            boundary_designs = data.loc[boundary_indices].copy()

            # 添加距离列
            boundary_designs['distance_to_boundary'] = distances.loc[boundary_indices]

            return boundary_designs

        except Exception as e:
            raise ValueError(f"无法计算边界距离: {str(e)}")

    def get_constraint_statistics(self) -> Dict:
        """
        获取约束统计信息

        Returns:
            统计信息字典
        """
        total_constraints = len(self.constraints)
        hard_constraints = sum(1 for c in self.constraints if c.type == 'hard')
        soft_constraints = total_constraints - hard_constraints

        avg_violation_rate = np.mean([c.violation_rate for c in self.constraints])

        return {
            'total_constraints': total_constraints,
            'hard_constraints': hard_constraints,
            'soft_constraints': soft_constraints,
            'average_violation_rate': f"{avg_violation_rate:.1f}%",
            'most_restrictive': max(self.constraints, key=lambda c: c.violation_rate).name if self.constraints else None
        }


def create_example_constraints() -> ConstraintEngine:
    """创建示例约束（卫星雷达系统）"""
    engine = ConstraintEngine()

    # 硬约束
    engine.add_constraint(Constraint('budget', 'cost_total <= 5000', 'hard'))
    engine.add_constraint(Constraint('min_coverage', 'perf_coverage >= 30', 'hard'))
    engine.add_constraint(Constraint('max_power', 'transmit_power <= 4000', 'hard'))

    # 软约束
    engine.add_constraint(Constraint('preferred_resolution', 'perf_resolution <= 2', 'soft'))

    return engine
