@echo off
chcp 65001 >nul
echo ============================================================
echo 副歌剪辑器 - Windows可执行文件打包工具
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] 检查Python环境...
python --version
if errorlevel 1 (
    echo [ERROR] 未找到Python，请先安装Python
    pause
    exit /b 1
)
echo.

echo [2/3] 检查PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyInstaller未安装，正在安装...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller安装失败
        pause
        exit /b 1
    )
)
echo [OK] PyInstaller已安装
echo.

echo [3/3] 开始打包程序...
echo 使用spec文件打包，请稍候...
pyinstaller --clean chorus_cutter.spec
if errorlevel 1 (
    echo.
    echo [ERROR] 打包失败，请查看错误信息
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [SUCCESS] 打包成功！
echo ============================================================
echo.
echo 可执行文件位置: dist\副歌剪辑器.exe
echo.
echo 注意事项：
echo 1. 运行程序前需要确保目标电脑已安装ffmpeg
echo 2. 可以将exe文件复制到任意位置使用
echo 3. 首次运行可能需要几秒钟启动时间
echo.
echo 正在清理临时文件...
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__
echo.
echo 打包完成！按任意键退出...
pause >nul

