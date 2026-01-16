"""
Phase 4: 效用与偏好建模
三个代码编辑区 (成本模型, 性能模型, 价值模型)
"""

from dash import html, dcc, callback, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
from dash_ace import DashAceEditor
import pandas as pd
import json
import sys
import os
import re
from datetime import datetime

# 将 StateManager 的引用移到这里 (解决 NameError)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.state_manager import get_state_manager
from utils.calculation_engine import CalculationEngine, CODE_TEMPLATES

# 名称清洗辅助函数，确保与验证逻辑一致
def sanitize_name(name):
    """
    清洗变量名或属性名，生成合法的 Python 标识符。
    规则：替换所有非字母数字字符为下划线，数字开头加前缀。
    """
    if not name:
        return "unknown"
    # 替换非单词字符 (包括空格, 标点) 为 _
    clean = re.sub(r'\W', '_', str(name))
    # 避免以数字开头
    if clean and clean[0].isdigit():
        clean = '_' + clean
    return clean


# 构建代码编辑器组件
def build_code_editor(editor_id, height="400px", placeholder="", initial_code=""):
    """构建代码编辑器组件"""
    return DashAceEditor(
        id=f"{editor_id}-code",
        value=initial_code or placeholder or "# 编写您的计算函数...\n",
        mode='python',
        theme='monokai',
        height=height,
        width='100%',
        fontSize=13,
        tabSize=4,
        enableBasicAutocompletion=True,
        enableLiveAutocompletion=True,
        wrapEnabled=True,
        showPrintMargin=False,
        style={
            "borderRadius": "4px",
            "border": "1px solid #ddd"
        }
    )

def get_phase3_columns():
    """获取 Phase 3 设计空间的所有列名 (Design Vars + Potential Static Attributes)"""
    state = get_state_manager()
    alternatives = state.load("phase3", "alternatives")
    
    columns = []
    
    if alternatives is not None:
        # 1. 支持 List[Dict] (通常是 state_manager 保存的格式)
        if isinstance(alternatives, list) and len(alternatives) > 0:
            columns = list(alternatives[0].keys())
            
        # 2. 支持 DataFrame (直接加载 Pandas 对象的情况)
        elif isinstance(alternatives, pd.DataFrame):
            if not alternatives.empty:
                columns = alternatives.columns.tolist()
                
        # 3. 支持 Dict (Dash Store 的 JSON 格式)
        elif isinstance(alternatives, dict) and 'data' in alternatives:
             if alternatives['data']:
                columns = list(alternatives['data'][0].keys())

    # 过滤掉内部ID
    return [c for c in columns if c != 'design_id']

def render_variable_badges(var_list, context_type="input", values_dict=None):
    """
    生成带复制功能的变量徽章 (增强版：支持数值预览与函数调用格式优化)
    Args:
        var_list: 变量名/函数名列表
        context_type: 变量类型 (input/attr/utility)
        values_dict: (可选) 变量名到数值的映射字典，用于显示预览值
    """
    if not var_list:
        return html.Small("暂无可用变量", className="text-muted")

    badges = []
    for var in var_list:
        # 1. 确定复制内容和样式
        if context_type == "input":
            # 输入变量：获取值
            copy_text = f"design_vars.get('{var}')"
            color = "secondary"
            icon = "fas fa-cube"
            title = "Phase 3 原始数据"
        elif context_type == "attr":
            # 4.1 属性模型：[修改] 现在 var 是函数名 calculate_xxx
            copy_text = f"{var}(**design_vars)"
            color = "info"
            icon = "fas fa-calculator"
            title = "Phase 4.1 计算函数"
        elif context_type == "utility":
            # 4.2 效用函数：var 是函数名 utility_xxx
            copy_text = f"{var}(**design_vars)" 
            color = "success"
            icon = "fas fa-balance-scale"
            title = "Phase 4.2 效用函数"
        else:
            copy_text = var
            color = "light"
            icon = "fas fa-question"
            title = ""

        # 2. 构建显示标签 (包含数值预览，仅针对 input 类型有效)
        display_label = [html.Span(var, className="me-2")]
        if values_dict and var in values_dict:
            val = values_dict[var]
            # 格式化数值
            if isinstance(val, (int, float)):
                val_str = f"{val:.4g}"
                val_style = "font-monospace small opacity-75 border-start ps-2"
            else:
                val_str = str(val)
                val_style = "small opacity-75 border-start ps-2"
            
            display_label.append(html.Span(f"[{val_str}]", className=val_style))

        badges.append(
            dbc.Badge(
                [
                    html.I(className=f"{icon} me-1"),
                    *display_label, # 展开标签内容
                    dcc.Clipboard(
                        content=copy_text,
                        title="点击复制代码",
                        style={
                            "display": "inline-block",
                            "color": "white",
                            "cursor": "pointer",
                            "fontSize": "0.8em",
                            "marginLeft": "8px"
                        },
                    ),
                ],
                color=color,
                className="me-2 mb-2 p-2",
                title=f"{title}\n代码: {copy_text}",
                style={"fontSize": "0.85rem"}
            )
        )
    
    return html.Div(badges, className="d-flex flex-wrap")



# ===== 动态生成Alert =====
def get_design_vars_list():
    """
    获取设计变量列表以供代码提示。
    [关键修改] 强制只从 Phase 3 的实际设计空间(alternatives)获取列名。
    这保证了 Phase 4 的代码提示与 Phase 3 生成的数据完全一致。
    """
    state = get_state_manager()
    
    # 1. 加载 Phase 3 生成的实际数据
    alternatives = state.load("phase3", "alternatives")
    
    design_vars = []
    
    # 检查 Phase 3 数据是否存在且有效
    if alternatives is not None:
        first_row = None
        
        if isinstance(alternatives, pd.DataFrame) and not alternatives.empty:
            first_row = alternatives.iloc[0].to_dict()
        elif isinstance(alternatives, list) and len(alternatives) > 0:
            first_row = alternatives[0]
        elif isinstance(alternatives, dict) and 'data' in alternatives and len(alternatives['data']) > 0:
            first_row = alternatives['data'][0]
            
        if isinstance(first_row, dict):
            # 获取所有键，过滤掉内部ID
            cols = list(first_row.keys())
            design_vars = [
                {'name': col, 'description': '来自 Phase 3 设计空间', 'unit': ''} 
                for col in cols if col != 'design_id'
            ]

    # 如果 Phase 3 还没生成数据，返回空列表，并在UI提示
    return design_vars

def generate_smart_code_template(func_name, variable_list, description=""):
    """
    生成智能代码模板：自动解包所有可用变量
    """
    code_lines = [
        f"def {func_name}(**design_vars):",
        f'    """',
        f'    {description}',
        f'    输入变量 (kwargs):'
    ]
    
    # 自动生成文档注释
    for var in variable_list:
        v_name = var.get('name')
        v_unit = var.get('unit', '')
        code_lines.append(f"    - {v_name} ({v_unit})")
        
    code_lines.append(f'    """')
    code_lines.append(f"    # --- 1. 自动解包变量 (按需使用) ---")
    
    # 自动生成变量获取代码
    for var in variable_list:
        v_name = var.get('name')
        # 尝试处理中文变量名转合法的Python变量名 (简单处理：替换特殊字符，或者直接用 v_Ref)
        safe_var_name = v_name.replace(' ', '_').replace('(', '').replace(')', '')
        # 如果是纯中文，为了方便，可以直接保留，或者加 v_ 前缀
        # 这里为了演示，生成标准的 .get 代码
        code_lines.append(f"    {safe_var_name} = design_vars.get('{v_name}', 0.0)")
        
    code_lines.append(f"")
    code_lines.append(f"    # --- 2. 编写计算逻辑 ---")
    code_lines.append(f"    # TODO: 使用上述变量计算结果")
    code_lines.append(f"    result = 0.0")
    code_lines.append(f"    ")
    code_lines.append(f"    return float(result)")
    
    return "\n".join(code_lines)

