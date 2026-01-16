"""
StateManager 兼容适配器

提供向后兼容的接口,支持无缝切换内存存储和数据库存储。
通过环境变量 USE_DATABASE_BACKEND 控制后端选择。

使用示例:
    # 方式1: 直接实例化(默认使用数据库)
    manager = StateManagerAdapter("my_project")

    # 方式2: 使用工厂函数(推荐,支持单例)
    manager = get_state_manager("my_project")

    # 方式3: 强制使用内存后端
    manager = get_state_manager("my_project", use_database=False)
"""
import os
from typing import Any, Optional

# 根据环境变量决定默认后端
_USE_DATABASE_DEFAULT = os.getenv("USE_DATABASE_BACKEND", "true").lower() == "true"

# 单例缓存
_state_manager_cache = {}


class StateManagerAdapter:
    """
    状态管理器适配器

    提供与原 StateManager 完全一致的API,内部委托给:
    - StateManagerV2 (数据库后端,默认)
    - StateManager (内存后端,可选)

    参数:
        project_name: 项目名称
        use_database: 是否使用数据库后端(默认从环境变量读取)
    """

    def __init__(self, project_name: str = "default_project", use_database: bool = None):
        """
        初始化状态管理器适配器

        Args:
            project_name: 项目名称
            use_database: 是否使用数据库后端。
                         None = 从环境变量读取(默认),
                         True = 强制数据库,
                         False = 强制内存
        """
        self.project_name = project_name

        # 确定使用哪个后端
        if use_database is None:
            use_database = _USE_DATABASE_DEFAULT

        self._use_database = use_database

        # 延迟导入,避免循环依赖
        if self._use_database:
            from utils.state_manager_v2 import StateManagerV2
            self._backend = StateManagerV2(project_name)
            self._backend_type = "database"
        else:
            from utils.state_manager import StateManager
            self._backend = StateManager(project_name)
            self._backend_type = "memory"

    # ==================== 核心接口方法 ====================

    def save(self, phase: str, key: str, value: Any) -> None:
        """
        保存数据

        Args:
            phase: 阶段名称 (如 "phase1")
            key: 数据键 (如 "design_variables")
            value: 要保存的数据
        """
        self._backend.save(phase, key, value)

    def load(self, phase: str, key: str, default: Any = None) -> Any:
        """
        加载数据

        Args:
            phase: 阶段名称
            key: 数据键
            default: 默认值

        Returns:
            加载的数据,如不存在返回默认值
        """
        return self._backend.load(phase, key, default)

    def get_all_phase_data(self, phase: str) -> dict:
        """
        获取某个阶段的所有数据

        Args:
            phase: 阶段名称

        Returns:
            包含该阶段所有数据的字典
        """
        return self._backend.get_all_phase_data(phase)

    def export_to_json(self, filepath: str) -> None:
        """
        导出项目数据为 JSON 文件

        Args:
            filepath: 导出文件路径
        """
        self._backend.export_to_json(filepath)

    def import_from_json(self, filepath: str) -> None:
        """
        从 JSON 文件导入项目数据

        Args:
            filepath: 导入文件路径
        """
        self._backend.import_from_json(filepath)

    def log_activity(self, phase: str, action: str, description: str) -> None:
        """
        记录活动日志

        Args:
            phase: 阶段名称
            action: 操作类型
            description: 描述信息
        """
        self._backend.log_activity(phase, action, description)

    def create_snapshot(self, snapshot_name: str = None) -> str:
        """
        创建项目快照

        Args:
            snapshot_name: 快照名称(可选,默认自动生成)

        Returns:
            快照文件路径
        """
        return self._backend.create_snapshot(snapshot_name)

    def restore_snapshot(self, snapshot_name: str) -> bool:
        """
        恢复项目快照

        Args:
            snapshot_name: 快照名称

        Returns:
            是否成功恢复
        """
        return self._backend.restore_snapshot(snapshot_name)

    def validate_data_flow(self):
        """
        验证数据流完整性

        Returns:
            验证结果字典
        """
        return self._backend.validate_data_flow()

    def reset_all(self) -> None:
        """
        重置所有Phase数据到初始状态，清空所有会话缓存数据

        用于新建项目、打开项目、导入数据等场景。
        委托给底层后端实现（StateManager或StateManagerV2）。
        """
        self._backend.reset_all()

    # ==================== 辅助属性 ====================

    @property
    def backend_type(self) -> str:
        """
        获取当前使用的后端类型

        Returns:
            "database" 或 "memory"
        """
        return self._backend_type

    @property
    def is_database_backend(self) -> bool:
        """
        是否使用数据库后端

        Returns:
            True 表示数据库, False 表示内存
        """
        return self._use_database

    def __repr__(self):
        return f"<StateManagerAdapter(project='{self.project_name}', backend='{self._backend_type}')>"


# ==================== 工厂函数 ====================

def get_state_manager(project_name: str = "default_project",
                      use_database: bool = None,
                      use_cache: bool = True) -> StateManagerAdapter:
    """
    获取状态管理器实例(推荐使用此函数)

    支持单例模式缓存,同一项目名称返回同一实例。

    Args:
        project_name: 项目名称
        use_database: 是否使用数据库后端(None=从环境变量读取)
        use_cache: 是否使用单例缓存(默认True)

    Returns:
        StateManagerAdapter 实例

    使用示例:
        # 默认使用数据库后端
        manager = get_state_manager("my_project")

        # 强制使用内存后端
        manager = get_state_manager("my_project", use_database=False)

        # 每次都创建新实例
        manager = get_state_manager("my_project", use_cache=False)
    """
    # 确定实际使用的后端
    actual_use_db = use_database if use_database is not None else _USE_DATABASE_DEFAULT

    # 缓存键
    cache_key = f"{project_name}_{actual_use_db}"

    if use_cache and cache_key in _state_manager_cache:
        return _state_manager_cache[cache_key]

    # 创建新实例
    manager = StateManagerAdapter(project_name, use_database=actual_use_db)

    if use_cache:
        _state_manager_cache[cache_key] = manager

    return manager


def reset_state_manager_cache() -> None:
    """
    重置状态管理器缓存(主要用于测试)

    清空单例缓存,下次调用 get_state_manager() 将创建新实例。
    """
    global _state_manager_cache
    _state_manager_cache.clear()


def get_backend_info() -> dict:
    """
    获取当前后端配置信息

    Returns:
        包含后端配置的字典,如:
        {
            'default_backend': 'database',
            'env_variable': 'USE_DATABASE_BACKEND=true',
            'cached_instances': 2
        }
    """
    return {
        'default_backend': 'database' if _USE_DATABASE_DEFAULT else 'memory',
        'env_variable': f"USE_DATABASE_BACKEND={os.getenv('USE_DATABASE_BACKEND', 'true')}",
        'cached_instances': len(_state_manager_cache),
        'cache_keys': list(_state_manager_cache.keys())
    }
