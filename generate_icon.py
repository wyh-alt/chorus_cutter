"""
生成程序图标
使用PyQt6内置功能将SVG图标转换为PNG格式
无需额外依赖，只需要PyQt6（程序已安装）
"""

import os
import sys

try:
    from PyQt6.QtCore import QSize, QCoreApplication
    from PyQt6.QtGui import QImage, QPainter, QColor
    from PyQt6.QtSvg import QSvgRenderer
    
    def generate_png_from_svg(svg_path, png_path, size=256):
        """使用PyQt6将SVG转换为PNG"""
        try:
            # 创建SVG渲染器
            renderer = QSvgRenderer(svg_path)
            if not renderer.isValid():
                print(f"✗ SVG文件无效: {svg_path}")
                return False
            
            # 创建图像
            image = QImage(size, size, QImage.Format.Format_ARGB32)
            image.fill(QColor(0, 0, 0, 0))  # 透明背景
            
            # 绘制SVG到图像
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            
            # 保存PNG文件
            if image.save(png_path, "PNG"):
                print(f"✓ 成功生成PNG图标: {png_path} ({size}x{size})")
                return True
            else:
                print(f"✗ 保存失败: {png_path}")
                return False
        except Exception as e:
            print(f"✗ 转换失败: {e}")
            return False
    
    if __name__ == "__main__":
        # 初始化Qt应用（不需要GUI，只需要核心功能）
        app = QCoreApplication(sys.argv)
        
        svg_file = "icon_scissors.svg"
        png_file = "icon_scissors.png"
        
        if not os.path.exists(svg_file):
            print(f"✗ 找不到SVG文件: {svg_file}")
            sys.exit(1)
        
        print("使用PyQt6生成PNG图标...")
        print("-" * 40)
        
        # 生成主图标文件（256x256，推荐尺寸）
        success = False
        if generate_png_from_svg(svg_file, png_file, 256):
            success = True
        
        # 可选：生成其他尺寸
        sizes = [16, 32, 48, 64, 128]
        success_count = 1 if success else 0
        
        for size in sizes:
            output_file = f"icon_scissors_{size}.png"
            if generate_png_from_svg(svg_file, output_file, size):
                success_count += 1
        
        print("-" * 40)
        if success:
            print(f"\n✓ 完成！成功生成 {success_count} 个图标文件。")
            print(f"主图标文件: {png_file}")
        else:
            print("\n✗ 生成失败，请检查SVG文件是否正确。")
            sys.exit(1)
        
except ImportError as e:
    print("错误：需要安装PyQt6")
    print("  pip install PyQt6")
    print(f"\n详细错误: {e}")
    sys.exit(1)
