"""
Phase 5: 多域建模
集成ComputationEngine实现真实计算
"""

from dash import html, dcc, callback, Input, Output, State, no_update
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sys
import os
import re
import sklearn
from typing import Tuple, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.computation_engine import CostModel, PerformanceModel, ValueModel, ResultAssembler
from utils.calculation_engine import CalculationEngine
from utils.state_manager import get_state_manager

# 名称清洗辅助函数 (必须与 Phase 4 保持一致)
def sanitize_name(name):
    """
    清洗变量名或属性名，生成合法的 Python 标识符。
    """
    if not name:
        return "unknown"
    clean = re.sub(r'\W', '_', str(name))
    if clean and clean[0].isdigit():
        clean = '_' + clean
    return clean

# ========== Phase 5 UI Layout ==========

layout = dbc.Container([
    dcc.Store(id='phase5-unified-results-store', data=None),
    dcc.Store(id='global-selection-store', data={'selected_ids': []}, storage_type='session'),
    dcc.Store(id='phase5-model-source-store', data=None),
    dcc.Store(id='phase5-ui-state', data={}),

    html.H2([
        html.I(className="fas fa-calculator me-2 text-danger"),
        "Phase 5: 多域建模"
    ], className="mb-4"),

    # 动态模型状态提示
    html.Div(id="model-source-alert", className="mb-4"),

    # ===== 5.1 执行批量评估 =====
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5([
                    html.I(className="fas fa-play-circle me-2"),
                    "5.1 执行批量评估"
                ], className="mb-0")),
                dbc.CardBody([
                    dbc.Button([
                        html.I(className="fas fa-play-circle me-2"),
                        "运行批量计算"
                    ], id="btn-run-evaluation", color="success", size="lg", className="w-100 mb-3"),
                    html.Div(id="evaluation-status")
                ])
            ], className="shadow-sm mb-4")
        ], md=12)
    ]),

    # ===== 5.2 计算结果统计 =====
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("5.2 计算结果统计", className="mb-0")),
                dbc.CardBody([
                    html.Div(id="evaluation-stats") # 这里将包含 Top 50 列表和统计摘要
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("5.3 性能分布可视化", className="mb-0")),
                dbc.CardBody([
                    dcc.Graph(id="performance-distribution", figure={})
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # 回归模型拟合功能
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("5.4 回归建模", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "使用回归分析探索设计变量与性能指标之间的关系"
                    ], color="info", className="mb-3"),

                    dbc.Label("自变量（X）- 可多选"),
                    dcc.Dropdown(
                        id='select-independent-vars',
                        options=[], # 动态填充
                        multi=True,
                        placeholder="选择自变量 (通常为设计变量)...",
                        className="mb-3"
                    ),

                    dbc.Label("因变量（Y）"),
                    dcc.Dropdown(
                        id='select-dependent-var',
                        options=[], # 动态填充
                        placeholder="选择因变量 (通常为属性或MAU)...",
                        className="mb-3"
                    ),

                    dbc.Label("回归类型"),
                    dbc.RadioItems(
                        id='radio-regression-type',
                        options=[
                            {'label': '线性回归', 'value': 'linear'},
                            {'label': '多项式回归（2次）', 'value': 'polynomial'},
                            {'label': '岭回归（Ridge）', 'value': 'ridge'}
                        ],
                        value='linear',
                        className="mb-3"
                    ),

                    dbc.Button([
                        html.I(className="fas fa-chart-line me-2"),
                        "拟合模型"
                    ], id='btn-fit-regression', color="primary", className='w-100 mb-3'),

                    html.Div(id='regression-results')
                ])
            ], className="shadow-sm mb-4")
        ], md=12),

        # 箱线图对比功能
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("5.5 箱线图分析", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "箱线图显示数据分布的五数概括"
                    ], color="info", className="mb-3"),

                    dbc.Label("选择指标"),
                    dbc.Select(
                        id='select-metric-boxplot',
                        options=[], # 动态填充
                        placeholder="选择要分析的指标...",
                        className="mb-3"
                    ),

                    dbc.Button([
                        html.I(className="fas fa-chart-bar me-2"),
                        "生成箱线图"
                    ], id='btn-create-boxplot', color="success", className='w-100 mb-3'),

                    dcc.Graph(id='box-whisker-plot', figure={}, config={'displayModeBar': True})
                ])
            ], className="shadow-sm mb-4")
        ], md=12)
    ]),

    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("5.6 回归拟合可视化", className="mb-0")),
                dbc.CardBody([
                    dcc.Graph(id='regression-plot', figure={}, config={'displayModeBar': True},
                             style={'height': '500px'})
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    # 性能分布统计增强
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("5.7 性能分布统计分析", className="mb-0")),
                dbc.CardBody([
                    dbc.Alert([
                        html.I(className="fas fa-info-circle me-2"),
                        "深度统计分析：百分位数、相关性矩阵、异常值检测"
                    ], color="info", className="mb-3"),

                    dbc.Button([
                        html.I(className="fas fa-chart-pie me-2"),
                        "生成统计报告"
                    ], id='btn-generate-stats-report', color="success", className="w-100 mb-3"),

                    html.Div(id='stats-report-output')
                ])
            ], className="shadow-sm mb-4")
        ], md=12),

        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("5.8 指标相关性热图", className="mb-0")),
                dbc.CardBody([
                    dcc.Graph(id='correlation-heatmap', figure={}, config={'displayModeBar': True})
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
                            "保存Phase 5数据"
                        ], id="btn-save-phase5", color="success", className="me-2"),
                        dbc.Button([
                            html.I(className="fas fa-upload me-2"),
                            "加载Phase 5数据"
                        ], id="btn-load-phase5", color="info")
                    ]),
                    html.Div(id="phase5-save-status", className="mt-3")
                ])
            ], className="shadow-sm mb-4")
        ])
    ]),

    dbc.Row([
        dbc.Col([
            dbc.ButtonGroup([
                dbc.Button("上一步: Phase 4", href="/phase4", color="secondary", outline=True),
                dbc.Button("下一步: Phase 6", href="/phase6", color="primary")
            ], className="w-100")
        ])
    ])
], fluid=True)


