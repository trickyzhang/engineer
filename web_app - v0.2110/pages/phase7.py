"""
Phase 7: 权衡空间探索
"""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.state_manager import get_state_manager

layout = dbc.Container([
    # 仅当Phase 7页面渲染时触发，替代全局URL触发
    dcc.Interval(id='phase7-autoloader', interval=500, max_intervals=1),

    # 全局刷选状态存储 (P0-3)
    dcc.Store(id='global-selection-store', data={'selected_ids': []}),

    #Phase 6 数据存储组件
    dcc.Store(id='phase6-feasible-store', data=[]),
    
    # Phase 7 核心数据存储
    dcc.Store(id='pareto-designs-store', data=[]),

    html.H2([
        html.I(className="fas fa-chart-scatter me-2 text-info"),
        "Phase 7: 权衡空间探索"
    ], className="mb-4"),

    # 视图配置
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.1 视图配置 (ViewDataMapper)", className="mb-0")),
                dbc.CardBody([
                    dbc.Label("视图名称"),
                    dbc.Input(id="input-view-name", placeholder="例如：cost_vs_resolution", className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("X轴字段"),
                            dbc.Select(id="select-x-field", className="mb-2")
                        ], md=6),
                        dbc.Col([
                            dbc.Label("Y轴字段"),
                            dbc.Select(id="select-y-field", className="mb-2")
                        ], md=6)
                    ]),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("颜色字段"),
                            dbc.Select(id="select-color-field", className="mb-2")
                        ], md=6),
                        dbc.Col([
                            dbc.Label("尺寸字段"),
                            dbc.Select(id="select-size-field", className="mb-2")
                        ], md=6)
                    ]),

                    dbc.Button("创建视图", id="btn-create-view", color="primary", className="mt-2"),

                    html.Hr(),

                    dbc.Label("已创建的视图"),
                    html.Div(id="views-list", children=[
                        dbc.Alert("尚未创建视图", color="light")
                    ])
                ])
            ], className="shadow-sm mb-4")
        ], md=12),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.2 Pareto优化配置", className="mb-0")),
                dbc.CardBody([
                    dbc.Label("选择优化目标"),
                    dbc.Checklist(
                        id="checklist-objectives",
                        options=[],
                        value=[],
                        className="mb-3"
                    ),

                    dbc.Label("优化方向"),
                    html.Div(id="objectives-directions"),

                    dbc.Label("ε-容差"),
                    dbc.Input(id="input-epsilon", type="number", value=0.0, min=0, max=0.1, step=0.01, className="mb-3"),

                    # [FIX] ID修正: 将 'btn-find-pareto' 改为 'btn-run-pareto' 以匹配回调函数
                    dbc.Button("识别Pareto前沿", id="btn-run-pareto", color="success")
                ])
            ], className="shadow-sm mb-4")
        ], md=12),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.3 可视化选项", className="mb-0")),
                dbc.CardBody([
                    dbc.Checklist(
                        id="checklist-viz-options",
                        options=[
                            {"label": "高亮Pareto前沿", "value": "pareto"},
                            {"label": "显示网格", "value": "grid"},
                            {"label": "显示图例", "value": "legend"},
                            {"label": "交互式悬停", "value": "hover"}
                        ],
                        value=["pareto", "grid", "legend", "hover"],
                        className="mb-3"
                    ),

                    dbc.Label("图表类型"),
                    dbc.RadioItems(
                        id="radio-chart-type",
                        options=[
                            {"label": "散点图", "value": "scatter"},
                            {"label": "平行坐标图", "value": "parallel"},
                            {"label": "多视图联动", "value": "brushing"}
                        ],
                        value="scatter",
                        className="mb-3"
                    ),

                    dbc.Button("更新图表", id="btn-update-chart", color="info")
                ])
            ], className="shadow-sm mb-4")
        ], md=12)
    ]),

    # 主要可视化区域
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader([
                    html.H5("7.4 权衡空间可视化", className="mb-0 d-inline"),
                    dbc.ButtonGroup([
                        dbc.Button([html.I(className="fas fa-download")], id="btn-download-chart", color="secondary", size="sm", outline=True),
                        dbc.Button([html.I(className="fas fa-expand")], id="btn-fullscreen", color="secondary", size="sm", outline=True)
                    ], className="float-end")
                ]),
                dbc.CardBody([
                    dcc.Graph(
                        id="tradespace-plot",
                        figure={},
                        config={
                            'displayModeBar': True,
                            'displaylogo': False,
                            'modeBarButtonsToRemove': ['lasso2d']
                        },
                        style={'height': '600px'}
                    )
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # P2-9: 3D权衡空间可视化
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.4.1 3D权衡空间可视化 (P2-9)", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "使用3D散点图展示三个关键指标之间的权衡关系，支持交互式旋转和缩放"
                    ], color="info", className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("🔵 X轴指标"),
                            dbc.Select(
                                id='select-3d-x-axis',
                                options=[
                                    {'label': '总成本 (M$)', 'value': 'cost_total'},
                                    {'label': '覆盖范围 (°)', 'value': 'perf_coverage'},
                                    {'label': '分辨率 (m)', 'value': 'perf_resolution'},
                                    {'label': 'MAU效用值', 'value': 'MAU'},
                                    {'label': '发射功率 (W)', 'value': 'transmit_power'},
                                    {'label': '性价比', 'value': 'cost_effectiveness'}
                                ],
                                value='cost_total',
                                className="mb-3"
                            ),
                        ], md=4),

                        dbc.Col([
                            dbc.Label("🟢 Y轴指标"),
                            dbc.Select(
                                id='select-3d-y-axis',
                                options=[
                                    {'label': '总成本 (M$)', 'value': 'cost_total'},
                                    {'label': '覆盖范围 (°)', 'value': 'perf_coverage'},
                                    {'label': '分辨率 (m)', 'value': 'perf_resolution'},
                                    {'label': 'MAU效用值', 'value': 'MAU'},
                                    {'label': '发射功率 (W)', 'value': 'transmit_power'},
                                    {'label': '性价比', 'value': 'cost_effectiveness'}
                                ],
                                value='perf_coverage',
                                className="mb-3"
                            ),
                        ], md=4),

                        dbc.Col([
                            dbc.Label("🔴 Z轴指标"),
                            dbc.Select(
                                id='select-3d-z-axis',
                                options=[
                                    {'label': '总成本 (M$)', 'value': 'cost_total'},
                                    {'label': '覆盖范围 (°)', 'value': 'perf_coverage'},
                                    {'label': '分辨率 (m)', 'value': 'perf_resolution'},
                                    {'label': 'MAU效用值', 'value': 'MAU'},
                                    {'label': '发射功率 (W)', 'value': 'transmit_power'},
                                    {'label': '性价比', 'value': 'cost_effectiveness'}
                                ],
                                value='MAU',
                                className="mb-3"
                            ),
                        ], md=4)
                    ]),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("颜色编码"),
                            dbc.Select(
                                id='select-3d-color',
                                options=[
                                    {'label': 'MAU效用值', 'value': 'MAU'},
                                    {'label': '总成本 (M$)', 'value': 'cost_total'},
                                    {'label': '覆盖范围 (°)', 'value': 'perf_coverage'},
                                    {'label': '分辨率 (m)', 'value': 'perf_resolution'},
                                    {'label': '性价比', 'value': 'cost_effectiveness'}
                                ],
                                value='MAU',
                                className="mb-3"
                            ),
                        ], md=6),

                        dbc.Col([
                            dbc.Label("数据来源"),
                            dbc.RadioItems(
                                id='radio-3d-data-source',
                                options=[
                                    {'label': 'Pareto最优设计', 'value': 'pareto'},
                                    {'label': '所有可行设计', 'value': 'feasible'},
                                    {'label': '所有设计（含不可行）', 'value': 'all'}
                                ],
                                value='pareto',
                                className="mb-3"
                            ),
                        ], md=6)
                    ]),

                    dbc.Button([
                        html.I(className="fas fa-cube me-2"),
                        "生成3D权衡空间图"
                    ], id='btn-generate-3d-tradespace', color="primary", className="w-100 mb-3"),

                    dcc.Graph(
                        id='3d-tradespace-plot',
                        figure={},
                        config={'displayModeBar': True},
                        style={'height': '700px'}
                    )
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # 散点图矩阵
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.5 散点图矩阵 (SPLOM)", className="mb-0")),
                dbc.CardBody([
                    dbc.Label("选择维度（最多6个）"),
                    dbc.Checklist(id="checklist-splom-dims", options=[], value=[], className="mb-3"),
                    dbc.Button("生成SPLOM", id="btn-generate-splom", color="primary", className="mb-3"),
                    dcc.Graph(id="splom-plot", figure={}, config={'displayModeBar': True})
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # 平行坐标图
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.6 平行坐标图 (Parallel Coordinates)", className="mb-0")),
                dbc.CardBody([
                    dbc.Label("选择维度（建议7-10个）"),
                    dbc.Checklist(id="checklist-pcp-dims", options=[], value=[], className="mb-3"),

                    dbc.Label("颜色编码"),
                    dbc.Select(id="select-pcp-color", className="mb-3"),

                    dbc.Button("生成平行坐标图", id="btn-generate-pcp", color="primary", className="mb-3"),
                    dcc.Graph(id="pcp-plot", figure={}, config={'displayModeBar': True}, style={'height': '500px'})
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # Pareto前沿统计
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.7 Pareto前沿分析", className="mb-0")),
                dbc.CardBody([
                    # 回调 run_pareto_analysis 输出容器 'pareto-result-display'
                    html.Div(id="pareto-result-display", className="mb-3"),
                    
                    html.Div(id="pareto-stats", children=[
                        dbc.Table([
                            html.Thead([html.Tr([html.Th("指标"), html.Th("值")])]),
                            html.Tbody([
                                html.Tr([html.Td("Pareto最优设计数量"), html.Td("-", id="stat-pareto-count")]),
                                html.Tr([html.Td("占总设计比例"), html.Td("-", id="stat-pareto-ratio")]),
                                html.Tr([html.Td("支配层级"), html.Td("-", id="stat-dominance-layers")])
                            ])
                        ], bordered=True, striped=True)
                    ])
                ])
            ], className="shadow-sm mb-4")
        ], md=12),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("7.8 设计空间覆盖", className="mb-0")),
                dbc.CardBody([
                    dcc.Graph(id="coverage-plot", figure={}, config={'displayModeBar': False}, style={'height': '200px'})
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
                            "保存Phase 7数据"
                        ], id="btn-save-phase7", color="success", className="me-2"),
                        dbc.Button([
                            html.I(className="fas fa-upload me-2"),
                            "加载Phase 7数据"
                        ], id="btn-load-phase7", color="info")
                    ]),
                    html.Div(id="phase7-save-status", className="mt-3")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button("上一步: Phase 6", href="/phase6", color="secondary", outline=True),
                dbc.Button("下一步: Phase 8", href="/phase8", color="primary")
            ], className="w-100")
        ])
    ])
], fluid=True)


