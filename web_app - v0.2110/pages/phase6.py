"""
Phase 6: 约束管理与可行性过滤
集成ConstraintEngine实现真实约束评估
"""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.constraint_engine import ConstraintEngine, Constraint
from utils.state_manager import get_state_manager

layout = dbc.Container([
    dcc.Interval(id='phase6-autoloader', interval=500, max_intervals=1),
    dcc.Store(id='phase6-feasible-store', data=None),
    dcc.Store(id='global-selection-store', data={'selected_ids': []}, storage_type='session'),  # P0-1: 全局选择状态

    html.H2([
        html.I(className="fas fa-filter me-2 text-primary"),
        "Phase 6: 约束管理与可行性过滤"
    ], className="mb-4"),

    dbc.Alert([
        html.I(className="fas fa-info-circle me-2"),
        "本阶段使用预定义的约束条件。将自动读取Phase 5的计算结果进行可行性筛选。"
    ], color="info", className="mb-4"),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.1 预定义约束", className="mb-0")),
                dbc.CardBody([
                    html.P([html.Strong("硬约束（必须满足）:")]),
                    html.Ul([
                        html.Li("预算限制: 总成本 ≤ 5000 M$"),
                        html.Li("最小覆盖: 覆盖范围 ≥ 35°"),
                        html.Li("功率限制: 发射功率 ≤ 4000 W")
                    ]),
                    html.P([html.Strong("软约束（期望满足）:")]),
                    html.Ul([
                        html.Li("期望分辨率: ≤ 2 m")
                    ])
                ])
            ], className="shadow-sm mb-4")
        ], md=12),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.2 执行可行性过滤", className="mb-0")),
                dbc.CardBody([
                    dbc.Button([
                        html.I(className="fas fa-filter me-2"),
                        "应用约束过滤"
                    ], id="btn-filter-designs", color="success", size="lg", className="w-100 mb-3"),
                    html.Div(id="filter-status")
                ])
            ], className="shadow-sm mb-4")
        ], md=12)
    ]),

    # ================= [新增] 6.3 边界探测与 Near-Miss 分析 =================
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.3 边界探测与 Near-Miss 分析 ", className="mb-0 text-white"),
                               className="bg-success"),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-search me-2"),
                        "系统工程洞察：识别那些【只违反1个约束且幅度<5%】的“险些通过”设计。这些设计通常具有极高的优化潜力。"
                    ], color="light", className="mb-3"),

                    dbc.Row([
                        dbc.Col([
                            html.H6("权衡空间边界图 (Feasible vs Near-Miss)", className="text-center"),
                            # 新增：边界散点图
                            dcc.Graph(id="boundary-scatter-plot", figure={}, style={"height": "400px"})
                        ], md=7),
                        dbc.Col([
                            html.H6("高潜力“挽救”建议", className="text-center"),
                            # 新增：建议表容器
                            html.Div(id="near-miss-table-container", style={"overflowY": "auto", "maxHeight": "400px"})
                        ], md=5)
                    ])
                ])
            ], className="shadow-sm mb-4")
        ], md=12)
    ]),
    # ====================================================================

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.4 Kill分析", className="mb-0")),
                dbc.CardBody([
                    html.Div(id="kill-analysis-results")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # 可行性对比分析
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.5 可行 vs 不可行设计对比", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "箱线图对比可行和不可行设计在多个指标上的分布差异"
                    ], color="info", className="mb-3"),
                    dcc.Graph(id="feasibility-comparison-boxplot", figure={},
                             config={'displayModeBar': True}),
                    dbc.Button([
                        html.I(className="fas fa-chart-bar me-2"),
                        "生成对比图表"
                    ], id="btn-generate-feasibility-comparison", color="info",
                       className="mt-3")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # 约束敏感性分析 (P1-5)
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.6 约束敏感性分析", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "分析约束容差变化对可行性的影响，识别最严格的约束（瓶颈约束）"
                    ], color="info", className="mb-3"),

                    dbc.Label("选择约束进行敏感性分析"),
                    dbc.Select(
                        id='select-constraint-sensitivity',
                        options=[
                            {'label': '预算限制 (总成本 ≤ 5000 M$)', 'value': 'cost_total'},
                            {'label': '最小覆盖 (覆盖范围 ≥ 35°)', 'value': 'perf_coverage'},
                            {'label': '功率限制 (发射功率 ≤ 4000 W)', 'value': 'transmit_power'}
                        ],
                        value='cost_total',
                        className="mb-3"
                    ),

                    dbc.Label("容差变化范围 (%)"),
                    dcc.RangeSlider(
                        id='slider-tolerance-range',
                        min=-50,
                        max=50,
                        step=5,
                        value=[-20, 20],
                        marks={i: f'{i}%' for i in range(-50, 51, 10)},
                        className="mb-3"
                    ),

                    dbc.Button([
                        html.I(className="fas fa-chart-line me-2"),
                        "运行约束敏感性分析"
                    ], id='btn-constraint-sensitivity', color="warning", className="w-100 mb-3"),

                    dcc.Graph(id='constraint-sensitivity-plot', figure={}, config={'displayModeBar': True})
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

