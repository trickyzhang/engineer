#!/usr/bin/env python
"""
启动脚本 - 系统工程分析平台Web界面
"""

import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, server

if __name__ == '__main__':
    print("=" * 60)
    print("系统工程分析平台 - Web界面")
    print("=" * 60)
    print("\n启动信息:")
    print(f"  - 访问地址: http://localhost:8050")
    print(f"  - 调试模式: 已开启")
    print(f"  - Python版本: {sys.version.split()[0]}")
    print("\n按 Ctrl+C 停止服务器")
    print("=" * 60)
    print()

    app.run(
        debug=True,
        host='0.0.0.0',
        port=8050
    )
