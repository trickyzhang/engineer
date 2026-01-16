"""
Monaco Editor集成帮助程序
用于生成初始化Monaco编辑器的JavaScript代码
"""

def get_monaco_init_script():
    """返回Monaco编辑器初始化脚本"""
    return """
<script>
// 加载Monaco Editor库
require.config({ paths: { 'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.50.0/min/vs' }});

// 初始化Python编辑器
function initEditor(containerId, initialCode, storeId) {
    require(['vs/editor/editor.main'], function() {
        const editor = monaco.editor.create(document.getElementById(containerId), {
            value: initialCode || 'def calculate_value(**design_vars):\\n    # 编写您的计算逻辑\\n    return 0',
            language: 'python',
            theme: 'vs',
            automaticLayout: true,
            minimap: { enabled: false },
            lineNumbers: 'on',
            scrollBeyondLastLine: false,
            fontSize: 13,
            fontFamily: "'Monaco', 'Courier New', monospace"
        });

        // 实时保存代码到dcc.Store
        editor.onDidChangeModelContent(() => {
            const code = editor.getValue();
            // 使用Dash的clientside callbacks更新Store
            const event = new CustomEvent('editorChanged', {
                detail: { code: code, editorId: containerId }
            });
            document.dispatchEvent(event);
        });

        window.editors = window.editors || {};
        window.editors[containerId] = editor;
    });
}

// 在DOM加载完成后初始化所有编辑器
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        if (typeof monaco !== 'undefined') {
            initEditor('editor-cost-model', '', 'editor-cost-model-code');
            initEditor('editor-perf-model', '', 'editor-perf-model-code');
        } else {
            // 重试
            setTimeout(arguments.callee, 100);
        }
    }, 100);
});
</script>
"""

def get_code_templates_help():
    """返回代码模板帮助文本"""
    return {
        "cost_model": """
        成本模型应该定义一个 calculate_cost() 函数，接收设计变量并返回成本值。

        函数签名: def calculate_cost(**design_vars) -> float

        可用的设计变量:
        - orbit_altitude (轨道高度, km)
        - antenna_diameter (天线直径, m)
        - transmit_power (发射功率, W)
        - component_count (组件数量)

        返回值: 系统总成本（通常为百万美元）

        示例:
        def calculate_cost(**design_vars):
            altitude = design_vars.get('orbit_altitude', 600)
            antenna = design_vars.get('antenna_diameter', 10)

            satellite_cost = 50 + 0.05 * altitude + 15 * antenna
            launch_cost = 40 + 0.03 * altitude
            total = satellite_cost + launch_cost + 20  # 基础设施成本

            return round(total, 2)
        """,

        "performance_model": """
        性能模型应该定义一个 calculate_<metric>() 函数。

        函数签名: def calculate_<metric>(**design_vars) -> float

        可用的设计变量: 同成本模型

        返回值: 对应指标的性能值

        示例（分辨率）:
        def calculate_resolution(**design_vars):
            import math
            antenna = design_vars.get('antenna_diameter', 10)
            altitude = design_vars.get('orbit_altitude', 600)

            # X波段雷达波长 (米)
            wavelength = 0.03

            # 理论分辨率
            resolution = wavelength / (2 * antenna)

            # 轨道高度影响
            degradation = 1 + (altitude - 400) / 400 * 0.2

            return round(resolution * degradation, 4)
        """,

        "value_model": """
        价值模型定义了如何评估性能指标的好坏。
        通常包括权重配置和效用函数定义。

        权重: 表示每个指标在最终决策中的重要性
        效用函数: 将性能指标值映射到0-1的效用值
        """
    }
