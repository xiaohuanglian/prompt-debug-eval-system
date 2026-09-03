#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prompt 自动化调试与评测系统 - GUI 桌面程序入口
==============================================
基于 PyQt5 的图形界面，实现完整的 Prompt 调试与评测全流程。

使用方法:
    1. 安装依赖: pip install -r requirements.txt
    2. 配置 API Key: 编辑 Virtual-Coach-main/code/models/api_keys.py
    3. 生成模型调用文件:
       cd Virtual-Coach-main/code/utils
       python auto_generate_llm_call.py
    4. 启动 GUI:
       cd gui_app
       python main.py
"""

import os
import sys
import traceback

# Ensure the gui_app directory is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# Ensure Virtual-Coach-main is importable
PROJECT_ROOT = os.path.normpath(
    os.path.join(CURRENT_DIR, "..", "Virtual-Coach-main")
)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Verify critical paths exist
API_KEYS_PATH = os.path.join(PROJECT_ROOT, "code", "models", "api_keys.py")
if not os.path.exists(API_KEYS_PATH):
    print(f"\n{'=' * 60}")
    print(f"  警告: API 配置文件不存在!")
    print(f"  请先创建: {API_KEYS_PATH}")
    print(f"  参考模板: {API_KEYS_PATH.replace('api_keys.py', 'api_keys_template.py')}")
    print(f"{'=' * 60}\n")


def main():
    try:
        from prompt_gui.app import run_app
        run_app()
    except ImportError as e:
        print(f"导入错误: {e}")
        print("\n请确保已安装依赖:")
        print("  pip install -r requirements.txt")
        print(f"\n完整错误信息:\n{traceback.format_exc()}")
        sys.exit(1)
    except ModuleNotFoundError as e:
        print(f"模块未找到: {e}")
        print("\n请确保在正确的目录运行:")
        print("  cd gui_app")
        print("  python main.py")
        print(f"\n完整错误信息:\n{traceback.format_exc()}")
        sys.exit(1)
    except Exception as e:
        print(f"运行错误: {e}")
        print(f"\n完整错误信息:\n{traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