# ========== 回调函数 ==========

# [新增回调] 动态更新下拉菜单选项 (解决硬编码问题)
@callback(
    [Output('select-independent-vars', 'options'),
     Output('select-dependent-var', 'options'),
     Output('select-metric-boxplot', 'options')],
    [Input('phase5-unified-results-store', 'data')]
)
def update_analysis_dropdowns(unified_results):
    """
    当计算结果更新时，动态填充后续分析步骤的所有下拉菜单
    排除非数值列和 ID 列
    """
    if not unified_results:
        return [], [], []
    
    try:
        import pandas as pd
        if isinstance(unified_results, list):
            df = pd.DataFrame(unified_results)
        elif isinstance(unified_results, dict) and 'data' in unified_results:
            df = pd.DataFrame(unified_results['data'])
        else:
            return [], [], []
            
        if df.empty:
            return [], [], []

        # 筛选数值列
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        
        # 排除 ID 列
        valid_cols = [c for c in numeric_cols if c != 'design_id']
        
        # 生成选项列表
        options = [{'label': c, 'value': c} for c in valid_cols]
        
        return options, options, options

    except Exception as e:
        print(f"更新下拉菜单失败: {e}")
        return [], [], []


@callback(
    [Output('evaluation-status', 'children'),
     Output('evaluation-stats', 'children'),
     Output('performance-distribution', 'figure'),
     Output('phase5-unified-results-store', 'data', allow_duplicate=True)],
    [Input('btn-run-evaluation', 'n_clicks')],
    prevent_initial_call=True
)
def run_batch_evaluation(n_clicks):
    """
    批量评估 - 修复版执行流
    """
    if not n_clicks:
        return no_update, no_update, no_update, no_update

    try:
        import pandas as pd
        state = get_state_manager()
        
        # --- 1. 加载数据源 ---
        alternatives = state.load('phase3', 'alternatives')
        
        df_inputs = pd.DataFrame()
        if isinstance(alternatives, list):
            df_inputs = pd.DataFrame(alternatives)
        elif isinstance(alternatives, dict) and 'data' in alternatives:
            df_inputs = pd.DataFrame(alternatives['data'])
        elif isinstance(alternatives, pd.DataFrame):
            df_inputs = alternatives
            
        if df_inputs.empty:
             return dbc.Alert("❌ Phase 3 设计空间为空！请先在 Phase 3 生成数据。", color="warning"), no_update, {}, None

        # --- 2. 加载 Phase 4 定义的所有模型 ---
        perf_models_dict = state.load("phase4", "perf_models_dict") or {}
        utility_funcs_dict = state.load("phase4", "utility_functions_dict") or {}
        weights_mau_code = state.load("phase4", "weights_mau_code")

        if not weights_mau_code:
             return dbc.Alert(f"❌ Phase 4 MAU模型未定义，无法执行计算。", color="danger"), no_update, {}, None

        # --- 3. 编译执行环境 ---
        exec_ctx = {}
        
        try:
            for code in perf_models_dict.values():
                exec(code, exec_ctx)
            for code in utility_funcs_dict.values():
                exec(code, exec_ctx)
            exec(weights_mau_code, exec_ctx)
            
            if 'calculate_mau' not in exec_ctx: 
                raise ValueError("MAU 模型代码中缺少 'calculate_mau' 函数定义")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return dbc.Alert(f"❌ 代码编译错误: {str(e)}", color="danger"), no_update, {}, None

        # --- 4. 批量执行计算循环 ---
        results = []
        calc_mau = exec_ctx['calculate_mau']
        
        metric_funcs = {}
        for metric in perf_models_dict.keys():
            safe_metric = sanitize_name(metric)
            func_name = f"calculate_{safe_metric}"
            if func_name in exec_ctx:
                metric_funcs[metric] = exec_ctx[func_name]

        for idx, row in df_inputs.iterrows():
            row_context = {k: v for k, v in row.to_dict().items() if k != 'design_id'}
            
            # Step 4.1: 属性计算
            for metric, func in metric_funcs.items():
                try:
                    val = func(**row_context)
                    row_context[metric] = val
                except Exception as e:
                    row_context[metric] = 0.0
            
            # Step 4.2: MAU 计算
            try:
                mau_val = float(calc_mau(**row_context))
            except Exception as e:
                mau_val = 0.0
            
            row_context['MAU'] = mau_val
            
            if 'design_id' in row:
                row_context['design_id'] = row['design_id']
            else:
                row_context['design_id'] = idx
            
            results.append(row_context)

        # --- 5. 结果处理 ---
        unified_df = pd.DataFrame(results)
        unified_records = unified_df.to_dict('records')
        state.save('phase5', 'unified_results', unified_records)

        # --- 6. 生成 UI 反馈 ---
        status = dbc.Alert([
            html.H5([html.I(className="fas fa-check-circle me-2"), "计算完成"], className="alert-heading"),
            html.P(f"成功评估了 {len(unified_df)} 个设计方案。结果已保存。")
        ], color="success")

        # === 新增功能：5.2 数据预览列表 (Top 50) ===
        # 将 design_id 移到第一列
        cols = unified_df.columns.tolist()
        if 'design_id' in cols:
            cols.insert(0, cols.pop(cols.index('design_id')))
            preview_df = unified_df[cols].head(50) # 取前50行
        else:
            preview_df = unified_df.head(50)

        # 生成 Table Header
        table_header = [html.Th(col) for col in preview_df.columns]
        
        # 生成 Table Rows
        table_rows = []
        for i in range(len(preview_df)):
            row_cells = []
            for col in preview_df.columns:
                val = preview_df.iloc[i][col]
                # 格式化数值
                if isinstance(val, (int, float)):
                    display_val = f"{val:.4f}"
                else:
                    display_val = str(val)
                row_cells.append(html.Td(display_val))
            table_rows.append(html.Tr(row_cells))

        preview_table_component = html.Div([
            html.H6(f"数据预览 (前 {len(preview_df)} 条)", className="text-primary mt-2"),
            dbc.Table(
                [html.Thead(html.Tr(table_header)), html.Tbody(table_rows)],
                bordered=True, hover=True, striped=True, responsive=True, size='sm',
                style={'maxHeight': '400px', 'overflowY': 'auto'} # 增加滚动条
            ),
            html.Hr()
        ])

        # === 统计摘要表 ===
        numeric_cols = unified_df.select_dtypes(include=['float64', 'int64']).columns
        stats_cols = [c for c in numeric_cols if c != 'design_id']
        sorted_cols = ['MAU'] + [c for c in stats_cols if c != 'MAU']
        
        stats_rows = []
        for col in sorted_cols[:15]: 
            if col in unified_df.columns:
                series = unified_df[col]
                stats_rows.append(html.Tr([
                    html.Td(col),
                    html.Td(f"{series.min():.4f}"),
                    html.Td(f"{series.max():.4f}"),
                    html.Td(f"{series.mean():.4f}")
                ]))
        
        stats_summary_component = html.Div([
            html.H6("关键指标统计摘要", className="text-info"),
            dbc.Table([
                html.Thead(html.Tr([html.Th("指标"), html.Th("Min"), html.Th("Max"), html.Th("Mean")])),
                html.Tbody(stats_rows)
            ], bordered=True, hover=True, size='sm')
        ])

        # 组合 5.2 的输出内容
        stats_output_container = html.Div([
            preview_table_component,
            stats_summary_component
        ])

        # 分布图
        fig = make_subplots(rows=1, cols=2, subplot_titles=("MAU 分布", "属性分布示例"))
        fig.add_trace(go.Histogram(x=unified_df['MAU'], name='MAU', marker_color='green'), row=1, col=1)
        second_col = next((c for c in sorted_cols if c != 'MAU'), None)
        if second_col:
            fig.add_trace(go.Histogram(x=unified_df[second_col], name=second_col), row=1, col=2)
            fig.update_xaxes(title_text=second_col, row=1, col=2)
        else:
            fig.add_annotation(text="无其他属性", row=1, col=2, showarrow=False)
        fig.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))

        return status, stats_output_container, fig, unified_records

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = dbc.Alert([
            html.H4("计算流程崩溃", className="alert-heading"),
            html.Pre(str(e))
        ], color="danger")
        return error, no_update, {}, None
    

