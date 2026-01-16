"""
Phase 2: 物理架构与接口定义
"""

from dash import html, dcc, callback, Input, Output, State, no_update, ALL, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import networkx as nx
import sys
import os
import dash # 确保导入 dash
import pandas as pd # 导入 pandas 处理时间戳

# 路径设置，确保能导入 utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.state_manager import get_state_manager

layout = dbc.Container([
    # 组件和接口数据存储
    dcc.Store(id='components-store', data=[]),
    dcc.Store(id='interfaces-store', data=[]),
    # 自动加载触发器 (配合 Dashboard)
    dcc.Store(id='phase2-auto-load-trigger', data=None),
    dcc.Store(id='phase2-ui-state', data={}),

    html.H2([
        html.I(className="fas fa-project-diagram me-2 text-success"),
        "Phase 2: 物理架构与接口定义"
    ], className="mb-4"),

    dbc.Alert([
        html.I(className="fas fa-info-circle me-2"),
        "N²图（N-squared diagram）是系统工程核心工具，用于可视化组件间的接口关系。对角线上是组件，非对角线单元格表示接口。"
    ], color="info", className="mb-4"),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("2.1 组件管理", className="mb-0")),
                dbc.CardBody([
                    dbc.Label("组件名称"),
                    dbc.Input(id="input-component-name", placeholder="例如：天线子系统", className="mb-2"),

                    dbc.Label("组件类型"),
                    dbc.Select(
                        id="select-component-type",
                        options=[
                            {"label": "硬件 (Hardware)", "value": "hardware"},
                            {"label": "软件 (Software)", "value": "software"},
                            {"label": "人员 (Personnel)", "value": "personnel"},
                            {"label": "设施 (Facility)", "value": "facility"}
                        ],
                        value="hardware",
                        className="mb-2"
                    ),

                    dbc.Label("描述"),
                    dbc.Textarea(id="input-component-desc", placeholder="简要描述组件功能...",
                               rows=2, className="mb-3"),

                    dbc.Button([
                        html.I(className="fas fa-plus me-2"),
                        "添加组件"
                    ], id="btn-add-component", color="success", className="w-100 mb-3"),

                    html.Hr(),
                    html.H6("已添加的组件"),
                    html.Div(id="components-list", style={'maxHeight': '300px', 'overflowY': 'auto'})
                ])
            ], className="shadow-sm mb-4")
        ], md=6),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("2.2 接口管理", className="mb-0")),
                dbc.CardBody([
                    dbc.Label("源组件"),
                    dbc.Select(id="select-interface-from", className="mb-2"),

                    dbc.Label("目标组件"),
                    dbc.Select(id="select-interface-to", className="mb-2"),

                    dbc.Label("接口类型"),
                    dbc.Select(
                        id="select-interface-type",
                        options=[
                            {"label": "数据 (Data)", "value": "data"},
                            {"label": "能量 (Energy)", "value": "energy"},
                            {"label": "物理 (Physical)", "value": "physical"},
                            {"label": "控制 (Control)", "value": "control"},
                            {"label": "信息 (Information)", "value": "information"}
                        ],
                        value="data",
                        className="mb-2"
                    ),

                    dbc.Label("接口描述"),
                    dbc.Input(id="input-interface-desc", placeholder="例如：传输雷达信号数据",
                            className="mb-3"),

                    dbc.Button([
                        html.I(className="fas fa-link me-2"),
                        "添加接口"
                    ], id="btn-add-interface", color="info", className="w-100 mb-3"),

                    html.Hr(),
                    html.H6("已添加的接口"),
                    html.Div(id="interfaces-list", style={'maxHeight': '300px', 'overflowY': 'auto'})
                ])
            ], className="shadow-sm mb-4")
        ], md=6)
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("2.3 N²图交互式可视化", className="mb-0 d-inline"),
                    dbc.Badge(id="badge-n2-status", color="secondary", className="float-end")
                ]),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-lightbulb me-2"),
                        html.Strong("使用说明: "),
                        "点击N²图中的单元格查看接口详情。对角线显示组件名称，非对角线单元格显示接口数量。"
                    ], color="light", className="mb-3"),

                    dcc.Graph(id="n2-diagram", figure={},
                             config={'displayModeBar': True, 'displaylogo': False},
                             style={'height': '600px'}),

                    dbc.ButtonGroup([
                        dbc.Button([
                            html.I(className="fas fa-sync me-2"),
                            "刷新N²图"
                        ], id="btn-generate-n2", color="primary"),
                        dbc.Button([
                            html.I(className="fas fa-download me-2"),
                            "导出为PNG"
                        ], id="btn-export-n2", color="secondary", outline=True)
                    ], className="mt-3")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # 接口详情模态框
    dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("接口详情")),
        dbc.ModalBody(id="modal-interface-details"),
        dbc.ModalFooter(
            dbc.Button("关闭", id="btn-close-modal", className="ms-auto", n_clicks=0)
        )
    ], id="modal-interface", is_open=False, size="lg"),

    # 数据管理
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("数据管理", className="mb-0")),
                dbc.CardBody([
                    dbc.ButtonGroup([
                        dbc.Button([
                            html.I(className="fas fa-save me-2"),
                            "保存Phase 2数据"
                        ], id="btn-save-phase2", color="success", className="me-2"),
                        dbc.Button([
                            html.I(className="fas fa-upload me-2"),
                            "加载Phase 2数据"
                        ], id="btn-load-phase2", color="info")
                    ]),
                    html.Div(id="phase2-save-status", className="mt-3")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button("上一步: Phase 1", href="/phase1", color="secondary", outline=True),
                dbc.Button("下一步: Phase 3", href="/phase3", color="primary")
            ], className="w-100")
        ])
    ])
], fluid=True)