# ==================== 回调函数 ====================

# 更新2D权衡图
@callback(
    Output('tradespace-plot', 'figure'), 
    [Input('select-x-field', 'value'),
     Input('select-y-field', 'value'),
     Input('select-color-field', 'value'),
     Input('select-size-field', 'value'),
     Input('phase6-feasible-store', 'data'),
     Input('global-selection-store', 'data')]
)
def update_tradeoff_plot(x_field, y_field, color_field, size_field, feasible_data, selection_data):
    """更新2D散点图"""
    if not feasible_data or not x_field or not y_field:
        fig = go.Figure()
        fig.update_layout(
            title="请选择X轴和Y轴字段以生成图表",
            xaxis={'visible': False}, yaxis={'visible': False},
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig

    try:
        import pandas as pd
        import plotly.express as px
        
        # 1. 准备数据
        df = pd.DataFrame(feasible_data)
        
        # 处理全局选择状态
        selected_ids = selection_data.get('selected_ids', []) if selection_data else []
        df['selected'] = df['design_id'].apply(lambda x: 'Selected' if x in selected_ids else 'Normal')
        
        # 2. 生成图表
        color_arg = color_field if color_field else None
        size_arg = size_field if size_field else None
        
        fig = px.scatter(
            df, 
            x=x_field, 
            y=y_field,
            color=color_arg,
            size=size_arg,
            hover_data=['design_id', 'cost_total', 'MAU'],
            title=f"2D权衡分析: {x_field} vs {y_field}",
            template="plotly_white",
            opacity=0.7
        )
        
        # 高亮选中点
        if selected_ids:
            selected_df = df[df['design_id'].isin(selected_ids)]
            if not selected_df.empty:
                fig.add_trace(go.Scatter(
                    x=selected_df[x_field],
                    y=selected_df[y_field],
                    mode='markers',
                    marker=dict(symbol='circle-open', size=15, color='red', line=dict(width=2)),
                    name='已选中',
                    showlegend=False
                ))

        fig.update_layout(
            height=600,
            hovermode='closest',
            margin=dict(l=20, r=20, t=50, b=20)
        )

        return fig

    except Exception as e:
        import traceback
        print(f"生成2D权衡图失败: {e}")
        return go.Figure()

# P0-2功能：散点图矩阵 (SPLOM) - 维度填充
@callback(
    Output('checklist-splom-dims', 'options'),
    Input('tradespace-plot', 'figure')  # 当主图表更新时触发
)
def populate_splom_dimensions(figure):
    """填充SPLOM维度选项"""
    try:
        import pandas as pd

        state = get_state_manager()
        pareto_designs = state.load('phase7', 'pareto_designs')

        # 如果没有Pareto设计，尝试加载可行设计
        if not pareto_designs:
            pareto_designs = state.load('phase6', 'feasible_designs')

        if not pareto_designs:
            return []
            
        if isinstance(pareto_designs, list):
            pareto_designs = pd.DataFrame(pareto_designs)

        # 提取数值型列作为可选维度
        numeric_cols = pareto_designs.select_dtypes(include=['float64', 'int64']).columns.tolist()
        excluded = ['design_id', 'feasible', 'kills']
        numeric_cols = [col for col in numeric_cols if col not in excluded]

        label_map = {
            'cost_total': '总成本 (M$)',
            'perf_coverage': '覆盖范围 (°)',
            'perf_resolution': '分辨率 (m)',
            'transmit_power': '发射功率 (W)',
            'MAU': 'MAU效用值',
            'orbit_altitude': '轨道高度 (km)',
            'antenna_diameter': '天线直径 (m)',
            'frequency_band': '频段编码'
        }

        options = [
            {'label': label_map.get(col, col), 'value': col}
            for col in numeric_cols[:10]  # 限制最多10个选项
        ]

        return options

    except Exception as e:
        print(f"填充SPLOM维度失败: {e}")
        return []

# 生成SPLOM图表
@callback(
    Output('splom-plot', 'figure'),
    Input('btn-generate-splom', 'n_clicks'),
    State('checklist-splom-dims', 'value'),
    prevent_initial_call=True
)
def generate_splom(n_clicks, selected_dims):
    """生成散点图矩阵 (SPLOM)"""
    if not n_clicks or not selected_dims:
        return go.Figure()

    try:
        import pandas as pd
        import plotly.graph_objects as go

        state = get_state_manager()
        pareto_designs = state.load('phase7', 'pareto_designs')

        if not pareto_designs:
            pareto_designs = state.load('phase6', 'feasible_designs')

        if not pareto_designs:
            return go.Figure()
            
        if isinstance(pareto_designs, list):
            pareto_designs = pd.DataFrame(pareto_designs)

        if len(selected_dims) > 6:
            selected_dims = selected_dims[:6]

        plot_data = pareto_designs[selected_dims].copy()

        label_map = {
            'cost_total': '总成本', 'perf_coverage': '覆盖',
            'perf_resolution': '分辨率', 'transmit_power': '功率',
            'MAU': 'MAU', 'orbit_altitude': '高度',
            'antenna_diameter': '天线', 'frequency_band': '频段'
        }

        dimensions = [
            dict(label=label_map.get(dim, dim), values=plot_data[dim])
            for dim in selected_dims
        ]

        color_col = 'MAU' if 'MAU' in pareto_designs.columns else None

        fig = go.Figure(data=go.Splom(
            dimensions=dimensions,
            marker=dict(
                size=5,
                color=pareto_designs[color_col] if color_col else None,
                colorscale='Viridis',
                showscale=bool(color_col),
                line=dict(width=0.5, color='rgba(0,0,0,0.2)')
            ),
            diagonal_visible=False,
            showupperhalf=False
        ))

        fig.update_layout(
            title="散点图矩阵 (SPLOM)",
            height=150 * len(selected_dims) + 100,
            width=150 * len(selected_dims) + 100,
            hovermode='closest',
            dragmode='select'
        )

        return fig

    except Exception as e:
        print(f"生成SPLOM失败: {e}")
        return go.Figure()

# P0-3功能：全局刷选 (Global Brushing) 
@callback(
    Output('global-selection-store', 'data'),
    [Input('splom-plot', 'selectedData'),
     Input('tradespace-plot', 'selectedData')],
    prevent_initial_call=True
)
def update_global_selection(splom_selection, tradespace_selection):
    """更新全局选择状态"""
    from dash import ctx
    triggered_id = ctx.triggered_id
    selected_ids = []

    if triggered_id == 'splom-plot' and splom_selection:
        if 'points' in splom_selection:
            selected_ids = [p.get('pointIndex', p.get('pointNumber', -1)) for p in splom_selection['points']]
    elif triggered_id == 'tradespace-plot' and tradespace_selection:
        if 'points' in tradespace_selection:
            selected_ids = [p.get('pointIndex', p.get('pointNumber', -1)) for p in tradespace_selection['points']]

    selected_ids = [idx for idx in selected_ids if idx >= 0]
    return {'selected_ids': selected_ids, 'source': triggered_id}

@callback(
    Output('splom-plot', 'figure', allow_duplicate=True),
    Input('global-selection-store', 'data'),
    State('splom-plot', 'figure'),
    State('checklist-splom-dims', 'value'),
    prevent_initial_call=True
)
def highlight_splom_selection(selection_data, current_figure, selected_dims):
    """在SPLOM中高亮显示"""
    if not selection_data or not current_figure:
        return no_update
    # 简化逻辑
    return no_update 

@callback(
    Output('tradespace-plot', 'figure', allow_duplicate=True),
    Input('global-selection-store', 'data'),
    State('tradespace-plot', 'figure'),
    prevent_initial_call=True
)
def highlight_tradespace_selection(selection_data, current_figure):
    """在主散点图中高亮显示"""
    return no_update

# 添加选择统计显示
@callback(
    Output('pareto-stats', 'children', allow_duplicate=True),
    Input('global-selection-store', 'data'),
    prevent_initial_call=True
)
def update_selection_stats(selection_data):
    """更新选择统计信息"""
    if not selection_data:
        return html.P("当前无选择", className="text-muted")

    selected_ids = selection_data.get('selected_ids', [])
    source = selection_data.get('source', '未知')

    if not selected_ids:
        return html.P("当前无选择", className="text-muted")

    return dbc.Alert([
        html.H6([html.I(className="fas fa-hand-pointer me-2"), "全局刷选激活"], className="alert-heading"),
        html.Hr(),
        html.P([
            html.Strong("选中数量: "), f"{len(selected_ids)}", html.Br(),
            html.Strong("来源: "), source
        ]),
        dbc.Button([html.I(className="fas fa-times me-2"), "清除"], id="btn-clear-selection", size="sm", color="secondary")
    ], color="info")

@callback(
    Output('global-selection-store', 'data', allow_duplicate=True),
    Input('btn-clear-selection', 'n_clicks'),
    prevent_initial_call=True
)
def clear_global_selection(n_clicks):
    if n_clicks: return {'selected_ids': [], 'source': 'manual_clear'}
    return no_update

# P1-3功能：平行坐标图维度填充
@callback(
    [Output('checklist-pcp-dims', 'options'),
     Output('select-pcp-color', 'options')],
    Input('tradespace-plot', 'figure')
)
def populate_pcp_dimensions(figure):
    """填充PCP维度选项"""
    opts = populate_splom_dimensions(figure)
    return opts, opts

# 生成平行坐标图
@callback(
    Output('pcp-plot', 'figure'),
    Input('btn-generate-pcp', 'n_clicks'),
    [State('checklist-pcp-dims', 'value'),
     State('select-pcp-color', 'value')],
    prevent_initial_call=True
)
def generate_parallel_coordinates(n_clicks, selected_dims, color_metric):
    """生成平行坐标图"""
    if not n_clicks or not selected_dims:
        return go.Figure()

    try:
        import pandas as pd
        state = get_state_manager()
        pareto_designs = state.load('phase7', 'pareto_designs')
        
        if not pareto_designs:
            pareto_designs = state.load('phase6', 'feasible_designs')
            
        if not pareto_designs:
            return go.Figure()
            
        if isinstance(pareto_designs, list):
            pareto_designs = pd.DataFrame(pareto_designs)

        if len(selected_dims) > 10: selected_dims = selected_dims[:10]
        
        plot_data = pareto_designs[selected_dims].copy()
        
        dimensions = []
        for dim in selected_dims:
            dimensions.append(dict(
                label=dim,
                values=plot_data[dim],
                range=[plot_data[dim].min(), plot_data[dim].max()]
            ))

        fig = go.Figure(data=go.Parcoords(
            line=dict(
                color=pareto_designs[color_metric] if color_metric else 'blue',
                colorscale='Viridis' if color_metric else None,
                showscale=bool(color_metric)
            ),
            dimensions=dimensions
        ))
        
        fig.update_layout(title="平行坐标图", height=500)
        return fig

    except Exception as e:
        print(f"PCP生成失败: {e}")
        return go.Figure()

# ========== P2-9: 3D权衡空间可视化回调 ==========

@callback(
    Output('3d-tradespace-plot', 'figure'),
    Input('btn-generate-3d-tradespace', 'n_clicks'),
    [State('select-3d-x-axis', 'value'),
     State('select-3d-y-axis', 'value'),
     State('select-3d-z-axis', 'value'),
     State('select-3d-color', 'value'),
     State('radio-3d-data-source', 'value')],
    prevent_initial_call=True
)
def generate_3d_tradespace(n_clicks, x_axis, y_axis, z_axis, color_metric, data_source):
    """生成3D权衡空间可视化"""
    if not n_clicks:
        return go.Figure()

    try:
        import pandas as pd
        state = get_state_manager()

        if data_source == 'pareto':
            data = state.load('phase7', 'pareto_designs')
            label = 'Pareto设计'
        elif data_source == 'feasible':
            data = state.load('phase6', 'feasible_designs')
            label = '可行设计'
        else:
            data = state.load('phase5', 'unified_results')
            label = '所有设计'

        if not data:
            return go.Figure()
            
        if isinstance(data, list):
            data = pd.DataFrame(data)

        required = [x_axis, y_axis, z_axis, color_metric]
        if not all(col in data.columns for col in required):
            return go.Figure()

        fig = go.Figure(data=[go.Scatter3d(
            x=data[x_axis],
            y=data[y_axis],
            z=data[z_axis],
            mode='markers',
            marker=dict(
                size=5,
                color=data[color_metric],
                colorscale='Viridis',
                colorbar=dict(title=color_metric),
                opacity=0.8
            ),
            text=data.index,
            hovertemplate=f'{x_axis}: %{{x}}<br>{y_axis}: %{{y}}<br>{z_axis}: %{{z}}<extra></extra>'
        )])

        fig.update_layout(
            title=f"3D权衡空间 ({label})",
            scene=dict(xaxis_title=x_axis, yaxis_title=y_axis, zaxis_title=z_axis),
            height=700
        )
        return fig

    except Exception as e:
        print(f"3D图生成失败: {e}")
        return go.Figure()


# ===== 1. 自动保存 UI 状态 =====
@callback(
    Output('phase7-save-status', 'children', allow_duplicate=True),
    [Input('input-view-name', 'value'),
     Input('select-x-field', 'value'),
     Input('select-y-field', 'value'),
     Input('select-color-field', 'value'),
     Input('select-size-field', 'value'),
     Input('checklist-objectives', 'value'),
     Input('input-epsilon', 'value'),
     Input('checklist-viz-options', 'value'),
     Input('radio-chart-type', 'value'),
     Input('select-3d-x-axis', 'value'),
     Input('select-3d-y-axis', 'value'),
     Input('select-3d-z-axis', 'value'),
     Input('select-3d-color', 'value'),
     Input('radio-3d-data-source', 'value'),
     Input('checklist-splom-dims', 'value'),
     Input('checklist-pcp-dims', 'value'),
     Input('select-pcp-color', 'value')],
    prevent_initial_call=True
)
def auto_save_phase7_ui(view_name, x_axis, y_axis, color_field, size_field, 
                       objectives, epsilon, viz_opts, chart_type,
                       x3d, y3d, z3d, c3d, src3d, splom_dims, pcp_dims, pcp_color):
    """
    自动保存所有视图配置控件的状态
    """
    from dash import ctx
    if not ctx.triggered: return no_update
    
    state = get_state_manager()
    current_ui = state.load('phase7', 'ui_state') or {}
    
    current_ui.update({
        'view_name': view_name,
        'x_axis': x_axis, 'y_axis': y_axis,
        'color_field': color_field, 'size_field': size_field,
        'pareto_objectives': objectives, 'epsilon': epsilon,
        'viz_options': viz_opts, 'chart_type': chart_type,
        'x_axis_3d': x3d, 'y_axis_3d': y3d, 'z_axis_3d': z3d, 
        'color_field_3d': c3d, 'data_source_3d': src3d,
        'splom_dims': splom_dims, 'pcp_dims': pcp_dims, 'pcp_color': pcp_color
    })
    
    state.save('phase7', 'ui_state', current_ui)
    return no_update

# ===== 2. 手动保存 Phase 7 数据 =====
@callback(
    Output('phase7-save-status', 'children', allow_duplicate=True),
    Input('btn-save-phase7', 'n_clicks'),
    [State('pareto-designs-store', 'data'),
     State('input-view-name', 'value'),
     State('select-x-field', 'value'),
     State('select-y-field', 'value'),
     State('select-color-field', 'value'),
     State('select-size-field', 'value'),
     State('checklist-objectives', 'value'),
     State('input-epsilon', 'value'),
     State('checklist-viz-options', 'value'),
     State('radio-chart-type', 'value'),
     State('select-3d-x-axis', 'value'),
     State('select-3d-y-axis', 'value'),
     State('select-3d-z-axis', 'value'),
     State('select-3d-color', 'value'),
     State('radio-3d-data-source', 'value'),
     State('checklist-splom-dims', 'value'),
     State('checklist-pcp-dims', 'value'),
     State('select-pcp-color', 'value')],
    prevent_initial_call=True
)
def save_phase7_data(n_clicks, pareto_data, view_name, x_axis, y_axis, color_field, size_field,
                    objectives, epsilon, viz_opts, chart_type,
                    x3d, y3d, z3d, c3d, src3d, splom_dims, pcp_dims, pcp_color):
    """
    手动保存 Phase 7 所有数据
    """
    if not n_clicks: return no_update
    
    state = get_state_manager()
    
    # 1. 保存 Core Data (如果有)
    if pareto_data:
        state.save('phase7', 'pareto_designs', pareto_data)
        
    # 2. 保存 UI State
    ui_state = {
        'view_name': view_name,
        'x_axis': x_axis, 'y_axis': y_axis,
        'color_field': color_field, 'size_field': size_field,
        'pareto_objectives': objectives, 'epsilon': epsilon,
        'viz_options': viz_opts, 'chart_type': chart_type,
        'x_axis_3d': x3d, 'y_axis_3d': y3d, 'z_axis_3d': z3d, 
        'color_field_3d': c3d, 'data_source_3d': src3d,
        'splom_dims': splom_dims, 'pcp_dims': pcp_dims, 'pcp_color': pcp_color
    }
    state.save('phase7', 'ui_state', ui_state)
    
    return dbc.Alert([
        html.I(className="fas fa-check-circle me-2"),
        "Phase 7 数据与视图配置已保存"
    ], color="success")



@callback(
    [Output('pareto-result-display', 'children'),
     Output('pareto-designs-store', 'data', allow_duplicate=True)],
    [Input('btn-run-pareto', 'n_clicks')],
    [State('checklist-objectives', 'value'),
     State('input-epsilon', 'value'),
     State('phase6-feasible-store', 'data')], 
    prevent_initial_call=True
)
def run_pareto_analysis(n_clicks, objectives, epsilon, feasible_data):
    """
    执行帕累托分析并保存结果
    """
    if not n_clicks:
        return no_update, no_update

    try:
        import pandas as pd
        
        # 1. 准备数据
        state = get_state_manager()
        
        # 如果前端 Store 没数据，尝试从 StateManager 加载 Phase 6 数据
        if not feasible_data:
            feasible_data = state.load('phase6', 'feasible_designs')
            
        def _to_df(data):
            if data is None: return pd.DataFrame()
            if isinstance(data, pd.DataFrame): return data
            if isinstance(data, list): return pd.DataFrame(data)
            if isinstance(data, dict) and 'data' in data: return pd.DataFrame(data['data'])
            return pd.DataFrame()

        df = _to_df(feasible_data)

        if df.empty:
            return dbc.Alert("数据不足: 请先在 Phase 6 完成约束过滤。", color="warning"), no_update

        if not objectives or len(objectives) < 2:
            return dbc.Alert("请至少选择 2 个优化目标。", color="warning"), no_update

        # 2. 执行计算 (简单的帕累托过滤逻辑示例)
        # 假设所有目标都是"越小越好" (Minimize)，如果有些是Maximize需要预处理
        # 这里为了演示，使用简单的非支配排序逻辑
        subset = df[objectives].copy()
        
        # 简单的 O(N^2) 帕累托过滤 (生产环境建议使用 pymoo 或 pareto.py)
        is_efficient = lambda row: not any(
            all(r <= row[objectives]) and any(r < row[objectives])
            for _, r in subset.iterrows()
        )
        # 注意：这里仅为演示，实际计算量大时需优化
        mask = subset.apply(is_efficient, axis=1)
        pareto_front = df[mask].to_dict('records')
        dominated = df[~mask].to_dict('records')

        # 3. [Core Data] 立即持久化
        analysis_result = {
            'pareto_front': pareto_front,
            'dominated_solutions': dominated,
            'objectives': objectives,
            'epsilon': epsilon
        }
        
        # 保存到 StateManager
        state.save('phase7', 'pareto_analysis', analysis_result)
        # 同时更新 Store 供前端绘图使用
        state.save('phase7', 'pareto_designs', pareto_front) # 冗余存储方便前端直接取用

        # 4. 生成报告
        report = dbc.Alert([
            html.H5([html.I(className="fas fa-trophy me-2"), "帕累托分析完成"], className="alert-heading"),
            html.Hr(),
            html.P([
                html.Strong("非支配解数量: "), f"{len(pareto_front)}", html.Br(),
                html.Strong("被支配解数量: "), f"{len(dominated)}", html.Br(),
                html.Strong("优化目标: "), ", ".join(objectives)
            ])
        ], color="success")

        return report, pareto_front

    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"分析失败: {str(e)}", color="danger"), no_update


