"""
计算引擎 - 用于Phase 3的模型代码加载和执行

Phase 7.4 安全加固版:
- 集成 SecureExecutionEngine 进行安全代码执行
- 使用 RestrictedPython 进行 AST 级别安全检查
- 添加资源限制 (超时、内存、CPU、递归)
- 保持向后兼容的 API
"""

import re
import math
import logging
from typing import Callable, Dict, Any

# Phase 7.4: 导入安全执行引擎
from utils.secure_execution_engine import SecureExecutionEngine, SecurityError

logger = logging.getLogger(__name__)


class CalculationEngine:
    """
    动态计算引擎 - 支持从字符串代码加载并执行Python函数

    Phase 7.4 安全加固版:
    - 使用 SecureExecutionEngine 替代原有 exec()
    - 添加 RestrictedPython AST 检查
    - 添加资源限制 (超时、内存、CPU)
    - 保持 API 签名不变
    """

    # Phase 7.4: 单例安全执行引擎
    _secure_engine: SecureExecutionEngine = None

    @classmethod
    def get_secure_engine(cls) -> SecureExecutionEngine:
        """
        获取安全执行引擎实例 (单例模式)

        Returns:
            SecureExecutionEngine 实例
        """
        if cls._secure_engine is None:
            cls._secure_engine = SecureExecutionEngine(
                timeout_seconds=5,
                max_memory_mb=100,
                max_cpu_seconds=2,
                recursion_limit=500,
                enable_logging=True
            )
        return cls._secure_engine

    @staticmethod
    def load_function_from_code(code_str: str, function_name: str = None) -> Callable:
        """
        从字符串代码动态加载Python函数 (安全版本)

        ✅ Phase 7.4 变更:
        - 使用 SecureExecutionEngine 替代原有 exec()
        - 添加 RestrictedPython AST 检查
        - 添加资源限制 (超时、内存、CPU)
        - 保持 API 签名不变

        Args:
            code_str: Python函数代码字符串
            function_name: 期望的函数名（如果为None，自动检测）

        Returns:
            安全的函数对象

        Raises:
            ValueError: 代码安全检查失败、语法错误或函数签名错误
        """
        engine = CalculationEngine.get_secure_engine()

        try:
            # 使用安全引擎编译
            func = engine.compile_safe_function(code_str, function_name)
            return func

        except SecurityError as e:
            # 安全错误 - 代码包含危险操作
            raise ValueError(f"代码安全检查失败:\n{str(e)}")
        except SyntaxError as e:
            # 语法错误
            raise ValueError(f"代码语法错误: {str(e)}")
        except Exception as e:
            # 其他错误
            raise ValueError(f"代码加载失败: {str(e)}")

    @staticmethod
    def validate_function_signature(func: Callable) -> bool:
        """
        验证函数签名 - 必须接受 **kwargs 参数

        Args:
            func: 要验证的函数

        Returns:
            True 如果签名有效

        Raises:
            ValueError: 签名无效
        """
        import inspect

        try:
            sig = inspect.signature(func)
        except Exception as e:
            raise ValueError(f"无法获取函数签名: {str(e)}")

        # 检查是否有 **kwargs 参数
        has_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )

        if not has_kwargs:
            raise ValueError("函数必须接受 **design_vars 或 **kwargs 参数")

        return True

    @staticmethod
    def test_function_execution(func: Callable, test_vars: Dict[str, Any]) -> Any:
        """
        测试函数是否能正确执行 (安全版本)

        ✅ Phase 7.4 变更:
        - 使用 SecureExecutionEngine.execute_safe()
        - 资源限制自动生效
        - 保持 API 签名不变

        Args:
            func: 要测试的函数
            test_vars: 测试变量字典

        Returns:
            函数执行结果

        Raises:
            ValueError: 执行失败 (超时、内存、递归或其他错误)
        """
        engine = CalculationEngine.get_secure_engine()

        try:
            result = engine.execute_safe(func, test_vars)
            return result

        except TimeoutError as e:
            raise ValueError(f"执行超时: {str(e)}")
        except MemoryError as e:
            raise ValueError(f"内存超限: {str(e)}")
        except RecursionError as e:
            raise ValueError(f"递归超限: {str(e)}")
        except Exception as e:
            raise ValueError(f"函数执行失败: {str(e)}")