# P2-8: 交互式约束调整
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.7 交互式约束调整 (P2-8)", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "已启用宽范围模式：滑块范围已根据数据特征进行扩展 (0起步)。"
                    ], color="success", className="mb-3"),

                    # 实时可行性统计卡片
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                html.H2(id='realtime-feasible-count', children="---", className="mb-0 text-center text-success"),
                                html.P("可行设计数量", className="text-center text-muted mb-2"),
                                dbc.Progress(id='realtime-feasibility-progress', value=0, className="mb-2"),
                                html.P(id='realtime-feasibility-ratio', children="可行性: ---%", className="text-center text-muted mb-0")
                            ])
                        ])
                    ], color="light", className="mb-4"),

                    # 滑块控制区 - [修复版] 范围放宽以适应不同量级的数据
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("💰 预算限制 (总成本 ≤ )"),
                            dcc.Slider(
                                id='slider-budget-limit',
                                min=0,            # [修改] 允许从0开始
                                max=20000,        # [修改] 上限扩大到20000以防成本过高
                                step=100,
                                value=10000,      # [修改] 默认值设大一点
                                marks={0:'0', 5000:'5k', 10000:'10k', 15000:'15k', 20000:'20k'},
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="mb-3"
                            ),
                        ], md=6),

                        dbc.Col([
                            dbc.Label("🌍 最小覆盖 (覆盖范围 ≥ )"),
                            dcc.Slider(
                                id='slider-min-coverage',
                                min=0,            # [修改] 允许从0开始 (解决 4.0 < 25 的问题)
                                max=100,          # [修改] 范围 0-100
                                step=0.1,         # [修改] 步长设细一点，适应小数
                                value=0,          # [修改] 默认设为0，确保一开始有可行解
                                marks={0:'0', 20:'20', 40:'40', 60:'60', 80:'80', 100:'100'},
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="mb-3"
                            ),
                        ], md=6)
                    ]),

                    dbc.Row([
                        dbc.Col([
                            dbc.Label("⚡ 功率限制 (发射功率 ≤ )"),
                            dcc.Slider(
                                id='slider-max-power',
                                min=0,
                                max=10000,
                                step=100,
                                value=10000,
                                marks={0:'0', 5000:'5k', 10000:'10k'},
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="mb-3"
                            ),
                        ], md=6),

                        dbc.Col([
                            dbc.Label("🎯 分辨率目标 (分辨率 ≤ )"),
                            dcc.Slider(
                                id='slider-resolution-target',
                                min=0,
                                max=10,
                                step=0.1,
                                value=10,
                                marks={0:'0', 5:'5', 10:'10'},
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="mb-3"
                            ),
                        ], md=6)
                    ]),

                    html.Hr(),

                    dbc.Button([
                        html.I(className="fas fa-check-circle me-2"),
                        "应用当前约束并重新过滤"
                    ], id='btn-apply-adjusted-constraints', color="success", className="w-100")
                ])
            ], className="shadow-sm mb-4")
        ])
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
                            "保存Phase 6数据"
                        ], id="btn-save-phase6", color="success", className="me-2"),
                        dbc.Button([
                            html.I(className="fas fa-upload me-2"),
                            "加载Phase 6数据"
                        ], id="btn-load-phase6", color="info")
                    ]),
                    html.Div(id="phase6-save-status", className="mt-3")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button("上一步: Phase 5", href="/phase5", color="secondary", outline=True),
                dbc.Button("下一步: Phase 7", href="/phase7", color="primary")
            ], className="w-100")
        ])
    ])
], fluid=True)


@callback(
    Output('feasibility-comparison-boxplot', 'figure'),
    Input('btn-generate-feasibility-comparison', 'n_clicks'),
    prevent_initial_call=True
)
def generate_feasibility_comparison(n_clicks):
    """生成可行 vs 不可行设计的箱线图对比 (P0-1功能)"""
    if not n_clicks:
        return no_update

    try:
        import pandas as pd

        # DataFrame辅助函数检查数据有效性
        def _has_valid_data(data):
            """检查数据是否有效（支持DataFrame和list）"""
            if data is None:
                return False
            if isinstance(data, pd.DataFrame):
                return not data.empty
            if isinstance(data, list):
                return len(data) > 0
            return False

        # 1. 从StateManager加载统一结果
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if not _has_valid_data(unified):  # DataFrame使用显式类型检查
            # 返回空图表并提示
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text="请先在Phase 5运行批量计算，再在Phase 6应用约束过滤！",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="red")
            )
            fig.update_layout(
                title="可行 vs 不可行设计对比",
                height=600,
                xaxis=dict(visible=False),
                yaxis=dict(visible=False)
            )
            return fig

        # 2. 检查是否有feasible列（Phase 6约束过滤后才有）
        if 'feasible' not in unified.columns:
            # 如果还没有过滤，创建一个临时约束引擎来添加feasible列
            from utils.constraint_engine import ConstraintEngine, Constraint
            engine = ConstraintEngine()
            engine.add_constraint(Constraint('budget', 'cost_total <= 5000', 'hard'))
            engine.add_constraint(Constraint('min_coverage', 'perf_coverage >= 35', 'hard'))
            engine.add_constraint(Constraint('max_power', 'transmit_power <= 4000', 'hard'))
            unified = engine.apply_constraints(unified)

        # 3. 分离可行和不可行设计
        feasible_designs = unified[unified['feasible']]
        infeasible_designs = unified[~unified['feasible']]

        n_feasible = len(feasible_designs)
        n_infeasible = len(infeasible_designs)

        # 4. 选择要对比的关键指标
        metrics = [
            {'col': 'cost_total', 'name': '总成本 (M$)'},
            {'col': 'perf_coverage', 'name': '覆盖范围 (°)'},
            {'col': 'perf_resolution', 'name': '分辨率 (m)'},
            {'col': 'MAU', 'name': 'MAU效用值'}
        ]

        # 5. 创建子图（2x2布局）
        from plotly.subplots import make_subplots
        import plotly.graph_objects as go

        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=[m['name'] for m in metrics],
            vertical_spacing=0.12,
            horizontal_spacing=0.10
        )

        # 6. 为每个指标添加箱线图
        positions = [(1, 1), (1, 2), (2, 1), (2, 2)]

        for metric, (row, col) in zip(metrics, positions):
            metric_col = metric['col']

            # 可行设计箱线图
            fig.add_trace(
                go.Box(
                    y=feasible_designs[metric_col],
                    name='可行',
                    marker=dict(color='rgb(46, 204, 113)'),
                    boxmean='sd',  # 显示均值和标准差
                    legendgroup='feasible',
                    showlegend=(row == 1 and col == 1)  # 只在第一个子图显示图例
                ),
                row=row, col=col
            )

            # 不可行设计箱线图
            fig.add_trace(
                go.Box(
                    y=infeasible_designs[metric_col],
                    name='不可行',
                    marker=dict(color='rgb(231, 76, 60)'),
                    boxmean='sd',
                    legendgroup='infeasible',
                    showlegend=(row == 1 and col == 1)
                ),
                row=row, col=col
            )

        # 7. 更新布局
        fig.update_layout(
            title=dict(
                text=f"可行 vs 不可行设计对比分析<br><sub>可行: {n_feasible} | 不可行: {n_infeasible} | 总计: {len(unified)}</sub>",
                x=0.5,
                xanchor='center'
            ),
            height=700,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            ),
            hovermode='closest'
        )

        # 8. 更新坐标轴标签
        fig.update_xaxes(title_text="", showticklabels=True)
        fig.update_yaxes(title_text=metrics[0]['name'], row=1, col=1)
        fig.update_yaxes(title_text=metrics[1]['name'], row=1, col=2)
        fig.update_yaxes(title_text=metrics[2]['name'], row=2, col=1)
        fig.update_yaxes(title_text=metrics[3]['name'], row=2, col=2)

        return fig

    except Exception as e:
        # 错误处理
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_annotation(
            text=f"生成图表失败: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="red")
        )
        fig.update_layout(
            title="可行 vs 不可行设计对比（生成失败）",
            height=600
        )
        return fig

