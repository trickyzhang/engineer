"""
系统工程分析平台 - Web界面主应用
System Engineering Analysis Platform - Web Application

基于Dash框架的交互式Web界面，提供完整的8阶段系统工程分析流程。
"""

import sys
sys.path.insert(0, '..')

import dash
from dash import dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from flask import Flask, send_from_directory, Response

# 创建Flask服务器
server = Flask(__name__)

# Flask路由：提供教程文件（正确的MIME type，让浏览器显示而不是下载）
@server.route('/tutorial')
def serve_tutorial():
    """提供教程Markdown文件，设置正确的Content-Type让浏览器显示"""
    import os
    filepath = os.path.join(os.path.dirname(__file__), 'assets', 'tutorial.md')
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    # 返回HTML预格式化显示markdown内容
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>系统工程分析平台 - 使用教程</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; line-height: 1.6; }}
            h1 {{ color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
            h2 {{ color: #28a745; margin-top: 30px; }}
            h3 {{ color: #17a2b8; margin-top: 20px; }}
            ul {{ margin-left: 20px; }}
            li {{ margin-bottom: 8px; }}
            hr {{ border: 1px solid #ccc; margin: 30px 0; }}
            pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <pre style="white-space: pre-wrap; background: none; padding: 0;">{content}</pre>
    </body>
    </html>
    """
    return Response(html_content, mimetype='text/html; charset=utf-8')

# 创建Dash应用
app = dash.Dash(
    __name__,
    server=server,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
    suppress_callback_exceptions=True,
    title="系统工程分析平台",
    update_title="加载中...",
)

# 导入所有页面模块（必须在app创建后导入，以便注册回调）
from pages import dashboard, phase1, phase2, phase3, phase4, phase5, phase6, phase7, phase8, data_management

# 应用布局
app.layout = dbc.Container([
    # 页面标题栏
    dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.I(className="fas fa-satellite fa-2x text-primary me-3"),
                        html.Span("系统工程分析平台", className="h3 mb-0 fw-bold")
                    ], className="d-flex align-items-center")
                ], width="auto"),
                dbc.Col([
                    html.Div([
                        dbc.Badge("v4.0", color="success", className="me-2"),
                        dbc.Badge("Web界面", color="info")
                    ], className="d-flex justify-content-end align-items-center")
                ], width="auto")
            ], justify="between", className="w-100")
        ], fluid=True),
        color="light",
        className="mb-4 shadow-sm"
    ),

    # 主要内容区域
    dcc.Location(id='url', refresh=False),
    # 修复1.1：Dashboard-Phase1联动 - 全局session Store用于跨页面数据传递
    dcc.Store(id='phase1-auto-load-trigger', storage_type='session', data=None),
    dcc.Store(id='phase2-auto-load-trigger', storage_type='session', data=None),  # 新增：Phase 2自动加载触发器

    # 侧边导航栏
    dbc.Row([
        # 左侧导航
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.H5("工作流导航", className="mb-0")),
                dbc.CardBody([
                    dbc.Nav([
                        dbc.NavLink([
                            html.I(className="fas fa-home me-2"),
                            "仪表盘"
                        ], href="/", id="nav-dashboard", active=True),

                        html.Hr(className="my-2"),
                        html.Small("8阶段工作流", className="text-muted ps-3"),

                        dbc.NavLink([
                            html.I(className="fas fa-bullseye me-2"),
                            "Phase 1: 问题定义"
                        ], href="/phase1", id="nav-phase1"),

                        dbc.NavLink([
                            html.I(className="fas fa-project-diagram me-2"),
                            "Phase 2: 物理架构"
                        ], href="/phase2", id="nav-phase2"),

                        dbc.NavLink([
                            html.I(className="fas fa-th me-2"),
                            "Phase 3: 设计空间"
                        ], href="/phase3", id="nav-phase3"),

                        dbc.NavLink([
                            html.I(className="fas fa-sliders-h me-2"),
                            "Phase 4: 效用建模"
                        ], href="/phase4", id="nav-phase4"),

                        dbc.NavLink([
                            html.I(className="fas fa-calculator me-2"),
                            "Phase 5: 多域建模"
                        ], href="/phase5", id="nav-phase5"),

                        dbc.NavLink([
                            html.I(className="fas fa-filter me-2"),
                            "Phase 6: 约束过滤"
                        ], href="/phase6", id="nav-phase6"),

                        dbc.NavLink([
                            html.I(className="fas fa-chart-scatter me-2"),
                            "Phase 7: 权衡空间"
                        ], href="/phase7", id="nav-phase7"),

                        dbc.NavLink([
                            html.I(className="fas fa-trophy me-2"),
                            "Phase 8: 决策分析"
                        ], href="/phase8", id="nav-phase8"),

                        html.Hr(className="my-2"),

                        dbc.NavLink([
                            html.I(className="fas fa-download me-2"),
                            "数据管理"
                        ], href="/data", id="nav-data"),

                    ], vertical=True, pills=True)
                ], className="p-0")
            ], className="shadow-sm")
        ], md=3, className="mb-4"),

        # 右侧内容区
        dbc.Col([
            html.Div(id='page-content')
        ], md=9)
    ]),

    # 全局存储
    dcc.Store(id='platform-state', storage_type='session'),
    dcc.Store(id='current-project', storage_type='session'),

    # 页脚
    html.Footer([
        html.Hr(),
        dbc.Row([
            dbc.Col([
                html.P([
                    "系统工程分析平台 © 2025 | ",
                    html.A("文档", href="#", className="text-decoration-none"),
                    " | ",
                    html.A("GitHub", href="#", className="text-decoration-none")
                ], className="text-muted text-center mb-0")
            ])
        ])
    ], className="mt-5")

], fluid=True, className="px-4 py-3")

# 路由回调
@app.callback(
    Output('page-content', 'children'),
    [Input('url', 'pathname')]
)
def display_page(pathname):
    """根据URL路径显示对应页面"""
    if pathname == '/' or pathname is None:
        return dashboard.layout
    elif pathname == '/phase1':
        return phase1.layout
    elif pathname == '/phase2':
        return phase2.layout
    elif pathname == '/phase3':
        return phase3.layout
    elif pathname == '/phase4':
        return phase4.layout
    elif pathname == '/phase5':
        return phase5.layout
    elif pathname == '/phase6':
        return phase6.layout
    elif pathname == '/phase7':
        return phase7.layout
    elif pathname == '/phase8':
        return phase8.layout
    elif pathname == '/data':
        return data_management.layout
    else:
        return html.Div([
            html.H1("404: 页面未找到", className="text-danger"),
            html.P("您访问的页面不存在"),
            dbc.Button("返回首页", href="/", color="primary")
        ], className="text-center mt-5")

# 导航激活状态回调
@app.callback(
    [Output(f'nav-{page}', 'active') for page in ['dashboard', 'phase1', 'phase2', 'phase3',
                                                     'phase4', 'phase5', 'phase6', 'phase7',
                                                     'phase8', 'data']],
    [Input('url', 'pathname')]
)
def update_nav_active(pathname):
    """更新导航栏激活状态"""
    pages = ['/', '/phase1', '/phase2', '/phase3', '/phase4',
             '/phase5', '/phase6', '/phase7', '/phase8', '/data']
    return [pathname == page for page in pages]

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8050)