# P1-1 回归模型拟合回调
@callback(
    [Output('regression-results', 'children'),
     Output('regression-plot', 'figure')],
    Input('btn-fit-regression', 'n_clicks'),
    [State('select-independent-vars', 'value'),
     State('select-dependent-var', 'value'),
     State('radio-regression-type', 'value')],
    prevent_initial_call=True
)
def fit_regression_model(n_clicks, X_cols, y_col, reg_type):
    """拟合回归模型 (已修复硬编码)"""
    if not n_clicks or not X_cols or not y_col:
        return dbc.Alert("请选择自变量和因变量！", color="warning"), {}

    try:
        from sklearn.linear_model import LinearRegression, Ridge
        from sklearn.preprocessing import PolynomialFeatures
        from sklearn.metrics import r2_score, mean_squared_error
        import numpy as np
        import pandas as pd

        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if unified is None:
            return dbc.Alert("请先在Phase 5运行批量计算！", color="warning"), {}
        
        if isinstance(unified, list):
            unified = pd.DataFrame(unified)
        
        if unified.empty:
             return dbc.Alert("数据为空", color="warning"), {}

        # 检查列是否存在 (防止选择后重新计算导致列丢失)
        missing_cols = [c for c in X_cols + [y_col] if c not in unified.columns]
        if missing_cols:
             return dbc.Alert(f"数据中缺少列: {', '.join(missing_cols)}，请重新运行计算或刷新页面。", color="danger"), {}

        X = unified[X_cols].values
        y = unified[y_col].values

        # 3. 根据类型拟合模型
        if reg_type == 'linear':
            model = LinearRegression()
            X_transformed = X
            model.fit(X_transformed, y)
            y_pred = model.predict(X_transformed)
            model_name = "线性回归"

        elif reg_type == 'polynomial':
            poly = PolynomialFeatures(degree=2)
            X_transformed = poly.fit_transform(X)
            model = LinearRegression()
            model.fit(X_transformed, y)
            y_pred = model.predict(X_transformed)
            model_name = "多项式回归（2次）"

        elif reg_type == 'ridge':
            model = Ridge(alpha=1.0)
            X_transformed = X
            model.fit(X_transformed, y)
            y_pred = model.predict(X_transformed)
            model_name = "岭回归（Ridge）"

        # 4. 计算性能指标
        r2 = r2_score(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        mae = np.mean(np.abs(y - y_pred))

        # 5. 构建回归方程字符串
        equation = f"{y_col} = "
        if reg_type in ['linear', 'ridge']:
            equation += f"{model.intercept_:.4f}"
            for i, coef in enumerate(model.coef_):
                var_name = X_cols[i] if i < len(X_cols) else f"X{i}"
                equation += f" + ({coef:.4f}) × {var_name}"
        else:
            equation += "多项式函数（2次）"

        # 6. 生成结果显示
        if r2 > 0.9: badge_color = "success"; badge_text = "拟合优秀"
        elif r2 > 0.7: badge_color = "warning"; badge_text = "拟合良好"
        else: badge_color = "danger"; badge_text = "拟合一般"

        results = dbc.Card([
            dbc.CardHeader(html.H5(f"{model_name}结果", className="mb-0")),
            dbc.CardBody([
                html.P([html.Strong("回归方程:")]),
                html.P(equation, className="text-monospace", style={'fontSize': '0.9em', 'wordBreak': 'break-all'}),
                html.Hr(),
                html.P([
                    dbc.Badge(f"R² = {r2:.4f}", color=badge_color, className="me-2"),
                    dbc.Badge(badge_text, color=badge_color)
                ]),
                html.P([
                    html.Strong("RMSE: "), f"{rmse:.4f}", html.Br(),
                    html.Strong("MAE: "), f"{mae:.4f}", html.Br(),
                    html.Strong("样本数: "), f"{len(y)}"
                ])
            ])
        ], color="light")

        # 7. 生成拟合图
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=y, y=y_pred, mode='markers', name='数据点',
            marker=dict(size=6, color=unified['MAU'] if 'MAU' in unified.columns else 'blue', colorscale='Viridis', showscale=True),
            text=[str(i) for i in range(len(y))],
            hovertemplate='ID: %{text}<br>实际: %{x:.2f}<br>预测: %{y:.2f}<extra></extra>'
        ))
        
        min_val, max_val = min(y.min(), y_pred.min()), max(y.max(), y_pred.max())
        fig.add_trace(go.Scatter(x=[min_val, max_val], y=[min_val, max_val], mode='lines', name='理想线', line=dict(dash='dash', color='red')))

        fig.update_layout(
            title=f"{model_name}拟合 (R²={r2:.3f})",
            xaxis_title=f"实际 {y_col}",
            yaxis_title=f"预测 {y_col}",
            height=500
        )

        return results, fig

    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"回归拟合失败: {str(e)}", color="danger"), {}