# ==================== 回调函数 ====================

@callback(
    [Output('components-store', 'data'),
     Output('input-component-name', 'value'),
     Output('input-component-desc', 'value')],
    Input('btn-add-component', 'n_clicks'),
    [State('input-component-name', 'value'),
     State('select-component-type', 'value'),
     State('input-component-desc', 'value'),
     State('components-store', 'data')],
    prevent_initial_call=True
)
def add_component(n_clicks, name, comp_type, description, current_components):
    """添加组件到列表并实时保存"""
    if not n_clicks or not name:
        return no_update, no_update, no_update

    # 确保列表已初始化
    if current_components is None:
        current_components = []

    # 检查重名
    if any(c.get('name') == name for c in current_components):
        return no_update, no_update, no_update

    new_component = {
        'id': len(current_components) + 1,
        'name': name,
        'type': comp_type,
        'description': description or ''
    }

    updated_components = current_components + [new_component]

    # === 实时保存 ===
    state = get_state_manager()
    state.save('phase2', 'components', updated_components)
    print(f"✅ Phase 2: 组件 '{name}' 已添加并保存")
    # ===============

    return updated_components, '', ''


@callback(
    Output('components-list', 'children'),
    Input('components-store', 'data')
)
def display_components(components):
    """显示组件列表"""
    if not components:
        return dbc.Alert("尚未添加组件", color="light", className="text-center")

    # 组件类型图标映射
    type_icons = {
        'hardware': 'fas fa-microchip',
        'software': 'fas fa-code',
        'personnel': 'fas fa-user',
        'facility': 'fas fa-building'
    }

    # 组件类型中文映射
    type_labels = {
        'hardware': '硬件',
        'software': '软件',
        'personnel': '人员',
        'facility': '设施'
    }

    items = []
    for idx, comp in enumerate(components):
        # 如果数据没有id字段，自动生成
        comp_id = comp.get('id', idx + 1)

        items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.I(className=f"{type_icons.get(comp['type'], 'fas fa-cube')} me-2 text-primary"),
                    html.Strong(comp['name']),
                    dbc.Badge(type_labels.get(comp['type'], comp['type']),
                            color="secondary", className="ms-2"),
                    html.Br(),
                    html.Small(comp['description'], className="text-muted")
                ], className="d-inline-block", style={'width': '80%'}),
                dbc.Button([
                    html.I(className="fas fa-trash")
                ], id={'type': 'btn-delete-component', 'index': comp_id},
                   size="sm", color="danger", outline=True, className="float-end")
            ])
        )

    return dbc.ListGroup(items)


@callback(
    Output('components-store', 'data', allow_duplicate=True),
    Input({'type': 'btn-delete-component', 'index': ALL}, 'n_clicks'),
    State('components-store', 'data'),
    prevent_initial_call=True
)
def delete_component(n_clicks_list, current_components):
    """删除指定组件并实时保存"""
    from dash import ctx

    if not any(n_clicks_list):
        return no_update

    triggered = ctx.triggered_id
    if triggered and triggered['type'] == 'btn-delete-component':
        comp_id = triggered['index']
        if current_components:
            updated_components = [c for c in current_components if c.get('id') != comp_id]
            
            # === 实时保存 ===
            state = get_state_manager()
            state.save('phase2', 'components', updated_components)
            # ===============
            
            return updated_components

    return no_update