def get_value_attributes_from_phase1():
    """从Phase 1读取价值属性列表 (修复：强制返回列表，防止DataFrame真值歧义报错)"""
    state = get_state_manager()
    value_attrs = state.load("phase1", "value_attributes")

    # 1. 处理 DataFrame 情况
    if isinstance(value_attrs, pd.DataFrame):
        if value_attrs.empty:
            value_attrs = []
        else:
            value_attrs = value_attrs.to_dict('records')

    # 2. 处理 None 或其他非列表情况
    if not isinstance(value_attrs, list):
        value_attrs = []

    return value_attrs

def format_var_display(item_dict):
    """
    通用格式化函数：将变量字典转换为“代码变量名 (业务描述)”的格式。
    
    Args:
        item_dict (dict): 包含 'name' 和 'description' 的字典
        
    Returns:
        str: 格式化后的字符串，例如 "speed (飞行速度)"
    """
    # 获取变量名，如果丢失则显示'未知变量'
    var_name = item_dict.get('name', 'unknown_var')
    
    # 获取描述，如果用户没填描述，就只显示变量名
    description = item_dict.get('description', '')
    
    if description:
        # 格式：变量名 (描述) -> 让用户写代码时知道含义
        return f"{var_name} ({description})"
    else:
        # 如果没有描述，只返回变量名
        return var_name


def build_model_context_alert():
    """
    动态生成模型上下文提示 - 增强版 (带复制提示)
    """
    import dash_bootstrap_components as dbc
    from dash import html
    
    # 1. 获取动态数据
    design_vars = get_design_vars_list()
    
    # 2. 生成输入变量展示 (Input Items) - 增加点击复制的提示
    input_items = []
    if design_vars:
        for var in design_vars:
            name = var.get('name', 'unknown')
            unit = var.get('unit', '')
            
            # 构建一个类似代码片段的Badge
            code_snippet = f"design_vars.get('{name}')"
            
            input_items.append(
                dbc.Badge(
                    [
                        html.I(className="fas fa-copy me-1"),
                        f"{name} {f'[{unit}]' if unit else ''}"
                    ],
                    color="light",
                    text_color="dark",
                    className="me-2 mb-2 p-2 border",
                    style={"cursor": "pointer", "userSelect": "all"}, # 允许全选复制
                    title=f"代码片段: {code_snippet}"
                )
            )
    else:
        input_items.append(
            html.Span("⚠️ 未检测到 Phase 3 变量，请先生成设计空间", className="text-danger")
        )

    # 4. 返回 Alert
    return dbc.Alert([
        html.H6([html.I(className="fas fa-database me-2"), "可用变量池 (Phase 3 Design Space)"], className="alert-heading"),
        html.P("下方列出了 Phase 3 生成的所有设计变量。您可以直接参考这些变量名编写代码。", className="small text-muted mb-2"),
        html.Div(
            input_items, 
            className="d-flex flex-wrap align-items-center"
        ),
        html.Hr(),
        html.Small([
            html.I(className="fas fa-info-circle me-1"),
            "提示：点击模板按钮可自动生成包含所有变量的代码框架。"
        ], className="text-muted")
    ], color="light", className="mb-3 border")



def build_utility_alert():
    """
    动态生成效用函数说明 Alert（优化版）。
    依赖 get_value_attributes_from_phase1 返回的清洗后数据。
    """
    import dash_bootstrap_components as dbc
    from dash import html
    
    # 1. 获取清洗后的数据
    value_attrs = get_value_attributes_from_phase1()
    attr_items = [html.Li(f"{attr.get('name')} ({attr.get('unit','')})") for attr in value_attrs]

    # 2. 定义内部格式化逻辑：变量名 (描述)
    def format_label(item):
        name = item.get('name', 'unknown')
        desc = item.get('description', '')
        return f"{name} ({desc})" if desc else name

    # 4. 生成函数签名示例列表
    # 格式：def utility_cost(**design_vars): # 计算 'cost (成本)' 的效用
    func_examples = [
        html.Li(
            [
                # 高亮显示代码部分
                html.Code(f"def utility_{attr.get('name', 'attr')}(**design_vars):"),
                # 后面跟上灰色的注释说明，方便阅读
                html.Span(
                    f" # 计算 '{format_label(attr)}' 的效用值 (返回0.0-1.0)", 
                    className="text-muted small ms-2"
                )
            ],
            className="mb-1"
        )
        for attr in value_attrs
    ]

    # 5. 返回 Alert 组件
    return dbc.Alert([
        html.I(className="fas fa-sliders-h me-2"),
        html.Div([
            "定义效用函数和权重配置。使用 Python 代码定义如何将属性值转换为满意度 [0,1]。",
            html.Br(),
            html.Br(),
            
            html.Strong("当前定义的价值属性（需为其编写效用函数）："),
            html.Ul(attr_items, className="ms-3 mt-2"),
            
            html.Strong("函数命名规范参考："),
            html.Div("请确保函数名与下方列表严格一致：", className="text-muted small mb-2"),
            html.Ul(func_examples, className="ms-3"),
        ])
    ], color="info", className="mb-3")

# ==================== Layout ====================

