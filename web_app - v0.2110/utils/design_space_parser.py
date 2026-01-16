"""
设计空间解析器 - 用于从CSV/Excel文件提取变量、属性和设计信息
支持ATSV格式的完整兼容
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Any, Optional


class DesignSpaceParser:
    """
    从CSV/Excel文件解析设计空间
    支持ATSV格式：第一行为变量名，第一列为设计ID
    """

    @staticmethod
    def parse_csv(file_path: str) -> Dict[str, Any]:
        """
        解析CSV/Excel文件，提取设计变量、性能属性和设计方案

        返回值: {
            'variables': [{'name': str, 'type': 'continuous'|'categorical',
                          'min': float, 'max': float, 'unit': str, 'values': list}],
            'attributes': [{'name': str, 'unit': str, 'type': str}],
            'designs': DataFrame,
            'metadata': {总方案数, 变量数等}
        }
        """
        try:
            # 读取文件
            if isinstance(file_path, str):
                if file_path.endswith('.csv'):
                    df = pd.read_csv(file_path)
                elif file_path.endswith(('.xlsx', '.xls')):
                    df = pd.read_excel(file_path)
                else:
                    raise ValueError("不支持的文件格式，仅支持CSV和Excel")
            else:
                # 假设已经是DataFrame
                df = file_path

            if df.empty:
                raise ValueError("文件为空")

            # 提取元数据
            metadata = DesignSpaceParser.extract_metadata(df)

            # 分离设计变量、性能属性、设计方案
            variables = metadata.get('variables', [])
            attributes = metadata.get('attributes', [])
            designs = metadata.get('designs', df)

            return {
                'variables': variables,
                'attributes': attributes,
                'designs': designs,
                'metadata': {
                    'n_designs': len(designs),
                    'n_variables': len(variables),
                    'n_attributes': len(attributes),
                    'n_cols': len(df.columns)
                }
            }

        except Exception as e:
            return {
                'error': str(e),
                'variables': [],
                'attributes': [],
                'designs': pd.DataFrame(),
                'metadata': {}
            }

    @staticmethod
    def extract_metadata(df: pd.DataFrame) -> Dict[str, Any]:
        """
        从DataFrame第一行/列提取元数据（变量名、单位、类型）

        ATSV格式假设：
        - 第一行：变量名或列头
        - 第一列：设计ID或行号
        - 其他单元格：设计变量值或性能属性值
        """
        variables = []
        attributes = []
        designs = df.copy()

        # 检查第一列是否是ID列
        first_col = df.columns[0]
        first_col_lower = first_col.lower()

        is_id_column = any(kw in first_col_lower for kw in ['id', '设计', 'design', 'alternative'])

        if is_id_column:
            id_col_name = first_col
            designs.rename(columns={first_col: '设计ID'}, inplace=True)
            data_cols = df.columns[1:]
        else:
            designs.insert(0, '设计ID', range(1, len(df) + 1))
            data_cols = df.columns

        # 分析每一列
        for col in data_cols:
            var_info = DesignSpaceParser._analyze_column(df[col], col)

            # 判断是设计变量还是性能属性
            if var_info['is_performance']:
                attributes.append({
                    'name': col,
                    'unit': var_info.get('unit', ''),
                    'type': 'continuous' if var_info['type'] == 'continuous' else 'categorical'
                })
            else:
                variables.append(var_info)

        return {
            'variables': variables,
            'attributes': attributes,
            'designs': designs
        }

    @staticmethod
    def _analyze_column(column: pd.Series, col_name: str) -> Dict[str, Any]:
        """
        分析单个列的类型、范围和性质

        返回: {
            'name': str,
            'type': 'continuous'|'categorical',
            'min': float (if continuous),
            'max': float (if continuous),
            'values': list (if categorical),
            'unit': str,
            'is_performance': bool
        }
        """
        result = {
            'name': col_name,
            'unit': '',
            'is_performance': False
        }

        # 尝试转换为数值
        try:
            numeric_data = pd.to_numeric(column, errors='coerce')
            non_null_count = numeric_data.notna().sum()

            if non_null_count / len(column) < 0.7:
                # 大部分非数值
                result['type'] = 'categorical'
                result['values'] = column.dropna().unique().tolist()
                return result

            # 数值列
            unique_count = numeric_data.nunique()
            min_val = numeric_data.min()
            max_val = numeric_data.max()
            value_range = max_val - min_val

            # 判断是连续还是离散
            if unique_count < 10:
                # 离散（分类）
                result['type'] = 'categorical'
                result['values'] = numeric_data.dropna().unique().tolist()
            else:
                # 连续
                result['type'] = 'continuous'
                result['min'] = float(min_val)
                result['max'] = float(max_val)
                result['mean'] = float(numeric_data.mean())
                result['std'] = float(numeric_data.std())

            # 判断是否为性能属性（基于列名启发式）
            col_lower = col_name.lower()
            performance_keywords = [
                '分辨', 'resolution', '覆盖', 'coverage', '成本', 'cost',
                '功率', 'power', '可靠', 'reliability', 'mau', 'score',
                '效用', 'utility', '排名', 'rank', '功耗'
            ]
            result['is_performance'] = any(kw in col_lower for kw in performance_keywords)

            return result

        except Exception:
            # 非数值列
            result['type'] = 'categorical'
            result['values'] = column.dropna().unique().tolist()
            return result

    @staticmethod
    def reconcile_with_phase1(
        parsed_data: Dict[str, Any],
        phase1_vars: List[Dict],
        phase1_attrs: List[Dict]
    ) -> Dict[str, Any]:
        """
        将解析的数据与Phase 1配置对齐

        功能：
        1. 去重处理
        2. 补充缺失的变量/属性
        3. 检查一致性
        4. 返回融合后的数据

        返回: {
            'merged_variables': list,
            'merged_attributes': list,
            'new_variables': list (新增的),
            'new_attributes': list (新增的),
            'conflicts': list (冲突的),
            'consistency_score': float (0-100)
        }
        """
        parsed_vars = parsed_data.get('variables', [])
        parsed_attrs = parsed_data.get('attributes', [])

        merged_variables = []
        merged_attributes = []
        new_variables = []
        new_attributes = []
        conflicts = []

        # 处理变量
        phase1_var_names = {v.get('name', ''): v for v in phase1_vars}
        parsed_var_names = {v['name']: v for v in parsed_vars}

        # 合并变量：Phase 1 + 新增
        for var_name, phase1_var in phase1_var_names.items():
            if var_name in parsed_var_names:
                # 检查一致性
                parsed_var = parsed_var_names[var_name]
                merged_var = DesignSpaceParser._merge_variable(phase1_var, parsed_var)
                merged_variables.append(merged_var)
                if merged_var.get('conflict'):
                    conflicts.append(f"变量'{var_name}'在Phase 1和导入数据中定义不一致")
            else:
                # 保留Phase 1的定义
                merged_variables.append(phase1_var)

        # 添加新的变量（仅在导入数据中出现）
        for var_name, parsed_var in parsed_var_names.items():
            if var_name not in phase1_var_names:
                new_variables.append(parsed_var)
                merged_variables.append(parsed_var)

        # 处理属性
        phase1_attr_names = {a.get('name', ''): a for a in phase1_attrs}
        parsed_attr_names = {a['name']: a for a in parsed_attrs}

        # 合并属性
        for attr_name, phase1_attr in phase1_attr_names.items():
            if attr_name in parsed_attr_names:
                merged_attr = {**phase1_attr, **parsed_attr_names[attr_name]}
                merged_attributes.append(merged_attr)
            else:
                merged_attributes.append(phase1_attr)

        # 添加新的属性
        for attr_name, parsed_attr in parsed_attr_names.items():
            if attr_name not in phase1_attr_names:
                new_attributes.append(parsed_attr)
                merged_attributes.append(parsed_attr)

        # 计算一致性评分
        consistency_score = DesignSpaceParser._calculate_consistency(
            merged_variables, parsed_vars, conflicts
        )

        return {
            'merged_variables': merged_variables,
            'merged_attributes': merged_attributes,
            'new_variables': new_variables,
            'new_attributes': new_attributes,
            'conflicts': conflicts,
            'consistency_score': consistency_score
        }

    @staticmethod
    def _merge_variable(phase1_var: Dict, parsed_var: Dict) -> Dict:
        """
        合并两个变量定义
        """
        merged = {**phase1_var}

        # 如果解析得到的范围更完整，使用它
        if 'min' in parsed_var and 'max' in parsed_var:
            merged['min'] = parsed_var.get('min', phase1_var.get('min'))
            merged['max'] = parsed_var.get('max', phase1_var.get('max'))

        # 检查是否一致
        if phase1_var.get('type') != parsed_var.get('type'):
            merged['conflict'] = True

        return merged

    @staticmethod
    def _calculate_consistency(merged_vars: List, parsed_vars: List, conflicts: List) -> float:
        """
        计算Phase 1和导入数据之间的一致性评分（0-100）
        """
        if not merged_vars:
            return 100.0

        # 基础分数
        score = 100.0

        # 缺少定义的变量减分
        missing_score = (len(parsed_vars) / len(merged_vars)) * 100
        score = max(0, (score + missing_score) / 2)

        # 冲突减分
        if conflicts:
            conflict_penalty = len(conflicts) * 10
            score = max(0, score - conflict_penalty)

        return float(score)

    @staticmethod
    def extract_design_matrix(
        designs_df: pd.DataFrame,
        variable_names: List[str],
        include_id: bool = True
    ) -> pd.DataFrame:
        """
        从designs中提取特定变量的设计矩阵

        返回: DataFrame，每行为一个设计方案
        """
        if include_id and '设计ID' in designs_df.columns:
            cols = ['设计ID'] + variable_names
        else:
            cols = variable_names

        # 过滤存在的列
        existing_cols = [c for c in cols if c in designs_df.columns]

        return designs_df[existing_cols].copy()
