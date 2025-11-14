@echo off
chcp 65001 >nul
title 副歌剪辑器 Chorus Cutter

echo ========================================
echo   副歌剪辑器 Chorus Cutter
echo ========================================
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/3] 检测到 Python 环境...
python --version

REM 检查依赖是否安装
echo.
echo [2/3] 检查依赖包...
python -c "import PyQt6, pandas, pydub, openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 部分依赖未安装，正在安装...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [错误] 依赖安装失败
        pause
        exit /b 1
    )
    echo [成功] 依赖安装完成
) else (
    echo [成功] 所有依赖已安装
)

REM 检查 ffmpeg
echo.
echo [3/3] 检查 ffmpeg...
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 未检测到 ffmpeg！
    echo.
    echo 请安装 ffmpeg 以使用本程序：
    echo 1. 访问 https://ffmpeg.org/download.html
    echo 2. 下载 Windows 版本
    echo 3. 解压并添加到系统 PATH
    echo.
    echo 按任意键继续启动程序（功能可能受限）...
    pause >nul
) else (
    echo [成功] ffmpeg 已就绪
)

echo.
echo ========================================
echo   正在启动程序...
echo ========================================
echo.

REM 启动程序
python chorus_cutter.py

if %errorlevel% neq 0 (
    echo.
    echo [错误] 程序运行出错
    pause
    exit /b 1
)

