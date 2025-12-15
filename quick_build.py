#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速打包脚本 - 简化版
"""

import subprocess
import sys
import os

# 切换到脚本所在目录
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("="*60)
print("开始打包副歌剪辑器...")
print("="*60)
print()

# 执行打包命令
cmd = ["pyinstaller", "--clean", "chorus_cutter.spec"]

print("执行命令:", " ".join(cmd))
print()

try:
    result = subprocess.run(cmd, check=True, capture_output=False, text=True)
    print()
    print("="*60)
    print("[SUCCESS] 打包成功！")
    print("="*60)
    print()
    print("可执行文件位置: dist\\副歌剪辑器.exe")
    print()
except subprocess.CalledProcessError as e:
    print()
    print("[ERROR] 打包失败")
    print(f"错误码: {e.returncode}")
    sys.exit(1)
except Exception as e:
    print()
    print("[ERROR] 打包过程出错")
    print(f"错误信息: {e}")
    sys.exit(1)