layout = dbc.Container([
    # 数据存储 (Unified)
    dcc.Store(id='phase4-perf-models-store', data={}), 
    dcc.Store(id='phase4-weights-store', data={}),
    dcc.Store(id='refresh-badges-trigger', data=0),
    dcc.Store(id='phase4-ui-state', data={}),

    html.H2([
        html.I(className="fas fa-code me-2 text-info"),
        "Phase 4: 多域属性建模"
    ], className="mb-4"),

    dbc.Alert([
        html.I(className="fas fa-lightbulb me-2"),
        "本阶段将 Phase 3 的设计变量映射为系统属性（成本、性能等），并定义效用偏好。请为左侧下拉框中的每个属性编写 Python 计算逻辑。"
    ], color="light", className="mb-4"),

    # ===== 4.1 统一属性模型编辑器 =====
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("4.1 属性模型定义 (Attribute Models)", className="mb-0 text-white"), className="bg-primary"),
                dbc.CardBody([
                    # 动态容器
                    dbc.Alert([
                        html.H6([html.I(className="fas fa-database me-2"), "可用变量池 (点击图标复制)"], className="alert-heading"),
                        html.Hr(),
                        html.Div([
                            html.Strong("Phase 3 Design Space:", className="text-secondary small"),
                            html.Div(id="badges-4-1-container", className="mt-1")
                        ])
                    ], color="light", className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("1. 选择要建模的属性:", className="fw-bold mb-2"),
                            dbc.Select(
                                id="select-attribute-model", 
                                options=[], 
                                placeholder="请选择",
                                className="mb-3"
                            ),
                            html.Label("2. 模板选择（点击按钮快速填充）:", className="fw-bold mb-2"),
                            dbc.ButtonGroup([
                                dbc.Button("简单线性", id="btn-tmpl-linear", size="sm", outline=True, color="primary"),
                                dbc.Button("成本累加", id="btn-tmpl-cost", size="sm", outline=True, color="primary"),
                                dbc.Button("物理公式", id="btn-tmpl-physics", size="sm", outline=True, color="primary"),
                                dbc.Button("指数模型", id="btn-tmpl-exponential", size="sm", outline=True, color="primary"),
                            ], className="w-100 mb-3")
                        ])
                    ]),

                    html.Label("3. Python 计算逻辑:", className="fw-bold"),
                    build_code_editor("editor-attr-model", height="400px"),
                    
                    # 操作按钮区
                    dbc.Row([
                        dbc.Col([
                            dbc.Button([html.I(className="fas fa-check me-2"),"验证代码"], id="btn-validate-attr", color="success", size="sm", className="w-100")
                        ], md=3),
                        dbc.Col([
                            dbc.Button([html.I(className="fas fa-play me-2"),"测试执行"], id="btn-test-attr", color="info", size="sm", className="w-100")
                        ], md=3),
                        dbc.Col([
                            dbc.Button([html.I(className="fas fa-save me-2"),"保存函数"], id="btn-save-attr", color="warning", size="sm", className="w-100")
                        ], md=3),
                        dbc.Col(id="attr-validation-status", md=3) 
                    ], className="g-2 mt-2"),

                    html.Div(id="attr-test-results", className="mt-3"),
                    html.Hr(),
                    html.Div(id="saved-models-list", className="mt-2")
                ])
            ], className="shadow-sm mb-4 border-primary")
        ], md=12)
    ]),

    # ===== 4.2 价值模型与权重配置 =====
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("4.2 价值模型与权重配置", className="mb-0")),
                dbc.CardBody([

                    # ===== 编辑器1: 效用函数定义 =====
                    dbc.Row([
                        dbc.Col([
                            html.H6("编辑器1: 效用函数定义", className="fw-bold mb-2"),
                            dbc.Alert([
                                html.H6([html.I(className="fas fa-database me-2"), "可用变量池 (点击图标复制)"], className="alert-heading"),
                                html.Hr(),
                                html.Div([
                                    html.Strong("Phase 3 Design Space:", className="text-secondary small"),
                                    html.Div(id="badges-4-2-util-p3", className="mt-1 mb-2"),
                                    html.Strong("Phase 4.1 Calculated Attributes:", className="text-info small"),
                                    html.Div(id="badges-4-2-util-p41", className="mt-1")
                                ])
                            ], color="light", className="mb-3"),

                            html.Label("单一效用（选择一个开始编辑）:", className="fw-bold mb-2"),
                            dbc.Select(id="select-utility-attr", placeholder="请选择", className="mb-3"),

                            html.Label("模板选择（点击按钮快速填充）:", className="fw-bold mb-2"),
                            dbc.ButtonGroup([
                                dbc.Button("线性", id="btn-utility-linear", size="sm", outline=True, color="primary"),
                                dbc.Button("指数", id="btn-utility-exponential", size="sm", outline=True, color="primary"),
                                dbc.Button("凹函数", id="btn-utility-concave", size="sm", outline=True, color="primary"),
                                dbc.Button("凸函数", id="btn-utility-convex", size="sm", outline=True, color="primary"),
                                dbc.Button("S曲线", id="btn-utility-scurve", size="sm", outline=True, color="primary"),
                            ], className="w-100 mb-3"),

                            html.Label("Python代码编辑器:", className="fw-bold"),
                            build_code_editor("editor-utility-functions", height="350px"),

                            dbc.Row([
                                dbc.Col([
                                    dbc.Button([html.I(className="fas fa-check me-2"),"验证代码"], id="btn-validate-utility", color="success", size="sm", className="w-100")
                                ], md=3),
                                dbc.Col([
                                    dbc.Button([html.I(className="fas fa-play me-2"),"测试执行"], id="btn-test-utility", color="info", size="sm", className="w-100")
                                ], md=3),
                                dbc.Col([
                                    dbc.Button([html.I(className="fas fa-save me-2"),"保存函数"], id="btn-save-utility", color="warning", size="sm", className="w-100")
                                ], md=3),
                                dbc.Col(id="utility-validation-status", md=3)
                            ], className="g-2 mt-2"),

                            html.Div(id="utility-test-results", className="mt-3"),
                            html.Div(id="saved-utility-code", className="mt-3"),
                        ])
                    ], className="mb-4"),

                    html.Hr(),

                    # ===== 编辑器2: 权重和MAU计算 =====
                    dbc.Row([
                        dbc.Col([
                            html.H6("编辑器2: 权重和MAU计算", className="fw-bold mb-2"),
                            dbc.Alert([
                                html.H6([html.I(className="fas fa-database me-2"), "可用变量池 (点击图标复制)"], className="alert-heading"),
                                html.Hr(),
                                html.Div([
                                    html.Strong("Phase 3 Design Space:", className="text-secondary small"),
                                    html.Div(id="badges-4-2-mau-p3", className="mt-1 mb-2"),
                                    html.Strong("Phase 4.1 Calculated Attributes:", className="text-info small"),
                                    html.Div(id="badges-4-2-mau-p41", className="mt-1 mb-2"),
                                    html.Strong("Phase 4.2 Utility Functions:", className="text-success small"),
                                    html.Div(id="badges-4-2-mau-p42", className="mt-1")
                                ])
                            ], color="light", className="mb-3"),

html.Label("Python代码编辑器:", className="fw-bold"),
                            build_code_editor("editor-weights-mau", height="350px"),
                            
                            dbc.Row([
                                dbc.Col([
                                    dbc.Button([html.I(className="fas fa-check me-2"),"验证代码"], id="btn-validate-weights-mau", color="success", size="sm", className="w-100")
                                ], md=3),
                                dbc.Col([
                                    dbc.Button([html.I(className="fas fa-play me-2"),"测试执行"], id="btn-test-weights-mau", color="info", size="sm", className="w-100")
                                ], md=3),
                                dbc.Col([
                                    dbc.Button([html.I(className="fas fa-save me-2"),"保存代码"], id="btn-save-weights-mau", color="warning", size="sm", className="w-100")
                                ], md=3),
                                dbc.Col(id="weights-mau-validation-status", md=3)
                            ], className="g-2 mt-2"),

                            html.Div(id="weights-mau-test-results", className="mt-3"),
                            html.Div(id="saved-weights-mau-code", className="mt-3"),
                        ])
                    ]),
                ])
            ], className="shadow-sm mb-4")
        ], md=12)
    ]),

    # ===== 数据管理 =====
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("数据管理", className="mb-0")),
                dbc.CardBody([
                    dbc.ButtonGroup([
                        dbc.Button([
                            html.I(className="fas fa-save me-2"),
                            "保存Phase 4数据"
                        ], id="btn-save-phase4", color="success", className="me-2"),
                        dbc.Button([
                            html.I(className="fas fa-upload me-2"),
                            "加载Phase 4数据"
                        ], id="btn-load-phase4", color="info")
                    ]),
                    html.Div(id="phase4-save-status", className="mt-3")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # ===== 导航按钮 =====
    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button("上一步: Phase 3", href="/phase3", color="secondary", outline=True),
                dbc.Button("下一步: Phase 5", href="/phase5", color="primary")
            ], className="w-100")
        ])
    ])
], fluid=True)