@callback(
    [Output('phase6-feasible-store', 'data', allow_duplicate=True), 
     Output('pareto-designs-store', 'data', allow_duplicate=True), 
     Output('input-view-name', 'value'),
     Output('select-x-field', 'value'),
     Output('select-y-field', 'value'),
     Output('select-color-field', 'value'),
     Output('select-size-field', 'value'),
     Output('checklist-objectives', 'value'),
     Output('input-epsilon', 'value'),
     Output('checklist-viz-options', 'value'),
     Output('radio-chart-type', 'value'),
     Output('select-3d-x-axis', 'value'),
     Output('select-3d-y-axis', 'value'),
     Output('select-3d-z-axis', 'value'),
     Output('select-3d-color', 'value'),
     Output('radio-3d-data-source', 'value'),
     Output('checklist-splom-dims', 'value'),
     Output('checklist-pcp-dims', 'value'),
     Output('select-pcp-color', 'value'),
     Output('phase7-save-status', 'children', allow_duplicate=True)],
    [Input('btn-load-phase7', 'n_clicks'),
     Input('phase7-autoloader', 'n_intervals')], 
    prevent_initial_call=True
)
def load_phase7_data(n_clicks, n_intervals):
    """
    统一加载：恢复输入数据、分析结果和视图配置
    """
    from dash import ctx
    
    # 逻辑：点击按钮 或 页面加载(Interval触发)
    triggered_id = ctx.triggered_id
    
    # 如果没有触发源（初始加载）或不是这两个ID触发的，直接返回
    if not triggered_id:
        return tuple([no_update] * 20)

    try:
        state = get_state_manager()
        
        # 1. 恢复 Phase 6 输入数据 (关键依赖)
        feasible_data = state.load('phase6', 'feasible_designs')
        final_feasible = []
        if feasible_data is not None:
            if isinstance(feasible_data, dict) and 'data' in feasible_data:
                final_feasible = feasible_data['data']
            elif hasattr(feasible_data, 'to_dict'):
                final_feasible = feasible_data.to_dict('records')
            elif isinstance(feasible_data, list):
                final_feasible = feasible_data

        # 2. 恢复 Phase 7 分析结果
        pareto_designs = state.load('phase7', 'pareto_designs')
        final_pareto = []
        if pareto_designs:
             if isinstance(pareto_designs, list): final_pareto = pareto_designs
             elif hasattr(pareto_designs, 'to_dict'): final_pareto = pareto_designs.to_dict('records')

        # 3. 恢复 UI State
        ui = state.load('phase7', 'ui_state') or {}
        
        # 4. 生成状态提示
        status_msg = no_update
        # 只有在明确点击按钮时才显示"加载成功"的提示，自动加载保持静默（或根据需求显示）
        if triggered_id == 'btn-load-phase7' or (n_intervals and n_intervals > 0):
            msg = []
            if final_feasible: msg.append(f"输入数据({len(final_feasible)})")
            if final_pareto: msg.append(f"帕累托解({len(final_pareto)})")
            
            if msg:
                # 如果是自动加载且数据存在，可以选择不弹窗，或者只显示轻量提示
                # 这里为了明确反馈，统一显示
                status_msg = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"数据已同步: {' + '.join(msg)}"
                ], color="success", duration=4000) # 4秒后自动消失
            elif triggered_id == 'btn-load-phase7':
                status_msg = dbc.Alert("未找到相关数据，请先完成前序步骤", color="warning")

        # 返回所有 Output
        return (
            final_feasible or no_update,
            final_pareto or no_update,
            ui.get('view_name', ''),
            ui.get('x_axis', 'cost_total'),
            ui.get('y_axis', 'perf_resolution'),
            ui.get('color_field', 'MAU'),
            ui.get('size_field', None),
            ui.get('pareto_objectives', []),
            ui.get('epsilon', 0.0),
            ui.get('viz_options', ["pareto", "grid", "legend", "hover"]),
            ui.get('chart_type', 'scatter'),
            ui.get('x_axis_3d', 'cost_total'),
            ui.get('y_axis_3d', 'perf_coverage'),
            ui.get('z_axis_3d', 'MAU'),
            ui.get('color_field_3d', 'MAU'),
            ui.get('data_source_3d', 'pareto'),
            ui.get('splom_dims', []),
            ui.get('pcp_dims', []),
            ui.get('pcp_color', 'MAU'),
            status_msg
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = dbc.Alert(f"加载异常: {str(e)}", color="danger")
        return tuple([no_update] * 19) + (error,)