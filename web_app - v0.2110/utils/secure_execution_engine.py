# utils/secure_execution_engine.py
"""
安全代码执行引擎 - Phase 7.3 实现

基于 Phase 7.2 架构设计文档实现的安全代码执行引擎。
使用 RestrictedPython 提供 AST 级别的安全检查，
并通过系统资源限制防止 DoS 攻击。

作者: Claude Code
日期: 2025-12-21
版本: v1.0
依赖: Phase 7.2 架构设计
"""

from RestrictedPython import compile_restricted_exec, safe_builtins, safe_globals
from RestrictedPython.Guards import guarded_iter_unpack_sequence, safer_getattr
import operator
import signal
import sys
import platform
import hashlib
import logging
from typing import Callable, Dict, Any, Optional
import inspect
import re
import sys

# === Windows 兼容性补丁开始 ===
try:
    import resource
except ImportError:
    if sys.platform.startswith('win'):
        # 创建一个假的 resource 模块
        class MockResource:
            # 定义代码中可能用到的常量
            RLIMIT_AS = 0       # 限制地址空间（内存）
            RLIMIT_CPU = 1      # 限制 CPU 时间
            RLIMIT_DATA = 2
            RLIMIT_NOFILE = 3
            
            # 定义假的 setrlimit 方法，什么都不做
            def setrlimit(self, resource, limits):
                pass 
            
            # 定义假的 getrlimit 方法
            def getrlimit(self, resource):
                return (float('inf'), float('inf'))

        resource = MockResource()
        print("[System] Windows environment detected. Resource limits disabled.")
    else:
        raise
# === Windows 兼容性补丁结束 ===

class SecurityError(Exception):
    """代码包含不安全操作的异常"""
    pass