# ===== 模板加载回调 =====
@callback(
    [Output("badges-4-1-container", "children"),
     Output("badges-4-2-util-p3", "children"),
     Output("badges-4-2-util-p41", "children"),
     Output("badges-4-2-mau-p3", "children"),
     Output("badges-4-2-mau-p41", "children"),
     Output("badges-4-2-mau-p42", "children")],
    [Input("url", "pathname"),
     Input("btn-save-attr", "n_clicks"),      # 监听 4.1 保存
     Input("btn-save-utility", "n_clicks"),   # 监听 4.2 保存
     Input("btn-load-phase4", "n_clicks"),    # 监听加载
     Input("select-attribute-model", "value"), # 监听 4.1 属性选择
     Input("select-utility-attr", "value")],   # 监听 4.2 属性选择
    prevent_initial_call=False
)
def update_context_badges(pathname, save_attr_clicks, save_util_clicks, load_clicks, 
                          selected_attr_model, selected_util_attr):
    """
    统一刷新所有编程上下文徽章 (修复：4.1/4.2显示标准函数名)
    """
    if pathname != "/phase4":
        return [no_update] * 6

    state = get_state_manager()
    
    # --- 1. 获取 Phase 3 数据 (作为 Input) ---
    p3_vars = []
    p3_snapshot = {}
    
    alternatives = state.load("phase3", "alternatives")
    
    # 安全地提取第一行数据
    first_row = {}
    if alternatives is not None:
        if isinstance(alternatives, pd.DataFrame):
            if not alternatives.empty:
                first_row = alternatives.iloc[0].to_dict()
        elif isinstance(alternatives, list) and len(alternatives) > 0:
            first_row = alternatives[0]
        elif isinstance(alternatives, dict) and 'data' in alternatives and alternatives['data']:
            first_row = alternatives['data'][0]
            
    if first_row:
        p3_vars = [k for k in first_row.keys() if k != 'design_id']
        p3_snapshot = first_row 

    # --- 2. 获取 Phase 4.1 数据 (转换为标准函数名) ---
    p41_funcs = []
    perf_models = state.load("phase4", "perf_models_dict") or {}
    for metric in perf_models.keys():
        # [核心修复] 显示 calculate_xxx 函数名，而非原始属性名
        func_name = f"calculate_{sanitize_name(metric)}"
        p41_funcs.append(func_name)

    # --- 3. 获取 Phase 4.2 效用函数名 ---
    p42_utils = []
    utility_funcs = state.load("phase4", "utility_functions_dict") or {}
    for attr_name in utility_funcs.keys():
        p42_utils.append(f"utility_{sanitize_name(attr_name)}")
    
    # --- 4. 生成基础徽章组件 ---
    badges_p3_input = render_variable_badges(p3_vars, "input", p3_snapshot)
    badges_p41_attr = render_variable_badges(p41_funcs, "attr") # 使用转换后的函数名列表
    badges_p42_util = render_variable_badges(p42_utils, "utility")

    # --- 5. 构造动态函数提示 (保持原逻辑) ---
    hint_4_1 = []
    if selected_attr_model:
        safe_name = sanitize_name(selected_attr_model)
        func_sig = f"def calculate_{safe_name}(**design_vars):"
        hint_4_1 = dbc.Alert([
            html.Div([
                html.I(className="fas fa-exclamation-circle me-2"),
                html.Strong("当前任务："), f"为 '{selected_attr_model}' 编写计算逻辑"
            ]),
            html.Div([
                html.Span("必须定义函数：", className="me-2"),
                html.Code(func_sig, className="bg-white px-2 py-1 border rounded text-dark fw-bold"),
            ], className="mt-2"),
            html.Div("注意：特殊字符已自动转换为下划线，请严格复制上述函数名。", className="small text-muted mt-1")
        ], color="info", className="mb-2 border-info small")

    hint_4_2_util = []
    if selected_util_attr:
        safe_name = sanitize_name(selected_util_attr)
        func_sig = f"def utility_{safe_name}(**design_vars):"
        hint_4_2_util = dbc.Alert([
            html.Div([
                html.I(className="fas fa-exclamation-circle me-2"),
                html.Strong("当前任务："), f"为 '{selected_util_attr}' 定义效用函数"
            ]),
            html.Div([
                html.Span("必须定义函数：", className="me-2"),
                html.Code(func_sig, className="bg-white px-2 py-1 border rounded text-dark fw-bold"),
            ], className="mt-2"),
            html.Div("输入 design_vars 包含 Phase 3 变量和 Phase 4.1 计算属性。", className="small text-muted mt-1")
        ], color="warning", className="mb-2 border-warning small")

    hint_4_2_mau = dbc.Alert([
        html.Div([
            html.I(className="fas fa-info-circle me-2"),
            html.Strong("编程规范："), "MAU计算必须包含以下两部分"
        ]),
        html.Div([
            dbc.Badge("1", color="dark", className="me-1"), " 字典 ", html.Code("weights = {'属性名': 0.5, ...}"),
            html.Br(),
            dbc.Badge("2", color="dark", className="me-1"), " 函数 ", html.Code("def calculate_mau(**design_vars):")
        ], className="mt-2 ms-1")
    ], color="secondary", className="mb-2 small")

    # --- 6. 组装最终输出 ---
    
    # 4.1 容器
    out_4_1 = html.Div([
        hint_4_1 if hint_4_1 else html.Div("请在左侧选择一个属性以查看编程指引...", className="text-muted small mb-2"),
        badges_p3_input
    ])
    
    # 4.2 效用容器
    out_4_2_util_p3 = html.Div([
        hint_4_2_util if hint_4_2_util else html.Div("请选择效用属性...", className="text-muted small mb-2"),
        badges_p3_input
    ])
    
    # 4.2 MAU容器
    out_4_2_mau_p3 = html.Div([
        hint_4_2_mau,
        badges_p3_input
    ])

    return (
        out_4_1,            # badges-4-1-container
        out_4_2_util_p3,    # badges-4-2-util-p3
        badges_p41_attr,    # badges-4-2-util-p41 (现在显示函数名)
        out_4_2_mau_p3,     # badges-4-2-mau-p3
        badges_p41_attr,    # badges-4-2-mau-p41 (现在显示函数名)
        badges_p42_util     # badges-4-2-mau-p42
    )


# =============================================================================
# 4.1 统一属性模型回调
# =============================================================================

# 性能模型模板
# =============================================================================
# 4.1 统一属性模型回调 (修复版)
# =============================================================================

@callback(
    Output("editor-attr-model-code", "value", allow_duplicate=True),
    [Input("select-attribute-model", "value"),  # [核心修复] 这里必须是 Input，才能监听切换
     Input("btn-tmpl-linear", "n_clicks"),
     Input("btn-tmpl-cost", "n_clicks"),
     Input("btn-tmpl-physics", "n_clicks"),
     Input("btn-tmpl-exponential", "n_clicks")],
    [State("phase4-ui-state", "data")],         # [新增] 读取 UI 草稿
    prevent_initial_call=True
)
def update_attr_model_editor(metric, n_lin, n_cost, n_phy, n_exp, ui_state):
    """
    更新属性模型编辑器内容
    触发源: 下拉框切换 OR 模板按钮点击
    策略: 优先恢复草稿 > 数据库保存值 > 默认模板
    """
    from dash import ctx
    
    # 如果没有选属性，或者初始加载，不更新
    if not metric:
        return no_update
        
    triggered_id = ctx.triggered_id
    safe_metric = sanitize_name(metric)
    func_name = f"calculate_{safe_metric}"
    
    # 准备 Phase 3 变量 (用于生成智能模板)
    p3_cols = get_phase3_columns()
    design_vars_objs = [{'name': col, 'unit': ''} for col in p3_cols]

    # --- 场景 1: 切换下拉菜单 (加载逻辑) ---
    if triggered_id == "select-attribute-model":
        # 1.1 尝试恢复草稿 (Draft)
        # 只有当 UI State 中记录的"上次选中项"与当前 metric 一致时，草稿才有效
        # (实际上由于 auto_save 是实时的，只要有草稿就可以读)
        if ui_state and ui_state.get('selected_attribute_model') == metric:
            draft = ui_state.get('draft_attr_code')
            if draft and draft.strip():
                return draft
                
        # 1.2 尝试加载已保存的模型 (Database)
        state = get_state_manager()
        models_dict = state.load("phase4", "perf_models_dict") or {}
        if metric in models_dict:
            return models_dict[metric]
            
        # 1.3 都没有，生成默认基础模板
        return generate_smart_code_template(func_name, design_vars_objs, f"计算 {metric}")

    # --- 场景 2: 点击模板按钮 (覆盖逻辑) ---
    # 注意：点击按钮会直接覆盖当前代码框内容
    
    if triggered_id == "btn-tmpl-linear":
        return generate_smart_code_template(
            func_name, 
            design_vars_objs, 
            f"简单线性模型 - 计算 {metric}"
        )
        
    elif triggered_id == "btn-tmpl-cost":
        code = generate_smart_code_template(func_name, design_vars_objs, "成本累加模型")
        # 智能替换示例逻辑
        code = code.replace(
            "result = 0.0", 
            "result = sum(v for k, v in design_vars.items() if isinstance(v, (int, float))) * 1.0  # 示例"
        )
        return code
        
    elif triggered_id == "btn-tmpl-physics":
        code = generate_smart_code_template(func_name, design_vars_objs, "物理公式模型")
        code = code.replace(
            "# TODO: 使用上述变量计算结果", 
            "# result = 变量A * 变量B / (4 * 3.14)  # 示例"
        )
        return code
        
    elif triggered_id == "btn-tmpl-exponential":
        code = generate_smart_code_template(func_name, design_vars_objs, "指数模型")
        code += "\n    import math\n    # result = 100 * math.exp(-0.1 * design_vars.get('某个变量', 0))"
        return code

    return no_update


