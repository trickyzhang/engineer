"""
Phase 7: 可视化与权衡空间分析
包括ViewDataMapper、Pareto分析、交互式可视化
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, List, Tuple, Optional


class ViewDataMapper:
    """
    视图-数据映射适配器
    设计方案v4的核心创新：灵活映射任意数据字段到可视化通道
    """

    def __init__(self):
        self.mapping_config: Dict = {}

    def configure_mapping(
        self,
        x_axis: str,
        y_axis: str,
        color: Optional[str] = None,
        size: Optional[str] = None,
        hover_data: Optional[List[str]] = None
    ) -> Dict:
        """
        配置数据到视觉通道的映射

        Args:
            x_axis: X轴映射的字段名
            y_axis: Y轴映射的字段名
            color: 颜色编码的字段名（可选）
            size: 点大小编码的字段名（可选）
            hover_data: 悬停时显示的额外字段

        Returns:
            映射配置字典
        """
        self.mapping_config = {
            'x': x_axis,
            'y': y_axis,
            'color': color,
            'size': size,
            'hover_data': hover_data or []
        }

        return self.mapping_config

    def apply_mapping(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        应用映射配置，提取用于绘图的数据

        Args:
            data: 完整的数据DataFrame

        Returns:
            包含映射字段的DataFrame
        """
        plot_data = pd.DataFrame()

        # 提取映射字段
        for channel, field in self.mapping_config.items():
            if field and channel != 'hover_data':
                if field in data.columns:
                    plot_data[channel] = data[field]
                else:
                    print(f"⚠️ 字段'{field}'不存在于数据中")

        return plot_data


class ParetoAnalyzer:
    """Pareto前沿分析器"""

    @staticmethod
    def identify_pareto_frontier(
        data: pd.DataFrame,
        objectives: List[str],
        directions: List[str]
    ) -> pd.DataFrame:
        """
        识别Pareto最优前沿

        Args:
            data: 包含目标值的DataFrame
            objectives: 目标列名列表（如['MAU', 'cost_total']）
            directions: 优化方向列表（'max'或'min'，与objectives对应）

        Returns:
            添加了'pareto_optimal'列的DataFrame

        Example:
            data = pareto.identify_pareto_frontier(
                data,
                objectives=['MAU', 'cost_total'],
                directions=['max', 'min']  # 最大化MAU，最小化成本
            )
        """
        if len(objectives) != len(directions):
            raise ValueError("objectives和directions长度必须相同")

        n = len(data)
        data = data.copy()

        # 标准化目标：全部转为最大化问题
        normalized = data.copy()
        for obj, direction in zip(objectives, directions):
            if direction == 'min':
                normalized[obj] = -data[obj]  # 最小化转为最大化
            elif direction != 'max':
                raise ValueError(f"方向必须是'max'或'min'，得到: {direction}")

        # 判断每个设计是否被支配
        is_dominated = np.zeros(n, dtype=bool)

        for i in range(n):
            if is_dominated[i]:
                continue  # 已被标记为被支配，跳过

            for j in range(n):
                if i == j or is_dominated[j]:
                    continue

                # 检查j是否支配i
                # 支配条件：j在所有目标上都不差于i，且至少有一个目标上严格更好
                all_better_or_equal = True
                at_least_one_better = False

                for obj in objectives:
                    if normalized.iloc[j][obj] > normalized.iloc[i][obj]:
                        at_least_one_better = True
                    elif normalized.iloc[j][obj] < normalized.iloc[i][obj]:
                        all_better_or_equal = False
                        break

                # 如果j支配i
                if all_better_or_equal and at_least_one_better:
                    is_dominated[i] = True
                    break

        # Pareto最优 = 未被支配的设计
        data['pareto_optimal'] = ~is_dominated

        return data

    @staticmethod
    def calculate_hypervolume(pareto_points: pd.DataFrame, reference_point: Dict) -> float:
        """
        计算Pareto前沿的超体积指标（简化2D版本）

        Args:
            pareto_points: Pareto最优点
            reference_point: 参考点字典（如{'MAU': 0, 'cost_total': 10000}）

        Returns:
            超体积值
        """
        # 简化实现：仅支持2D
        if len(pareto_points) == 0:
            return 0.0

        # 提取目标列
        objectives = [col for col in pareto_points.columns if col != 'pareto_optimal']

        if len(objectives) != 2:
            raise ValueError("简化版本仅支持2个目标")

        obj1, obj2 = objectives
        ref1, ref2 = reference_point[obj1], reference_point[obj2]

        # 按第一个目标排序
        sorted_points = pareto_points.sort_values(obj1)

        # 计算面积
        area = 0.0
        for i, point in sorted_points.iterrows():
            width = abs(point[obj1] - ref1)
            height = abs(point[obj2] - ref2)
            area += width * height

        return area


