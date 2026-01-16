"""
CSV处理模块 - 用于Phase 4识别和映射CSV文件
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


class CSVHandler:
    """CSV文件处理和列识别"""

    @staticmethod
    def detect_column_types(df: pd.DataFrame) -> Dict[str, str]:
        """
        自动检测CSV列的类型

        返回值: {column_name: 'design_var'|'performance'|'level'|'other'}
        """
        column_types = {}

        for col in df.columns:
            # 跳过ID列
            if col.lower() in ['id', '设计id', 'design_id']:
                column_types[col] = 'id'
                continue

            # 检测数据类型和值范围
            try:
                numeric_data = pd.to_numeric(df[col], errors='coerce')
                non_null_count = numeric_data.notna().sum()

                if non_null_count / len(df) < 0.7:
                    # 缺失值太多
                    column_types[col] = 'other'
                    continue

                # 检查唯一值数量和范围
                unique_count = df[col].nunique()
                value_range = numeric_data.max() - numeric_data.min()

                # 如果唯一值少于10，可能是水平（离散设计变量）
                if unique_count < 10:
                    column_types[col] = 'level'
                # 如果范围较大且连续，是设计变量或性能指标
                elif value_range > 10:
                    # 基于列名启发式猜测
                    col_lower = col.lower()

                    # 性能指标关键词
                    if any(kw in col_lower for kw in
                           ['分辨', 'resolution', '覆盖', 'coverage', '成本', 'cost',
                            '功率', 'power', '可靠', 'reliability', 'mau', 'score']):
                        column_types[col] = 'performance'
                    else:
                        column_types[col] = 'design_var'
                else:
                    column_types[col] = 'design_var'

            except Exception:
                # 非数值列，标记为其他
                column_types[col] = 'other'

        return column_types

    @staticmethod
    def map_columns_to_phase1(
        csv_columns: Dict[str, str],
        phase1_value_attrs: List[Dict]
    ) -> Dict[str, str]:
        """
        将CSV列映射到Phase 1的价值属性

        返回值: {csv_column: phase1_attribute_name}
        """
        mapping = {}

        if not phase1_value_attrs:
            return mapping

        # 构建Phase 1属性名的小写版本用于匹配
        phase1_attrs_lower = {
            attr['name'].lower(): attr['name']
            for attr in phase1_value_attrs
        }

        # 对于性能指标列，尝试匹配到Phase 1的value_attributes
        for col, col_type in csv_columns.items():
            if col_type != 'performance':
                continue

            col_lower = col.lower()

            # 尝试直接匹配
            for attr_lower, attr_name in phase1_attrs_lower.items():
                if attr_lower in col_lower or col_lower in attr_lower:
                    mapping[col] = attr_name
                    break

        return mapping

    @staticmethod
    def validate_csv_structure(df: pd.DataFrame, column_types: Dict) -> Tuple[bool, str]:
        """
        验证CSV文件结构是否有效

        返回值: (is_valid, message)
        """
        if df.empty:
            return False, "CSV文件为空"

        if len(df) < 2:
            return False, "CSV文件行数过少（最少2行）"

        # 检查是否至少有一列设计变量
        design_vars = sum(1 for t in column_types.values() if t == 'design_var')
        if design_vars == 0:
            return False, "未检测到设计变量列"

        # 检查数值有效性
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) == 0:
            return False, "CSV中无数值列"

        return True, "✅ CSV结构有效"

    @staticmethod
    def extract_alternatives(
        df: pd.DataFrame,
        column_types: Dict[str, str],
        selected_cols: Dict[str, str] = None
    ) -> pd.DataFrame:
        """
        从CSV提取alternatives表格

        参数:
        - df: 原始DataFrame
        - column_types: 列类型字典
        - selected_cols: 用户选择的列映射 {csv_col: use_as} 或None表示自动

        返回值: 处理后的alternatives DataFrame
        """
        alternatives = pd.DataFrame()

        # 添加ID列
        if 'id' in column_types.values():
            id_col = [k for k, v in column_types.items() if v == 'id'][0]
            alternatives['设计ID'] = df[id_col]
        else:
            alternatives['设计ID'] = range(1, len(df) + 1)

        # 添加设计变量
        design_vars = [k for k, v in column_types.items() if v == 'design_var']
        for var in design_vars:
            alternatives[var] = pd.to_numeric(df[var], errors='coerce')

        # 添加水平（离散变量）
        levels = [k for k, v in column_types.items() if v == 'level']
        for level in levels:
            alternatives[level] = df[level]

        # 添加性能指标
        perf_metrics = [k for k, v in column_types.items() if v == 'performance']
        for metric in perf_metrics:
            alternatives[metric] = pd.to_numeric(df[metric], errors='coerce')

        return alternatives.reset_index(drop=True)

    @staticmethod
    def get_column_summary(df: pd.DataFrame, column_types: Dict[str, str]) -> str:
        """
        生成CSV列摘要
        """
        summary = []

        summary.append("📋 **CSV列检测结果:**\n")

        by_type = {}
        for col, col_type in column_types.items():
            if col_type not in by_type:
                by_type[col_type] = []
            by_type[col_type].append(col)

        type_labels = {
            'id': '🔑 ID列',
            'design_var': '📊 设计变量',
            'level': '🎯 水平（离散）',
            'performance': '⚡ 性能指标',
            'other': '❓ 其他'
        }

        for col_type, cols in sorted(by_type.items()):
            label = type_labels.get(col_type, col_type)
            summary.append(f"\n{label}:")
            for col in cols:
                summary.append(f"  - {col}")

        return "\n".join(summary)