# =============================================================================
# 4.2 效用函数回调 (Validation, Testing, Saving)
# =============================================================================
#4.2 验证：validate_utility_code 强制检查函数名。
@callback(
    Output("utility-validation-status", "children"),
    [Input("btn-validate-utility", "n_clicks")],
    [State("editor-utility-functions-code", "value"),
     State("select-utility-attr", "value")],
    prevent_initial_call=True
)
def validate_utility_code(n_clicks, code, attr):
    """验证效用函数代码 (支持清洗后的函数名)"""
    if not n_clicks or not code: return no_update
    if not attr: return dbc.Alert("❌ 请先选择一个属性", color="warning")

    try:
        namespace = {}
        exec(code, namespace)
        
        safe_attr = sanitize_name(attr)
        expected_func_name = f"utility_{safe_attr}"
        
        if expected_func_name not in namespace:
            return dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                f"命名错误: 未找到函数 '{expected_func_name}'", html.Br(),
                f"因为属性名含有特殊字符，必须使用: {expected_func_name}"
            ], color="danger", className="mb-0 small p-2")
            
        if not callable(namespace[expected_func_name]):
             return dbc.Alert(f"❌ '{expected_func_name}' 必须是一个函数", color="danger")

        # [UI修复] 添加时间戳
        import pandas as pd
        time_str = pd.Timestamp.now().strftime("%H:%M:%S")

        return dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"✅ 验证通过: {expected_func_name} ({time_str})"
        ], color="success", className="mb-0 small p-2")
        
    except Exception as e:
        return dbc.Alert(f"❌ 语法错误: {str(e)}", color="danger")
    


@callback(
    Output("utility-test-results", "children"),
    [Input("btn-test-utility", "n_clicks")],
    [State("editor-utility-functions-code", "value"),
     State("select-utility-attr", "value")],
    prevent_initial_call=True
)
def test_utility_execution(n_clicks, code, attr):
    """测试效用函数执行 (支持清洗后的函数名)"""
    if not n_clicks or not code or not attr: return no_update
    try:
        namespace = {}
        exec(code, namespace)
        
        safe_attr = sanitize_name(attr)
        func_name = f"utility_{safe_attr}"
        func = namespace.get(func_name)
        
        if not func: return dbc.Alert(f"未找到函数 {func_name}", color="danger")
        
        # [UI修复] 添加时间戳
        import pandas as pd
        time_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        
        test_vals = [0, 10, 50, 100, 500]
        rows = []
        for val in test_vals:
            res = func(**{attr: val}) 
            style = "text-danger" if res < 0 or res > 1 else "text-success"
            rows.append(html.Tr([html.Td(str(val)), html.Td(f"{res:.4f}", className=style)]))
            
        return html.Div([
            html.Div(f"Test Run: {time_str}", className="text-muted small mb-2 text-end border-bottom"),
            dbc.Table([html.Thead(html.Tr([html.Th(f"输入 ({attr})"), html.Th("效用")])), html.Tbody(rows)], bordered=True, size="sm")
        ])
    except Exception as e:
        return dbc.Alert(f"测试失败: {str(e)}", color="danger")
    


@callback(
    Output("saved-utility-code", "children", allow_duplicate=True),
    [Input("btn-save-utility", "n_clicks")],
    [State("editor-utility-functions-code", "value"),
     State("select-utility-attr", "value")],
    prevent_initial_call=True
)
def save_utility_functions(n_clicks, code, attr):
    """保存效用函数 (支持清洗后的函数名验证)"""
    if not n_clicks or not code or not attr: return no_update
    try:
        namespace = {}
        exec(code, namespace)
        
        # [核心修改]
        safe_attr = sanitize_name(attr)
        if f"utility_{safe_attr}" not in namespace:
            return dbc.Alert(f"函数名不匹配，应为 utility_{safe_attr}", color="danger")

        state = get_state_manager()
        utility_funcs = state.load("phase4", "utility_functions_dict") or {}
        utility_funcs[attr] = code
        state.save("phase4", "utility_functions_dict", utility_funcs)
        
        badges = [dbc.Badge(f"utility_{sanitize_name(k)}", color="success" if k==attr else "info", className="me-2 p-2") for k in utility_funcs.keys()]
        return html.Div([dbc.Alert(f"✅ {attr} 已保存", color="success", className="mb-2 p-2"), html.Div(badges)])
    except Exception as e:
        return dbc.Alert(f"保存失败: {str(e)}", color="danger")
    


# =============================================================================
# 4.2 权重与 MAU 回调 (Validation, Testing, Saving)
# =============================================================================

@callback(
    Output("weights-mau-validation-status", "children"),
    [Input("btn-validate-weights-mau", "n_clicks")],
    [State("editor-weights-mau-code", "value")],
    prevent_initial_call=True
)
def validate_weights_mau_code(n_clicks, code):
    """验证 MAU 代码结构 (修复：移除weights字典强校验，修复pd引用)"""
    if not n_clicks or not code: return no_update
    try:
        namespace = {}
        exec(code, namespace)
        
        # [修改] 只检查核心入口函数，不强制要求 weights 字典
        if "calculate_mau" not in namespace: 
            raise ValueError("缺少 calculate_mau 函数")
        # if "weights" not in namespace: raise ValueError("缺少 weights 字典") # 已移除此行
        
        # [修改] 使用全局 pd，不局部导入
        time_str = pd.Timestamp.now().strftime("%H:%M:%S")
        
        return dbc.Alert(f"✅ 结构验证通过 ({time_str})", color="success", className="mb-0 small p-2")
    except Exception as e:
        return dbc.Alert(f"❌ {str(e)}", color="danger", className="mb-0 small p-2")
    

    

# MAU 全链路测试
@callback(
    Output("weights-mau-test-results", "children"),
    [Input("btn-test-weights-mau", "n_clicks")],
    [State("editor-utility-functions-code", "value"), 
     State("editor-weights-mau-code", "value")],
    prevent_initial_call=True
)
def test_weights_mau_execution(n_clicks, current_utility_code, weights_mau_code):
    """
    测试 MAU 执行 (全链路集成测试 - 修复版)
    [核心修复]：严禁在此函数内部 import pandas，否则会导致 UnboundLocalError
    """
    if not n_clicks or not weights_mau_code: return no_update
    
    try:
        state = get_state_manager()
        
        # 1. 获取 Phase 3 真实数据
        alternatives = state.load("phase3", "alternatives")
        
        # [关键] 健壮的数据获取逻辑 (此时使用全局 pd)
        test_case = {}
        has_data = False
        if alternatives is None: has_data = False
        elif isinstance(alternatives, pd.DataFrame): has_data = not alternatives.empty
        elif isinstance(alternatives, (list, dict)): has_data = bool(alternatives)
            
        if has_data:
            if isinstance(alternatives, list): 
                test_case = alternatives[0]
            elif isinstance(alternatives, dict) and 'data' in alternatives: 
                test_case = alternatives['data'][0]
            elif isinstance(alternatives, pd.DataFrame):
                test_case = alternatives.iloc[0].to_dict()
        
        row_context = {k:v for k,v in test_case.items() if k != 'design_id'}
        
        if not row_context:
            return dbc.Alert("⚠️ Phase 3 无数据，无法进行全链路测试。请先生成设计空间。", color="warning")

        # 2. 构建执行环境
        exec_ctx = {}
        model_logs = []
        
        # 2.1 加载并执行所有 Phase 4.1 属性模型
        perf_models = state.load("phase4", "perf_models_dict") or {}
        for metric, code in perf_models.items():
            try:
                temp_ctx = {}
                exec(code, temp_ctx)
                safe_metric = sanitize_name(metric)
                func_name = f"calculate_{safe_metric}"
                
                if func_name in temp_ctx:
                    func = temp_ctx[func_name]
                    val = func(**row_context)
                    row_context[metric] = val 
                    exec_ctx[func_name] = func 
                    model_logs.append(f"Step 4.1: {metric} = {val:.4f}")
            except Exception as e:
                model_logs.append(f"❌ 4.1 {metric} Error: {e}")

        # 2.2 加载所有 Phase 4.2 效用函数
        utility_funcs = state.load("phase4", "utility_functions_dict") or {}
        for attr, code in utility_funcs.items():
            try:
                exec(code, exec_ctx)
                safe_attr = sanitize_name(attr)
                func_name = f"utility_{safe_attr}"
                
                if func_name in exec_ctx:
                     if attr in row_context:
                         exec_ctx[func_name](**row_context)
            except Exception as e:
                model_logs.append(f"❌ 4.2 {attr} Error: {e}")

        # 2.3 执行 MAU 计算
        exec(weights_mau_code, exec_ctx)
        
        if "calculate_mau" not in exec_ctx:
            return dbc.Alert("❌ 代码中缺少 'calculate_mau' 函数", color="danger")
            
        mau_result = exec_ctx['calculate_mau'](**row_context)
        
        # 3. 生成输出 (使用全局 pd，这里不再 import)
        time_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        return html.Div([
            html.Div(f"Test Run: {time_str}", className="text-muted small mb-2 text-end border-bottom"),
            dbc.Alert(f"✅ MAU 计算结果: {mau_result:.4f} (基于 Phase 3 设计 #0)", color="success"),
            html.Ul([html.Li(log) for log in model_logs], className="small text-muted")
        ])

    except Exception as e:
        import traceback
        return dbc.Alert([
            html.H6("系统执行错误", className="alert-heading"),
            html.Pre(str(e))
        ], color="danger")
   