# 2. 接口管理回调 (升级版：同时处理 Options 和 Value 恢复)
@callback(
    [Output('select-interface-from', 'options'),
     Output('select-interface-to', 'options'),
     Output('select-interface-from', 'value'), 
     Output('select-interface-to', 'value')],
    [Input('components-store', 'data'),
     Input('phase2-ui-state', 'data')] 
)
def update_interface_selects(components, ui_state):
    """根据已有组件更新接口选择框，并尝试恢复选中的值"""
    # 1. 生成 Options
    if not components:
        options = []
    else:
        options = [{'label': c['name'], 'value': c['name']} for c in components]
    
    # 2. 尝试恢复 Values
    val_from = no_update
    val_to = no_update
    
    # 只有当 ui_state 存在时才尝试恢复
    if ui_state:
        saved_from = ui_state.get('interface_from')
        saved_to = ui_state.get('interface_to')
        
        # 验证值是否有效（防止组件被删后，草稿里还留着旧ID导致报错）
        valid_values = {o['value'] for o in options}
        
        if saved_from and saved_from in valid_values:
            val_from = saved_from
        
        if saved_to and saved_to in valid_values:
            val_to = saved_to
            
    return options, options, val_from, val_to


# 添加接口回调
@callback(
    [Output('interfaces-store', 'data'),
     Output('input-interface-desc', 'value')],
    Input('btn-add-interface', 'n_clicks'),
    [State('select-interface-from', 'value'),
     State('select-interface-to', 'value'),
     State('select-interface-type', 'value'),
     State('input-interface-desc', 'value'),
     State('interfaces-store', 'data')],
    prevent_initial_call=True
)
def add_interface(n_clicks, from_comp, to_comp, if_type, description, current_interfaces):
    """添加接口到列表并实时保存"""
    if not n_clicks or not from_comp or not to_comp:
        return no_update, no_update

    # 不允许自己到自己的接口
    if from_comp == to_comp:
        return no_update, no_update

    if current_interfaces is None:
        current_interfaces = []

    new_interface = {
        'id': len(current_interfaces) + 1,
        'from': from_comp,
        'to': to_comp,
        'type': if_type,
        'description': description or ''
    }

    updated_interfaces = current_interfaces + [new_interface]

    # === 实时保存 ===
    state = get_state_manager()
    state.save('phase2', 'interfaces', updated_interfaces)
    print(f"✅ Phase 2: 接口 {from_comp}->{to_comp} 已添加并保存")


    return updated_interfaces, ''

@callback(
    Output('interfaces-list', 'children'),
    Input('interfaces-store', 'data')
)
def display_interfaces(interfaces):
    """显示接口列表（防御性处理缺失id字段）"""
    if not interfaces:
        return dbc.Alert("尚未添加接口", color="light", className="text-center")

    # 接口类型颜色映射
    type_colors = {
        'data': 'primary',
        'energy': 'warning',
        'physical': 'secondary',
        'control': 'info',
        'information': 'success'
    }

    # 接口类型中文映射
    type_labels = {
        'data': '数据',
        'energy': '能量',
        'physical': '物理',
        'control': '控制',
        'information': '信息'
    }

    items = []
    for idx, intf in enumerate(interfaces):
        # 如果数据没有id字段，自动生成
        intf_id = intf.get('id', idx + 1)

        items.append(
            dbc.ListGroupItem([
                html.Div([
                    html.I(className="fas fa-arrow-right me-2 text-success"),
                    html.Strong(f"{intf['from']} → {intf['to']}"),
                    dbc.Badge(type_labels.get(intf['type'], intf['type']),
                            color=type_colors.get(intf['type'], 'secondary'),
                            className="ms-2"),
                    html.Br(),
                    html.Small(intf['description'], className="text-muted")
                ], className="d-inline-block", style={'width': '80%'}),
                dbc.Button([
                    html.I(className="fas fa-trash")
                ], id={'type': 'btn-delete-interface', 'index': intf_id},
                   size="sm", color="danger", outline=True, className="float-end")
            ])
        )

    return dbc.ListGroup(items)

