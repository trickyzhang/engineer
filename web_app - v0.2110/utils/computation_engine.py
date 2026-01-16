"""
Phase 5: 多域计算引擎
包括成本模型、性能模型和结果组装器
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Callable, Any, Optional, Tuple
import sympy as sp
from datetime import datetime


class CostModel:
    """成本计算模型"""

    def __init__(self):
        self.cost_functions: Dict[str, Dict] = {}

    def define_cost_function(self, name: str, formula_str: str, variables: List[str]) -> None:
        """
        定义成本函数

        Args:
            name: 成本项名称（如'satellite_cost', 'launch_cost'）
            formula_str: Python表达式字符串（如'1000 + 50 * antenna_diameter**2'）
            variables: 公式中用到的变量名列表

        Example:
            model.define_cost_function(
                'satellite_cost',
                '1000 + 50 * antenna_diameter**2 + 0.1 * transmit_power',
                ['antenna_diameter', 'transmit_power']
            )
        """
        # 验证公式安全性（简化版）
        # 实际应用中应该使用更严格的验证
        allowed_names = set(variables + ['np', 'sqrt', 'log', 'exp', 'pow'])

        # 编译成lambda函数
        try:
            # 创建安全的命名空间
            safe_dict = {
                '__builtins__': {},
                'np': np,
                'sqrt': np.sqrt,
                'log': np.log,
                'exp': np.exp,
                'pow': pow
            }

            # 创建lambda参数字符串
            lambda_params = ', '.join(variables)
            lambda_code = f"lambda {lambda_params}: {formula_str}"

            # 编译函数
            func = eval(lambda_code, safe_dict)

            self.cost_functions[name] = {
                'formula': formula_str,
                'variables': variables,
                'function': func
            }

        except Exception as e:
            raise ValueError(f"无法编译成本函数'{name}': {str(e)}")

    def define_cost_function_from_callable(
        self,
        name: str,
        func: Callable,
        variables: List[str]
    ) -> None:
        """
        从Python函数定义成本函数 (Phase 8 新增)

        与define_cost_function()不同，此方法接受已编译的Callable函数，
        而不是字符串公式。这允许使用SecureExecutionEngine编译的安全函数。

        Args:
            name: 成本项名称（如'user_cost_model', 'satellite_cost'）
            func: 已编译的Python函数 (from CalculationEngine.load_function_from_code)
            variables: 函数参数列表

        Example:
            # Phase 3用户自定义成本模型
            from utils.calculation_engine import CalculationEngine

            user_code = '''
def calculate_cost(**design_vars):
    orbit = design_vars.get('orbit_altitude', 600)
    antenna = design_vars.get('antenna_diameter', 10)
    return 1000 + 50 * orbit + 10 * antenna**2
'''
            func = CalculationEngine.load_function_from_code(user_code, "calculate_cost")

            cost_model = CostModel()
            cost_model.define_cost_function_from_callable(
                'user_cost_model',
                func,
                ['**design_vars']  # 支持**kwargs语法
            )

        Technical Notes:
            - 函数必须接受**design_vars参数或明确的参数列表
            - 函数通过SecureExecutionEngine执行，享有Phase 7的安全保护
            - formula字段设为'<user_defined_function>'以区分预定义公式
        """
        self.cost_functions[name] = {
            'formula': '<user_defined_function>',  # 标记为用户定义函数
            'variables': variables,
            'function': func  # 直接使用Callable，保留SecureExecutionEngine保护
        }

    def calculate_cost(self, design: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
        """
        计算单个设计的总成本

        Args:
            design: 设计变量字典（如{'antenna_diameter': 5, 'transmit_power': 1000}）

        Returns:
            (总成本, 成本分解字典)
        """
        total_cost = 0.0
        cost_breakdown = {}

        for cost_name, cost_func_info in self.cost_functions.items():
            # 提取所需变量值
            try:
                # Phase 8改进: 支持两种函数调用方式
                variables = cost_func_info['variables']

                # 检查是否为Phase 3用户定义函数 (使用**design_vars参数)
                if variables == ['**design_vars'] or (len(variables) == 1 and variables[0].startswith('**')):
                    # 用户定义函数: 传递整个design字典作为kwargs
                    cost = cost_func_info['function'](**design)
                else:
                    # 预定义公式: 提取特定变量作为位置参数
                    var_values = [design[var] for var in variables]
                    cost = cost_func_info['function'](*var_values)

                cost_breakdown[cost_name] = float(cost)
                total_cost += cost

            except KeyError as e:
                raise ValueError(f"设计中缺少变量 {e} (成本项 '{cost_name}' 需要)")
            except Exception as e:
                raise ValueError(f"计算成本项'{cost_name}'时出错: {str(e)}")

        return total_cost, cost_breakdown

    def calculate_batch(self, designs_df: pd.DataFrame) -> pd.DataFrame:
        """
        批量计算成本

        Args:
            designs_df: 包含设计变量的DataFrame

        Returns:
            包含成本列的DataFrame
        """
        cost_results = []

        for idx, design in designs_df.iterrows():
            total_cost, breakdown = self.calculate_cost(design.to_dict())

            result = {'cost_total': total_cost}
            for cost_name, cost_value in breakdown.items():
                result[f'cost_{cost_name}'] = cost_value

            cost_results.append(result)

        return pd.DataFrame(cost_results, index=designs_df.index)


class PerformanceModel:
    """性能计算模型"""

    def __init__(self):
        self.physics_models: Dict[str, Dict] = {}

    def add_physics_model(self, name: str, formula_str: str, variables: List[str]) -> None:
        """
        添加物理性能模型

        Args:
            name: 性能指标名称（如'coverage', 'resolution', 'max_range'）
            formula_str: 公式字符串（支持numpy函数）
            variables: 变量列表

        Example:
            model.add_physics_model(
                'coverage',
                'arccos(6371/(6371 + orbit_altitude)) * 2 * 180/pi',
                ['orbit_altitude']
            )
        """
        try:
            # 创建安全的命名空间
            safe_dict = {
                '__builtins__': {},
                'np': np,
                'pi': np.pi,
                'sqrt': np.sqrt,
                'log': np.log,
                'exp': np.exp,
                'sin': np.sin,
                'cos': np.cos,
                'tan': np.tan,
                'arcsin': np.arcsin,
                'arccos': np.arccos,
                'arctan': np.arctan,
                'pow': pow
            }

            # 创建lambda函数
            lambda_params = ', '.join(variables)
            lambda_code = f"lambda {lambda_params}: {formula_str}"

            func = eval(lambda_code, safe_dict)

            self.physics_models[name] = {
                'formula': formula_str,
                'variables': variables,
                'function': func
            }

        except Exception as e:
            raise ValueError(f"无法编译性能模型'{name}': {str(e)}")

    def add_callable_model(
        self,
        name: str,
        func: Callable,
        variables: List[str]
    ) -> None:
        """
        从Python函数添加性能模型 (Phase 8 新增)

        与add_physics_model()不同，此方法接受已编译的Callable函数。
        这允许使用SecureExecutionEngine编译的Phase 3用户自定义模型。

        Args:
            name: 性能指标名称（如'resolution', 'coverage', 'power'）
            func: 已编译的Python函数 (from CalculationEngine.load_function_from_code)
            variables: 函数参数列表

        Example:
            # Phase 3用户自定义性能模型
            from utils.calculation_engine import CalculationEngine

            user_code = '''
def calculate_resolution(**design_vars):
    orbit = design_vars.get('orbit_altitude', 600)
    antenna = design_vars.get('antenna_diameter', 10)
    # 分辨率计算: 轨道高度越高,分辨率越差
    return 0.001 * orbit / antenna
'''
            func = CalculationEngine.load_function_from_code(user_code, "calculate_resolution")

            perf_model = PerformanceModel()
            perf_model.add_callable_model(
                'resolution',
                func,
                ['**design_vars']
            )

        Technical Notes:
            - 函数必须接受**design_vars参数或明确的参数列表
            - 函数通过SecureExecutionEngine执行，享有Phase 7的安全保护
            - formula字段设为'<user_defined_function>'以区分预定义公式
        """
        self.physics_models[name] = {
            'formula': '<user_defined_function>',  # 标记为用户定义函数
            'variables': variables,
            'function': func  # 直接使用Callable，保留SecureExecutionEngine保护
        }

    def calculate_performance(self, design: Dict[str, Any]) -> Dict[str, float]:
        """
        计算单个设计的性能指标

        Args:
            design: 设计变量字典

        Returns:
            性能指标字典
        """
        performance = {}

        for perf_name, model_info in self.physics_models.items():
            try:
                # Phase 8改进: 支持两种函数调用方式
                variables = model_info['variables']

                # 检查是否为Phase 3用户定义函数 (使用**design_vars参数)
                if variables == ['**design_vars'] or (len(variables) == 1 and variables[0].startswith('**')):
                    # 用户定义函数: 传递整个design字典作为kwargs
                    result = model_info['function'](**design)
                else:
                    # 预定义公式: 提取特定变量作为位置参数
                    var_values = [design[var] for var in variables]
                    result = model_info['function'](*var_values)

                performance[perf_name] = float(result)

            except KeyError as e:
                raise ValueError(f"设计中缺少变量 {e} (性能指标 '{perf_name}' 需要)")
            except Exception as e:
                raise ValueError(f"计算性能指标'{perf_name}'时出错: {str(e)}")

        return performance

    def calculate_batch(self, designs_df: pd.DataFrame) -> pd.DataFrame:
        """批量计算性能"""
        perf_results = []

        for idx, design in designs_df.iterrows():
            perf = self.calculate_performance(design.to_dict())
            perf_results.append({f'perf_{k}': v for k, v in perf.items()})

        return pd.DataFrame(perf_results, index=designs_df.index)


class ValueModel:
    """价值计算模型（效用函数）"""

    def __init__(self):
        self.utility_functions: Dict[str, Callable] = {}
        self.weights: Dict[str, float] = {}

    def add_utility_function(self, attribute: str, func: Callable) -> None:
        """
        添加效用函数

        Args:
            attribute: 属性名称
            func: 效用函数，接受物理值，返回0-1之间的效用值
        """
        self.utility_functions[attribute] = func

    def set_weights(self, weights: Dict[str, float]) -> None:
        """
        设置权重（会自动归一化）

        Args:
            weights: 属性权重字典
        """
        total = sum(weights.values())
        self.weights = {k: v/total for k, v in weights.items()}

    def calculate_mau(self, attributes: Dict[str, float]) -> float:
        """
        计算多属性效用 (Multi-Attribute Utility)

        Args:
            attributes: 属性值字典

        Returns:
            MAU值（0-1之间）
        """
        if not self.utility_functions or not self.weights:
            raise ValueError("未定义效用函数或权重")

        total_utility = 0.0

        for attr, value in attributes.items():
            if attr in self.utility_functions and attr in self.weights:
                utility = self.utility_functions[attr](value)
                weight = self.weights[attr]
                total_utility += utility * weight

        return total_utility

    def calculate_batch(self, data_df: pd.DataFrame) -> pd.DataFrame:
        """
        批量计算MAU

        Args:
            data_df: 包含性能属性的DataFrame

        Returns:
            包含MAU列的DataFrame
        """
        mau_values = []

        for idx, row in data_df.iterrows():
            # 提取相关属性
            attrs = {attr: row[f'perf_{attr}'] for attr in self.utility_functions.keys()
                    if f'perf_{attr}' in row}

            mau = self.calculate_mau(attrs)
            mau_values.append(mau)

        return pd.DataFrame({'MAU': mau_values}, index=data_df.index)


class ResultAssembler:
    """结果组装器 - 组装X→Y_cost→Y_phy→Y_val的完整数据流"""

    @staticmethod
    def assemble_results(
        designs_df: pd.DataFrame,
        costs_df: pd.DataFrame,
        performance_df: pd.DataFrame,
        value_df: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        组装统一结果集（宽表）

        Args:
            designs_df: 设计变量 (X)
            costs_df: 成本数据 (Y_cost)
            performance_df: 性能数据 (Y_phy)
            value_df: 价值数据 (Y_val, 可选)

        Returns:
            统一的DataFrame，包含所有X和Y
        """
        # 复制设计变量DataFrame
        unified = designs_df.copy()

        # 合并成本数据
        for col in costs_df.columns:
            unified[col] = costs_df[col]

        # 合并性能数据
        for col in performance_df.columns:
            unified[col] = performance_df[col]

        # 合并价值数据（如果有）
        if value_df is not None:
            for col in value_df.columns:
                unified[col] = value_df[col]

            # 计算性价比
            if 'MAU' in value_df.columns and 'cost_total' in costs_df.columns:
                unified['cost_effectiveness'] = unified['MAU'] / unified['cost_total']

        # 添加元数据
        unified['computed_at'] = datetime.now().isoformat()

        return unified


def create_example_models():
    """创建示例模型（卫星雷达系统）"""

    # 成本模型
    cost_model = CostModel()
    cost_model.define_cost_function(
        'satellite_cost',
        '1000 + 50 * antenna_diameter**2 + 0.1 * transmit_power',
        ['antenna_diameter', 'transmit_power']
    )
    cost_model.define_cost_function(
        'launch_cost',
        '20 + 0.01 * (500 + 100 * antenna_diameter)',
        ['antenna_diameter']
    )

    # 性能模型
    perf_model = PerformanceModel()
    perf_model.add_physics_model(
        'coverage',
        'np.arccos(6371/(6371 + orbit_altitude)) * 2 * 180/np.pi',
        ['orbit_altitude']
    )
    perf_model.add_physics_model(
        'resolution',
        '0.5 * 3e8 / (2 * 10e9 * antenna_diameter)',  # 简化的分辨率公式
        ['antenna_diameter']
    )

    return cost_model, perf_model