# P1-2 箱线图生成回调
@callback(
    Output('box-whisker-plot', 'figure'),
    Input('btn-create-boxplot', 'n_clicks'),
    State('select-metric-boxplot', 'value'),
    prevent_initial_call=True
)
def create_box_whisker_plot(n_clicks, metric):
    """创建箱线图 (已修复硬编码)"""
    if not n_clicks or not metric:
        return no_update

    try:
        import pandas as pd
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if unified is None:
             return go.Figure()
        
        if isinstance(unified, list): unified = pd.DataFrame(unified)
        
        if metric not in unified.columns:
             return go.Figure(layout=dict(title=f"指标 {metric} 不存在"))

        data = unified[metric]
        
        fig = go.Figure()
        fig.add_trace(go.Box(
            y=data, name=metric, boxmean='sd',
            marker=dict(color='rgb(107, 174, 214)'),
            line=dict(color='rgb(31, 119, 180)', width=2)
        ))

        fig.update_layout(
            title=f"{metric} 箱线图 (N={len(data)})",
            yaxis_title=metric,
            height=450,
            showlegend=False
        )
        return fig

    except Exception as e:
        return go.Figure(layout=dict(title=f"错误: {str(e)}"))

# P2-7: 性能分布统计增强
@callback(
    [Output('stats-report-output', 'children'),
     Output('correlation-heatmap', 'figure')],
    [Input('btn-generate-stats-report', 'n_clicks')],
    prevent_initial_call=True
)
def generate_statistics_report(n_clicks):
    """生成深度统计分析报告 (修复 dbc.Div 报错)"""
    if not n_clicks:
        return no_update, no_update

    try:
        import pandas as pd
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if unified is None:
            return dbc.Alert("请先运行计算！", color="warning"), go.Figure()
        
        if isinstance(unified, list): unified = pd.DataFrame(unified)
        if unified.empty: return dbc.Alert("数据为空", color="warning"), go.Figure()

        # 动态获取数值列
        numeric_df = unified.select_dtypes(include=['float64', 'int64'])
        metric_cols = [c for c in numeric_df.columns if c != 'design_id']
        
        if not metric_cols:
             return dbc.Alert("未检测到数值型指标", color="warning"), go.Figure()

        # 生成统计表
        percentiles = [10, 25, 50, 75, 90]
        percentile_rows = []
        
        for col in metric_cols:
            row = [html.Td(col)]
            for p in percentiles:
                row.append(html.Td(f"{unified[col].quantile(p/100):.3f}"))
            percentile_rows.append(html.Tr(row))

        percentile_table = dbc.Table([
            html.Thead(html.Tr([html.Th("指标")] + [html.Th(f"P{p}") for p in percentiles])),
            html.Tbody(percentile_rows)
        ], bordered=True, size='sm', striped=True, hover=True)

        # 尝试进行正态性检验 (依赖 scipy)
        normality_content = html.Div()
        try:
            from scipy import stats
            normality_rows = []
            for col in metric_cols:
                clean_series = unified[col].dropna()
                if len(clean_series) < 3: continue
                
                # 根据样本量选择检验方法
                if len(unified) < 5000:
                    stat, p_value = stats.shapiro(clean_series)
                else:
                    stat, p_value = stats.kstest(clean_series, 'norm')

                is_normal = p_value > 0.05
                normality_rows.append(html.Tr([
                    html.Td(col),
                    html.Td(f"{stat:.4f}"),
                    html.Td(f"{p_value:.4f}"),
                    html.Td(dbc.Badge(
                        "是" if is_normal else "否", 
                        color="success" if is_normal else "warning"
                    ))
                ]))
            
            if normality_rows:
                normality_table = dbc.Table([
                    html.Thead(html.Tr([html.Th("指标"), html.Th("统计量"), html.Th("P值"), html.Th("正态分布?")])),
                    html.Tbody(normality_rows)
                ], bordered=True, size='sm', striped=True)
                
                normality_content = html.Div([
                    html.H6("📈 正态性检验 (Shapiro-Wilk/KS)", className="mt-4"),
                    normality_table
                ])
        except ImportError:
            normality_content = html.Div("提示: 安装 scipy 库可查看正态性检验结果", className="text-muted small mt-2")

        # 相关性热图
        corr_matrix = unified[metric_cols].corr()
        corr_fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=metric_cols,
            y=metric_cols,
            colorscale='RdBu_r', zmid=0,
            text=corr_matrix.values, texttemplate='%{text:.2f}',
            colorbar=dict(title="Corr")
        ))
        corr_fig.update_layout(title="指标相关性矩阵", height=500 + len(metric_cols)*10)

        stats_report = html.Div([
            dbc.Alert([
                html.H5("统计分析摘要", className="alert-heading"),
                html.Hr(),
                html.H6("📊 百分位数分布"),
                percentile_table,
                normality_content
            ], color="light", className="border")
        ])

        return stats_report, corr_fig

    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"生成失败: {str(e)}", color="danger"), go.Figure()