# 删除接口回调
@callback(
    Output('interfaces-store', 'data', allow_duplicate=True),
    Input({'type': 'btn-delete-interface', 'index': ALL}, 'n_clicks'),
    State('interfaces-store', 'data'),
    prevent_initial_call=True
)
def delete_interface(n_clicks_list, current_interfaces):
    """删除指定接口并实时保存"""
    from dash import ctx

    if not any(n_clicks_list):
        return no_update

    triggered = ctx.triggered_id
    if triggered and triggered['type'] == 'btn-delete-interface':
        intf_id = triggered['index']
        if current_interfaces:
            updated_interfaces = [i for i in current_interfaces if i.get('id') != intf_id]
            
            # === 实时保存 ===
            state = get_state_manager()
            state.save('phase2', 'interfaces', updated_interfaces)


            return updated_interfaces

    return no_update

# 3. N²图生成回调
@callback(
    [Output('n2-diagram', 'figure'),
     Output('badge-n2-status', 'children')],
    Input('btn-generate-n2', 'n_clicks'),
    [State('components-store', 'data'),
     State('interfaces-store', 'data')],
    prevent_initial_call=True
)
def generate_n2_diagram(n_clicks, components, interfaces):
    """生成交互式N²矩阵图"""
    if not n_clicks:
        return no_update, no_update

    if not components:
        # 空图提示
        fig = go.Figure()
        fig.add_annotation(
            text="请先添加组件！",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20, color="red")
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=600
        )
        return fig, "无数据"

    # 创建N²矩阵
    n = len(components)
    comp_names = [c['name'] for c in components]

    # 初始化接口计数矩阵
    import numpy as np
    matrix = np.zeros((n, n), dtype=int)

    # 统计每对组件间的接口数量
    for intf in interfaces:
        try:
            from_idx = comp_names.index(intf['from'])
            to_idx = comp_names.index(intf['to'])
            matrix[from_idx, to_idx] += 1
        except ValueError:
            continue  # 忽略无效接口

    # 创建热图文本（对角线显示组件名，非对角线显示接口数）
    text_matrix = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                # 对角线：显示组件名称
                row.append(f"<b>{comp_names[i]}</b>")
            else:
                # 非对角线：显示接口数量
                if matrix[i, j] > 0:
                    row.append(f"{matrix[i, j]}")
                else:
                    row.append("")
        text_matrix.append(row)

    # 创建热图
    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        x=comp_names,
        y=comp_names,
        colorscale=[
            [0, 'rgb(255,255,255)'],      # 0: 白色（无接口）
            [0.5, 'rgb(173,216,230)'],    # 中等：浅蓝色
            [1, 'rgb(65,105,225)']        # 最多：深蓝色
        ],
        showscale=True,
        colorbar=dict(title="接口数量"),
        text=text_matrix,
        texttemplate='%{text}',
        textfont={"size": 12},
        hovertemplate='从 %{y}<br>到 %{x}<br>接口数: %{z}<extra></extra>'
    ))

    # 添加对角线高亮
    shapes = []
    for i in range(n):
        shapes.append(dict(
            type='rect',
            x0=i-0.5, y0=i-0.5,
            x1=i+0.5, y1=i+0.5,
            line=dict(color='red', width=2)
        ))

    fig.update_layout(
        title=dict(
            text=f"N²图 (N-squared Diagram)<br><sub>{n}个组件 | {len(interfaces)}个接口</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis={
            'side': 'top',
            'tickangle': -45,
            'title': '目标组件 (To)'
        },
        yaxis={
            'title': '源组件 (From)',
            'autorange': 'reversed'  # Y轴反转，使矩阵符合惯例
        },
        height=600,
        margin=dict(l=150, r=100, t=150, b=50),
        shapes=shapes
    )

    status_badge = f"{n}组件 | {len(interfaces)}接口"
    return fig, status_badge