@callback(
    Output("saved-weights-mau-code", "children", allow_duplicate=True),
    [Input("btn-save-weights-mau", "n_clicks")],
    [State("editor-weights-mau-code", "value")],
    prevent_initial_call=True
)
def save_weights_mau(n_clicks, code):
    """保存 MAU 代码"""
    if not n_clicks or not code: return no_update
    try:
        exec(code, {}) # 简单验证
        state = get_state_manager()
        state.save("phase4", "weights_mau_code", code)
        return dbc.Alert("✅ MAU 模型已保存", color="success", className="mt-2")
    except Exception as e:
        return dbc.Alert(f"保存失败: {str(e)}", color="danger")





# ===== 效用函数和权重配置编辑器 =====

def generate_utility_template():
    """生成效用函数模板 - 根据Phase 1的属性动态生成 (修复：增强DataFrame兼容性)"""
    # 1. 获取数据
    value_attrs = get_value_attributes_from_phase1()
    
    # 2. 防御性处理：再次检查是否为 DataFrame，防止 ValueError
    if isinstance(value_attrs, pd.DataFrame):
        value_attrs = value_attrs.to_dict('records') if not value_attrs.empty else []
    
    # 3. 兜底默认值
    if not value_attrs:
        value_attrs = [
            {"name": "成本", "unit": "M$"},
            {"name": "分辨率", "unit": "m"},
            {"name": "覆盖范围", "unit": "km²"}
        ]

    template = """\"\"\"为每个属性定义效用函数
返回值范围 [0, 1]，0表示最不满意，1表示最满意
\"\"\"

"""

    for attr in value_attrs:
        # 兼容处理非字典数据
        if isinstance(attr, dict):
            attr_name = attr.get("name", "unknown")
        else:
            attr_name = str(attr)
            
        # 生成合法的函数名
        safe_name = sanitize_name(attr_name)
        
        template += f"def utility_{safe_name}(**design_vars):\n"
        template += f'    """\n'
        template += f"    {attr_name}的效用函数\n"
        template += f'    """\n'
        template += f"    value = design_vars.get('{attr_name}', 0)\n"
        template += f"    # TODO: 定义效用函数 (例如: 线性、指数等)\n"
        template += f"    return max(0, min(1, value))  # 确保返回值在[0,1]范围内\n\n"

    return template

# MAU 模板生成 (修改为使用清洗后的函数名)
def generate_weights_mau_template():
    """生成权重和MAU计算模板 (修复：增强DataFrame兼容性，解决 Truth value ambiguous 报错)"""
    # 1. 获取数据
    value_attrs = get_value_attributes_from_phase1()
    
    # 2. 防御性处理：再次检查是否为 DataFrame
    # 这一步至关重要，因为 DataFrame 无法直接进行 `if not df:` 判断
    if isinstance(value_attrs, pd.DataFrame):
        value_attrs = value_attrs.to_dict('records') if not value_attrs.empty else []
    
    # 3. 兜底默认值 (现在 value_attrs 必定是 list，可以安全判断)
    if not value_attrs: 
        value_attrs = [{"name": "Cost"}, {"name": "Performance"}]

    template = """\"\"\"定义权重和多属性效用值(MAU)
MAU = Σ(weight_i × utility_i)
\"\"\"

"""
    # 生成权重字典
    template += "weights = {\n"
    for attr in value_attrs:
        # 兼容处理
        if isinstance(attr, dict):
            attr_name = attr.get('name', 'unknown')
        else:
            attr_name = str(attr)
        template += f"    '{attr_name}': 0.5,\n"
    template += "}\n\n"

    # 生成 MAU 函数
    template += "def calculate_mau(**design_vars):\n"
    template += "    mau = 0\n"
    for attr in value_attrs:
        if isinstance(attr, dict):
            attr_name = attr.get('name', 'unknown')
        else:
            attr_name = str(attr)
            
        # 调用清洗后的效用函数名
        safe_attr = sanitize_name(attr_name)
        template += f"    # {attr_name}\n"
        template += f"    mau += weights['{attr_name}'] * utility_{safe_attr}(**design_vars)\n"
    
    template += "    return round(max(0, min(1, mau)), 4)\n"

    return template


@callback(
    Output("phase4-save-status", "children"),
    [Input("btn-save-phase4", "n_clicks")], 
    [State("select-attribute-model", "value"), # 修正ID
     State("select-utility-attr", "value")], 
    prevent_initial_call=True
)
def save_phase4_all_models(n_clicks, current_attr, current_util):
    """
    保存 Phase 4 UI 状态 (模型代码已在单点保存)
    """
    if not n_clicks:
        return no_update
    
    state = get_state_manager()
    
    # 强制刷新 UI State (保存下拉框的选中状态)
    ui_state = {
        'selected_attribute_model': current_attr,
        'selected_utility_attr': current_util
    }
    state.save("phase4", "ui_state", ui_state)

    return dbc.Alert([
        html.I(className="fas fa-check-circle me-2"),
        "Phase 4 状态已确认保存 (代码修改需点击各模块的'保存'按钮)"
    ], color="success")


@callback(
    [Output("editor-weights-mau-code", "value", allow_duplicate=True),      # 1. 权重代码 (直接注入)
     Output("select-attribute-model", "value", allow_duplicate=True),       # 2. 属性下拉
     Output("select-utility-attr", "value", allow_duplicate=True),          # 3. 效用下拉
     Output("phase4-save-status", "children", allow_duplicate=True),        # 4. 状态提示
     Output("saved-models-list", "children", allow_duplicate=True),         # 5. 4.1 列表
     Output("saved-utility-code", "children", allow_duplicate=True),        # 6. 4.2 列表
     Output("phase4-ui-state", "data", allow_duplicate=True)],              # 7. 同步 UI State
    [Input("btn-load-phase4", "n_clicks"),
     Input("url", "pathname")], 
    prevent_initial_call="initial_duplicate"
)
def load_phase4_data(n_clicks, pathname):
    """
    统一加载 Phase 4 数据 (修复：强制显示 MAU 编辑器代码)
    针对 Editor 2 (MAU)：由于没有下拉菜单触发，必须在此函数中直接赋值。
    """
    from dash import ctx
    
    # 1. 路径校验
    if pathname != "/phase4":
        return tuple([no_update] * 7)

    try:
        state = get_state_manager()
        
        # 2. 从数据库加载核心数据
        weights_code_saved = state.load("phase4", "weights_mau_code")
        perf_models = state.load("phase4", "perf_models_dict") or {} 
        utility_funcs = state.load("phase4", "utility_functions_dict") or {}
        
        # 3. 加载 UI 草稿状态
        ui_state = state.load("phase4", "ui_state") or {}
        
        # === 修复核心：计算 Editor 2 (MAU) 的显示内容 ===
        # 逻辑优先级：UI草稿(未保存的修改) > 数据库存档(已保存) > 默认模板
        draft_mau = ui_state.get('draft_mau_code')
        restored_weights = ""

        if draft_mau and str(draft_mau).strip():
            # 优先恢复用户未保存的草稿
            restored_weights = draft_mau
        elif weights_code_saved and str(weights_code_saved).strip():
            # 其次恢复数据库中的代码
            restored_weights = weights_code_saved
        else:
            # 都没有则生成默认模板 (防止白屏)
            restored_weights = generate_weights_mau_template()
        
        # === 恢复下拉菜单状态 (Editor 1) ===
        restored_attr = ui_state.get('selected_attribute_model')
        restored_util = ui_state.get('selected_utility_attr')
        
        # === 构建视觉反馈 (Badges) ===
        # 4.1 属性模型列表
        attr_badges_list = []
        if perf_models:
            for name in perf_models.keys():
                attr_badges_list.append(dbc.Badge([html.I(className="fas fa-check me-1"), name], color="success", className="me-1 mb-1 p-2"))
        saved_attr_ui = html.Div([html.Div("✅ 已保存的属性模型:", className="text-muted small mb-2"), html.Div(attr_badges_list, className="d-flex flex-wrap")]) if perf_models else html.Div("暂无已保存模型", className="text-muted small")

        # 4.2 效用函数列表
        util_badges_list = []
        if utility_funcs:
            for name in utility_funcs.keys():
                util_badges_list.append(dbc.Badge([html.I(className="fas fa-check me-1"), name], color="info", className="me-1 mb-1 p-2"))
        saved_util_ui = html.Div([html.Div("✅ 已保存的效用函数:", className="text-muted small mb-2 mt-2"), html.Div(util_badges_list, className="d-flex flex-wrap")]) if utility_funcs else html.Div("暂无已保存效用", className="text-muted small mt-2")

        # === 状态提示 ===
        status_msg = no_update
        if ctx.triggered_id == "btn-load-phase4":
            status_msg = dbc.Alert([html.I(className="fas fa-check-circle me-2"), "数据与草稿已加载"], color="success", duration=4000)
        
        # 返回值 (顺序严格对应 Output)
        return (
            restored_weights,   # 1. editor-weights-mau-code (这里直接返回字符串，不再是 no_update)
            restored_attr,      # 2. select-attribute-model
            restored_util,      # 3. select-utility-attr
            status_msg,         # 4. status
            saved_attr_ui,      # 5. badges
            saved_util_ui,      # 6. badges
            ui_state            # 7. ui_state
        )

    except Exception as e:
        import traceback
        print(f"Phase 4 Loading Error: {e}")
        traceback.print_exc()
        
        # 发生错误时的兜底
        fallback_template = generate_weights_mau_template()
        error_msg = dbc.Alert(f"加载数据时发生错误: {str(e)}", color="danger")
        
        return (
            fallback_template, # 1. 至少显示模板
            no_update, no_update, 
            error_msg,         # 4. 显示错误提示
            no_update, no_update, no_update
        )

    

