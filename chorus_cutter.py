"""
副歌剪辑器 (Chorus Cutter)
============================
一个基于 PyQt6 的音频副歌剪辑工具

依赖安装：
pip install PyQt6 pandas pydub openpyxl

系统依赖：
需要安装 ffmpeg（https://ffmpeg.org/download.html）
Windows: 下载后添加到系统 PATH
macOS: brew install ffmpeg
Linux: apt-get install ffmpeg 或 yum install ffmpeg

使用方法：
python chorus_cutter.py
"""

import sys
import os
import re
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QProgressBar, QTextEdit, QComboBox, QCheckBox,
    QGroupBox, QRadioButton, QButtonGroup, QMessageBox, QHeaderView,
    QDoubleSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QColor, QPalette, QIcon

import pandas as pd
from pydub import AudioSegment
from pydub.utils import which


class DragDropLineEdit(QLineEdit):
    """支持拖拽的输入框"""
    
    # 定义信号，用于通知主窗口处理拖拽的文件
    filesDropped = pyqtSignal(list)  # 发送文件路径列表
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """拖拽进入事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """拖拽放下事件"""
        urls = event.mimeData().urls()
        if urls:
            file_paths = [url.toLocalFile() for url in urls]
            self.filesDropped.emit(file_paths)
            event.acceptProposedAction()


class TimeParser:
    """时间字符串解析器，支持多种格式"""
    
    @staticmethod
    def parse_time(time_str) -> Optional[float]:
        """
        解析时间字符串为秒数
        支持格式：
        - mm:ss (如 1:30)
        - m:ss (如 1:05)
        - hh:mm:ss (如 0:01:30)
        - ss.s (如 90.5)
        - 纯数字 (如 90)
        """
        if pd.isna(time_str):
            return None
            
        time_str = str(time_str).strip()
        
        if not time_str:
            return None
        
        # 尝试直接转换为浮点数（秒数）
        try:
            return float(time_str)
        except ValueError:
            pass
        
        # 尝试解析 hh:mm:ss 或 mm:ss 或 m:ss
        time_pattern = r'^(\d+):(\d+):(\d+(?:\.\d+)?)$|^(\d+):(\d+(?:\.\d+)?)$'
        match = re.match(time_pattern, time_str)
        
        if match:
            if match.group(1) and match.group(2) and match.group(3):
                # hh:mm:ss
                hours = int(match.group(1))
                minutes = int(match.group(2))
                seconds = float(match.group(3))
                return hours * 3600 + minutes * 60 + seconds
            elif match.group(4) and match.group(5):
                # mm:ss 或 m:ss
                minutes = int(match.group(4))
                seconds = float(match.group(5))
                return minutes * 60 + seconds
        
        return None


class AudioProcessor:
    """音频处理器"""
    
    def __init__(self):
        self.check_ffmpeg()
    
    @staticmethod
    def check_ffmpeg() -> bool:
        """检查 ffmpeg 是否已安装"""
        return which("ffmpeg") is not None
    
    @staticmethod
    def load_audio(file_path: str) -> Optional[AudioSegment]:
        """加载音频文件"""
        try:
            return AudioSegment.from_file(file_path)
        except Exception as e:
            print(f"加载音频失败: {file_path}, 错误: {e}")
            return None
    
    @staticmethod
    def cut_audio(audio: AudioSegment, start_time: float, end_time: float) -> Optional[AudioSegment]:
        """剪切音频"""
        try:
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            if start_ms >= end_ms:
                return None
            
            if end_ms > len(audio):
                end_ms = len(audio)
            
            return audio[start_ms:end_ms]
        except Exception as e:
            print(f"剪切音频失败: {e}")
            return None
    
    @staticmethod
    def export_audio(audio: AudioSegment, output_path: str, format: str = "wav") -> bool:
        """导出音频"""
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            if format.lower() == "mp3":
                audio.export(output_path, format="mp3", bitrate="320k")
            else:
                audio.export(output_path, format="wav")
            return True
        except Exception as e:
            print(f"导出音频失败: {output_path}, 错误: {e}")
            return False


class FileNameSanitizer:
    """文件名安全处理器"""
    
    @staticmethod
    def sanitize(filename: str, max_length: int = 200) -> str:
        """清理文件名中的危险字符"""
        # 移除或替换危险字符
        dangerous_chars = r'[<>:"/\\|?*]'
        filename = re.sub(dangerous_chars, '_', filename)
        
        # 移除前后空格
        filename = filename.strip()
        
        # 限制长度
        if len(filename) > max_length:
            filename = filename[:max_length]
        
        return filename
    
    @staticmethod
    def get_unique_filename(output_dir: str, base_name: str, extension: str) -> str:
        """生成唯一文件名（如果文件已存在，添加数字后缀）"""
        output_path = os.path.join(output_dir, f"{base_name}.{extension}")
        
        if not os.path.exists(output_path):
            return output_path
        
        counter = 1
        while True:
            output_path = os.path.join(output_dir, f"{base_name}({counter}).{extension}")
            if not os.path.exists(output_path):
                return output_path
            counter += 1


class ProcessWorker(QThread):
    """音频处理工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int)  # current, total
    row_updated = pyqtSignal(int, dict)  # row_index, row_data
    log_message = pyqtSignal(str)
    finished = pyqtSignal(dict)  # statistics
    
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self.is_stopped = False
        self.audio_processor = AudioProcessor()
        self.time_parser = TimeParser()
        self.sanitizer = FileNameSanitizer()
    
    def stop(self):
        """停止处理"""
        self.is_stopped = True
    
    def run(self):
        """执行音频处理"""
        try:
            self._process()
        except Exception as e:
            self.log_message.emit(f"处理过程出错: {str(e)}")
    
    def _process(self):
        """主处理逻辑"""
        audio_files = self.config['audio_files']
        excel_data = self.config['excel_data']
        output_dir = self.config['output_dir']
        export_format = self.config['export_format']
        mode_full = self.config['mode_full']
        mode_split = self.config['mode_split']
        overwrite = self.config['overwrite']
        match_strategy = self.config['match_strategy']
        
        total = len(excel_data)
        success_count = 0
        failed_count = 0
        cancelled_count = 0
        
        # 创建音频文件映射（用于快速查找）
        audio_map = self._build_audio_map(audio_files)
        
        # 打印调试信息
        self.log_message.emit(f"已加载 {len(audio_files)} 个音频文件")
        self.log_message.emit(f"音频文件名列表（前10个）：")
        for i, file_path in enumerate(audio_files[:10]):
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            self.log_message.emit(f"  [{i+1}] {file_name}")
        if len(audio_files) > 10:
            self.log_message.emit(f"  ... 还有 {len(audio_files) - 10} 个文件")
        self.log_message.emit("")
        
        for idx, row in excel_data.iterrows():
            if self.is_stopped:
                cancelled_count += 1
                self.log_message.emit(f"已取消处理")
                break
            
            result = self._process_single_row(row, idx, audio_map, output_dir, 
                                             export_format, mode_full, mode_split, 
                                             overwrite, match_strategy)
            
            self.row_updated.emit(idx, result)
            
            if result['status'] == '成功':
                success_count += 1
            elif result['status'] == '失败':
                failed_count += 1
            
            self.progress_updated.emit(idx + 1, total)
        
        # 发送完成统计
        stats = {
            'total': total,
            'success': success_count,
            'failed': failed_count,
            'cancelled': cancelled_count
        }
        self.finished.emit(stats)
    
    def _build_audio_map(self, audio_files: List[str]) -> Dict[str, str]:
        """构建音频文件映射"""
        audio_map = {}
        for file_path in audio_files:
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            # 同时保存原始名称和清理后的名称
            audio_map[file_name] = file_path
            audio_map[file_name.strip().lower()] = file_path
        return audio_map
    
    def _match_audio_file(self, row, audio_map: Dict[str, str], strategy: str, row_idx: int = 0) -> Optional[str]:
        """匹配音频文件，支持前缀匹配（如 12345 匹配 12345-原唱）"""
        # 获取伴奏ID和歌名
        accompaniment_id = row.get('伴奏ID', None)
        song_name = row.get('歌名', None)
        
        # 策略1: 优先按伴奏ID匹配
        if strategy in ['伴奏ID优先', '模糊匹配']:
            if pd.notna(accompaniment_id):
                # 处理数字型ID（Excel可能读取为浮点数）
                id_str = str(accompaniment_id).strip()
                # 如果是浮点数形式（如 12345.0），去掉小数点
                if '.' in id_str and id_str.replace('.', '').replace('-', '').isdigit():
                    try:
                        id_str = str(int(float(id_str)))
                    except:
                        pass
                
                # 1. 尝试精确匹配
                if id_str in audio_map:
                    return audio_map[id_str]
                # 2. 尝试小写匹配
                if id_str.lower() in audio_map:
                    return audio_map[id_str.lower()]
                
                # 3. 尝试前缀匹配（如 12345 匹配 12345-原唱、12345_vocal 等）
                id_lower = id_str.lower()
                for key, path in audio_map.items():
                    key_lower = key.lower()
                    # 检查是否以ID开头，后面跟着分隔符（-、_、空格等）
                    if (key_lower.startswith(id_lower + '-') or 
                        key_lower.startswith(id_lower + '_') or 
                        key_lower.startswith(id_lower + ' ') or
                        key_lower == id_lower):
                        return path
        
        # 策略2: 按歌名匹配
        if strategy in ['按歌名', '伴奏ID优先', '模糊匹配']:
            if pd.notna(song_name):
                name_str = str(song_name).strip()
                # 1. 尝试精确匹配
                if name_str in audio_map:
                    return audio_map[name_str]
                # 2. 尝试小写匹配
                if name_str.lower() in audio_map:
                    return audio_map[name_str.lower()]
                
                # 3. 尝试前缀匹配
                name_lower = name_str.lower()
                for key, path in audio_map.items():
                    key_lower = key.lower()
                    if (key_lower.startswith(name_lower + '-') or 
                        key_lower.startswith(name_lower + '_') or 
                        key_lower.startswith(name_lower + ' ') or
                        key_lower == name_lower):
                        return path
        
        # 策略3: 模糊匹配（包含匹配）
        if strategy == '模糊匹配':
            # 尝试伴奏ID模糊匹配
            if pd.notna(accompaniment_id):
                id_str = str(accompaniment_id).strip()
                if '.' in id_str:
                    try:
                        id_str = str(int(float(id_str)))
                    except:
                        pass
                id_lower = id_str.lower()
                
                for key, path in audio_map.items():
                    key_lower = key.lower()
                    if id_lower in key_lower or key_lower in id_lower:
                        return path
            
            # 尝试歌名模糊匹配
            if pd.notna(song_name):
                name_lower = str(song_name).strip().lower()
                for key, path in audio_map.items():
                    key_lower = key.lower()
                    if name_lower in key_lower or key_lower in name_lower:
                        return path
        
        return None
    
    def _process_single_row(self, row, idx: int, audio_map: Dict[str, str],
                           output_dir: str, export_format: str, mode_full: bool,
                           mode_split: bool, overwrite: bool, match_strategy: str) -> dict:
        """处理单行数据"""
        # 正确处理NaN值
        acc_id = row.get('伴奏ID', '')
        if pd.notna(acc_id):
            acc_id = str(acc_id)
        else:
            acc_id = ''
        
        song_name = row.get('歌名', '')
        if pd.notna(song_name):
            song_name = str(song_name)
        else:
            song_name = ''
        
        result = {
            'accompaniment_id': acc_id,
            'song_name': song_name,
            'input_path': '',
            'output_full': '',
            'output_part1': '',
            'output_part2': '',
            'status': '失败',
            'error': ''
        }
        
        try:
            # 匹配音频文件
            audio_path = self._match_audio_file(row, audio_map, match_strategy, idx)
            if not audio_path:
                # 提供更详细的错误信息
                acc_id = row.get('伴奏ID', '')
                song = row.get('歌名', '')
                result['error'] = f'未找到匹配的音频文件（伴奏ID:{acc_id}, 歌名:{song}）'
                self.log_message.emit(f"行 {idx + 1}: 匹配失败 - 伴奏ID='{acc_id}', 歌名='{song}'")
                return result
            
            result['input_path'] = audio_path
            
            # 解析时间
            start_time = self.time_parser.parse_time(row.get('副歌开始时间'))
            end_time = self.time_parser.parse_time(row.get('副歌结束时间'))
            split_time = self.time_parser.parse_time(row.get('段落剪切时间'))
            
            if start_time is None or end_time is None:
                result['error'] = '时间解析失败'
                self.log_message.emit(f"行 {idx + 1}: {result['error']}")
                return result
            
            # 应用剪辑位置微调
            start_adjust = self.config.get('start_adjust', 0.0)
            end_adjust = self.config.get('end_adjust', 0.0)
            
            # 开始时间：正数表示提前（向前），所以减去微调值
            start_time = max(0, start_time - start_adjust)
            # 结束时间：正数表示延后（向后），所以加上微调值
            end_time = end_time + end_adjust
            
            if start_time >= end_time:
                result['error'] = '副歌开始时间必须小于结束时间（应用微调后）'
                self.log_message.emit(f"行 {idx + 1}: {result['error']}")
                return result
            
            # 加载音频
            audio = self.audio_processor.load_audio(audio_path)
            if audio is None:
                result['error'] = '音频加载失败'
                self.log_message.emit(f"行 {idx + 1}: {result['error']}")
                return result
            
            # 生成基础文件名
            base_name = str(row.get('伴奏ID', row.get('歌名', f'track_{idx}')))
            base_name = self.sanitizer.sanitize(base_name)
            
            # 处理整段副歌模式
            if mode_full:
                if self.is_stopped:
                    result['status'] = '已取消'
                    return result
                
                chorus_full = self.audio_processor.cut_audio(audio, start_time, end_time)
                if chorus_full:
                    file_name = f"{base_name}-整段副歌"
                    if overwrite:
                        output_path = os.path.join(output_dir, f"{file_name}.{export_format}")
                    else:
                        output_path = self.sanitizer.get_unique_filename(output_dir, file_name, export_format)
                    
                    if self.audio_processor.export_audio(chorus_full, output_path, export_format):
                        result['output_full'] = output_path
                        self.log_message.emit(f"行 {idx + 1}: 导出整段副歌成功")
            
            # 处理分段副歌模式
            if mode_split:
                if split_time is None:
                    result['error'] = '分段模式需要段落剪切时间'
                    self.log_message.emit(f"行 {idx + 1}: {result['error']}")
                elif split_time <= start_time or split_time >= end_time:
                    result['error'] = '段落剪切时间必须在副歌开始和结束时间之间'
                    self.log_message.emit(f"行 {idx + 1}: {result['error']}")
                else:
                    if self.is_stopped:
                        result['status'] = '已取消'
                        return result
                    
                    # 前段
                    chorus_part1 = self.audio_processor.cut_audio(audio, start_time, split_time)
                    if chorus_part1:
                        file_name = f"{base_name}-前段副歌"
                        if overwrite:
                            output_path = os.path.join(output_dir, f"{file_name}.{export_format}")
                        else:
                            output_path = self.sanitizer.get_unique_filename(output_dir, file_name, export_format)
                        
                        if self.audio_processor.export_audio(chorus_part1, output_path, export_format):
                            result['output_part1'] = output_path
                            self.log_message.emit(f"行 {idx + 1}: 导出前段副歌成功")
                    
                    if self.is_stopped:
                        result['status'] = '已取消'
                        return result
                    
                    # 后段
                    chorus_part2 = self.audio_processor.cut_audio(audio, split_time, end_time)
                    if chorus_part2:
                        file_name = f"{base_name}-后段副歌"
                        if overwrite:
                            output_path = os.path.join(output_dir, f"{file_name}.{export_format}")
                        else:
                            output_path = self.sanitizer.get_unique_filename(output_dir, file_name, export_format)
                        
                        if self.audio_processor.export_audio(chorus_part2, output_path, export_format):
                            result['output_part2'] = output_path
                            self.log_message.emit(f"行 {idx + 1}: 导出后段副歌成功")
            
            # 判断是否成功
            if result['output_full'] or result['output_part1'] or result['output_part2']:
                result['status'] = '成功'
            else:
                result['error'] = '未生成任何输出文件'
            
        except Exception as e:
            result['error'] = str(e)
            self.log_message.emit(f"行 {idx + 1}: 处理出错 - {str(e)}")
        
        return result