class SecureExecutionEngine:
    """
    安全代码执行引擎 - Phase 7.2 设计实现

    职责:
    - 编译用户代码为受限字节码 (RestrictedPython)
    - 设置系统资源限制 (CPU, 内存, 超时)
    - 隔离异常并返回友好错误信息
    - 提供向后兼容的 API

    安全层级:
    1. 编译时: AST 白名单检查 (RestrictedPython)
    2. 运行时: 资源限制 (signal, resource)
    3. 异常层: 捕获所有异常并格式化

    示例:
        >>> engine = SecureExecutionEngine(timeout_seconds=5, max_memory_mb=100)
        >>> code = '''
        ... def calculate_cost(**design_vars):
        ...     orbit = design_vars['orbit_altitude']
        ...     diameter = design_vars['antenna_diameter']
        ...     return orbit * 100 + diameter * 500
        ... '''
        >>> func = engine.compile_safe_function(code, "calculate_cost")
        >>> result = engine.execute_safe(func, {"orbit_altitude": 600, "antenna_diameter": 10})
        >>> print(result)  # 65000
    """

    def __init__(
        self,
        timeout_seconds: int = 5,
        max_memory_mb: int = 100,
        max_cpu_seconds: int = 2,
        recursion_limit: int = 500,
        enable_logging: bool = True
    ):
        """
        初始化安全执行引擎

        参数:
            timeout_seconds: 执行超时时间 (墙钟时间)，默认5秒
            max_memory_mb: 最大内存限制 (MB)，默认100MB
            max_cpu_seconds: 最大 CPU 时间 (秒)，默认2秒
            recursion_limit: 最大递归深度，默认500层
            enable_logging: 是否启用日志记录，默认True
        """
        self.timeout_seconds = timeout_seconds
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.max_cpu_seconds = max_cpu_seconds
        self.recursion_limit = recursion_limit

        # 配置日志记录
        if enable_logging:
            self.logger = logging.getLogger(__name__)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.INFO)
        else:
            self.logger = None

        # 编译缓存 (SHA256 hash → compiled function)
        self._compilation_cache: Dict[str, Callable] = {}

        # 日志初始化信息
        if self.logger:
            self.logger.info(
                f"SecureExecutionEngine initialized: "
                f"timeout={timeout_seconds}s, "
                f"max_memory={max_memory_mb}MB, "
                f"max_cpu={max_cpu_seconds}s, "
                f"recursion_limit={recursion_limit}, "
                f"platform={platform.system()}"
            )

    # ========== 公共 API (向后兼容) ==========

    def compile_safe_function(
        self,
        code_str: str,
        function_name: Optional[str] = None
    ) -> Callable:
        """
        编译用户代码为安全函数 (主入口 API)

        等价于 CalculationEngine.load_function_from_code()
        但使用 RestrictedPython 进行安全编译

        参数:
            code_str: Python 代码字符串 (必须包含函数定义)
            function_name: 函数名 (可选，自动提取)

        返回:
            安全的函数对象 (可直接调用)

        抛出:
            SecurityError: 代码包含不安全操作
            SyntaxError: 代码语法错误
            ValueError: 函数签名不正确

        示例:
            >>> code = 'def calc(**vars): return vars["x"] * 2'
            >>> func = engine.compile_safe_function(code)
            >>> func(x=10)
            20
        """
        # 检查编译缓存
        code_hash = hashlib.sha256(code_str.encode()).hexdigest()
        if code_hash in self._compilation_cache:
            if self.logger:
                self.logger.info(f"Using cached compilation for hash {code_hash[:8]}...")
            return self._compilation_cache[code_hash]

        if self.logger:
            self.logger.info(f"Compiling new function (hash {code_hash[:8]}...)")

        # Step 1: 编译为受限字节码
        byte_code = self._compile_restricted(code_str)

        # Step 2: 创建安全命名空间
        safe_namespace = self._create_safe_namespace()

        # Step 3: 执行字节码 (提取函数定义)
        exec(byte_code.code, safe_namespace)

        # Step 4: 提取函数对象
        func = self._extract_function(safe_namespace, code_str, function_name)

        # Step 5: 验证函数签名
        self._validate_signature(func)

        # Step 6: 包装为资源限制函数
        wrapped_func = self._wrap_with_limits(func)

        # 存入缓存
        self._compilation_cache[code_hash] = wrapped_func

        if self.logger:
            self.logger.info(f"Function compiled successfully: {func.__name__}")

        return wrapped_func

    def execute_safe(
        self,
        func: Callable,
        test_vars: Dict[str, Any]
    ) -> Any:
        """
        在资源限制下执行函数 (用于测试)

        等价于 CalculationEngine.test_function_execution()

        参数:
            func: 待执行的函数对象
            test_vars: 测试变量字典

        返回:
            函数执行结果 (int 或 float)

        抛出:
            TimeoutError: 执行超时
            MemoryError: 内存超限
            RecursionError: 递归深度超限
            ValueError: 返回值类型错误、NameError、ImportError等运行时错误

        示例:
            >>> func = engine.compile_safe_function(code)
            >>> result = engine.execute_safe(func, {"x": 10, "y": 20})
        """
        if self.logger:
            self.logger.info(f"Executing function with test vars: {list(test_vars.keys())}")

        try:
            # 已经在 compile_safe_function 中包装了资源限制
            # 这里直接调用即可
            result = func(**test_vars)

            # 验证返回类型
            if not isinstance(result, (int, float)):
                error_msg = (
                    f"函数返回值必须是数值类型 (int/float), "
                    f"实际返回: {type(result).__name__}"
                )
                if self.logger:
                    self.logger.error(error_msg)
                raise ValueError(error_msg)

            if self.logger:
                self.logger.info(f"Function executed successfully, result: {result}")

            return result

        except (TimeoutError, MemoryError, RecursionError):
            # 这些异常不转换,直接抛出 (已在_wrap_with_limits中格式化)
            raise

        except (NameError, ImportError) as e:
            # 捕获运行时尝试访问不存在的函数/模块
            error_msg = (
                f"函数执行失败: {str(e)}\n"
                f"提示: 代码中尝试使用未定义的函数或模块\n"
                f"  - 'open' 文件操作不允许\n"
                f"  - 'import' 语句不允许 (使用预定义的 math 模块)"
            )
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)

        except ValueError:
            # ValueError直接抛出 (可能来自返回类型检查)
            raise

        except Exception as e:
            # 其他所有异常转换为ValueError
            error_msg = f"函数执行失败: {str(e)}"
            if self.logger:
                self.logger.error(error_msg)
            raise ValueError(error_msg)

    # ========== 内部方法 (安全机制实现) ==========

    def _compile_restricted(self, code_str: str):
        """
        使用 RestrictedPython 编译代码

        检查:
        - 禁止 import 语句
        - 禁止 open(), eval(), exec(), compile()
        - 禁止 __import__, getattr, setattr, delattr
        - 禁止访问 _ 开头的私有属性

        参数:
            code_str: Python 代码字符串

        返回:
            RestrictedPython 编译后的字节码对象

        抛出:
            SecurityError: 代码包含不安全操作
        """
        try:
            byte_code = compile_restricted_exec(code_str)
        except SyntaxError as e:
            # Python 语法错误
            error_msg = f"代码语法错误 (第{e.lineno}行): {e.msg}"
            if self.logger:
                self.logger.error(error_msg)
            raise SyntaxError(error_msg)

        # 检查是否有安全错误
        if byte_code.errors:
            # 格式化错误信息
            errors_str = "\n".join([
                f"  - {error}" for error in byte_code.errors
            ])
            error_msg = (
                f"代码包含不安全的操作:\n{errors_str}\n\n"
                f"请移除以下内容:\n"
                f"  - import 语句 (使用预定义的 math 模块)\n"
                f"  - 文件操作 (open, file, read, write)\n"
                f"  - 动态执行 (eval, exec, compile)\n"
                f"  - 属性访问 (getattr, setattr, __import__)"
            )
            if self.logger:
                self.logger.error(f"Security check failed: {byte_code.errors}")
            raise SecurityError(error_msg)

        if self.logger:
            self.logger.debug("Code passed RestrictedPython AST check")

        return byte_code

    def _create_safe_namespace(self) -> Dict[str, Any]:
        """
        创建安全的命名空间

        允许:
        - math 模块 (数学运算)
        - 基础数值函数 (abs, len, min, max, sum, pow)
        - 类型转换 (int, float, str)
        - 安全数据结构 (list, dict, range, sorted)

        禁止:
        - 所有 I/O 操作
        - 网络访问
        - 系统调用
        - 动态导入

        返回:
            安全的命名空间字典
        """
        import math

        safe_namespace = {
            '__builtins__': safe_builtins,
            '_getiter_': guarded_iter_unpack_sequence,
            '_getattr_': safer_getattr,
            '_getitem_': operator.getitem,  # Enable dict['key'] and list[index] access
            'math': math,
            # 额外允许的安全函数
            'abs': abs,
            'len': len,
            'min': min,
            'max': max,
            'sum': sum,
            'round': round,
            'int': int,
            'float': float,
            'str': str,
            'list': list,
            'dict': dict,
            'range': range,
            'pow': pow,
            'sorted': sorted,
        }

        if self.logger:
            self.logger.debug(f"Created safe namespace with {len(safe_namespace)} allowed functions")

        return safe_namespace

    def _extract_function(
        self,
        namespace: Dict[str, Any],
        code_str: str,
        function_name: Optional[str]
    ) -> Callable:
        """
        从命名空间提取函数对象

        如果未指定 function_name，自动从代码中提取第一个函数定义

        参数:
            namespace: 执行后的命名空间
            code_str: 原始代码字符串
            function_name: 函数名 (可选)

        返回:
            函数对象

        抛出:
            ValueError: 未找到函数定义或函数名不正确
        """
        if function_name is None:
            # 使用正则提取函数名
            match = re.search(r'def\s+(\w+)', code_str)
            if not match:
                error_msg = (
                    "代码中未找到函数定义\n"
                    "请确保代码包含 'def function_name(...)' 形式的函数定义"
                )
                if self.logger:
                    self.logger.error("No function definition found in code")
                raise ValueError(error_msg)
            function_name = match.group(1)

        # 从命名空间获取函数
        if function_name not in namespace:
            error_msg = (
                f"函数 '{function_name}' 未在代码中定义\n"
                f"请检查函数名拼写是否正确"
            )
            if self.logger:
                self.logger.error(f"Function '{function_name}' not found in namespace")
            raise ValueError(error_msg)

        func = namespace[function_name]

        # 验证是否为可调用对象
        if not callable(func):
            error_msg = (
                f"'{function_name}' 不是一个函数对象\n"
                f"实际类型: {type(func).__name__}"
            )
            if self.logger:
                self.logger.error(f"'{function_name}' is not callable")
            raise ValueError(error_msg)

        if self.logger:
            self.logger.debug(f"Extracted function: {function_name}")

        return func

    def _validate_signature(self, func: Callable) -> None:
        """
        验证函数签名必须接受 **kwargs 参数

        合法示例:
        - def calculate_cost(**design_vars)
        - def calculate_cost(orbit_altitude, **kwargs)
        - def calculate_cost(**kw)

        不合法示例:
        - def calculate_cost(orbit_altitude)  # 缺少 **kwargs
        - def calculate_cost()                 # 无参数

        参数:
            func: 函数对象

        抛出:
            ValueError: 函数签名不正确
        """
        sig = inspect.signature(func)

        has_var_keyword = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )

        if not has_var_keyword:
            error_msg = (
                f"函数签名不正确: 缺少 **kwargs 参数\n\n"
                f"当前签名: {sig}\n\n"
                f"正确示例:\n"
                f"  def calculate_cost(**design_vars):\n"
                f"      orbit_altitude = design_vars['orbit_altitude']\n"
                f"      antenna_diameter = design_vars['antenna_diameter']\n"
                f"      return orbit_altitude * 100 + antenna_diameter * 500\n"
            )
            if self.logger:
                self.logger.error(f"Invalid function signature: {sig}")
            raise ValueError(error_msg)

        if self.logger:
            self.logger.debug(f"Function signature validated: {sig}")

    def _wrap_with_limits(self, func: Callable) -> Callable:
        """
        包装函数，添加资源限制

        限制:
        1. 墙钟超时 (signal.alarm)
        2. CPU 时间限制 (resource.RLIMIT_CPU)
        3. 内存限制 (resource.RLIMIT_AS)
        4. 递归深度限制 (sys.setrecursionlimit)

        参数:
            func: 原始函数对象

        返回:
            包装后的函数对象 (带资源限制)
        """
        def limited_func(**kwargs):
            # 保存原始递归限制
            original_recursion_limit = sys.getrecursionlimit()

            # 超时处理函数
            def timeout_handler(signum, frame):
                error_msg = (
                    f"函数执行超时 ({self.timeout_seconds}秒)\n"
                    f"可能原因:\n"
                    f"  - 代码存在无限循环\n"
                    f"  - 计算复杂度过高\n"
                    f"请优化代码逻辑或减少计算量"
                )
                if self.logger:
                    self.logger.error("Function execution timed out")
                raise TimeoutError(error_msg)

            try:
                # 1. 设置递归限制
                sys.setrecursionlimit(self.recursion_limit)
                if self.logger:
                    self.logger.debug(f"Set recursion limit to {self.recursion_limit}")

                # 2-3. 设置超时和资源限制 (仅 Unix/Linux/macOS)
                if platform.system() != 'Windows':
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(self.timeout_seconds)
                    if self.logger:
                        self.logger.debug(f"Set timeout to {self.timeout_seconds}s")

                    try:
                        # CPU 时间限制
                        resource.setrlimit(
                            resource.RLIMIT_CPU,
                            (self.max_cpu_seconds, self.max_cpu_seconds)
                        )
                        if self.logger:
                            self.logger.debug(f"Set CPU limit to {self.max_cpu_seconds}s")

                        # 内存限制 (虚拟内存地址空间)
                        resource.setrlimit(
                            resource.RLIMIT_AS,
                            (self.max_memory_bytes, self.max_memory_bytes)
                        )
                        if self.logger:
                            self.logger.debug(f"Set memory limit to {self.max_memory_bytes / (1024*1024):.0f}MB")

                    except (ValueError, OSError) as e:
                        # 某些系统可能不支持资源限制
                        if self.logger:
                            self.logger.warning(f"无法设置资源限制: {e}")
                else:
                    # Windows 平台警告
                    if self.logger:
                        self.logger.warning(
                            "Windows 平台不支持资源限制 (signal/resource)。"
                            "建议在 Linux 容器中运行生产环境。"
                        )

                # 4. 执行函数
                result = func(**kwargs)

                return result

            except RecursionError:
                error_msg = (
                    f"递归深度超过限制 ({self.recursion_limit})\n"
                    f"可能原因:\n"
                    f"  - 递归函数未正确终止\n"
                    f"  - 递归层数过多\n"
                    f"请检查递归终止条件或改用迭代算法"
                )
                if self.logger:
                    self.logger.error("Recursion depth exceeded")
                raise RecursionError(error_msg)

            except MemoryError:
                error_msg = (
                    f"内存使用超过限制 ({self.max_memory_bytes / (1024*1024):.0f}MB)\n"
                    f"可能原因:\n"
                    f"  - 创建了过大的列表/数组\n"
                    f"  - 内存泄漏\n"
                    f"请优化数据结构或减少数据量"
                )
                if self.logger:
                    self.logger.error("Memory limit exceeded")
                raise MemoryError(error_msg)

            finally:
                # 5. 清理资源限制
                if platform.system() != 'Windows':
                    signal.alarm(0)  # 取消超时
                    if self.logger:
                        self.logger.debug("Cleared timeout alarm")

                # 恢复递归限制
                sys.setrecursionlimit(original_recursion_limit)
                if self.logger:
                    self.logger.debug(f"Restored recursion limit to {original_recursion_limit}")

        return limited_func

    def clear_cache(self) -> None:
        """
        清空编译缓存

        用于释放内存或强制重新编译
        """
        cache_size = len(self._compilation_cache)
        self._compilation_cache.clear()
        if self.logger:
            self.logger.info(f"Cleared compilation cache ({cache_size} entries)")

    def get_cache_info(self) -> Dict[str, int]:
        """
        获取缓存信息

        返回:
            包含缓存统计信息的字典
        """
        return {
            "cache_size": len(self._compilation_cache),
            "max_cache_size": -1  # 无限制
        }
