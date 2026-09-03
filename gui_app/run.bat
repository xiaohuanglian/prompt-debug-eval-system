@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Prompt 自动化调试与评测系统

echo ============================================
echo  Prompt 自动化调试与评测系统 - GUI
echo ============================================
echo.
echo 正在检测环境...

:: Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: Check PyQt5
python -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装 PyQt5...
    pip install PyQt5
)

:: Check requests
python -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装 requests...
    pip install requests
)

:: Check tqdm
python -c "import tqdm" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装 tqdm...
    pip install tqdm
)

:: Check python-docx
python -c "import docx" >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 正在安装 python-docx...
    pip install python-docx
)

echo.
echo 启动 GUI 程序...
echo.

python main.py

if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序异常退出，错误码: %errorlevel%
    pause
)