class ChorusCutterGUI(QMainWindow):
    """副歌剪辑器主界面"""
    
    def __init__(self):
        super().__init__()
        self.excel_data = None
        self.audio_files = []
        self.process_worker = None
        self.results = []
        
        self.init_ui()
        self.check_dependencies()
    
    def init_ui(self):
        """初始化UI"""
        self.setWindowTitle("副歌剪辑器 Chorus Cutter v1.0")
        self.setGeometry(100, 100, 1000, 800)
        
        # 设置窗口图标（优先使用PNG，否则使用SVG）
        icon_dir = os.path.dirname(__file__)
        icon_path = None
        # 优先尝试PNG图标
        png_path = os.path.join(icon_dir, "icon_scissors.png")
        svg_path = os.path.join(icon_dir, "icon_scissors.svg")
        if os.path.exists(png_path):
            icon_path = png_path
        elif os.path.exists(svg_path):
            icon_path = svg_path
        
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))
        
        # 主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        
        # 输入区域
        input_group = QGroupBox("输入设置")
        input_layout = QVBoxLayout()
        
        # 音频文件/目录
        audio_row = QHBoxLayout()
        audio_label = QLabel("歌曲目录/文件:")
        audio_label.setStyleSheet("font-weight: bold; color: #333333;")
        audio_row.addWidget(audio_label)
        self.audio_input = DragDropLineEdit()
        self.audio_input.setPlaceholderText("拖拽文件夹或音频文件到此处，或点击浏览...")
        self.audio_input.filesDropped.connect(self.on_audio_files_dropped)
        audio_row.addWidget(self.audio_input)
        self.audio_browse_btn = QPushButton("浏览")
        self.audio_browse_btn.clicked.connect(self.browse_audio)
        audio_row.addWidget(self.audio_browse_btn)
        input_layout.addLayout(audio_row)
        
        # Excel 文件
        excel_row = QHBoxLayout()
        excel_label = QLabel("剪切时间表格:")
        excel_label.setStyleSheet("font-weight: bold; color: #333333;")
        excel_row.addWidget(excel_label)
        self.excel_input = DragDropLineEdit()
        self.excel_input.setPlaceholderText("拖拽 Excel/CSV 文件到此处，或点击加载...")
        self.excel_input.filesDropped.connect(self.on_excel_file_dropped)
        excel_row.addWidget(self.excel_input)
        self.excel_browse_btn = QPushButton("加载")
        self.excel_browse_btn.clicked.connect(self.browse_excel)
        excel_row.addWidget(self.excel_browse_btn)
        input_layout.addLayout(excel_row)
        
        # 输出目录
        output_row = QHBoxLayout()
        output_label = QLabel("输出目录:")
        output_label.setStyleSheet("font-weight: bold; color: #333333;")
        output_row.addWidget(output_label)
        self.output_input = DragDropLineEdit()
        self.output_input.setPlaceholderText("拖拽文件夹到此处，或点击浏览...")
        self.output_input.filesDropped.connect(self.on_output_dir_dropped)
        output_row.addWidget(self.output_input)
        self.output_browse_btn = QPushButton("浏览")
        self.output_browse_btn.clicked.connect(self.browse_output)
        output_row.addWidget(self.output_browse_btn)
        input_layout.addLayout(output_row)
        
        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)
        
        # 设置区域 - 左右两个板块布局
        settings_group = QGroupBox("处理设置")
        settings_layout = QHBoxLayout()
        settings_layout.setSpacing(20)  # 左右板块间距
        
        # 左边板块：匹配策略 + 其他选项
        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)
        
        # 匹配策略
        match_row = QHBoxLayout()
        match_row.setSpacing(10)
        match_label = QLabel("匹配策略:")
        match_label.setStyleSheet("font-weight: bold; color: #333333;")
        match_row.addWidget(match_label)
        
        self.match_group = QButtonGroup()
        self.match_id_radio = QRadioButton("伴奏ID优先")
        self.match_name_radio = QRadioButton("按歌名")
        self.match_fuzzy_radio = QRadioButton("模糊匹配")
        self.match_id_radio.setChecked(True)
        self.match_group.addButton(self.match_id_radio)
        self.match_group.addButton(self.match_name_radio)
        self.match_group.addButton(self.match_fuzzy_radio)
        match_row.addWidget(self.match_id_radio)
        match_row.addWidget(self.match_name_radio)
        match_row.addWidget(self.match_fuzzy_radio)
        match_row.addStretch()
        left_panel.addLayout(match_row)
        
        # 其他选项
        options_row = QHBoxLayout()
        options_row.setSpacing(10)
        options_label = QLabel("其他选项:")
        options_label.setStyleSheet("font-weight: bold; color: #333333;")
        options_row.addWidget(options_label)
        
        self.overwrite_check = QCheckBox("覆盖已存在文件")
        self.skip_error_check = QCheckBox("处理失败时跳过")
        self.skip_error_check.setChecked(True)
        options_row.addWidget(self.overwrite_check)
        options_row.addWidget(self.skip_error_check)
        options_row.addStretch()
        left_panel.addLayout(options_row)
        
        left_panel.addStretch()
        settings_layout.addLayout(left_panel)
        
        # 右边板块：导出格式 + 导出模式 + 时间微调
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)
        
        # 导出格式
        format_row = QHBoxLayout()
        format_row.setSpacing(10)
        format_label = QLabel("导出格式:")
        format_label.setStyleSheet("font-weight: bold; color: #333333;")
        format_row.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["wav", "mp3"])
        self.format_combo.setMaximumWidth(100)
        format_row.addWidget(self.format_combo)
        format_row.addStretch()
        right_panel.addLayout(format_row)
        
        # 导出模式
        mode_row = QHBoxLayout()
        mode_row.setSpacing(10)
        mode_label = QLabel("导出模式:")
        mode_label.setStyleSheet("font-weight: bold; color: #333333;")
        mode_row.addWidget(mode_label)
        
        self.mode_full_check = QCheckBox("整段副歌")
        self.mode_full_check.setChecked(True)
        self.mode_split_check = QCheckBox("分段副歌")
        mode_row.addWidget(self.mode_full_check)
        mode_row.addWidget(self.mode_split_check)
        mode_row.addStretch()
        right_panel.addLayout(mode_row)
        
        # 剪辑位置微调
        adjust_row = QHBoxLayout()
        adjust_row.setSpacing(10)
        adjust_label = QLabel("剪辑位置微调:")
        adjust_label.setStyleSheet("font-weight: bold; color: #333333;")
        adjust_row.addWidget(adjust_label)
        
        adjust_row.addWidget(QLabel("开始提前"))
        self.start_adjust_spinbox = QDoubleSpinBox()
        self.start_adjust_spinbox.setRange(-10.0, 10.0)
        self.start_adjust_spinbox.setSingleStep(0.1)
        self.start_adjust_spinbox.setDecimals(2)
        self.start_adjust_spinbox.setValue(0.0)
        self.start_adjust_spinbox.setSuffix(" 秒")
        self.start_adjust_spinbox.setMaximumWidth(100)
        self.start_adjust_spinbox.setToolTip("正数表示提前（向前），负数表示延后（向后）")
        adjust_row.addWidget(self.start_adjust_spinbox)
        
        adjust_row.addSpacing(8)
        
        adjust_row.addWidget(QLabel("结束延后"))
        self.end_adjust_spinbox = QDoubleSpinBox()
        self.end_adjust_spinbox.setRange(-10.0, 10.0)
        self.end_adjust_spinbox.setSingleStep(0.1)
        self.end_adjust_spinbox.setDecimals(2)
        self.end_adjust_spinbox.setValue(0.0)
        self.end_adjust_spinbox.setSuffix(" 秒")
        self.end_adjust_spinbox.setMaximumWidth(100)
        self.end_adjust_spinbox.setToolTip("正数表示延后（向后），负数表示提前（向前）")
        adjust_row.addWidget(self.end_adjust_spinbox)
        
        adjust_row.addStretch()
        right_panel.addLayout(adjust_row)
        
        right_panel.addStretch()
        settings_layout.addLayout(right_panel)
        
        settings_group.setLayout(settings_layout)
        settings_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Maximum
        )
        main_layout.addWidget(settings_group)
        
        # 控制按钮 - 简洁样式
        control_layout = QHBoxLayout()
        
        self.check_btn = QPushButton("检查匹配")
        self.check_btn.setMinimumHeight(35)
        self.check_btn.setToolTip("检查音频文件与Excel表格的匹配情况")
        self.check_btn.clicked.connect(self.check_matching)
        control_layout.addWidget(self.check_btn)
        
        self.start_btn = QPushButton("开始处理")
        self.start_btn.setMinimumHeight(35)
        self.start_btn.clicked.connect(self.start_processing)
        control_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.setMinimumHeight(35)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_processing)
        control_layout.addWidget(self.stop_btn)
        
        self.export_btn = QPushButton("导出结果")
        self.export_btn.setMinimumHeight(35)
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_results)
        control_layout.addWidget(self.export_btn)
        
        main_layout.addLayout(control_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)
        
        # 结果表格 - 优化列宽（删除歌名、输入路径和行号列）
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(6)
        self.result_table.setHorizontalHeaderLabels([
            "伴奏ID", "整段导出", "前段导出", "后段导出", "状态", "错误信息"
        ])
        
        # 设置合理的列宽模式
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # 伴奏ID
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 整段导出
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 前段导出
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 后段导出
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)  # 状态
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)  # 错误信息
        
        # 设置固定列的宽度
        self.result_table.setColumnWidth(0, 100)   # 伴奏ID
        self.result_table.setColumnWidth(4, 80)    # 状态
        
        # 强制使用亮色主题样式
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #F5F5F5;
                gridline-color: #D0D0D0;
                color: black;
            }
            QTableWidget::item {
                color: black;
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #CCE8FF;
                color: black;
            }
            QHeaderView::section {
                background-color: #F0F0F0;
                color: black;
                padding: 5px;
                border: 1px solid #D0D0D0;
                font-weight: bold;
            }
        """)
        main_layout.addWidget(self.result_table)
        
        # 日志区域 - 默认隐藏
        log_label = QLabel("处理日志:")
        log_label.setVisible(False)
        main_layout.addWidget(log_label)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setVisible(False)
        main_layout.addWidget(self.log_text)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
    
    def check_dependencies(self):
        """检查依赖"""
        if not AudioProcessor.check_ffmpeg():
            QMessageBox.warning(
                self,
                "缺少依赖",
                "未检测到 ffmpeg！\n\n"
                "请安装 ffmpeg 以使用本程序：\n"
                "• Windows: 从 https://ffmpeg.org/download.html 下载并添加到 PATH\n"
                "• macOS: brew install ffmpeg\n"
                "• Linux: apt-get install ffmpeg 或 yum install ffmpeg"
            )
    
    def on_audio_files_dropped(self, file_paths: List[str]):
        """处理拖拽到音频输入框的文件"""
        if not file_paths:
            return
        
        # 取第一个文件/目录
        file_path = file_paths[0]
        
        if os.path.isdir(file_path):
            # 如果是目录，加载目录中的所有音频文件
            self.audio_input.setText(file_path)
            self.load_audio_from_directory(file_path)
        elif file_path.lower().endswith(('.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma', '.aac')):
            # 如果是音频文件，加载所有拖拽的音频文件
            audio_files = [f for f in file_paths if f.lower().endswith(('.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma', '.aac'))]
            if audio_files:
                self.audio_input.setText('; '.join(audio_files))
                self.load_audio_files(audio_files)
        else:
            self.log("请拖拽音频文件或文件夹到此处")
    
    def on_excel_file_dropped(self, file_paths: List[str]):
        """处理拖拽到Excel输入框的文件"""
        if not file_paths:
            return
        
        file_path = file_paths[0]
        
        if file_path.lower().endswith(('.xlsx', '.xls', '.csv')):
            self.excel_input.setText(file_path)
            self.load_excel(file_path)
        else:
            self.log("请拖拽Excel或CSV文件到此处")
    
    def on_output_dir_dropped(self, file_paths: List[str]):
        """处理拖拽到输出目录输入框的文件"""
        if not file_paths:
            return
        
        file_path = file_paths[0]
        
        if os.path.isdir(file_path):
            self.output_input.setText(file_path)
            self.log(f"输出目录已设置为: {file_path}")
        else:
            # 如果拖的是文件，使用文件所在的目录
            dir_path = os.path.dirname(file_path)
            self.output_input.setText(dir_path)
            self.log(f"输出目录已设置为: {dir_path}")
    
    def browse_audio(self):
        """浏览音频文件/目录"""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        
        if dialog.exec():
            selected = dialog.selectedFiles()
            if selected:
                path = selected[0]
                self.audio_input.setText(path)
                self.load_audio_from_directory(path)
    
    def browse_excel(self):
        """浏览 Excel 文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择剪切时间表格",
            "",
            "Excel/CSV 文件 (*.xlsx *.xls *.csv)"
        )
        if file_path:
            self.excel_input.setText(file_path)
            self.load_excel(file_path)
    
    def browse_output(self):
        """浏览输出目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if directory:
            self.output_input.setText(directory)
    
    def load_audio_from_directory(self, directory: str):
        """从目录加载音频文件"""
        audio_extensions = {'.mp3', '.wav', '.flac', '.m4a', '.ogg', '.wma', '.aac'}
        audio_files = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if os.path.splitext(file)[1].lower() in audio_extensions:
                    audio_files.append(os.path.join(root, file))
        
        self.audio_files = audio_files
        self.log(f"已加载 {len(audio_files)} 个音频文件")
    
    def load_audio_files(self, files: List[str]):
        """加载音频文件列表"""
        self.audio_files.extend(files)
        self.log(f"已添加 {len(files)} 个音频文件")
    
    def load_excel(self, file_path: str):
        """加载 Excel 文件"""
        try:
            if file_path.lower().endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path)
            
            # 标准化列名（支持中英文）
            column_mapping = {
                '伴奏ID': '伴奏ID',
                'accompaniment_id': '伴奏ID',
                'id': '伴奏ID',
                '歌名': '歌名',
                'song_name': '歌名',
                'name': '歌名',
                '歌手': '歌手',
                'artist': '歌手',
                '副歌开始时间': '副歌开始时间',
                'chorus_start': '副歌开始时间',
                'start_time': '副歌开始时间',
                '副歌结束时间': '副歌结束时间',
                'chorus_end': '副歌结束时间',
                'end_time': '副歌结束时间',
                '段落剪切时间': '段落剪切时间',
                'split_time': '段落剪切时间',
                'cut_time': '段落剪切时间',
            }
            
            # 重命名列
            df = df.rename(columns=lambda x: column_mapping.get(x.strip(), x))
            
            self.excel_data = df
            self.log(f"已加载 Excel 文件，共 {len(df)} 行数据")
            
            # 初始化结果表格
            self.init_result_table(len(df))
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载 Excel 文件失败：\n{str(e)}")
            self.log(f"加载 Excel 失败: {str(e)}")
    
    def init_result_table(self, row_count: int):
        """初始化结果表格"""
        self.result_table.setRowCount(row_count)
        self.results = [None] * row_count
    
    def check_matching(self):
        """检查音频文件与Excel的匹配情况"""
        # 验证输入
        if not self.audio_files:
            QMessageBox.warning(self, "警告", "请先加载音频文件或目录")
            return
        
        if self.excel_data is None or len(self.excel_data) == 0:
            QMessageBox.warning(self, "警告", "请先加载剪切时间表格")
            return
        
        # 获取匹配策略
        if self.match_id_radio.isChecked():
            match_strategy = '伴奏ID优先'
        elif self.match_name_radio.isChecked():
            match_strategy = '按歌名'
        else:
            match_strategy = '模糊匹配'
        
        self.log("=" * 50)
        self.log("开始检查匹配情况...")
        self.log(f"匹配策略: {match_strategy}")
        self.log("")
        
        # 显示音频文件列表
        self.log(f"已加载 {len(self.audio_files)} 个音频文件：")
        for i, file_path in enumerate(self.audio_files[:20]):
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            self.log(f"  [{i+1}] {file_name}")
        if len(self.audio_files) > 20:
            self.log(f"  ... 还有 {len(self.audio_files) - 20} 个文件")
        self.log("")
        
        # 构建音频映射
        audio_map = {}
        for file_path in self.audio_files:
            file_name = os.path.splitext(os.path.basename(file_path))[0]
            audio_map[file_name] = file_path
            audio_map[file_name.strip().lower()] = file_path
        
        # 检查匹配
        matched_count = 0
        unmatched_count = 0
        
        self.log("开始匹配检查：")
        self.log("")
        
        for idx, row in self.excel_data.iterrows():
            acc_id = row.get('伴奏ID', '')
            song_name = row.get('歌名', '')
            
            # 尝试匹配
            audio_path = None
            if match_strategy in ['伴奏ID优先', '模糊匹配']:
                if pd.notna(acc_id):
                    id_str = str(acc_id).strip()
                    # 处理数字型ID
                    if '.' in id_str and id_str.replace('.', '').replace('-', '').isdigit():
                        try:
                            id_str = str(int(float(id_str)))
                        except:
                            pass
                    
                    # 1. 精确匹配
                    if id_str in audio_map:
                        audio_path = audio_map[id_str]
                    elif id_str.lower() in audio_map:
                        audio_path = audio_map[id_str.lower()]
                    
                    # 2. 前缀匹配（如 12345 匹配 12345-原唱）
                    if not audio_path:
                        id_lower = id_str.lower()
                        for key, path in audio_map.items():
                            key_lower = key.lower()
                            if (key_lower.startswith(id_lower + '-') or 
                                key_lower.startswith(id_lower + '_') or 
                                key_lower.startswith(id_lower + ' ')):
                                audio_path = path
                                break
            
            if not audio_path and match_strategy in ['按歌名', '伴奏ID优先', '模糊匹配']:
                if pd.notna(song_name):
                    name_str = str(song_name).strip()
                    # 1. 精确匹配
                    if name_str in audio_map:
                        audio_path = audio_map[name_str]
                    elif name_str.lower() in audio_map:
                        audio_path = audio_map[name_str.lower()]
                    
                    # 2. 前缀匹配
                    if not audio_path:
                        name_lower = name_str.lower()
                        for key, path in audio_map.items():
                            key_lower = key.lower()
                            if (key_lower.startswith(name_lower + '-') or 
                                key_lower.startswith(name_lower + '_') or 
                                key_lower.startswith(name_lower + ' ')):
                                audio_path = path
                                break
            
            # 模糊匹配（包含匹配）
            if not audio_path and match_strategy == '模糊匹配':
                if pd.notna(acc_id):
                    id_str = str(acc_id).strip()
                    if '.' in id_str:
                        try:
                            id_str = str(int(float(id_str)))
                        except:
                            pass
                    id_lower = id_str.lower()
                    
                    for key in audio_map.keys():
                        if id_lower in key.lower() or key.lower() in id_lower:
                            audio_path = audio_map[key]
                            break
                
                if not audio_path and pd.notna(song_name):
                    name_lower = str(song_name).strip().lower()
                    for key in audio_map.keys():
                        if name_lower in key.lower() or key.lower() in name_lower:
                            audio_path = audio_map[key]
                            break
            
            # 显示结果
            if audio_path:
                matched_count += 1
                matched_file = os.path.basename(audio_path)
                self.log(f"✓ 行 {idx + 1}: 伴奏ID='{acc_id}' 歌名='{song_name}' → {matched_file}")
            else:
                unmatched_count += 1
                self.log(f"✗ 行 {idx + 1}: 伴奏ID='{acc_id}' 歌名='{song_name}' → 未匹配")
        
        # 显示统计
        self.log("")
        self.log("=" * 50)
        self.log(f"匹配统计：")
        self.log(f"  总行数: {len(self.excel_data)}")
        self.log(f"  成功匹配: {matched_count}")
        self.log(f"  未匹配: {unmatched_count}")
        self.log(f"  匹配率: {matched_count / len(self.excel_data) * 100:.1f}%")
        self.log("=" * 50)
        
        # 显示提示
        if unmatched_count > 0:
            QMessageBox.warning(
                self,
                "匹配检查完成",
                f"匹配完成！\n\n"
                f"成功匹配: {matched_count}\n"
                f"未匹配: {unmatched_count}\n\n"
                f"请检查日志窗口查看详细信息。\n"
                f"建议：\n"
                f"1. 检查音频文件名是否与Excel中的伴奏ID或歌名一致\n"
                f"2. 尝试使用'模糊匹配'策略\n"
                f"3. 确认Excel中的伴奏ID和歌名没有多余空格"
            )
        else:
            QMessageBox.information(
                self,
                "匹配检查完成",
                f"太棒了！所有 {matched_count} 行数据都成功匹配！\n\n可以开始处理了。"
            )
    
    def start_processing(self):
        """开始处理"""
        # 验证输入
        if not self.audio_files:
            QMessageBox.warning(self, "警告", "请先加载音频文件或目录")
            return
        
        if self.excel_data is None or len(self.excel_data) == 0:
            QMessageBox.warning(self, "警告", "请先加载剪切时间表格")
            return
        
        output_dir = self.output_input.text().strip()
        if not output_dir:
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return
        
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建输出目录失败：\n{str(e)}")
                return
        
        # 检查导出模式
        if not self.mode_full_check.isChecked() and not self.mode_split_check.isChecked():
            QMessageBox.warning(self, "警告", "请至少选择一种导出模式")
            return
        
        # 获取匹配策略
        if self.match_id_radio.isChecked():
            match_strategy = '伴奏ID优先'
        elif self.match_name_radio.isChecked():
            match_strategy = '按歌名'
        else:
            match_strategy = '模糊匹配'
        
        # 准备配置
        config = {
            'audio_files': self.audio_files,
            'excel_data': self.excel_data,
            'output_dir': output_dir,
            'export_format': self.format_combo.currentText(),
            'mode_full': self.mode_full_check.isChecked(),
            'mode_split': self.mode_split_check.isChecked(),
            'overwrite': self.overwrite_check.isChecked(),
            'match_strategy': match_strategy,
            'start_adjust': self.start_adjust_spinbox.value(),
            'end_adjust': self.end_adjust_spinbox.value()
        }
        
        # 禁用控件
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        
        # 清空日志和进度
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        # 启动工作线程
        self.process_worker = ProcessWorker(config)
        self.process_worker.progress_updated.connect(self.update_progress)
        self.process_worker.row_updated.connect(self.update_result_row)
        self.process_worker.log_message.connect(self.log)
        self.process_worker.finished.connect(self.processing_finished)
        self.process_worker.start()
        
        self.log("开始处理...")
    
    def stop_processing(self):
        """停止处理"""
        if self.process_worker:
            self.process_worker.stop()
            self.log("正在停止处理...")
            self.stop_btn.setEnabled(False)
    
    def update_progress(self, current: int, total: int):
        """更新进度条"""
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.statusBar().showMessage(f"处理中: {current}/{total}")
    
    def update_result_row(self, row_idx: int, result: dict):
        """更新结果表格行"""
        self.results[row_idx] = result
        
        # 列0: 伴奏ID
        acc_id = result.get('accompaniment_id', '')
        if acc_id:
            self.result_table.setItem(row_idx, 0, QTableWidgetItem(str(acc_id)))
        else:
            self.result_table.setItem(row_idx, 0, QTableWidgetItem(''))
        
        # 列1: 整段导出
        output_full = result.get('output_full', '')
        if output_full:
            self.result_table.setItem(row_idx, 1, QTableWidgetItem(os.path.basename(output_full)))
        else:
            self.result_table.setItem(row_idx, 1, QTableWidgetItem(''))
        
        # 列2: 前段导出
        output_part1 = result.get('output_part1', '')
        if output_part1:
            self.result_table.setItem(row_idx, 2, QTableWidgetItem(os.path.basename(output_part1)))
        else:
            self.result_table.setItem(row_idx, 2, QTableWidgetItem(''))
        
        # 列3: 后段导出
        output_part2 = result.get('output_part2', '')
        if output_part2:
            self.result_table.setItem(row_idx, 3, QTableWidgetItem(os.path.basename(output_part2)))
        else:
            self.result_table.setItem(row_idx, 3, QTableWidgetItem(''))
        
        # 列4: 状态（使用更柔和的颜色）
        status_item = QTableWidgetItem(result.get('status', ''))
        status = result.get('status', '')
        if status == '成功':
            # 更柔和的绿色（降低饱和度）
            status_item.setBackground(QColor(240, 255, 240))
            status_item.setForeground(QColor(0, 0, 0))  # 黑色文字
        elif status == '失败':
            # 更柔和的红色（降低饱和度）
            status_item.setBackground(QColor(255, 240, 240))
            status_item.setForeground(QColor(0, 0, 0))  # 黑色文字
        elif status == '已取消':
            # 更柔和的黄色（降低饱和度）
            status_item.setBackground(QColor(255, 250, 240))
            status_item.setForeground(QColor(0, 0, 0))  # 黑色文字
        else:
            status_item.setForeground(QColor(0, 0, 0))  # 黑色文字
        self.result_table.setItem(row_idx, 4, status_item)
        
        # 列5: 错误信息
        error_msg = result.get('error', '')
        self.result_table.setItem(row_idx, 5, QTableWidgetItem(str(error_msg) if error_msg else ''))
    
    def processing_finished(self, stats: dict):
        """处理完成"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(True)
        
        total = stats['total']
        success = stats['success']
        failed = stats['failed']
        cancelled = stats['cancelled']
        
        message = f"处理完成！\n总数: {total}\n成功: {success}\n失败: {failed}\n已取消: {cancelled}"
        self.log(message)
        self.statusBar().showMessage(f"完成: {success}/{total} 成功")
        
        QMessageBox.information(self, "完成", message)
    
    def export_results(self):
        """导出结果"""
        if not self.results or not any(self.results):
            QMessageBox.warning(self, "警告", "没有可导出的结果")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出处理结果",
            f"处理结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "Excel 文件 (*.xlsx);;CSV 文件 (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            # 准备数据
            export_data = []
            for idx, result in enumerate(self.results):
                if result:
                    export_data.append({
                        '行号': idx + 1,
                        '伴奏ID': result.get('accompaniment_id', ''),
                        '歌名': result.get('song_name', ''),
                        '输入路径': result.get('input_path', ''),
                        '整段导出路径': result.get('output_full', ''),
                        '前段导出路径': result.get('output_part1', ''),
                        '后段导出路径': result.get('output_part2', ''),
                        '状态': result.get('status', ''),
                        '错误信息': result.get('error', '')
                    })
            
            df = pd.DataFrame(export_data)
            
            if file_path.lower().endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                df.to_excel(file_path, index=False)
            
            self.log(f"结果已导出到: {file_path}")
            QMessageBox.information(self, "成功", f"结果已导出到:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出结果失败：\n{str(e)}")
            self.log(f"导出失败: {str(e)}")
    
    def log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用图标（优先使用PNG，否则使用SVG）
    icon_dir = os.path.dirname(__file__)
    icon_path = None
    # 优先尝试PNG图标
    png_path = os.path.join(icon_dir, "icon_scissors.png")
    svg_path = os.path.join(icon_dir, "icon_scissors.svg")
    if os.path.exists(png_path):
        icon_path = png_path
    elif os.path.exists(svg_path):
        icon_path = svg_path
    
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    
    # 设置应用样式为 Fusion
    app.setStyle('Fusion')
    
    # 强制使用亮色主题，禁用夜间模式
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 120, 215))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)
    
    window = ChorusCutterGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