# 4. N²图点击事件 - 显示接口详情
@callback(
    [Output('modal-interface', 'is_open'),
     Output('modal-interface-details', 'children')],
    [Input('n2-diagram', 'clickData'),
     Input('btn-close-modal', 'n_clicks')],
    [State('modal-interface', 'is_open'),
     State('interfaces-store', 'data')],
    prevent_initial_call=True
)
def toggle_interface_modal(click_data, n_close, is_open, interfaces):
    """点击N²图单元格显示接口详情"""
    if ctx.triggered_id == 'btn-close-modal':
        return False, ""

    if not click_data or not interfaces:
        return no_update, no_update

    # 提取点击的单元格坐标
    point = click_data['points'][0]
    from_comp = point['y']
    to_comp = point['x']

    # 对角线单元格（组件自身），不显示模态框
    if from_comp == to_comp:
        return no_update, no_update

    # 查找该单元格的所有接口
    cell_interfaces = [
        intf for intf in interfaces
        if intf['from'] == from_comp and intf['to'] == to_comp
    ]

    if not cell_interfaces:
        content = dbc.Alert([
            html.I(className="fas fa-info-circle me-2"),
            f"从 <strong>{from_comp}</strong> 到 <strong>{to_comp}</strong> 没有接口。"
        ], color="light")
        return True, content

    # 显示接口列表
    type_labels = {
        'data': '数据',
        'energy': '能量',
        'physical': '物理',
        'control': '控制',
        'information': '信息'
    }

    type_colors = {
        'data': 'primary',
        'energy': 'warning',
        'physical': 'secondary',
        'control': 'info',
        'information': 'success'
    }

    items = []
    for intf in cell_interfaces:
        items.append(
            dbc.Card([
                dbc.CardBody([
                    html.H5([
                        html.I(className="fas fa-link me-2"),
                        f"{intf['from']} → {intf['to']}"
                    ]),
                    html.Hr(),
                    html.P([
                        html.Strong("接口类型: "),
                        dbc.Badge(type_labels.get(intf['type'], intf['type']),
                                color=type_colors.get(intf['type'], 'secondary'))
                    ]),
                    html.P([
                        html.Strong("描述: "),
                        intf['description'] or "无描述"
                    ])
                ])
            ], className="mb-2")
        )

    content = html.Div([
        dbc.Alert([
            html.I(className="fas fa-arrow-right me-2"),
            f"从 <strong>{from_comp}</strong> 到 <strong>{to_comp}</strong> 的接口 (共{len(cell_interfaces)}个)："
        ], color="info"),
        html.Div(items)
    ])

    return True, content

# 5. 实时自动保存 UI 草稿状态
@callback(
    [Output('phase2-save-status', 'children', allow_duplicate=True),
     Output('phase2-ui-state', 'data', allow_duplicate=True)], # 同步 Store
    [Input('input-component-name', 'value'),
     Input('select-component-type', 'value'),
     Input('input-component-desc', 'value'),
     Input('select-interface-from', 'value'),
     Input('select-interface-to', 'value'),
     Input('select-interface-type', 'value'),
     Input('input-interface-desc', 'value')],
    prevent_initial_call=True
)
def auto_save_phase2_ui(comp_name, comp_type, comp_desc, 
                       intf_from, intf_to, intf_type, intf_desc):
    """当输入框内容变化时自动保存 UI 草稿状态 (防空值 + 双写)"""
    from dash import ctx
    
    if not ctx.triggered:
        return no_update, no_update
        
    state = get_state_manager()
    
    # 读取现有状态
    current_ui = state.load('phase2', 'ui_state') or {}
    
    # 构造更新
    updates = {}
    
    # Phase 2 的输入框通常没有初始化为空的情况（默认是 None 或 ""），
    # 但为了统一风格，我们只更新非 None 的值
    if comp_name is not None: updates['component_name'] = comp_name
    if comp_type is not None: updates['component_type'] = comp_type
    if comp_desc is not None: updates['component_desc'] = comp_desc
    if intf_from is not None: updates['interface_from'] = intf_from
    if intf_to is not None: updates['interface_to'] = intf_to
    if intf_type is not None: updates['interface_type'] = intf_type
    if intf_desc is not None: updates['interface_desc'] = intf_desc
    
    updates['timestamp'] = pd.Timestamp.now().isoformat()
    
    current_ui.update(updates)
    
    # 双写保存
    state.save('phase2', 'ui_state', current_ui)
    
    return no_update, current_ui

