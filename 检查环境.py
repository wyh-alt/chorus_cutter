"""
环境检查脚本
用于检查所有依赖是否正确安装
"""

import sys
import subprocess


def check_python_version():
    """检查 Python 版本"""
    print("=" * 60)
    print("检查 Python 版本...")
    print("=" * 60)
    
    version = sys.version_info
    print(f"当前 Python 版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major >= 3 and version.minor >= 8:
        print("✅ Python 版本符合要求（3.8+）\n")
        return True
    else:
        print("❌ Python 版本过低，需要 3.8 或更高版本\n")
        return False


def check_package(package_name, import_name=None):
    """检查 Python 包是否已安装"""
    if import_name is None:
        import_name = package_name
    
    try:
        __import__(import_name)
        print(f"✅ {package_name} 已安装")
        return True
    except ImportError:
        print(f"❌ {package_name} 未安装")
        return False


def check_python_packages():
    """检查所有 Python 依赖包"""
    print("=" * 60)
    print("检查 Python 依赖包...")
    print("=" * 60)
    
    packages = [
        ("PyQt6", "PyQt6"),
        ("pandas", "pandas"),
        ("pydub", "pydub"),
        ("openpyxl", "openpyxl"),
    ]
    
    all_installed = True
    for package_name, import_name in packages:
        if not check_package(package_name, import_name):
            all_installed = False
    
    print()
    
    if not all_installed:
        print("💡 安装缺失的包，请运行：")
        print("   pip install -r requirements.txt\n")
    
    return all_installed


def check_ffmpeg():
    """检查 ffmpeg 是否已安装"""
    print("=" * 60)
    print("检查 ffmpeg...")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # 提取版本信息（第一行）
            version_line = result.stdout.split('\n')[0]
            print(f"✅ {version_line}\n")
            return True
        else:
            print("❌ ffmpeg 未正确安装\n")
            return False
            
    except FileNotFoundError:
        print("❌ ffmpeg 未安装或未添加到系统 PATH\n")
        print_ffmpeg_install_instructions()
        return False
    except Exception as e:
        print(f"❌ 检查 ffmpeg 时出错: {e}\n")
        return False


def print_ffmpeg_install_instructions():
    """打印 ffmpeg 安装说明"""
    print("💡 安装 ffmpeg：")
    print()
    print("Windows:")
    print("  1. 访问 https://ffmpeg.org/download.html")
    print("  2. 下载 Windows 版本（选择 Windows builds from gyan.dev）")
    print("  3. 解压到任意目录（如 C:\\ffmpeg）")
    print("  4. 将 bin 目录添加到系统 PATH 环境变量")
    print("  5. 重启命令提示符，验证：ffmpeg -version")
    print()
    print("macOS:")
    print("  brew install ffmpeg")
    print()
    print("Linux (Ubuntu/Debian):")
    print("  sudo apt-get update")
    print("  sudo apt-get install ffmpeg")
    print()
    print("Linux (CentOS/RHEL):")
    print("  sudo yum install ffmpeg")
    print()


def main():
    """主函数"""
    print()
    print("╔═══════════════════════════════════════════════════════════╗")
    print("║        副歌剪辑器 Chorus Cutter - 环境检查工具            ║")
    print("╚═══════════════════════════════════════════════════════════╝")
    print()
    
    results = []
    
    # 检查 Python 版本
    results.append(("Python 版本", check_python_version()))
    
    # 检查 Python 包
    results.append(("Python 依赖包", check_python_packages()))
    
    # 检查 ffmpeg
    results.append(("ffmpeg", check_ffmpeg()))
    
    # 总结
    print("=" * 60)
    print("检查结果总结")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    print()
    
    if all_passed:
        print("🎉 恭喜！所有依赖已正确安装，可以运行程序了！")
        print()
        print("运行程序：")
        print("  • Windows: 双击 '启动程序.bat'")
        print("  • 命令行: python chorus_cutter.py")
    else:
        print("⚠️  部分依赖未正确安装，请根据上述提示完成安装")
    
    print()
    input("按 Enter 键退出...")


if __name__ == "__main__":
    main()

