"""
Phase 4: 设计空间采样引擎
支持多种采样方法：LHS、蒙特卡洛、Sobol序列、全因子
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Union, Optional
from scipy.stats import qmc
import itertools


class DesignVariable:
    """设计变量定义"""

    def __init__(self, name: str, var_type: str, domain: Union[Tuple, List], unit: str = None):
        """
        Args:
            name: 变量名称
            var_type: 变量类型 ('continuous', 'discrete', 'categorical')
            domain: 取值域
                - continuous: (min, max) 元组
                - discrete: [val1, val2, ...] 列表
                - categorical: ['option1', 'option2', ...] 列表
            unit: 单位（可选）
        """
        self.name = name
        self.var_type = var_type
        self.domain = domain
        self.unit = unit

        # 验证
        if var_type == 'continuous':
            if not isinstance(domain, (tuple, list)) or len(domain) != 2:
                raise ValueError(f"Continuous variable '{name}' requires domain as (min, max)")
            if domain[0] >= domain[1]:
                raise ValueError(f"Invalid domain for '{name}': min must be < max")
        elif var_type in ['discrete', 'categorical']:
            if not isinstance(domain, list) or len(domain) == 0:
                raise ValueError(f"{var_type} variable '{name}' requires non-empty list domain")

    def to_dict(self):
        return {
            'name': self.name,
            'type': self.var_type,
            'domain': self.domain,
            'unit': self.unit
        }


class SamplingEngine:
    """设计空间采样引擎"""

    def __init__(self):
        self.design_variables: Dict[str, DesignVariable] = {}

    def add_variable(self, var: DesignVariable) -> None:
        """添加设计变量"""
        self.design_variables[var.name] = var

    def estimate_space_size(self) -> int:
        """
        估算设计空间大小
        对于连续变量，假设离散化为100个点
        """
        size = 1

        for var in self.design_variables.values():
            if var.var_type == 'continuous':
                size *= 100  # 假设每个连续变量100个离散点
            else:
                size *= len(var.domain)

        return size

    def generate_lhs(self, n_samples: int = 1000, seed: int = 42) -> pd.DataFrame:
        """
        拉丁超立方采样 (Latin Hypercube Sampling)

        特点：
        - 比纯随机采样覆盖更均匀
        - 适合中等规模采样（100-10000个样本）
        - 每个维度都被均匀分层

        Args:
            n_samples: 采样数量
            seed: 随机种子

        Returns:
            包含所有设计变量的DataFrame
        """
        # 分离连续变量和离散变量
        continuous_vars = {k: v for k, v in self.design_variables.items() if v.var_type == 'continuous'}
        discrete_vars = {k: v for k, v in self.design_variables.items() if v.var_type in ['discrete', 'categorical']}

        results = {}

        # 1. 对连续变量使用LHS
        if continuous_vars:
            n_dim = len(continuous_vars)
            sampler = qmc.LatinHypercube(d=n_dim, seed=seed)
            lhs_samples = sampler.random(n=n_samples)

            # 缩放到实际范围
            for i, (var_name, var) in enumerate(continuous_vars.items()):
                min_val, max_val = var.domain
                results[var_name] = lhs_samples[:, i] * (max_val - min_val) + min_val

        # 2. 对离散/分类变量进行随机采样
        np.random.seed(seed)
        for var_name, var in discrete_vars.items():
            results[var_name] = np.random.choice(var.domain, size=n_samples)

        df = pd.DataFrame(results)
        df['design_id'] = range(len(df))

        return df

    def generate_monte_carlo(self, n_samples: int = 1000, seed: int = 42) -> pd.DataFrame:
        """
        蒙特卡洛随机采样

        特点：
        - 最简单的采样方法
        - 覆盖可能不均匀
        - 适合快速探索

        Args:
            n_samples: 采样数量
            seed: 随机种子

        Returns:
            包含所有设计变量的DataFrame
        """
        np.random.seed(seed)
        results = {}

        for var_name, var in self.design_variables.items():
            if var.var_type == 'continuous':
                min_val, max_val = var.domain
                results[var_name] = np.random.uniform(min_val, max_val, size=n_samples)
            else:
                results[var_name] = np.random.choice(var.domain, size=n_samples)

        df = pd.DataFrame(results)
        df['design_id'] = range(len(df))

        return df

    def generate_sobol(self, n_samples: int = 1024, seed: int = 42) -> pd.DataFrame:
        """
        Sobol序列准随机采样

        特点：
        - 低差异序列，覆盖最均匀
        - n_samples建议使用2的幂次（如512, 1024, 2048）
        - 适合高精度空间探索

        Args:
            n_samples: 采样数量（建议2的幂次）
            seed: 随机种子

        Returns:
            包含所有设计变量的DataFrame
        """
        continuous_vars = {k: v for k, v in self.design_variables.items() if v.var_type == 'continuous'}
        discrete_vars = {k: v for k, v in self.design_variables.items() if v.var_type in ['discrete', 'categorical']}

        results = {}

        # 1. 对连续变量使用Sobol序列
        if continuous_vars:
            n_dim = len(continuous_vars)
            sampler = qmc.Sobol(d=n_dim, seed=seed)
            sobol_samples = sampler.random(n=n_samples)

            # 缩放到实际范围
            for i, (var_name, var) in enumerate(continuous_vars.items()):
                min_val, max_val = var.domain
                results[var_name] = sobol_samples[:, i] * (max_val - min_val) + min_val

        # 2. 离散变量随机采样
        np.random.seed(seed)
        for var_name, var in discrete_vars.items():
            results[var_name] = np.random.choice(var.domain, size=n_samples)

        df = pd.DataFrame(results)
        df['design_id'] = range(len(df))

        return df

    def generate_full_factorial(self, discretization: int = 10) -> pd.DataFrame:
        """
        全因子设计 (Full Factorial)

        警告：
        - 仅适用于变量数量少（<5个）的情况
        - 会产生组合爆炸

        Args:
            discretization: 连续变量的离散化点数

        Returns:
            包含所有设计变量的DataFrame
        """
        # 估算大小
        estimated_size = self.estimate_space_size()
        if estimated_size > 1e6:
            raise ValueError(
                f"全因子设计会产生{estimated_size:e}个样本，超过100万！"
                f"请使用LHS、蒙特卡洛或Sobol采样代替。"
            )

        # 为每个变量生成离散值
        variable_values = {}

        for var_name, var in self.design_variables.items():
            if var.var_type == 'continuous':
                min_val, max_val = var.domain
                variable_values[var_name] = np.linspace(min_val, max_val, discretization)
            else:
                variable_values[var_name] = var.domain

        # 生成笛卡尔积
        var_names = list(variable_values.keys())
        combinations = list(itertools.product(*[variable_values[name] for name in var_names]))

        # 转为DataFrame
        df = pd.DataFrame(combinations, columns=var_names)
        df['design_id'] = range(len(df))

        return df

    def validate_coverage(self, samples: pd.DataFrame) -> Dict:
        """
        验证采样覆盖度

        Args:
            samples: 采样结果DataFrame

        Returns:
            包含每个变量统计信息的字典
        """
        coverage_report = {}

        for var_name, var in self.design_variables.items():
            if var_name not in samples.columns:
                continue

            values = samples[var_name]

            if var.var_type == 'continuous':
                min_val, max_val = var.domain
                coverage_report[var_name] = {
                    'type': 'continuous',
                    'domain': var.domain,
                    'samples_min': float(values.min()),
                    'samples_max': float(values.max()),
                    'samples_mean': float(values.mean()),
                    'samples_std': float(values.std()),
                    'coverage_min': float(values.min() - min_val),  # 偏离下界的距离
                    'coverage_max': float(max_val - values.max()),  # 偏离上界的距离
                    'n_unique': int(values.nunique())
                }
            else:
                coverage_report[var_name] = {
                    'type': var.var_type,
                    'domain_size': len(var.domain),
                    'sampled_values': list(values.unique()),
                    'n_unique': int(values.nunique()),
                    'coverage_rate': float(values.nunique() / len(var.domain) * 100)  # 覆盖百分比
                }

        return coverage_report


def create_example_variables() -> SamplingEngine:
    """创建示例设计变量（卫星雷达系统）"""
    engine = SamplingEngine()

    # 连续变量
    engine.add_variable(DesignVariable('orbit_altitude', 'continuous', (400, 800), 'km'))
    engine.add_variable(DesignVariable('antenna_diameter', 'continuous', (1, 10), 'm'))
    engine.add_variable(DesignVariable('transmit_power', 'continuous', (100, 5000), 'W'))

    # 离散变量
    engine.add_variable(DesignVariable('frequency_band', 'categorical', ['L', 'S', 'C', 'X', 'Ku']))
    engine.add_variable(DesignVariable('polarization', 'categorical', ['HH', 'VV', 'HH+VV', 'Quad']))

    return engine