# 全局刷选响应
@callback(
    Output('performance-distribution', 'figure', allow_duplicate=True),
    Input('global-selection-store', 'data'),
    State('performance-distribution', 'figure'),
    prevent_initial_call=True
)
def highlight_phase5_selection(selection_data, current_figure):
    """在Phase 5性能分布图中高亮显示全局选中的设计"""
    if not selection_data or not current_figure:
        return no_update

    selected_ids = selection_data.get('selected_ids', [])
    if not selected_ids:
        return no_update

    try:
        state = get_state_manager()
        unified = state.load('phase5', 'unified_results')

        if unified is None or (isinstance(unified, pd.DataFrame) and unified.empty):
            return no_update

        import plotly.graph_objects as go
        fig = go.Figure(current_figure)

        fig.data = [trace for trace in fig.data if trace.name != 'Selected']

        selected_indices = [i for i in selected_ids if i < len(unified)]

        if selected_indices and len(fig.data) > 0:
            main_trace = fig.data[0]
            if hasattr(main_trace, 'x') and hasattr(main_trace, 'y'):
                selected_x = [main_trace.x[i] if i < len(main_trace.x) else None for i in selected_indices]
                selected_y = [main_trace.y[i] if i < len(main_trace.y) else None for i in selected_indices]

                valid_points = [(x, y) for x, y in zip(selected_x, selected_y) if x is not None and y is not None]

                if valid_points:
                    selected_x_clean, selected_y_clean = zip(*valid_points)
                    fig.add_trace(go.Scatter(
                        x=selected_x_clean,
                        y=selected_y_clean,
                        mode='markers',
                        name='Selected',
                        marker=dict(
                            size=15,
                            color='rgba(255,0,0,0.7)',
                            symbol='circle-open',
                            line=dict(width=3, color='red')
                        ),
                        hovertemplate='<b>选中设计 #%{text}</b><extra></extra>',
                        text=[str(i) for i in selected_indices]
                    ))

        fig.add_annotation(
            text=f"✓ 已选中 {len(selected_ids)} 个设计",
            xref="paper", yref="paper",
            x=0.02, y=0.98,
            showarrow=False,
            bgcolor="rgba(255,0,0,0.1)",
            bordercolor="red",
            borderwidth=2,
            font=dict(size=12, color="red"),
            align="left"
        )

        return fig

    except Exception as e:
        print(f"Phase 5全局刷选高亮失败: {e}")
        return no_update