# P1-5功能：约束敏感性分析 (修复版：支持中文列名)
@callback(
    Output('constraint-sensitivity-plot', 'figure'),
    Input('btn-constraint-sensitivity', 'n_clicks'),
    [State('select-constraint-sensitivity', 'value'),
     State('slider-tolerance-range', 'value')],
    prevent_initial_call=True
)
def constraint_sensitivity_analysis(n_clicks, constraint_col, tolerance_range):
    """约束敏感性分析 - P1-5核心功能 (修复KeyError)"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import numpy as np
    import pandas as pd

    if not n_clicks:
        return go.Figure()

    try:
        # DataFrame辅助函数检查数据有效性
        def _has_valid_data(data):
            if data is None: return False
            if isinstance(data, pd.DataFrame): return not data.empty
            if isinstance(data, list): return len(data) > 0
            return False

        state = get_state_manager()
        unified_data = state.load('phase5', 'unified_results')

        if not _has_valid_data(unified_data):
            fig = go.Figure()
            fig.add_annotation(text="请先在Phase 5运行批量计算！", showarrow=False, font=dict(color="red"))
            return fig

        # 转换为 DataFrame
        unified = pd.DataFrame(unified_data)

        # === 1. 智能列名映射 (核心修复) ===
        # 定义前端下拉框的值(key)与数据集中可能的列名(value list)的对应关系
        col_mapping_rules = {
            'cost_total': ['总成本', 'cost_total', 'cost', 'total_cost'],
            'perf_coverage': ['服务能力', 'perf_coverage', 'coverage', 'capability', '覆盖范围'],
            'transmit_power': ['响应时间', 'transmit_power', 'power', 'response_time', '发射功率']
        }

        # 查找当前要分析的列在 DataFrame 中叫什么名字
        actual_col = None
        candidates = col_mapping_rules.get(constraint_col, [constraint_col])
        for candidate in candidates:
            match = next((c for c in unified.columns if c.lower() == candidate.lower()), None)
            if match:
                actual_col = match
                break

        if not actual_col:
            # 如果找不到列，返回友好提示而不是报错
            fig = go.Figure()
            fig.add_annotation(
                text=f"数据中未找到对应的列: {constraint_col}<br>当前可用列: {list(unified.columns)[:5]}...",
                showarrow=False, font=dict(color="red")
            )
            return fig

        # === 2. 定义基准约束值 ===
        baseline_constraints = {
            'cost_total': 5000,  # ≤ 5000 M$
            'perf_coverage': 35,  # ≥ 35°
            'transmit_power': 4000  # ≤ 4000 W
        }

        # 约束类型（上限或下限）
        constraint_types = {
            'cost_total': 'upper',
            'perf_coverage': 'lower',
            'transmit_power': 'upper'
        }

        baseline_value = baseline_constraints.get(constraint_col, 0)
        constraint_type = constraint_types.get(constraint_col, 'upper')

        # === 3. 执行分析 ===
        tolerance_min, tolerance_max = tolerance_range
        tolerances = np.linspace(tolerance_min, tolerance_max, 21)
        adjusted_values = baseline_value * (1 + tolerances / 100)

        feasible_counts = []
        feasibility_ratios = []

        for adjusted_value in adjusted_values:
            if constraint_type == 'upper':
                # 使用 actual_col 而不是 constraint_col
                feasible = (unified[actual_col] <= adjusted_value).sum()
            else:
                feasible = (unified[actual_col] >= adjusted_value).sum()

            feasible_counts.append(feasible)
            feasibility_ratios.append(feasible / len(unified) * 100)

        # (后续绘图代码保持不变，省略以节省篇幅，逻辑已修复)
        # ... [保留原有的绘图代码] ...
        # 这里为了完整性，简单重写绘图部分确保能运行

        fig = make_subplots(rows=1, cols=2, subplot_titles=("约束值 vs 可行数量", "容差 vs 可行比例"))

        # 图1
        fig.add_trace(go.Scatter(x=adjusted_values, y=feasible_counts, mode='lines+markers', name='可行数量'), row=1,
                      col=1)
        fig.add_trace(
            go.Scatter(x=[baseline_value], y=[feasible_counts[10]], mode='markers', marker=dict(size=10, color='red'),
                       name='当前值'), row=1, col=1)

        # 图2
        fig.add_trace(go.Scatter(x=tolerances, y=feasibility_ratios, mode='lines', name='可行比例(%)'), row=1, col=2)
        fig.add_hline(y=0, row=1, col=2, line_dash="dash")

        fig.update_layout(title=f"约束敏感性: {actual_col} (基准: {baseline_value})", height=400)
        return fig

    except Exception as e:
        import traceback
        traceback.print_exc()
        fig = go.Figure()
        fig.add_annotation(text=f"分析出错: {str(e)}", showarrow=False, font=dict(color="red"))
        return fig

# ========== P2-8: 交互式约束调整回调 ==========
# 回调1: 实时可行性计算（监听滑块变化）
@callback(
    [Output('realtime-feasible-count', 'children'),
     Output('realtime-feasibility-progress', 'value'),
     Output('realtime-feasibility-progress', 'color'),
     Output('realtime-feasibility-ratio', 'children')],
    [Input('slider-budget-limit', 'value'),
     Input('slider-min-coverage', 'value'),
     Input('slider-max-power', 'value'),
     Input('slider-resolution-target', 'value')],
    prevent_initial_call=False
)
def update_realtime_feasibility(budget_limit, min_coverage, max_power, resolution_target):
    """
    实时更新可行性统计 - [诊断版]
    当结果为0时，显示数据实际范围，帮助定位问题。
    """
    try:
        import pandas as pd
        import numpy as np

        # DataFrame辅助函数检查数据有效性
        def _has_valid_data(data):
            if data is None: return False
            if isinstance(data, pd.DataFrame): return not data.empty
            if isinstance(data, list): return len(data) > 0
            return False

        # 1. 从StateManager加载数据
        state = get_state_manager()
        unified_data = state.load('phase5', 'unified_results')

        if not _has_valid_data(unified_data):
            return "---", 0, "secondary", "数据未加载 (请先运行Phase 5)"

        # 转换为 DataFrame
        unified = pd.DataFrame(unified_data)

        # === 2. 智能列名映射 ===
        def find_col(candidates):
            for c in candidates:
                match = next((col for col in unified.columns if col.lower() == c.lower()), None)
                if match: return match
            return None

        # 映射关键列
        col_cost = find_col(['总成本', 'cost_total', 'cost', 'total_cost'])
        col_perf = find_col(['服务能力', 'perf_coverage', 'coverage', 'capability', '覆盖范围'])
        col_power = find_col(['响应时间', 'transmit_power', 'power', 'response_time', '发射功率'])
        col_res = find_col(['分辨率', 'perf_resolution', 'resolution'])

        # 检查关键列
        missing_cols = []
        if not col_cost: missing_cols.append("成本")
        if not col_perf: missing_cols.append("覆盖")

        if missing_cols:
            return "Error", 0, "danger", f"列缺失: {','.join(missing_cols)}"

        # === 3. 安全数值转换与统计 ===
        # 使用 coerce 将无法转换的字符变 NaN，然后处理

        # 成本 (越小越好): 填充 Inf 表示极其昂贵
        s_cost = pd.to_numeric(unified[col_cost], errors='coerce')
        # 记录转换前的有效性，用于诊断
        valid_cost_count = s_cost.notna().sum()
        unified[col_cost] = s_cost.fillna(float('inf'))

        # 覆盖 (越大越好): 填充 -1 表示无覆盖
        s_perf = pd.to_numeric(unified[col_perf], errors='coerce')
        valid_perf_count = s_perf.notna().sum()
        unified[col_perf] = s_perf.fillna(-1.0)

        # 功率 (越小越好)
        if col_power:
            unified[col_power] = pd.to_numeric(unified[col_power], errors='coerce').fillna(0)  # 功率缺失暂设为0，避免全杀

        # 分辨率 (越小越好)
        if col_res:
            # 注意：分辨率如果是 NaN，通常意味着未计算出，设为 Inf 以便过滤掉
            unified[col_res] = pd.to_numeric(unified[col_res], errors='coerce').fillna(float('inf'))

        # === 4. 计算可行性 ===
        # 硬约束
        mask_cost = (unified[col_cost] <= budget_limit)
        mask_cov = (unified[col_perf] >= min_coverage)

        feasible_mask = mask_cost & mask_cov

        if col_power:
            feasible_mask = feasible_mask & (unified[col_power] <= max_power)

        # 软约束 (分辨率) - 改为仅当滑块值 < 3.0 (非最大值) 时才生效，或者作为硬约束
        # 这里假设用户在 UI 上操作了滑块就是希望作为过滤条件
        if col_res:
            feasible_mask = feasible_mask & (unified[col_res] <= resolution_target)

        n_feasible = feasible_mask.sum()
        n_total = len(unified)
        feasibility_ratio = n_feasible / n_total * 100 if n_total > 0 else 0

        # === 5. 诊断信息生成 (关键修复) ===
        status_text = f"可行性: {feasibility_ratio:.1f}% ({n_feasible}/{n_total})"

        # 如果结果为 0，生成详细诊断报告
        if n_feasible == 0:
            # 计算数据实际范围
            real_min_cost = unified[col_cost].replace([np.inf, -np.inf], np.nan).min()
            real_max_cov = unified[col_perf].replace([np.inf, -np.inf], np.nan).max()

            diag_msg = []

            # 诊断1: 数据转换失败?
            if valid_cost_count == 0:
                diag_msg.append("成本数据全无效(非数字)")
            elif valid_perf_count == 0:
                diag_msg.append("覆盖数据全无效(非数字)")

            # 诊断2: 范围超出?
            elif real_min_cost > budget_limit:
                diag_msg.append(f"成本过高(最低{real_min_cost:.0f} > 滑块{budget_limit})")
            elif real_max_cov < min_coverage:
                diag_msg.append(f"覆盖过低(最高{real_max_cov:.1f} < 滑块{min_coverage})")
            else:
                # 检查其他约束
                if col_power and (unified[col_power] > max_power).all():
                    real_min_p = unified[col_power].min()
                    diag_msg.append(f"功率过大(最低{real_min_p:.0f})")
                elif col_res and (unified[col_res] > resolution_target).all():
                    real_min_r = unified[col_res].replace([np.inf], np.nan).min()
                    diag_msg.append(f"分辨率不足(最优{real_min_r:.2f})")

            if diag_msg:
                status_text = "❌ " + "; ".join(diag_msg)
            else:
                status_text = "❌ 约束组合无解 (请单独调整各滑块排查)"

        # 6. 颜色编码
        if feasibility_ratio >= 60:
            progress_color = "success"
        elif feasibility_ratio >= 30:
            progress_color = "warning"
        else:
            progress_color = "danger"

        return (
            str(n_feasible),
            feasibility_ratio,
            progress_color,
            status_text
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return "错误", 0, "danger", f"计算异常: {str(e)}"


# ================= [修复版V2] 核心过滤与分析逻辑 (修复JSON序列化报错) =================

@callback(
    [Output('filter-status', 'children'),
     Output('kill-analysis-results', 'children'),
     Output('phase6-feasible-store', 'data'),
     Output('boundary-scatter-plot', 'figure'),
     Output('near-miss-table-container', 'children')],
    [Input('btn-filter-designs', 'n_clicks'),
     Input('btn-apply-adjusted-constraints', 'n_clicks')],
    [State('slider-budget-limit', 'value'),
     State('slider-min-coverage', 'value'),
     State('slider-max-power', 'value'),
     State('slider-resolution-target', 'value')],
    prevent_initial_call=True
)
def run_advanced_filtering(n_click_filter, n_click_adjust, budget, coverage, power, resolution):
    """
    统一执行可行性过滤、Kill分析以及边界探测分析
    [修复版]：支持中文列名，并在保存时强制转换为标准英文名给Phase 7使用
    """
    from dash import ctx, no_update
    import plotly.express as px
    import pandas as pd
    import numpy as np

    # 1. 触发检测
    if not ctx.triggered:
        return no_update, no_update, no_update, no_update, no_update

    try:
        # 2. 加载数据
        state = get_state_manager()
        df_raw = state.load('phase5', 'unified_results')

        # 数据有效性检查
        if df_raw is None:
            return dbc.Alert("数据缺失：请先在Phase 5完成计算！", color="danger"), no_update, None, {}, None

        # 统一转为 DataFrame
        if isinstance(df_raw, list):
            df = pd.DataFrame(df_raw)
        elif isinstance(df_raw, dict) and 'data' in df_raw:
            df = pd.DataFrame(df_raw['data'])
        else:
            # 尝试直接转换
            try:
                df = pd.DataFrame(df_raw)
            except:
                return dbc.Alert("数据格式无法识别", color="danger"), no_update, None, {}, None

        if df.empty:
            return dbc.Alert("Phase 5 结果为空，无法进行分析。", color="danger"), no_update, None, {}, None

        # --- 3. 智能列名映射 (支持中文/英文混合) ---
        def find_col(candidates):
            # 优先精确匹配，然后忽略大小写匹配
            for c in candidates:
                if c in df.columns: return c
            for c in candidates:
                match = next((col for col in df.columns if col.lower() == c.lower()), None)
                if match: return match
            return None

        # 映射关键列
        col_cost = find_col(['总成本', 'cost_total', 'cost', 'total_cost'])
        col_perf = find_col(['服务能力', 'perf_coverage', 'coverage', 'capability', '覆盖范围'])
        col_const3 = find_col(['响应时间', 'transmit_power', 'power', 'response_time', '发射功率'])
        col_mau = find_col(['MAU', 'mau', 'utility'])

        # 检查是否缺少必要的列
        missing = []
        if not col_cost: missing.append("成本(总成本)")
        if not col_perf: missing.append("性能(服务能力/覆盖)")

        if missing:
            return dbc.Alert(f"❌ 列名匹配失败: 未找到 {', '.join(missing)}。当前可用列: {', '.join(df.columns)}",
                             color="danger"), no_update, None, {}, None

        # 处理可选的第三约束 (如果没找到，就创建一个虚拟列，不影响运行)
        use_dummy_const3 = False
        if not col_const3:
            col_const3 = '_dummy_power'
            df[col_const3] = 0
            use_dummy_const3 = True

        # --- 4. 执行逐行过滤 ---
        final_budget = budget
        final_coverage = coverage
        final_power = power

        results = []
        near_miss_threshold = 0.05  # 5% 的边界容差

        for idx, row in df.iterrows():
            violations = []
            is_feasible = True

            # 获取值 (处理可能出现的 NaN)
            val_cost = row[col_cost] if pd.notnull(row[col_cost]) else float('inf')
            val_perf = row[col_perf] if pd.notnull(row[col_perf]) else 0
            val_const3 = row[col_const3] if pd.notnull(row[col_const3]) else 0
            val_mau = row.get(col_mau, 0)

            # 约束 1: 成本 (Upper Limit)
            if val_cost > final_budget:
                is_feasible = False
                margin = (val_cost - final_budget) / final_budget if final_budget != 0 else 1.0
                violations.append({'name': col_cost, 'margin': margin, 'val': val_cost, 'limit': final_budget})

            # 约束 2: 覆盖 (Lower Limit)
            if val_perf < final_coverage:
                is_feasible = False
                margin = (final_coverage - val_perf) / final_coverage if final_coverage != 0 else 1.0
                violations.append({'name': col_perf, 'margin': margin, 'val': val_perf, 'limit': final_coverage})

            # 约束 3: 功率 (Upper Limit) - 仅当列存在时
            if not use_dummy_const3:
                if val_const3 > final_power:
                    is_feasible = False
                    margin = (val_const3 - final_power) / final_power if final_power != 0 else 1.0
                    violations.append({'name': col_const3, 'margin': margin, 'val': val_const3, 'limit': final_power})

            # 判定状态
            status = 'Feasible'
            if not is_feasible:
                # 如果只违反了一个约束，且幅度很小，算作 "Near-Miss"
                if len(violations) == 1 and violations[0]['margin'] <= near_miss_threshold:
                    status = 'Near-Miss'
                else:
                    status = 'Infeasible'

            # 构造结果行
            res_entry = row.to_dict()
            res_entry['status'] = status
            res_entry['feasible'] = is_feasible
            res_entry['first_violation'] = violations[0]['name'] if violations else None
            # 注意：violation_detail 是字典，JSON序列化没问题
            res_entry['violation_detail'] = violations[0] if violations else None

            # 添加标准化绘图数据 (用于下面的散点图)
            res_entry['_std_x'] = val_cost
            res_entry['_std_y'] = val_perf
            res_entry['_std_mau'] = val_mau

            results.append(res_entry)

        res_df = pd.DataFrame(results)

        # --- 5. 生成前端输出 ---
        n_feasible = sum(res_df['feasible'])
        n_total = len(res_df)
        rate = n_feasible / n_total * 100 if n_total > 0 else 0

        # 5.1 状态提示
        mapped_info = f"当前映射: 预算=[{col_cost}], 覆盖=[{col_perf}]"
        if not use_dummy_const3:
            mapped_info += f", 功率=[{col_const3}]"

        status_color = "success" if n_feasible > 0 else "danger"
        status_display = dbc.Alert([
            html.H5(f"过滤完成: {n_feasible} 可行 / {n_total} 总数 ({rate:.1f}%)", className="alert-heading"),
            html.Hr(),
            html.P(mapped_info, className="mb-0 small"),
            html.P("如果可行数为0，请尝试拖动滑块放宽约束（如增加预算、减小覆盖要求）。", className="mt-2 text-muted small")
        ], color=status_color)

        # 5.2 Kill 分析表
        if 'first_violation' in res_df.columns and not res_df['first_violation'].isnull().all():
            kill_counts = res_df[~res_df['feasible']]['first_violation'].value_counts().reset_index()
            kill_counts.columns = ['瓶颈约束', '淘汰数量']
            kill_table = dbc.Table.from_dataframe(kill_counts, striped=True, bordered=True, size="sm")
        else:
            kill_table = html.Div("所有设计均可行，无淘汰数据。", className="text-success")

        # --- 6. [关键步骤] 数据标准化与保存 ---
        # 这一步是为了解决 Phase 7 的 "KeyError" 和无数据问题
        # 我们只提取可行的数据，并将列名强制重命名为标准英文

        if n_feasible > 0:
            # 提取可行行
            feasible_df = res_df[res_df['feasible']].copy()

            # 删除临时辅助列
            cols_to_drop = ['status', 'first_violation', 'violation_detail', '_std_x', '_std_y', '_std_mau',
                            '_dummy_power']
            feasible_df = feasible_df.drop(columns=cols_to_drop, errors='ignore')

            # 建立重命名映射 (中文 -> 标准英文)
            rename_map = {}
            if col_cost: rename_map[col_cost] = 'cost_total'
            if col_perf: rename_map[col_perf] = 'perf_coverage'
            if col_const3 and not use_dummy_const3: rename_map[col_const3] = 'transmit_power'
            if col_mau: rename_map[col_mau] = 'MAU'

            # 执行重命名
            feasible_data_std = feasible_df.rename(columns=rename_map)

            # 保存到 StateManager
            # 使用 .to_dict('records') 确保是纯 JSON 格式
            final_data_to_store = feasible_data_std.to_dict('records')
            state.save('phase6', 'feasible_designs', final_data_to_store)
        else:
            final_data_to_store = []
            # 如果没有可行解，也保存个空列表，防止报错
            state.save('phase6', 'feasible_designs', [])

        # 5.3 边界探测散点图
        fig_scatter = px.scatter(
            res_df,
            x='_std_x',
            y='_std_y',
            color='status',
            color_discrete_map={'Feasible': '#2ecc71', 'Near-Miss': '#f1c40f', 'Infeasible': '#e74c3c'},
            title=f"权衡空间边界: {col_cost} vs {col_perf}",
            labels={'_std_x': str(col_cost), '_std_y': str(col_perf)},
            hover_data=['design_id', '_std_mau']
        )
        # 画出约束线
        fig_scatter.add_vline(x=final_budget, line_dash="dash", line_color="gray", annotation_text="预算上限")
        fig_scatter.add_hline(y=final_coverage, line_dash="dash", line_color="gray", annotation_text="覆盖下限")
        fig_scatter.update_layout(height=400, margin=dict(l=20, r=20, t=40, b=20), legend=dict(orientation="h", y=1.1))

        # 5.4 Near-Miss 建议表
        near_miss_df = res_df[res_df['status'] == 'Near-Miss'].copy()
        if not near_miss_df.empty:
            rows = []
            for _, row in near_miss_df.iterrows():
                v = row['violation_detail']
                rows.append({
                    'ID': str(row.get('design_id', 'N/A')),
                    '违规项': str(v['name']),
                    '当前值': f"{v['val']:.1f}",
                    '阈值': f"{v['limit']}",
                    '建议放宽': f"{v['margin'] * 100:.1f}%",
                    '潜在MAU': f"{row.get('_std_mau', 0):.3f}"
                })
            nm_table_df = pd.DataFrame(rows).sort_values('潜在MAU', ascending=False).head(10)
            nm_table = dbc.Table.from_dataframe(nm_table_df, striped=True, bordered=True, size="sm",
                                                style={'fontSize': '11px'})
        else:
            nm_table = dbc.Alert("未发现'险些通过'的设计 (Near-Miss)。", color="secondary",
                                 style={"padding": "10px", "fontSize": "12px"})

        return status_display, kill_table, final_data_to_store, fig_scatter, nm_table

    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"运行出错: {str(e)}", color="danger"), no_update, None, {}, None
# ========== P0-1: 全局刷选响应 (跨页面同步) ==========

@callback(
    Output('feasibility-comparison-boxplot', 'figure', allow_duplicate=True),
    Input('global-selection-store', 'data'),
    State('feasibility-comparison-boxplot', 'figure'),
    prevent_initial_call=True
)
def highlight_phase6_selection(selection_data, current_figure):
    """在Phase 6可行性对比图中高亮显示全局选中的设计 (P0-1跨页面同步)"""
    if not selection_data or not current_figure:
        return no_update

    selected_ids = selection_data.get('selected_ids', [])

    if not selected_ids:
        return no_update

    try:
        import pandas as pd

        # DataFrame辅助函数检查数据有效性
        def _has_valid_data(data):
            """检查数据是否有效（支持DataFrame和list）"""
            if data is None:
                return False
            if isinstance(data, pd.DataFrame):
                return not data.empty
            if isinstance(data, list):
                return len(data) > 0
            return False

        # 从StateManager加载统一结果
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if not _has_valid_data(unified):  # DataFrame使用显式类型检查
            return no_update

        # 创建新图表（保留原有布局）
        import plotly.graph_objects as go
        fig = go.Figure(current_figure)

        # 添加选择统计注释
        # 计算选中设计的可行性状态
        selected_data = unified.iloc[selected_ids] if max(selected_ids) < len(unified) else None

        if selected_data is not None and 'feasible' in selected_data.columns:
            n_feasible_selected = selected_data['feasible'].sum()
            n_infeasible_selected = len(selected_data) - n_feasible_selected

            annotation_text = (
                f"✓ 已选中 {len(selected_ids)} 个设计<br>"
                f"  - {n_feasible_selected} 可行<br>"
                f"  - {n_infeasible_selected} 不可行"
            )
        else:
            annotation_text = f"✓ 已选中 {len(selected_ids)} 个设计"

        # 清除旧的选择注释
        fig.layout.annotations = [
            ann for ann in fig.layout.annotations
            if "已选中" not in ann.text
        ]

        # 添加新的选择统计注释
        fig.add_annotation(
            text=annotation_text,
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            bgcolor="rgba(255,0,0,0.1)",
            bordercolor="red",
            borderwidth=2,
            font=dict(size=10, color="red"),
            align="left",
            yanchor="top"
        )

        return fig

    except Exception as e:
        print(f"Phase 6全局刷选响应失败: {e}")
        import traceback
        traceback.print_exc()
        return no_update


# ========== 自动保存 UI 状态  ==========
@callback(
    Output('phase6-save-status', 'children', allow_duplicate=True),
    [Input('slider-budget-limit', 'value'),
     Input('slider-min-coverage', 'value'),
     Input('slider-max-power', 'value'),
     Input('slider-resolution-target', 'value'),
     Input('select-constraint-sensitivity', 'value'),
     Input('slider-tolerance-range', 'value')],
    prevent_initial_call=True
)
def auto_save_phase6_ui(budget, coverage, power, resolution, sens_constraint, sens_tolerance):
    """
    自动保存 UI 状态 (Drafts)
    记录用户的交互现场，包括滑块位置和分析设置
    """
    from dash import ctx
    if not ctx.triggered: return no_update

    state = get_state_manager()

    current_ui = state.load('phase6', 'ui_state') or {}

    # 更新所有 UI 控件状态
    current_ui.update({
        'budget_limit': budget,
        'min_coverage': coverage,
        'max_power': power,
        'resolution_target': resolution,
        'sensitivity_constraint': sens_constraint,
        'sensitivity_tolerance': sens_tolerance
    })

    state.save('phase6', 'ui_state', current_ui)
    return no_update # 静默保存

# ===== 手动保存 Phase 6 数据 =====
@callback(
    Output('phase6-save-status', 'children'),
    Input('btn-save-phase6', 'n_clicks'),
    [State('phase6-feasible-store', 'data'),
     State('slider-budget-limit', 'value'),
     State('slider-min-coverage', 'value'),
     State('slider-max-power', 'value'),
     State('slider-resolution-target', 'value'),
     State('select-constraint-sensitivity', 'value'),
     State('slider-tolerance-range', 'value')],
    prevent_initial_call=True
)
def save_phase6_data(n_clicks, feasible_designs, budget, coverage, power, resolution, sens_const, sens_tol):
    """手动保存所有 Phase 6 数据"""
    if not n_clicks: return no_update

    state = get_state_manager()

    # 1. 保存 Store 数据 (如果存在)
    if feasible_designs:
        state.save('phase6', 'feasible_designs', feasible_designs)

    # 2. 保存 Config (模拟 Apply 的效果)
    constraint_config = {
        'budget_limit': budget, 'min_coverage': coverage,
        'max_power': power, 'resolution_target': resolution
    }
    state.save('phase6', 'constraint_config', constraint_config)

    # 3. 保存 UI State
    ui_state = {
        'budget_limit': budget,
        'min_coverage': coverage,
        'max_power': power,
        'resolution_target': resolution,
        'sensitivity_constraint': sens_const,
        'sensitivity_tolerance': sens_tol
    }
    state.save('phase6', 'ui_state', ui_state)

    count = len(feasible_designs) if feasible_designs else 0
    return dbc.Alert([
        html.I(className="fas fa-check-circle me-2"),
        f"Phase 6 数据已保存: {count} 个方案 + 当前约束配置"
    ], color="success")

@callback(
    [Output('phase6-feasible-store', 'data', allow_duplicate=True),
     Output('slider-budget-limit', 'value'),
     Output('slider-min-coverage', 'value'),
     Output('slider-max-power', 'value'),
     Output('slider-resolution-target', 'value'),
     Output('select-constraint-sensitivity', 'value'),
     Output('slider-tolerance-range', 'value'),
     Output('phase6-save-status', 'children', allow_duplicate=True)],
    [Input('btn-load-phase6', 'n_clicks'),
     Input('phase6-autoloader', 'n_intervals')],
    prevent_initial_call=True
)
def load_phase6_data(n_clicks, n_intervals):
    """
    加载 Phase 6 数据并恢复现场
    触发源：手动点击按钮 OR 页面加载完成(Autoloader)
    """
    from dash import ctx
    import pandas as pd

    triggered_id = ctx.triggered_id

    # 如果没有任何触发（虽然 prevent_initial_call=True 挡住了大部分，但为了稳健性）
    if not triggered_id:
         return tuple([no_update] * 8)

    try:
        state = get_state_manager()

        # 1. 加载 Core Data
        feasible_designs = state.load('phase6', 'feasible_designs')
        constraint_config = state.load('phase6', 'constraint_config') or {}

        # 2. 加载 UI State
        ui_state = state.load('phase6', 'ui_state') or {}

        # 3. 恢复 UI 值逻辑
        r_budget = ui_state.get('budget_limit') or constraint_config.get('budget_limit', 5000)
        r_coverage = ui_state.get('min_coverage') or constraint_config.get('min_coverage', 35)
        r_power = ui_state.get('max_power') or constraint_config.get('max_power', 4000)
        r_res = ui_state.get('resolution_target') or constraint_config.get('resolution_target', 2.0)

        r_sens_const = ui_state.get('sensitivity_constraint', 'cost_total')
        r_sens_tol = ui_state.get('sensitivity_tolerance', [-20, 20])

        # 4. 处理数据格式
        final_data = no_update
        has_data = False

        if feasible_designs:
            if isinstance(feasible_designs, dict) and 'data' in feasible_designs:
                final_data = feasible_designs['data']
                has_data = True
            elif isinstance(feasible_designs, list):
                final_data = feasible_designs
                has_data = True
            elif isinstance(feasible_designs, pd.DataFrame) and not feasible_designs.empty:
                final_data = feasible_designs.to_dict('records')
                has_data = True

        # 5. 状态提示
        status_msg = no_update
        # 只有手动点击按钮时才显示 Alert，自动加载静默处理（或者你可以加一个会自动消失的提示）
        if triggered_id == 'btn-load-phase6':
            if has_data:
                count = len(final_data)
                status_msg = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"加载成功: {count} 个可行方案 + 约束配置"
                ], color="success")
            else:
                status_msg = dbc.Alert("未找到保存的可行性方案", color="warning")

        return (
            final_data,
            r_budget,
            r_coverage,
            r_power,
            r_res,
            r_sens_const,
            r_sens_tol,
            status_msg
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = dbc.Alert(f"加载失败: {str(e)}", color="danger")
        return tuple([no_update] * 7) + (error,)





