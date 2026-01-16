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

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("6.3 Kill分析", className="mb-0")),
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
                dbc.CardHeader(html.H5("6.4 可行 vs 不可行设计对比", className="mb-0")),
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
                dbc.CardHeader(html.H5("6.5 约束敏感性分析", className="mb-0")),
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
                dbc.CardHeader(html.H5("6.6 交互式约束调整 (P2-8)", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "使用滑块实时调整约束条件，立即看到可行设计数量变化"
                    ], color="info", className="mb-3"),

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

                    # 滑块控制区
                    dbc.Row([
                        dbc.Col([
                            dbc.Label("💰 预算限制 (总成本 ≤ )"),
                            dcc.Slider(
                                id='slider-budget-limit',
                                min=3000,
                                max=7000,
                                step=100,
                                value=5000,
                                marks={i: f'{i}M$' for i in range(3000, 7001, 1000)},
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="mb-3"
                            ),
                        ], md=6),

                        dbc.Col([
                            dbc.Label("🌍 最小覆盖 (覆盖范围 ≥ )"),
                            dcc.Slider(
                                id='slider-min-coverage',
                                min=25,
                                max=50,
                                step=1,
                                value=35,
                                marks={i: f'{i}°' for i in range(25, 51, 5)},
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
                                min=2000,
                                max=6000,
                                step=100,
                                value=4000,
                                marks={i: f'{i}W' for i in range(2000, 6001, 1000)},
                                tooltip={"placement": "bottom", "always_visible": True},
                                className="mb-3"
                            ),
                        ], md=6),

                        dbc.Col([
                            dbc.Label("🎯 分辨率目标 (分辨率 ≤ )"),
                            dcc.Slider(
                                id='slider-resolution-target',
                                min=0.5,
                                max=3.0,
                                step=0.1,
                                value=2.0,
                                marks={i/10: f'{i/10}m' for i in range(5, 31, 5)},
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
    [Output('filter-status', 'children', allow_duplicate=True),
     Output('kill-analysis-results', 'children', allow_duplicate=True),
     Output('phase6-feasible-store', 'data', allow_duplicate=True)],
    [Input('btn-filter-designs', 'n_clicks')],
    prevent_initial_call=True
)
def apply_constraints(n_clicks):
    """应用约束 - 集成ConstraintEngine"""
    if not n_clicks:
        return no_update, no_update, no_update

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

        # 1. 从StateManager加载Phase 5数据
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if not _has_valid_data(unified):  # DataFrame使用显式类型检查
            return dbc.Alert("请先在Phase 5运行批量计算！", color="warning"), no_update, None

        # 2. 创建约束引擎
        engine = ConstraintEngine()

        # 添加约束
        engine.add_constraint(Constraint('budget', 'cost_total <= 5000', 'hard'))
        engine.add_constraint(Constraint('min_coverage', 'perf_coverage >= 35', 'hard'))
        engine.add_constraint(Constraint('max_power', 'transmit_power <= 4000', 'hard'))
        engine.add_constraint(Constraint('preferred_resolution', 'perf_resolution <= 2', 'soft'))

        # 3. 应用约束
        unified_filtered = engine.apply_constraints(unified)
        n_feasible = unified_filtered['feasible'].sum()
        n_total = len(unified_filtered)
        feasibility_rate = n_feasible / n_total * 100

        # 4. 保存到StateManager
        state.save('phase6', 'constraints', [c.to_dict() for c in engine.constraints])
        state.save('phase6', 'feasible_designs', unified_filtered[unified_filtered['feasible']])

        # 5. 状态显示
        if feasibility_rate >= 50:
            color = "success"
        elif feasibility_rate >= 20:
            color = "warning"
        else:
            color = "danger"

        status = dbc.Alert([
            html.H5([html.I(className="fas fa-check-circle me-2"), "过滤完成！"], className="alert-heading"),
            html.Hr(),
            html.H4(f"可行方案: {n_feasible} / {n_total}", className="mb-2"),
            html.P([
                dbc.Progress(value=feasibility_rate, label=f"{feasibility_rate:.1f}%",
                           color="success" if feasibility_rate >= 50 else "warning", className="mb-3")
            ]),
            html.P([
                html.Strong("约束数量: "), f"{len(engine.constraints)} (3硬+1软)", html.Br(),
                html.Strong("过滤率: "), f"{100-feasibility_rate:.1f}%"
            ])
        ], color=color)

        # 6. Kill分析
        analysis = engine.analyze_constraints()

        kill_display = dbc.Alert([
            html.H5("Kill分析 - 约束瓶颈识别", className="alert-heading"),
            html.Hr(),
            html.P("识别哪些约束导致了最多的设计被淘汰："),
            dbc.Table.from_dataframe(analysis, striped=True, bordered=True, hover=True)
        ], color="info")

        feasible_json = unified_filtered[unified_filtered['feasible']].to_dict('records')

        return status, kill_display, feasible_json

    except Exception as e:
        error = dbc.Alert(f"过滤失败: {str(e)}", color="danger")
        return error, no_update, None

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

# P1-5功能：约束敏感性分析
@callback(
    Output('constraint-sensitivity-plot', 'figure'),
    Input('btn-constraint-sensitivity', 'n_clicks'),
    [State('select-constraint-sensitivity', 'value'),
     State('slider-tolerance-range', 'value')],
    prevent_initial_call=True
)
def constraint_sensitivity_analysis(n_clicks, constraint_col, tolerance_range):
    """约束敏感性分析 - P1-5核心功能"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import numpy as np
    import pandas as pd

    if not n_clicks:
        return go.Figure()

    try:
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

        # 1. 从StateManager加载数据
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if not _has_valid_data(unified):  # DataFrame使用显式类型检查
            fig = go.Figure()
            fig.add_annotation(
                text="请先在Phase 5运行批量计算！",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="red")
            )
            fig.update_layout(title="约束敏感性分析", height=600)
            return fig

        # 2. 定义基准约束值
        baseline_constraints = {
            'cost_total': 5000,      # ≤ 5000 M$
            'perf_coverage': 35,     # ≥ 35°
            'transmit_power': 4000   # ≤ 4000 W
        }

        # 3. 约束类型（上限或下限）
        constraint_types = {
            'cost_total': 'upper',          # 越小越好，上限约束
            'perf_coverage': 'lower',       # 越大越好，下限约束
            'transmit_power': 'upper'       # 越小越好，上限约束
        }

        baseline_value = baseline_constraints[constraint_col]
        constraint_type = constraint_types[constraint_col]

        # 4. 生成容差变化序列
        tolerance_min, tolerance_max = tolerance_range
        tolerances = np.linspace(tolerance_min, tolerance_max, 21)  # 21个点
        adjusted_values = baseline_value * (1 + tolerances / 100)

        # 5. 对每个调整后的约束值，计算可行设计数量
        feasible_counts = []
        feasibility_ratios = []

        for adjusted_value in adjusted_values:
            if constraint_type == 'upper':
                # 上限约束（如成本、功率）
                feasible = (unified[constraint_col] <= adjusted_value).sum()
            else:
                # 下限约束（如覆盖范围）
                feasible = (unified[constraint_col] >= adjusted_value).sum()

            feasible_counts.append(feasible)
            feasibility_ratios.append(feasible / len(unified) * 100)

        # 6. 识别基准约束下的可行性
        baseline_feasible = feasible_counts[10]  # 中点对应基准值
        baseline_ratio = feasibility_ratios[10]

        # 7. 创建2×2子图布局
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=(
                "约束值 vs 可行设计数量",
                "容差变化 vs 可行性比例",
                "约束敏感度曲线",
                "约束放松建议"
            ),
            specs=[[{'type': 'scatter'}, {'type': 'scatter'}],
                   [{'type': 'scatter'}, {'type': 'table'}]]
        )

        # 子图1：约束值 vs 可行设计数量
        fig.add_trace(
            go.Scatter(
                x=adjusted_values,
                y=feasible_counts,
                mode='lines+markers',
                name='可行设计数量',
                line=dict(color='blue', width=2),
                marker=dict(size=6)
            ),
            row=1, col=1
        )

        # 标记基准值
        fig.add_trace(
            go.Scatter(
                x=[baseline_value],
                y=[baseline_feasible],
                mode='markers',
                name='基准约束',
                marker=dict(size=12, color='red', symbol='star')
            ),
            row=1, col=1
        )

        # 子图2：容差变化 vs 可行性比例
        fig.add_trace(
            go.Scatter(
                x=tolerances,
                y=feasibility_ratios,
                mode='lines+markers',
                name='可行性比例',
                line=dict(color='green', width=2),
                marker=dict(size=6),
                fill='tozeroy',
                fillcolor='rgba(0,255,0,0.1)'
            ),
            row=1, col=2
        )

        # 标记基准值
        fig.add_trace(
            go.Scatter(
                x=[0],
                y=[baseline_ratio],
                mode='markers',
                name='基准可行性',
                marker=dict(size=12, color='red', symbol='star')
            ),
            row=1, col=2
        )

        # 子图3：敏感度曲线（一阶导数近似）
        sensitivities = np.diff(feasibility_ratios) / np.diff(tolerances)
        tolerance_midpoints = (tolerances[:-1] + tolerances[1:]) / 2

        fig.add_trace(
            go.Scatter(
                x=tolerance_midpoints,
                y=sensitivities,
                mode='lines',
                name='敏感度',
                line=dict(color='purple', width=2)
            ),
            row=2, col=1
        )

        # 添加零敏感度参考线
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

        # 子图4：约束放松建议表格
        # 计算推荐的容差调整
        target_ratio = 80  # 目标可行性比例
        if baseline_ratio < target_ratio:
            # 需要放松约束
            idx_above_target = np.where(np.array(feasibility_ratios) >= target_ratio)[0]
            if len(idx_above_target) > 0:
                recommended_tolerance = tolerances[idx_above_target[0]]
                recommended_value = adjusted_values[idx_above_target[0]]
                recommendation = f"放松 {recommended_tolerance:.1f}%"
            else:
                recommendation = "需要放松超过50%"
        else:
            recommendation = "当前约束已足够宽松"

        # 构建表格数据
        table_data = [
            ["基准约束值", f"{baseline_value:.2f}"],
            ["基准可行性", f"{baseline_ratio:.1f}%"],
            ["约束类型", "上限约束" if constraint_type == 'upper' else "下限约束"],
            ["敏感度评级", "高" if abs(sensitivities).mean() > 2 else "中" if abs(sensitivities).mean() > 1 else "低"],
            ["推荐调整", recommendation]
        ]

        fig.add_trace(
            go.Table(
                header=dict(
                    values=["指标", "值"],
                    fill_color='lightblue',
                    align='center',
                    font=dict(size=12, color='black')
                ),
                cells=dict(
                    values=list(zip(*table_data)),
                    fill_color='lavender',
                    align='left',
                    font=dict(size=11)
                )
            ),
            row=2, col=2
        )

        # 8. 更新布局
        constraint_names = {
            'cost_total': '总成本 (M$)',
            'perf_coverage': '覆盖范围 (°)',
            'transmit_power': '发射功率 (W)'
        }

        fig.update_xaxes(title_text=constraint_names[constraint_col], row=1, col=1)
        fig.update_yaxes(title_text="可行设计数量", row=1, col=1)
        fig.update_xaxes(title_text="容差变化 (%)", row=1, col=2)
        fig.update_yaxes(title_text="可行性比例 (%)", row=1, col=2)
        fig.update_xaxes(title_text="容差变化 (%)", row=2, col=1)
        fig.update_yaxes(title_text="敏感度 (Δ可行性%/Δ容差%)", row=2, col=1)

        fig.update_layout(
            title=dict(
                text=f"约束敏感性分析: {constraint_names[constraint_col]}<br><sub>基准值: {baseline_value:.2f} | 容差范围: {tolerance_min}% ~ {tolerance_max}%</sub>",
                x=0.5,
                xanchor='center'
            ),
            height=800,
            showlegend=False
        )

        return fig

    except Exception as e:
        import traceback
        print(f"约束敏感性分析失败: {e}")
        print(traceback.format_exc())

        fig = go.Figure()
        fig.add_annotation(
            text=f"约束敏感性分析失败: {str(e)}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="red")
        )
        fig.update_layout(title="约束敏感性分析 - 生成失败", height=600)
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
    """实时更新可行性统计（P2-8核心功能）"""
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

        # 1. 从StateManager加载数据
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if not _has_valid_data(unified):  # DataFrame使用显式类型检查
            return "---", 0, "secondary", "请先运行Phase 5批量计算"

        # 2. 根据当前滑块值计算可行性
        # 硬约束（必须全部满足）
        feasible_mask = (
            (unified['cost_total'] <= budget_limit) &
            (unified['perf_coverage'] >= min_coverage) &
            (unified['transmit_power'] <= max_power)
        )

        # 软约束（分辨率，不影响可行性，但用于排序）
        # 这里我们将软约束也纳入可行性判断（用于展示）
        feasible_mask = feasible_mask & (unified['perf_resolution'] <= resolution_target)

        n_feasible = feasible_mask.sum()
        n_total = len(unified)
        feasibility_ratio = n_feasible / n_total * 100

        # 3. 颜色编码
        if feasibility_ratio >= 60:
            progress_color = "success"
        elif feasibility_ratio >= 30:
            progress_color = "warning"
        else:
            progress_color = "danger"

        # 4. 返回更新的UI
        return (
            str(n_feasible),
            feasibility_ratio,
            progress_color,
            f"可行性: {feasibility_ratio:.1f}% ({n_feasible}/{n_total})"
        )

    except Exception as e:
        return "错误", 0, "danger", f"计算失败: {str(e)}"
    

# 回调2: 应用调整后的约束并重新过滤
@callback(
    [Output('filter-status', 'children', allow_duplicate=True),
     Output('kill-analysis-results', 'children', allow_duplicate=True),
     Output('phase6-feasible-store', 'data', allow_duplicate=True)],
    [Input('btn-apply-adjusted-constraints', 'n_clicks'),
     Input('btn-filter-designs', 'n_clicks')], # 合并两个按钮的逻辑
    [State('slider-budget-limit', 'value'),
     State('slider-min-coverage', 'value'),
     State('slider-max-power', 'value'),
     State('slider-resolution-target', 'value')],
    prevent_initial_call=True
)
def apply_adjusted_constraints(n_click_adjust, n_click_filter, budget_limit, min_coverage, max_power, resolution_target):
    """
    应用约束过滤逻辑
    功能：
    1. 计算可行性过滤。
    2. 生成 Kill Analysis。
    3. 立即持久化核心数据 (Constraints, Config, Feasible Designs)。
    """
    from dash import ctx
    if not (n_click_adjust or n_click_filter):
        return no_update, no_update, no_update

    try:
        import pandas as pd

        state = get_state_manager()
        # 1. 加载 Phase 5 输入数据
        unified = state.load('phase5', 'unified_results')

        def _has_valid_data(data):
            if data is None: return False
            if isinstance(data, pd.DataFrame): return not data.empty
            if isinstance(data, list): return len(data) > 0
            return False

        if not _has_valid_data(unified):
            return dbc.Alert("请先在Phase 5运行批量计算！", color="warning"), no_update, None

        # 2. 创建约束引擎并应用
        engine = ConstraintEngine()
        engine.add_constraint(Constraint('budget', f'cost_total <= {budget_limit}', 'hard'))
        engine.add_constraint(Constraint('min_coverage', f'perf_coverage >= {min_coverage}', 'hard'))
        engine.add_constraint(Constraint('max_power', f'transmit_power <= {max_power}', 'hard'))
        engine.add_constraint(Constraint('preferred_resolution', f'perf_resolution <= {resolution_target}', 'soft'))

        unified_filtered = engine.apply_constraints(unified)
        n_feasible = unified_filtered['feasible'].sum()
        n_total = len(unified_filtered)
        feasibility_rate = n_feasible / n_total * 100

        # 3. [Core Data] 立即持久化关键结果
        # 保存具体约束定义
        state.save('phase6', 'constraints', [c.to_dict() for c in engine.constraints])
        # 保存可行设计结果集
        state.save('phase6', 'feasible_designs', unified_filtered[unified_filtered['feasible']])
        # 保存生效的配置参数 (用于下次加载恢复基准)
        constraint_config = {
            'budget_limit': budget_limit,
            'min_coverage': min_coverage,
            'max_power': max_power,
            'resolution_target': resolution_target
        }
        state.save('phase6', 'constraint_config', constraint_config)

        # 4. 生成分析报告
        analysis = engine.analyze_constraints()
        kill_display = dbc.Alert([
            html.H5("Kill分析 - 约束瓶颈识别", className="alert-heading"),
            html.Hr(),
            html.P("基于当前约束，识别导致最多设计被淘汰的条件："),
            dbc.Table.from_dataframe(analysis, striped=True, bordered=True, hover=True)
        ], color="info")

        # 5. 生成状态提示
        status = dbc.Alert([
            html.H5([html.I(className="fas fa-check-circle me-2"), "过滤完成 & 已保存"], className="alert-heading"),
            html.Hr(),
            html.P([
                dbc.Progress(value=feasibility_rate, label=f"{feasibility_rate:.1f}%",
                           color="success" if feasibility_rate >= 50 else "warning", className="mb-2"),
                f"可行方案: {n_feasible} / {n_total} (过滤率: {100-feasibility_rate:.1f}%)"
            ])
        ], color="success")

        feasible_json = unified_filtered[unified_filtered['feasible']].to_dict('records')

        return status, kill_display, feasible_json

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = dbc.Alert(f"应用约束失败: {str(e)}", color="danger")
        return error, no_update, None

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
    