# 模型来源检测
@callback(
    Output('model-source-alert', 'children'),
    Input('url', 'pathname'),
    prevent_initial_call=False
)
def display_model_source_status(pathname):
    """检测并显示当前使用的模型来源 (适配 Phase 4 统一模型存储架构)"""
    from dash import no_update
    
    if pathname != '/phase5':
        return no_update

    try:
        import pandas as pd
        state = get_state_manager()

        def _has_valid_data(data):
            if data is None: return False
            if isinstance(data, pd.DataFrame): return not data.empty
            if isinstance(data, dict): return len(data) > 0
            if isinstance(data, str): return len(data.strip()) > 0
            return bool(data)

        # [核心修改] Phase 4 已将所有属性计算（含成本）统一存入 perf_models_dict
        perf_models_dict = state.load('phase4', 'perf_models_dict')

        has_models = _has_valid_data(perf_models_dict)

        if has_models:
            model_names = list(perf_models_dict.keys())
            model_count = len(model_names)
            
            model_details = [
                f"✅ 已加载 {model_count} 个属性计算模型 (来自 Phase 4 4.1):",
                html.Br(),
                html.Span(", ".join(model_names), className="text-muted small")
            ]

            return dbc.Alert([
                html.H5([
                    html.I(className="fas fa-check-circle me-2"),
                    "模型加载就绪"
                ], className="alert-heading mb-3"),
                html.P([
                    html.Strong("当前模型状态:"), html.Br(),
                    *model_details
                ], className="mb-2"),
                html.Hr(),
                html.P([
                    html.I(className="fas fa-info-circle me-2"),
                    "如需修改计算逻辑，请返回 ",
                    html.A("Phase 4", href="/phase4", className="alert-link"),
                    " 进行编辑。"
                ], className="mb-0 small")
            ], color="success", className="mb-4")

        else:
            return dbc.Alert([
                html.H5([
                    html.I(className="fas fa-times-circle me-2"),
                    "未检测到计算模型"
                ], className="alert-heading mb-3"),
                html.P([
                    html.Strong("当前无法进行评估计算。"), html.Br(),
                    "系统未在 Phase 4 中检测到任何有效的属性计算模型（成本或性能）。"
                ], className="mb-2"),
                html.Hr(),
                html.P([
                    html.I(className="fas fa-arrow-right me-2"),
                    "请前往 ",
                    html.A("Phase 4: 效用与偏好建模", href="/phase4", className="alert-link fw-bold"),
                    " (4.1 步骤) 定义计算逻辑并点击“保存函数”。"
                ], className="mb-0")
            ], color="danger", className="mb-4")

    except Exception as e:
        import traceback
        return dbc.Alert([
            html.I(className="fas fa-exclamation-triangle me-2"),
            f"模型状态检测失败: {str(e)}"
        ], color="danger", className="mb-4")
    

