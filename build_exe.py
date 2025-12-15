"""
打包脚本 - 将副歌剪辑器打包为Windows可执行文件
使用方法：python build_exe.py
"""

import subprocess
import sys
import os
import shutil

def install_pyinstaller():
    """安装PyInstaller"""
    print("正在安装PyInstaller...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller安装成功")
        return True
    except subprocess.CalledProcessError:
        print("[ERROR] PyInstaller安装失败")
        return False

def build_exe():
    """打包为exe文件"""
    print("\n开始打包程序...")
    
    # 检查图标文件
    icon_file = "icon_scissors.png"
    if not os.path.exists(icon_file):
        icon_file = None
        print("[WARNING] 未找到图标文件，将使用默认图标")
    else:
        print(f"[OK] 使用图标: {icon_file}")
    
    # PyInstaller命令参数
    cmd = [
        "pyinstaller",
        "--name=副歌剪辑器",  # 程序名称
        "--onefile",  # 打包为单个exe文件
        "--windowed",  # 不显示控制台窗口（GUI程序）
        "--clean",  # 清理临时文件
    ]
    
    # 添加图标
    if icon_file:
        cmd.append(f"--icon={icon_file}")
    
    # 添加数据文件（图标文件）
    if os.path.exists("icon_scissors.png"):
        cmd.append("--add-data=icon_scissors.png;.")
    if os.path.exists("icon_scissors.svg"):
        cmd.append("--add-data=icon_scissors.svg;.")
    
    # 添加示例文件
    if os.path.exists("example_data.xlsx"):
        cmd.append("--add-data=example_data.xlsx;.")
    
    # 隐藏导入（确保所有依赖都被打包）
    hidden_imports = [
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "pandas",
        "pydub",
        "openpyxl",
    ]
    
    for module in hidden_imports:
        cmd.append(f"--hidden-import={module}")
    
    # 主程序文件
    cmd.append("chorus_cutter.py")
    
    print("\n执行命令:", " ".join(cmd))
    print("\n打包中，请稍候...")
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "="*60)
        print("[SUCCESS] 打包成功！")
        print("="*60)
        print(f"\n可执行文件位置: dist\\副歌剪辑器.exe")
        print("\n注意事项：")
        print("1. 运行程序前需要确保目标电脑已安装ffmpeg")
        print("2. 可以将exe文件复制到任意位置使用")
        print("3. 首次运行可能需要几秒钟启动时间")
        
        return True
    except subprocess.CalledProcessError as e:
        print("\n[ERROR] 打包失败")
        print(f"错误信息: {e}")
        return False

def clean_build_files():
    """清理构建文件"""
    print("\n正在清理临时文件...")
    dirs_to_remove = ["build", "__pycache__"]
    files_to_remove = ["副歌剪辑器.spec"]
    
    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"[OK] 已删除: {dir_name}")
    
    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"[OK] 已删除: {file_name}")

def main():
    print("="*60)
    print("副歌剪辑器 - Windows可执行文件打包工具")
    print("="*60)
    
    # 检查并安装PyInstaller
    try:
        import PyInstaller
        print("[OK] PyInstaller已安装")
    except ImportError:
        if not install_pyinstaller():
            print("\n请手动安装PyInstaller: pip install pyinstaller")
            return
    
    # 执行打包
    success = build_exe()
    
    # 清理临时文件
    if success:
        clean_build_files()
        print("\n打包完成！")
    else:
        print("\n打包失败，请检查错误信息")

if __name__ == "__main__":
    main()