class InteractiveVisualizer:
    """交互式可视化引擎"""

    @staticmethod
    def create_scatter_plot(
        data: pd.DataFrame,
        mapping: Dict,
        pareto_highlight: bool = True
    ) -> go.Figure:
        """
        创建交互式散点图（权衡空间图）

        Args:
            data: 数据DataFrame
            mapping: ViewDataMapper的映射配置
            pareto_highlight: 是否高亮Pareto前沿

        Returns:
            Plotly Figure对象
        """
        fig = go.Figure()

        # 如果有Pareto标记，分别绘制
        if 'pareto_optimal' in data.columns and pareto_highlight:
            # 非Pareto点
            non_pareto = data[~data['pareto_optimal']]
            if len(non_pareto) > 0:
                fig.add_trace(go.Scatter(
                    x=non_pareto[mapping['x']],
                    y=non_pareto[mapping['y']],
                    mode='markers',
                    name='Feasible Designs',
                    marker=dict(
                        size=8,
                        color='lightblue',
                        opacity=0.6
                    ),
                    text=non_pareto.get('design_id', ''),
                    hovertemplate='<b>Design %{text}</b><br>' +
                                 f"{mapping['x']}: %{{x:.2f}}<br>" +
                                 f"{mapping['y']}: %{{y:.2f}}<extra></extra>"
                ))

            # Pareto前沿点
            pareto = data[data['pareto_optimal']]
            if len(pareto) > 0:
                fig.add_trace(go.Scatter(
                    x=pareto[mapping['x']],
                    y=pareto[mapping['y']],
                    mode='markers',
                    name='Pareto Frontier',
                    marker=dict(
                        size=12,
                        color='red',
                        symbol='star',
                        line=dict(width=1, color='darkred')
                    ),
                    text=pareto.get('design_id', ''),
                    hovertemplate='<b>⭐ Pareto Design %{text}</b><br>' +
                                 f"{mapping['x']}: %{{x:.2f}}<br>" +
                                 f"{mapping['y']}: %{{y:.2f}}<extra></extra>"
                ))
        else:
            # 普通散点图
            color_data = data[mapping['color']] if mapping.get('color') else None

            fig.add_trace(go.Scatter(
                x=data[mapping['x']],
                y=data[mapping['y']],
                mode='markers',
                marker=dict(
                    size=8,
                    color=color_data,
                    colorscale='Viridis',
                    showscale=True if color_data is not None else False
                ),
                text=data.get('design_id', ''),
                hovertemplate='<b>Design %{text}</b><br>' +
                             f"{mapping['x']}: %{{x:.2f}}<br>" +
                             f"{mapping['y']}: %{{y:.2f}}<extra></extra>"
            ))

        fig.update_layout(
            title='Tradespace Exploration',
            xaxis_title=mapping['x'],
            yaxis_title=mapping['y'],
            height=600,
            hovermode='closest',
            showlegend=True,
            template='plotly_white'
        )

        return fig

    @staticmethod
    def create_parallel_coordinates(
        data: pd.DataFrame,
        dimensions: List[str],
        color_by: str = None
    ) -> go.Figure:
        """
        创建平行坐标图（展示X→Y全链路关系）

        Args:
            data: 数据DataFrame
            dimensions: 要显示的维度列表（按顺序）
            color_by: 用于着色的维度

        Returns:
            Plotly Figure对象
        """
        # 标准化数据（每个维度归一化到0-1）
        data_norm = data.copy()

        for dim in dimensions:
            if dim in data.columns:
                min_val = data[dim].min()
                max_val = data[dim].max()

                if max_val - min_val > 0:
                    data_norm[dim] = (data[dim] - min_val) / (max_val - min_val)
                else:
                    data_norm[dim] = 0.5

        # 创建维度配置
        dims = []
        for dim in dimensions:
            if dim in data.columns:
                dims.append(dict(
                    range=[0, 1],
                    label=dim,
                    values=data_norm[dim]
                ))

        # 颜色
        if color_by and color_by in data_norm.columns:
            color_values = data_norm[color_by]
        else:
            color_values = data_norm[dimensions[-1]]  # 默认用最后一个维度着色

        fig = go.Figure(data=
            go.Parcoords(
                dimensions=dims,
                line=dict(
                    color=color_values,
                    colorscale='Viridis',
                    showscale=True,
                    cmin=0,
                    cmax=1
                )
            )
        )

        fig.update_layout(
            title='Parallel Coordinates - Design Space to Performance Space',
            height=500,
            template='plotly_white'
        )

        return fig

    @staticmethod
    def create_pareto_frontier_plot(data: pd.DataFrame, obj1: str, obj2: str) -> go.Figure:
        """
        创建Pareto前沿专用可视化

        Args:
            data: 包含pareto_optimal列的数据
            obj1: 目标1名称
            obj2: 目标2名称

        Returns:
            Plotly Figure对象
        """
        if 'pareto_optimal' not in data.columns:
            raise ValueError("数据必须包含'pareto_optimal'列")

        fig = go.Figure()

        # 所有可行点
        feasible = data[data.get('feasible', True)]
        non_pareto = feasible[~feasible['pareto_optimal']]

        fig.add_trace(go.Scatter(
            x=non_pareto[obj1],
            y=non_pareto[obj2],
            mode='markers',
            name='Feasible',
            marker=dict(size=6, color='lightgray', opacity=0.5)
        ))

        # Pareto前沿
        pareto = data[data['pareto_optimal']]
        pareto_sorted = pareto.sort_values(obj1)

        fig.add_trace(go.Scatter(
            x=pareto_sorted[obj1],
            y=pareto_sorted[obj2],
            mode='markers+lines',
            name='Pareto Frontier',
            marker=dict(size=12, color='red', symbol='star'),
            line=dict(color='red', width=2, dash='dash')
        ))

        fig.update_layout(
            title=f'Pareto Frontier: {obj1} vs {obj2}',
            xaxis_title=obj1,
            yaxis_title=obj2,
            height=600,
            template='plotly_white',
            showlegend=True
        )

        return fig
