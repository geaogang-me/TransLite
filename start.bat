@echo off
chcp 65001 >nul
title TransLite

echo TransLite 启动器
echo ================

REM 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo ⚠ 虚拟环境不存在，请先运行以下命令创建环境：
    echo python -m venv .venv
    echo .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

REM 清理现有进程
taskkill /F /IM "TransLite.exe" >nul 2>&1
if "%ERRORLEVEL%"=="0" echo ✓ 已清理现有进程

REM 清理锁文件
del "%TEMP%\translite.lock" >nul 2>&1

echo 正在启动 TransLite...
echo 启动后将显示托盘通知
echo.

REM 启动开发版本（已验证可以正常运行）
.venv\Scripts\python.exe app.py
if "%ERRORLEVEL%"=="0" (
    echo ✓ TransLite 已启动（开发版本）
) else (
    echo ✗ 启动失败，错误代码: %ERRORLEVEL%
    echo.
    echo 尝试解决方案：
    echo 1. 重新安装 PyQt5: .venv\Scripts\pip install --force-reinstall PyQt5==5.15.10
    echo 2. 检查虚拟环境是否正确安装
    pause
    exit /b 1
)