# 6. 数据管理回调：加载/保存
@callback(
    [Output('components-store', 'data', allow_duplicate=True),
     Output('interfaces-store', 'data', allow_duplicate=True),
     Output('phase2-save-status', 'children', allow_duplicate=True),
     Output('input-component-name', 'value', allow_duplicate=True),
     Output('select-component-type', 'value', allow_duplicate=True),
     Output('input-component-desc', 'value', allow_duplicate=True),
     Output('select-interface-type', 'value', allow_duplicate=True),
     Output('input-interface-desc', 'value', allow_duplicate=True),
     Output('phase2-ui-state', 'data', allow_duplicate=True)], 
    [Input('btn-load-phase2', 'n_clicks'),
     Input('phase2-auto-load-trigger', 'data'),
     Input('url', 'pathname')], 
    prevent_initial_call='initial_duplicate'  
)
def load_phase2_data(n_clicks, auto_trigger, pathname):
    """从StateManager加载Phase 2数据并恢复UI状态"""
    from dash import ctx

    # 1. 触发逻辑校验
    triggered_by_button = ctx.triggered_id == 'btn-load-phase2' and n_clicks
    triggered_by_dashboard = ctx.triggered_id == 'phase2-auto-load-trigger' and auto_trigger is not None
    triggered_by_url = ctx.triggered_id == 'url' and pathname == '/phase2'
    
    # 兼容页面刷新时的自动触发 (pathname check)
    is_initial_load = not ctx.triggered_id and pathname == '/phase2'

    if not (triggered_by_button or triggered_by_dashboard or triggered_by_url or is_initial_load):
        return [no_update] * 9

    try:    
        state = get_state_manager()
        
        # 2. 加载数据
        components = state.load('phase2', 'components') or []
        interfaces = state.load('phase2', 'interfaces') or []
        ui_state = state.load('phase2', 'ui_state') or {}

        # 3. 准备恢复的值
        r_comp_name = ui_state.get('component_name', '')
        r_comp_type = ui_state.get('component_type', 'hardware')
        r_comp_desc = ui_state.get('component_desc', '')
        # 接口选择框的值 (from/to) 不在这里恢复，而是通过 ui_state 传给 update_interface_selects
        r_intf_type = ui_state.get('interface_type', 'data')
        r_intf_desc = ui_state.get('interface_desc', '')

        # 4. 状态提示
        status_msg = no_update
        if triggered_by_button:
            count_c = len(components)
            count_i = len(interfaces)
            if count_c > 0 or count_i > 0:
                status_msg = dbc.Alert([html.I(className="fas fa-check-circle me-2"), f"已加载：{count_c}组件, {count_i}接口"], color="success")
            else:
                status_msg = dbc.Alert("未找到保存的数据", color="warning")

        return (
            components, 
            interfaces, 
            status_msg,
            r_comp_name,
            r_comp_type,
            r_comp_desc,
            r_intf_type,
            r_intf_desc,
            ui_state # 注入 Store
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = dbc.Alert(f"加载异常: {str(e)}", color="danger")
        return [no_update] * 8 + [error_msg]
    

# 7. 手动保存回调
@callback(
    Output('phase2-save-status', 'children', allow_duplicate=True), # 添加 allow_duplicate
    Input('btn-save-phase2', 'n_clicks'),
    [State('components-store', 'data'),
     State('interfaces-store', 'data'),
     State('input-component-name', 'value'),
     State('select-component-type', 'value'),
     State('input-component-desc', 'value'),
     State('select-interface-from', 'value'),
     State('select-interface-to', 'value'),
     State('select-interface-type', 'value'),
     State('input-interface-desc', 'value'),
     # [新增] 读取 Store 以保证一致性
     State('phase2-ui-state', 'data')],
    prevent_initial_call=True
)
def save_phase2_data(n_clicks, components, interfaces,
                    comp_name, comp_type, comp_desc,
                    intf_from, intf_to, intf_type, intf_desc, current_ui_state):
    """保存 Phase 2 所有数据 (列表 + UI草稿状态)"""
    if not n_clicks:
        return no_update

    state = get_state_manager()

    # 1. 保存核心数据
    state.save('phase2', 'components', components)
    state.save('phase2', 'interfaces', interfaces)

    # 2. 保存 UI 状态
    # 优先使用 realtime 传入的值，回退到 store
    ui_state = current_ui_state or {}
    
    updates = {
        'component_name': comp_name,
        'component_type': comp_type,
        'component_desc': comp_desc,
        'interface_from': intf_from,
        'interface_to': intf_to,
        'interface_type': intf_type,
        'interface_desc': intf_desc,
        'timestamp': pd.Timestamp.now().isoformat()
    }
    ui_state.update(updates)
    
    state.save('phase2', 'ui_state', ui_state)

    return dbc.Alert([
        html.I(className="fas fa-check-circle me-2"),
        f"Phase 2数据已保存: {len(components or [])}个组件, {len(interfaces or [])}个接口 + 填写草稿"
    ], color="success")