# ===== 自动保存 UI 状态 (新增) =====
@callback(
    [Output('phase5-save-status', 'children', allow_duplicate=True),
     Output('phase5-ui-state', 'data', allow_duplicate=True)], # 同步前端 Store
    [Input('select-independent-vars', 'value'),
     Input('select-dependent-var', 'value'),
     Input('radio-regression-type', 'value'),
     Input('select-metric-boxplot', 'value')],
    prevent_initial_call=True
)
def auto_save_phase5_ui(indep_vars, dep_var, reg_type, boxplot_metric):
    """自动保存分析配置 UI 状态 (增强版：防空值覆盖 + 双写Store)"""
    from dash import ctx
    
    # 1. 触发校验
    if not ctx.triggered:
        return no_update, no_update
        
    state = get_state_manager()
    
    # 2. 读取旧状态
    current_ui = state.load('phase5', 'ui_state') or {}
    
    # 3. 准备更新 (仅当值非 None 时更新，防止初始化覆盖)
    # 注意：对于多选下拉框，[] 是有效值（表示清空），但 None 表示未初始化
    updates = {}
    
    if indep_vars is not None:
        updates['regression_independent_vars'] = indep_vars
        
    if dep_var is not None:
        updates['regression_dependent_var'] = dep_var
        
    if reg_type is not None:
        updates['regression_type'] = reg_type
        
    if boxplot_metric is not None:
        updates['boxplot_metric'] = boxplot_metric
        
    if not updates:
        return no_update, no_update

    current_ui.update(updates)
    
    # 4. 执行保存
    state.save('phase5', 'ui_state', current_ui)
    
    return no_update, current_ui