# ===== 性能属性下拉菜单初始化 =====
@callback(
    Output("select-attribute-model", "options"),
    [Input("url", "pathname")],
    prevent_initial_call=False
)
def initialize_perf_metric_dropdown(pathname):
    """初始化属性模型下拉菜单（4.1），从Phase 1动态读取，保持与4.2数据一致"""
    if pathname != "/phase4":
        return []

    # 从Phase 1读取属性列表（Value Attributes）
    attributes = get_value_attributes_from_phase1()

    # 生成下拉菜单选项
    options = []
    for attr in attributes:
        # 处理从Phase 1读取的数据
        if isinstance(attr, dict):
            # 获取用户定义的变量名、描述和单位
            attr_key = attr.get("name", "unknown")
            attr_desc = attr.get("description", "")
            attr_unit = attr.get("unit", "")
        else:
            # 兼容处理非字典数据
            attr_key = str(attr)
            attr_desc = ""
            attr_unit = ""

        # 构建显示标签：变量名 (描述, 单位)
        info_parts = []
        if attr_desc:
            info_parts.append(attr_desc)
        if attr_unit:
            info_parts.append(f"单位: {attr_unit}")
        
        if info_parts:
            label = f"{attr_key} ({', '.join(info_parts)})"
        else:
            label = attr_key

        options.append({
            "label": label,
            "value": attr_key
        })

    return options if options else [{"label": "未检测到属性 (请在Phase 1定义)", "value": ""}]


# ===== 效用属性下拉菜单初始化 =====
@callback(
    Output("select-utility-attr", "options"),
    [Input("url", "pathname")],
    prevent_initial_call=False
)
def initialize_utility_attr_dropdown(pathname):
    """初始化效用属性下拉菜单，从Phase 1动态读取"""
    if pathname != "/phase4":
        return []

    # 从Phase 1读取价值属性
    value_attrs = get_value_attributes_from_phase1()

    # 生成下拉菜单选项
    options = []
    for attr in value_attrs:
        # 处理从Phase 1读取的数据
        if isinstance(attr, dict):
            attr_key = attr.get("name", "unknown")
            attr_desc = attr.get("description", "")
            attr_unit = attr.get("unit", "")
        else:
            # 兼容非字典情况
            attr_key = str(attr)
            attr_desc = ""
            attr_unit = ""

        # 构建显示标签：变量名 (描述, 单位: xxx)
        info_parts = []
        if attr_desc:
            info_parts.append(attr_desc)
        if attr_unit:
            info_parts.append(f"单位: {attr_unit}")
        
        if info_parts:
            label = f"{attr_key} ({', '.join(info_parts)})"
        else:
            label = attr_key

        options.append({
            "label": label,
            "value": attr_key
        })

    return options if options else [{"label": "未检测到效用属性", "value": ""}]



@callback(
    Output("editor-utility-functions-code", "value", allow_duplicate=True), 
    [Input("select-utility-attr", "value"),
     Input("btn-utility-linear", "n_clicks"),
     Input("btn-utility-exponential", "n_clicks"),
     Input("btn-utility-concave", "n_clicks"),
     Input("btn-utility-convex", "n_clicks"),
     Input("btn-utility-scurve", "n_clicks")],
    prevent_initial_call=True
)
def update_utility_editor(selected_attr, linear_clicks, exp_clicks, concave_clicks, convex_clicks, scurve_clicks):
    """处理效用函数编辑器交互 (支持函数名清洗)"""
    from dash import ctx, no_update
    from utils.state_manager import get_state_manager

    if not selected_attr:
        return no_update

    triggered_id = ctx.triggered_id if ctx.triggered else "select-utility-attr"
    
    # [核心修改] 计算清洗后的函数名
    safe_attr = sanitize_name(selected_attr)

    if triggered_id == "select-utility-attr":
        state = get_state_manager()
        utility_funcs = state.load("phase4", "utility_functions_dict") or {}
        if selected_attr in utility_funcs:
            return utility_funcs[selected_attr]
        
        return f"""def utility_{safe_attr}(**design_vars):
    \"\"\"
    {selected_attr} 的默认效用函数
    \"\"\"
    val = design_vars.get('{selected_attr}', 0.0)
    # TODO: 映射逻辑
    return 0.5
"""

    if triggered_id and triggered_id.startswith("btn-utility-"):
        common_header = f"""def utility_{safe_attr}(**design_vars):
    \"\"\"
    {selected_attr} 的效用函数
    \"\"\"
    # 1. 获取属性值
    val = design_vars.get('{selected_attr}', 0.0)
    
    # 2. 定义目标/阈值
    target_min = 0.0
    target_max = 100.0
"""
        # ... (Templates dict 保持不变，使用 common_header) ...
        templates = {
            "btn-utility-linear": f"""{common_header}
    # 3. 线性映射 [0, 1]
    if val <= target_min: return 0.0
    if val >= target_max: return 1.0
    return (val - target_min) / (target_max - target_min)
""",
            # ... 其他模板省略，只需确保使用新的 common_header
        }
        return templates.get(triggered_id, no_update)

    return no_update


@callback(
    [Output("phase4-save-status", "children", allow_duplicate=True),
     Output("phase4-ui-state", "data", allow_duplicate=True)], 
    [Input("select-attribute-model", "value"),
     Input("select-utility-attr", "value"),
     Input("editor-attr-model-code", "value"),
     Input("editor-utility-functions-code", "value"),
     Input("editor-weights-mau-code", "value")],
    prevent_initial_call=True
)
def auto_save_phase4_ui(attr_select, util_select, 
                        attr_code, util_code, mau_code):
    """
    UI 草稿层自动保存 (修复版)
    [核心修复]: 增加 None 值检查。
    防止页面初始化时，组件尚未加载完成传来的 None 覆盖掉数据库中已有的草稿。
    """
    from dash import ctx
    # 1. 基础校验
    if not ctx.triggered:
        return no_update, no_update
        
    state = get_state_manager()
    # 2. 读取旧状态
    current_ui = state.load('phase4', 'ui_state') or {}
    
    # 3. 准备更新 (仅更新非 None 的字段)
    updates = {
        'timestamp': pd.Timestamp.now().isoformat()
    }
    
    if attr_select is not None:
        updates['selected_attribute_model'] = attr_select
    if util_select is not None:
        updates['selected_utility_attr'] = util_select
        
    # [关键] 仅当编辑器值不为 None 时才保存
    # 注意：空字符串 "" 是有效值 (代表用户清空了编辑器)，应该保存
    # 但 None 代表组件未就绪，绝不能保存
    if attr_code is not None:
        updates['draft_attr_code'] = attr_code
    if util_code is not None:
        updates['draft_util_code'] = util_code
    if mau_code is not None:
        updates['draft_mau_code'] = mau_code
        
    current_ui.update(updates)
    
    # 4. 执行保存
    state.save('phase4', 'ui_state', current_ui)
    
    return no_update, current_ui


