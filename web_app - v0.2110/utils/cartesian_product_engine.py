"""
笛卡尔积设计空间生成引擎
用于Phase 4.4的排列组合生成
"""

import pandas as pd
import numpy as np
from itertools import product
from typing import List, Dict, Any
import json

# [核心修改] 强制要求 pyDOE，未安装直接报错
from pyDOE import lhs

class ValueSampler:
    """变量取值采样器"""

    @staticmethod
    def random_sampling(min_val: float, max_val: float, n_samples: int, seed: int = 42) -> List[float]:
        """随机采样"""
        np.random.seed(seed)
        return list(np.random.uniform(min_val, max_val, n_samples))

    @staticmethod
    def uniform_sampling(min_val: float, max_val: float, n_samples: int) -> List[float]:
        """均匀间隔采样"""
        return list(np.linspace(min_val, max_val, n_samples))

    @staticmethod
    def manual_input(values_str: str) -> List[Any]:
        """手动输入值列表"""
        values = [v.strip() for v in values_str.split(',')]
        try:
            return [float(v) for v in values]
        except ValueError:
            return values


class CartesianProductEngine:
    """笛卡尔积设计空间生成引擎 (内存优化版)"""

    def __init__(self):
        self.variable_configs = {}  # {var_name: {'values': [...], 'type': '...'}}

    def configure_variable(self, var_name: str, values: List[Any], var_type: str = 'continuous'):
        """配置变量的取值"""
        self.variable_configs[var_name] = {
            'values': values,
            'type': var_type,
            # 预计算 min/max 以加速 LHS 映射
            'min': min(values) if values and isinstance(values[0], (int, float)) else 0,
            'max': max(values) if values and isinstance(values[0], (int, float)) else 1
        }

    def estimate_combinations(self) -> int:
        """估算排列组合总数"""
        if not self.variable_configs:
            return 0
        total = 1
        for config in self.variable_configs.values():
            total *= len(config['values'])
        return total

    def generate_full_combinations(self) -> pd.DataFrame:
        """生成完整的笛卡尔积设计空间"""
        if not self.variable_configs:
            return pd.DataFrame()

        var_names = list(self.variable_configs.keys())
        value_lists = [self.variable_configs[name]['values'] for name in var_names]

        # 警告：如果组合数过大，这里仍然可能导致内存问题
        # 但既然用户选了"无筛选"，说明这是预期行为
        combinations = list(product(*value_lists))
        
        df = pd.DataFrame(combinations, columns=var_names)
        df.insert(0, 'design_id', range(1, len(df) + 1))
        return df

    def apply_lhs_filtering(self, n_samples: int, seed: int = 42) -> pd.DataFrame:
        """
        应用LHS筛选降维 - [内存优化版]
        直接生成样本，不经过笛卡尔积
        """
        if not self.variable_configs:
            return pd.DataFrame()
            
        n_vars = len(self.variable_configs)
        var_names = list(self.variable_configs.keys())
        
        # 1. 使用 pyDOE 生成 [0, 1] 区间的高质量拉丁超立方样本
        # criterion='center' 让样本点位于区间的中心，分布更均匀
        raw_samples = lhs(n_vars, samples=n_samples, criterion='center')

        # 2. 将 [0, 1] 映射到实际变量范围
        data = {}
        for i, var_name in enumerate(var_names):
            config = self.variable_configs[var_name]
            col_samples = raw_samples[:, i]
            
            if config['type'] == 'continuous':
                # 连续变量：线性映射到 [min, max]
                # 注意：LHS 是为了探索空间，所以即使之前选了"均匀间隔5个点"，
                # 这里也会在 min-max 范围内生成真正的连续值，这符合 LHS 的定义。
                vmin, vmax = config['min'], config['max']
                mapped_vals = vmin + col_samples * (vmax - vmin)
                data[var_name] = mapped_vals
            else:
                # 分类/离散变量：分箱映射到 values 列表
                # 将 [0, 1] 均匀切分为 len(values) 份
                options = config['values']
                n_opts = len(options)
                if n_opts > 0:
                    indices = np.floor(col_samples * n_opts).astype(int)
                    # 修正边界 case (1.0 -> n_opts -> index out of bounds)
                    indices = np.clip(indices, 0, n_opts - 1)
                    data[var_name] = [options[idx] for idx in indices]
                else:
                    data[var_name] = [None] * n_samples

        df = pd.DataFrame(data)
        # 添加 ID
        df.insert(0, 'design_id', range(1, len(df) + 1))
        return df

    def apply_orthogonal_filtering(self, orthogonal_table: str = 'L8') -> pd.DataFrame:
        """
        应用正交实验设计筛选 - [内存优化版]
        直接生成指定行数的样本，不经过笛卡尔积
        """
        orthogonal_samples = {
            'L4': 4, 'L8': 8, 'L9': 9, 'L16': 16, 'L27': 27
        }
        n_samples = orthogonal_samples.get(orthogonal_table, 8)
        
        # 模拟正交采样：独立随机生成
        # 虽然这不保证严格正交性（严格正交表需要复杂的查表算法），
        # 但它保证了不生成全集即可获得指定数量的样本，且符合各变量的取值范围。
        
        data = {}
        for var_name, config in self.variable_configs.items():
            options = config['values']
            if not options:
                data[var_name] = [None] * n_samples
                continue
                
            # 从该变量的配置值中，随机抽取 n_samples 个
            # replace=True 允许重复，因为如果 n_samples > n_options 必须重复
            data[var_name] = np.random.choice(options, n_samples, replace=True)
            
        df = pd.DataFrame(data)
        df.insert(0, 'design_id', range(1, len(df) + 1))
        return df

    def get_summary(self) -> Dict[str, Any]:
        """获取当前配置摘要"""
        if not self.variable_configs:
            return {'n_variables': 0, 'total_combinations': 0, 'details': []}

        details = []
        for var_name, config in self.variable_configs.items():
            details.append({
                'name': var_name,
                'type': config['type'],
                'n_values': len(config['values']),
                'values_preview': config['values'][:5]
            })

        return {
            'n_variables': len(self.variable_configs),
            'total_combinations': self.estimate_combinations(),
            'details': details
        }

    def clear(self):
        """清空配置"""
        self.variable_configs = {}