# ===== 数据管理回调：加载/保存 (增强版) =====
@callback(
    [Output('phase5-unified-results-store', 'data', allow_duplicate=True),
     Output('select-independent-vars', 'value'),
     Output('select-dependent-var', 'value'),
     Output('radio-regression-type', 'value'),
     Output('select-metric-boxplot', 'value'),
     Output('phase5-save-status', 'children', allow_duplicate=True),
     Output('phase5-ui-state', 'data', allow_duplicate=True)], # 注入前端 Store
    [Input('btn-load-phase5', 'n_clicks'),
     Input('url', 'pathname')],
    prevent_initial_call='initial_duplicate'
)
def load_phase5_data(n_clicks, pathname):
    """加载 Phase 5 数据并恢复现场 (增强版：同步恢复 UI 组件和 UI State Store)"""
    from dash import ctx
    import pandas as pd
    
    triggered_by_button = ctx.triggered_id == 'btn-load-phase5' and n_clicks
    triggered_by_url = ctx.triggered_id == 'url' and pathname == '/phase5'
    is_initial = not ctx.triggered_id and pathname == '/phase5'

    if not (triggered_by_button or triggered_by_url or is_initial):
        return tuple([no_update] * 7)

    try:
        state = get_state_manager()
        
        # 1. 加载核心数据
        unified_results_df = state.load('phase5', 'unified_results')
        
        # 2. 加载 UI 状态
        ui_state = state.load('phase5', 'ui_state') or {}
        
        # 3. 恢复 UI 值 (优先用保存的状态)
        r_indep = ui_state.get('regression_independent_vars', no_update)
        r_dep = ui_state.get('regression_dependent_var', no_update)
        r_reg_type = ui_state.get('regression_type', 'linear') 
        r_boxplot = ui_state.get('boxplot_metric', 'cost_total') 

        # 4. 处理 DataFrame -> JSON 转换
        final_results = no_update
        has_data = False
        
        if unified_results_df is not None:
            if isinstance(unified_results_df, pd.DataFrame) and not unified_results_df.empty:
                 final_results = unified_results_df.to_dict('records')
                 has_data = True
            elif isinstance(unified_results_df, list) and len(unified_results_df) > 0:
                 final_results = unified_results_df
                 has_data = True

        # 5. 生成状态提示
        status_msg = None
        if has_data:
            if triggered_by_button:
                count = len(final_results)
                status_msg = dbc.Alert([
                    html.I(className="fas fa-check-circle me-2"),
                    f"加载成功: {count} 条计算结果 + 分析配置"
                ], color="success")
            else:
                pass # 自动加载时不打扰
        elif triggered_by_button:
            status_msg = dbc.Alert([
                html.I(className="fas fa-exclamation-triangle me-2"),
                "未找到保存的计算结果"
            ], color="warning")

        # 返回值顺序必须对应 Output
        return (
            final_results,  # 1. unified-results
            r_indep,        # 2. independent-vars
            r_dep,          # 3. dependent-var
            r_reg_type,     # 4. regression-type
            r_boxplot,      # 5. boxplot-metric
            status_msg,     # 6. save-status
            ui_state        # 7. ui-state (Store)
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        error = dbc.Alert(f"❌ 加载失败: {str(e)}", color="danger")
        return tuple([no_update] * 6) + (error,)
    

@callback(
    Output('phase5-save-status', 'children', allow_duplicate=True), # [注意] 必须加 allow_duplicate
    Input('btn-save-phase5', 'n_clicks'),
    [State('phase5-unified-results-store', 'data'),
     State('select-independent-vars', 'value'),
     State('select-dependent-var', 'value'),
     State('radio-regression-type', 'value'),
     State('select-metric-boxplot', 'value'),
     State('phase5-ui-state', 'data')],
    prevent_initial_call=True
)
def save_phase5_data(n_clicks, unified_results, indep_vars, dep_var, reg_type, boxplot_metric, current_ui_state):
    """
    手动保存 Phase 5 数据 (Core Data + UI State)
    """
    if not n_clicks:
        return no_update

    try:
        state = get_state_manager()
        
        # 1. 保存计算结果 (Core Data)
        if unified_results:
            if isinstance(unified_results, dict) and 'data' in unified_results:
                data_to_save = unified_results['data']
            else:
                data_to_save = unified_results
            state.save('phase5', 'unified_results', data_to_save)

        # 2. 保存 UI 状态
        # 优先使用 callback 传入的实时值，如果没有则回退到 store 中的值
        ui_state_to_save = current_ui_state or {}
        
        ui_updates = {
            'regression_independent_vars': indep_vars,
            'regression_dependent_var': dep_var,
            'regression_type': reg_type,
            'boxplot_metric': boxplot_metric,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        
        # 更新状态
        ui_state_to_save.update(ui_updates)
        state.save('phase5', 'ui_state', ui_state_to_save)

        count = len(data_to_save) if unified_results else 0
        
        return dbc.Alert([
            html.I(className="fas fa-check-circle me-2"),
            f"Phase 5 数据已保存: {count} 条评估结果 + 分析配置"
        ], color="success")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return dbc.Alert(f"保存失败: {str(e)}", color="danger")