# =============================================================================
# 4.1 统一属性模型回调  - 替代原有的 Cost/Perf 分离逻辑
# =============================================================================

@callback(
    Output("attr-validation-status", "children"),
    [Input("btn-validate-attr", "n_clicks")],
    [State("editor-attr-model-code", "value"),
     State("select-attribute-model", "value")],
    prevent_initial_call=True
)
def validate_attr_code(n_clicks, code, metric):
    """验证统一属性模型代码 (支持清洗后的函数名)"""
    if not code or not n_clicks or not metric:
        return no_update

    try:
        namespace = {}
        exec(code, namespace)

        safe_metric = sanitize_name(metric)
        func_name = f"calculate_{safe_metric}"
        
        if func_name not in namespace:
            raise ValueError(f"代码中必须定义函数: {func_name}\n(系统已将 '{metric}' 转换为合法标识符)")
        
        func = namespace[func_name]
        if not callable(func):
             raise ValueError(f"{func_name} 必须是一个函数")

        # [UI修复] 添加时间戳，确保内容变化触发刷新效果
        import pandas as pd
        time_str = pd.Timestamp.now().strftime("%H:%M:%S")
        
        return dbc.Alert([
            html.I(className="fas fa-check-circle me-2 text-success"),
            f"✅ 语法验证通过 ({time_str})"
        ], color="success", className="mb-0 small p-2")

    except Exception as e:
        return dbc.Alert([
            html.I(className="fas fa-exclamation-circle me-2 text-danger"),
            f"❌ {str(e)}"
        ], color="danger", className="mb-0 small p-2")



@callback(
    [Output("saved-models-list", "children", allow_duplicate=True),
     Output("phase4-perf-models-store", "data", allow_duplicate=True)],
    [Input("btn-save-attr", "n_clicks")],
    [State("editor-attr-model-code", "value"),
     State("select-attribute-model", "value")],
    prevent_initial_call=True
)
def save_attr_model(n_clicks, code, metric):
    """保存统一属性模型 (Key保持原始名，代码使用清洗名)"""
    if not code or not n_clicks or not metric:
        return no_update

    try:
        namespace = {}
        exec(code, namespace)
        
        # [核心修改] 验证清洗后的函数名
        safe_metric = sanitize_name(metric)
        func_name = f"calculate_{safe_metric}"
        
        if func_name not in namespace:
            return dbc.Alert(f"保存失败：代码中未找到函数 '{func_name}'", color="danger"), no_update

        state = get_state_manager()
        models_dict = state.load("phase4", "perf_models_dict") or {}
        
        # Key 使用原始 metric 名称 (UI显示用)，Value 是代码
        models_dict[metric] = code
        state.save("phase4", "perf_models_dict", models_dict)

        saved_badges = []
        for name in models_dict.keys():
            color = "success" if name == metric else "secondary"
            icon = "fas fa-check-circle" if name == metric else "fas fa-check"
            saved_badges.append(
                dbc.Badge([html.I(className=f"{icon} me-1"), name], color=color, className="me-1 mb-1 p-2")
            )

        success_ui = html.Div([
            dbc.Alert(f"✅ {metric} 模型已保存", color="success", duration=3000, className="mb-2 p-2"),
            html.Div(saved_badges)
        ])
        
        return success_ui, models_dict

    except Exception as e:
        return dbc.Alert(f"保存异常: {str(e)}", color="danger"), no_update
    

# 测试test_attr_execution_real_data 使用 Phase 3 真实数据。
@callback(
    Output("attr-test-results", "children", allow_duplicate=True),
    [Input("btn-test-attr", "n_clicks")],
    [State("editor-attr-model-code", "value"),
     State("select-attribute-model", "value")],
    prevent_initial_call=True
)
def test_attr_execution_real_data(n_clicks, code, metric):
    """
    使用 Phase 3 真实数据测试属性模型代码 (修复版)
    [修复]：删除局部 'import pandas as pd'，解决 UnboundLocalError
    """
    if not code or not n_clicks:
        return no_update
    
    try:
        # 1. 编译用户代码
        namespace = {}
        exec(code, namespace)
        
        safe_metric = sanitize_name(metric)
        func_name = f"calculate_{safe_metric}"
        
        if func_name not in namespace:
            return dbc.Alert(f"❌ 找不到函数: {func_name}，请检查函数定义。", color="danger")
            
        test_func = namespace[func_name]
        
        # 2. 获取 Phase 3 真实数据
        state = get_state_manager()
        alternatives = state.load("phase3", "alternatives")
        
        # [关键] 健壮的数据有效性检查 (此时使用全局 pd)
        has_data = False
        if alternatives is None:
            has_data = False
        elif isinstance(alternatives, pd.DataFrame):
            has_data = not alternatives.empty
        elif isinstance(alternatives, (list, dict)):
            has_data = bool(alternatives)
            
        test_cases = []
        if has_data:
            data_list = []
            if isinstance(alternatives, list):
                data_list = alternatives
            elif isinstance(alternatives, dict) and 'data' in alternatives:
                data_list = alternatives['data']
            elif isinstance(alternatives, pd.DataFrame):
                data_list = alternatives.to_dict('records')
            
            if data_list:
                indices = sorted(list(set([i for i in [0, len(data_list)//2, len(data_list)-1] if 0 <= i < len(data_list)])))
                for i in indices:
                    row = data_list[i]
                    if isinstance(row, dict):
                        case_inputs = {k:v for k,v in row.items() if k != 'design_id'}
                        test_cases.append((f"设计 #{i}", case_inputs))
        
        if not test_cases:
             test_cases.append(("Dummy Data", {"轨道高度": 500, "天线直径": 2.5}))
             warn_msg = "⚠️ Phase 3 无数据，使用虚拟数据测试。"
        else:
             warn_msg = None

        # 3. 准备 UI 输出 (使用全局 pd)
        time_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        
        results_ui = [
            html.Div(
                [html.I(className="fas fa-clock me-1"), f"Test Run: {time_str}"], 
                className="text-muted small mb-2 text-end border-bottom pb-1"
            )
        ]
        
        if warn_msg:
            results_ui.append(html.Div(warn_msg, className="text-warning small mb-2"))
            
        table_rows = []
        for label, inputs in test_cases:
            try:
                res = test_func(**inputs)
                val_display = f"{res:.4f}" if isinstance(res, (int, float)) else str(res)
                input_keys = list(inputs.keys())[:3]
                input_summary = ", ".join([f"{k}={inputs[k]}" for k in input_keys]) + ("..." if len(inputs)>3 else "")

                table_rows.append(html.Tr([
                    html.Td(label), 
                    html.Td(html.Small(input_summary, className="text-muted font-monospace")), 
                    html.Td(html.Strong(val_display, className="text-primary"))
                ]))
            except Exception as e:
                table_rows.append(html.Tr([
                    html.Td(label), 
                    html.Td("Error"), 
                    html.Td(str(e), className="text-danger")
                ]))

        return html.Div([
            *results_ui,
            dbc.Table(
                [html.Thead(html.Tr([html.Th("测试用例"), html.Th("输入摘要"), html.Th("计算结果")])), html.Tbody(table_rows)],
                bordered=True, size="sm", hover=True
            )
        ])

    except Exception as e:
        import traceback
        return dbc.Alert(f"代码执行错误: {str(e)}", color="danger")