# 示例代码库 - 提供常见的模型模板
CODE_TEMPLATES = {
    "cost_model_simple_linear": '''def calculate_cost(**design_vars):
    """
    简单线性成本模型
    """
    altitude = design_vars.get('orbit_altitude', 600)
    antenna = design_vars.get('antenna_diameter', 10)
    component_count = design_vars.get('component_count', 6)

    # 线性关系
    satellite_cost = 50 + 0.05 * altitude + 15 * antenna
    component_cost = 8 * component_count
    launch_cost = 40 + 0.03 * altitude
    infrastructure_cost = 20

    return round(satellite_cost + component_cost + launch_cost + infrastructure_cost, 2)
''',

    "cost_model_quadratic": '''def calculate_cost(**design_vars):
    """
    二次项成本模型（考虑非线性关系）
    """
    altitude = design_vars.get('orbit_altitude', 600)
    antenna = design_vars.get('antenna_diameter', 10)
    power = design_vars.get('transmit_power', 3000)

    # 非线性关系：轨道高度平方项（高度越高成本增长越快）
    altitude_factor = 50 + 0.05 * altitude + 0.0001 * altitude**2

    # 天线尺寸指数关系
    antenna_factor = 10 + 5 * pow(antenna, 1.5)

    # 功率线性
    power_factor = 0.02 * power

    # 固定成本
    fixed_cost = 30

    total = altitude_factor + antenna_factor + power_factor + fixed_cost

    return round(total, 2)
''',

    "cost_model_exponential": '''def calculate_cost(**design_vars):
    """
    指数成本模型（成本随复杂度指数增长）
    """
    # math模块已在安全命名空间中预加载，无需import

    altitude = design_vars.get('orbit_altitude', 600)
    antenna = design_vars.get('antenna_diameter', 10)
    component_count = design_vars.get('component_count', 6)

    # 基础成本
    base_cost = 30

    # 轨道高度：指数增长
    altitude_cost = 20 * math.exp((altitude - 400) / 200)

    # 天线尺寸：功率增长
    antenna_cost = 5 * pow(antenna, 2)

    # 组件复杂度：指数增长
    complexity_cost = 10 * math.exp((component_count - 4) / 3)

    total = base_cost + altitude_cost + antenna_cost + complexity_cost

    return round(total, 2)
''',

    "cost_model_piecewise": '''def calculate_cost(**design_vars):
    """
    分段函数成本模型（不同高度范围成本函数不同）
    """
    altitude = design_vars.get('orbit_altitude', 600)
    antenna = design_vars.get('antenna_diameter', 10)

    # LEO轨道 (400-600km)
    if altitude <= 600:
        altitude_cost = 40 + 0.02 * altitude
    # MEO轨道 (600-35786km)
    elif altitude <= 10000:
        altitude_cost = 50 + 0.05 * altitude
    # GEO轨道 (>35786km)
    else:
        altitude_cost = 100 + 0.1 * altitude

    antenna_cost = 10 + 8 * antenna
    infrastructure_cost = 30

    total = altitude_cost + antenna_cost + infrastructure_cost

    return round(total, 2)
''',

    "performance_model_resolution": '''def calculate_resolution(**design_vars):
    """
    图像分辨率模型 (基于 wavelength / (2 * antenna_diameter))
    """
    # math模块已在安全命名空间中预加载，无需import

    antenna = design_vars.get('antenna_diameter', 10)
    altitude = design_vars.get('orbit_altitude', 600)

    # X波段雷达波长 (米)
    wavelength = 0.03

    # 理论分辨率（与天线直径成反比）
    theoretical_resolution = wavelength / (2 * antenna)

    # 轨道高度影响：高度越高分辨率越低
    altitude_degradation = 1 + (altitude - 400) / 400 * 0.2

    # 最终分辨率
    resolution = theoretical_resolution * altitude_degradation

    return round(resolution, 4)
''',

    "performance_model_coverage": '''def calculate_coverage(**design_vars):
    """
    每日覆盖面积模型 (基于轨道高度的可见角度)
    """
    # math模块已在安全命名空间中预加载，无需import

    altitude = design_vars.get('orbit_altitude', 600)

    # 地球半径
    R = 6371  # km

    # 从轨道高度计算可见的地球角度
    # cos(half_angle) = R / (R + altitude)
    cos_half_angle = R / (R + altitude)

    # 处理边界情况
    if cos_half_angle >= 1:
        cos_half_angle = 0.9999
    if cos_half_angle <= -1:
        cos_half_angle = -0.9999

    half_angle = math.acos(cos_half_angle)  # 弧度
    full_angle = 2 * half_angle

    # 单圈扫描宽度
    swath_width = 2 * (R + altitude) * math.sin(half_angle)

    # 假设每天轨道通过14.4次（约100分钟周期）
    coverage_area = swath_width * R * 14.4 * 2 * math.pi / 360

    return round(coverage_area, 0)
''',

    "performance_model_power": '''def calculate_power_consumption(**design_vars):
    """
    功率消耗模型
    """
    transmit_power = design_vars.get('transmit_power', 3000)
    antenna = design_vars.get('antenna_diameter', 10)
    component_count = design_vars.get('component_count', 6)

    # 发射功率
    tx_power = transmit_power

    # 电子设备功率（基于组件数量）
    electronics_power = 100 * component_count

    # 天线指向和控制功率
    control_power = 50 + 10 * antenna

    total_power = tx_power + electronics_power + control_power

    return round(total_power, 2)
''',

    "performance_model_reliability": '''def calculate_reliability(**design_vars):
    """
    可靠性模型 (0-1, 1表示完全可靠)
    """
    # math模块已在安全命名空间中预加载，无需import

    component_count = design_vars.get('component_count', 6)
    transmit_power = design_vars.get('transmit_power', 3000)

    # 基础可靠性
    base_reliability = 0.95

    # 组件数量影响：每增加一个组件，可靠性降低
    component_penalty = (component_count - 4) * 0.02  # 每个组件-2%

    # 功率影响：功率越高，可靠性越低
    power_penalty = (transmit_power - 2000) / 3000 * 0.1  # 最多-10%

    reliability = base_reliability - component_penalty - power_penalty

    # 限制在[0, 1]范围内
    reliability = max(0, min(1, reliability))

    return round(reliability, 4)
'''
}
