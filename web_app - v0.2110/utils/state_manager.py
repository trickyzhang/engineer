"""
全局状态管理器 - StateManager
用于在8个Phase之间传递和持久化数据
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, Optional
import pandas as pd


class StateManager:
    """全局状态管理器 - 支持跨阶段数据传递和会话管理"""

    def __init__(self, project_name: str = "default_project"):
        self.project_name = project_name
        self.activity_log = []  # 活动日志
        self.snapshots = {}  # 快照管理
        self.data = {
            'project_info': {
                'name': project_name,
                'created_at': datetime.now().isoformat(),
                'last_modified': datetime.now().isoformat(),
                'version': '1.0'
            },
            'phase1': {
                'mission': None,
                'value_attributes': [],
                'design_variables': [],
                'objectives': [],
                'dvm_matrix': None
            },
            'phase2': {
                'components': [],
                'interfaces': [],
                'flows': [],
                'n2_matrix': None
            },
            'phase3': {
                'cost_model': '',  # 成本模型Python代码
                'perf_models': {},  # {metric_name: code} 性能模型字典
                'weights': {},  # 权重配置
                'utility_functions': [],
                'scenarios': []
            },
            'phase4': {
                'design_variables': [],
                'alternatives': None,  # DataFrame会转为dict
                'sampling_config': {}
            },
            'phase5': {
                'cost_models': [],
                'performance_models': [],
                'unified_results': None  # DataFrame
            },
            'phase6': {
                'constraints': [],
                'feasible_designs': None,
                'constraint_analysis': None
            },
            'phase7': {
                'view_mappings': [],
                'pareto_designs': None,  # 修正：统一为pareto_designs
                'pareto_frontier': None,  # 保留兼容性
                'visualization_config': {}
            },
            'phase8': {
                'rankings': None,
                'sensitivity_analysis': None,
                'decision_report': None
            }
        }

    def save(self, phase: str, key: str, value: Any) -> None:
        """
        保存数据到指定Phase

        Args:
            phase: Phase名称 (如 'phase1', 'phase2')
            key: 数据键名
            value: 要保存的数据
        """
        if phase not in self.data:
            raise ValueError(f"Invalid phase: {phase}. Must be one of {list(self.data.keys())}")

        # 特殊处理DataFrame
        if isinstance(value, pd.DataFrame):
            self.data[phase][key] = {
                'type': 'dataframe',
                'data': value.to_dict('records'),
                'columns': list(value.columns),
                'index': list(value.index)
            }
        else:
            self.data[phase][key] = value

        # 更新修改时间
        self.data['project_info']['last_modified'] = datetime.now().isoformat()

        # 记录活动日志
        self.log_activity(phase, 'save', f"保存 {key} 到 {phase}")

    def load(self, phase: str, key: str, default: Any = None) -> Any:
        """
        从指定Phase加载数据

        Args:
            phase: Phase名称
            key: 数据键名
            default: 如果数据不存在，返回的默认值

        Returns:
            保存的数据，如果不存在则返回default
        """
        if phase not in self.data:
            return default

        value = self.data[phase].get(key, default)

        # 还原DataFrame
        if isinstance(value, dict) and value.get('type') == 'dataframe':
            df = pd.DataFrame(value['data'], columns=value['columns'])
            df.index = value['index']
            return df

        return value

    def get_all_phase_data(self, phase: str) -> Dict:
        """获取某个Phase的所有数据"""
        return self.data.get(phase, {})

    def export_to_json(self, filepath: str) -> None:
        """导出状态到JSON文件"""
        # 自定义JSON编码器，处理numpy类型
        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                import numpy as np
                if isinstance(obj, (np.integer, np.int64)):
                    return int(obj)
                elif isinstance(obj, (np.floating, np.float64)):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super(NumpyEncoder, self).default(obj)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
        print(f"✅ 状态已导出到: {filepath}")

    def import_from_json(self, filepath: str) -> None:
        """从JSON文件导入状态,自动转换DataFrame数据"""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"文件不存在: {filepath}")

        with open(filepath, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        # 递归转换所有DataFrame格式的数据
        self._convert_dataframe_dicts(self.data)

        print(f"✅ 状态已从文件导入: {filepath}")

    def _convert_dataframe_dicts(self, obj):
        """递归地将DataFrame字典格式转换为实际的DataFrame对象"""
        if isinstance(obj, dict):
            # 检查是否是DataFrame格式的字典
            if obj.get('type') == 'dataframe':
                # 转换为DataFrame
                df = pd.DataFrame(obj['data'], columns=obj['columns'])
                df.index = obj['index']
                return df
            else:
                # 递归处理字典中的所有值
                for key, value in obj.items():
                    obj[key] = self._convert_dataframe_dicts(value)
        elif isinstance(obj, list):
            # 递归处理列表中的所有元素
            return [self._convert_dataframe_dicts(item) for item in obj]

        return obj

    def log_activity(self, phase: str, action: str, description: str) -> None:
        """记录活动日志"""
        self.activity_log.append({
            'timestamp': datetime.now().isoformat(),
            'phase': phase,
            'action': action,
            'description': description
        })

        # 限制日志长度（保留最近100条）
        if len(self.activity_log) > 100:
            self.activity_log = self.activity_log[-100:]

    def get_recent_activities(self, n: int = 10) -> list:
        """获取最近N条活动记录"""
        return self.activity_log[-n:] if self.activity_log else []

    def create_snapshot(self, snapshot_name: str = None) -> str:
        """创建当前状态快照"""
        if snapshot_name is None:
            snapshot_name = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.snapshots[snapshot_name] = {
            'data': json.loads(json.dumps(self.data, default=str)),
            'created_at': datetime.now().isoformat()
        }

        self.log_activity('system', 'snapshot', f"创建快照: {snapshot_name}")
        return snapshot_name

    def restore_snapshot(self, snapshot_name: str) -> bool:
        """恢复快照"""
        if snapshot_name not in self.snapshots:
            return False

        self.data = self.snapshots[snapshot_name]['data']
        self.log_activity('system', 'restore', f"恢复快照: {snapshot_name}")
        return True

    def list_snapshots(self) -> list:
        """列出所有快照"""
        return [
            {'name': name, 'created_at': info['created_at']}
            for name, info in self.snapshots.items()
        ]

    def delete_snapshot(self, snapshot_name: str) -> bool:
        """删除指定快照（P2-12功能）"""
        if snapshot_name in self.snapshots:
            del self.snapshots[snapshot_name]
            self.log_activity('system', 'delete_snapshot', f"删除快照: {snapshot_name}")
            return True
        return False

    def load_from_file(self, session_data: dict) -> bool:
        """从JSON文件加载完整会话数据（P2-12功能）

        Args:
            session_data: 包含version, timestamp, data, activity_log的字典

        Returns:
            bool: 加载是否成功
        """
        try:
            # 验证数据格式
            if 'version' not in session_data or 'data' not in session_data:
                return False

            # 恢复数据
            self.data = session_data['data']

            # 恢复活动日志（如果有）
            if 'activity_log' in session_data:
                self.activity_log.extend(session_data['activity_log'])

            self.log_activity('system', 'load_session', f"从文件加载会话 (版本: {session_data.get('version', 'unknown')})")
            return True

        except Exception as e:
            print(f"加载会话失败: {e}")
            return False

    def reset_phase(self, phase: str) -> None:
        """重置某个Phase的数据"""
        if phase == 'phase1':
            self.data[phase] = {
                'mission': None,
                'value_attributes': [],
                'design_variables': [],
                'objectives': [],
                'dvm_matrix': None
            }
        elif phase == 'phase2':
            self.data[phase] = {'components': [], 'interfaces': [], 'flows': [], 'n2_matrix': None}
        # ... 其他Phase类似

        self.data['project_info']['last_modified'] = datetime.now().isoformat()
        self.log_activity(phase, 'reset', f"重置 {phase}")

    def reset_all(self) -> None:
        """
        重置所有Phase数据到初始状态，清空所有会话缓存数据
        用于新建项目、打开项目、导入数据等场景
        """
        self.data = {
            'project_info': {
                'name': self.project_name,
                'created_at': datetime.now().isoformat(),
                'last_modified': datetime.now().isoformat(),
                'version': '1.0'
            },
            'phase1': {
                'mission': None,
                'value_attributes': [],
                'design_variables': [],
                'objectives': [],
                'dvm_matrix': None
            },
            'phase2': {
                'components': [],
                'interfaces': [],
                'flows': [],
                'n2_matrix': None
            },
            'phase3': {
                'cost_model': '',
                'perf_models': {},
                'weights': {},
                'utility_functions': [],
                'scenarios': []
            },
            'phase4': {
                'design_variables': [],
                'alternatives': None,
                'sampling_config': {}
            },
            'phase5': {
                'cost_models': [],
                'performance_models': [],
                'unified_results': None
            },
            'phase6': {
                'constraints': [],
                'feasible_designs': None,
                'constraint_analysis': None
            },
            'phase7': {
                'view_mappings': [],
                'pareto_designs': None,
                'pareto_frontier': None,
                'visualization_config': {}
            },
            'phase8': {
                'rankings': None,
                'sensitivity_analysis': None,
                'decision_report': None
            }
        }

        # 清空活动日志（可选：保留历史日志）
        # self.activity_log = []

        # 记录重置活动
        self.log_activity('system', 'reset_all', "重置所有Phase数据到初始状态")
        print("✅ StateManager已重置到初始状态")

    def get_data_flow_summary(self) -> Dict:
        """获取数据流摘要 - 显示各Phase的数据状态"""
        summary = {}

        for phase in ['phase1', 'phase2', 'phase3', 'phase4', 'phase5', 'phase6', 'phase7', 'phase8']:
            phase_data = self.data.get(phase, {})
            summary[phase] = {
                'has_data': any(v is not None and v != [] and v != {} for v in phase_data.values()),
                'data_keys': [k for k, v in phase_data.items() if v is not None and v != [] and v != {}]
            }

        return summary

    def validate_data_flow(self) -> Dict:
        """
        验证数据流完整性
        检查各Phase是否有必需的数据
        """
        validation = {
            'phase1': {
                'required': ['mission', 'value_attributes'],
                'status': 'unknown'
            },
            'phase2': {
                'required': ['components'],
                'status': 'unknown'
            },
            'phase3': {
                'required': ['utility_functions', 'weights'],
                'status': 'unknown'
            },
            'phase4': {
                'required': ['design_variables', 'alternatives'],
                'status': 'unknown'
            },
            'phase5': {
                'required': ['unified_results'],
                'status': 'unknown'
            },
            'phase6': {
                'required': ['constraints', 'feasible_designs'],
                'status': 'unknown'
            },
            'phase7': {
                'required': ['pareto_frontier'],
                'status': 'unknown'
            },
            'phase8': {
                'required': ['rankings'],
                'status': 'unknown'
            }
        }

        # 检查每个Phase的必需数据
        for phase, requirements in validation.items():
            phase_data = self.data.get(phase, {})
            missing = []

            for key in requirements['required']:
                value = phase_data.get(key)
                if value is None or value == [] or value == {}:
                    missing.append(key)

            if not missing:
                validation[phase]['status'] = 'complete'
            else:
                validation[phase]['status'] = 'incomplete'
                validation[phase]['missing'] = missing

        return validation


# 全局单例
_global_state_manager = None

def get_state_manager(project_name: str = "default_project"):
    """
    获取全局StateManager实例

    【重要】从2025-12-21起，此函数返回StateManagerAdapter实例，
    支持数据库持久化存储。通过环境变量USE_DATABASE_BACKEND控制后端：
    - USE_DATABASE_BACKEND=true (默认): 使用SQLite数据库
    - USE_DATABASE_BACKEND=false: 使用原内存存储

    Args:
        project_name: 项目名称

    Returns:
        StateManagerAdapter实例（向后兼容StateManager的所有API）
    """
    global _global_state_manager
    if _global_state_manager is None:
        # 延迟导入以避免循环依赖
        from utils.state_manager_adapter import get_state_manager as get_adapter
        _global_state_manager = get_adapter(project_name)
    return _global_state_manager

def reset_state_manager():
    """重置全局StateManager（用于测试）"""
    global _global_state_manager
    _global_state_manager = None
    # 同时重置adapter的缓存
    from utils.state_manager_adapter import reset_state_manager_cache
    reset_state_manager_cache()
