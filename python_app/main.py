import sys
import subprocess
import os
import time
import colorsys
import math
import random
import ctypes
import json
import webbrowser
from ctypes.wintypes import MSG, RECT
try:
    import mss
    from PIL import Image
    HAS_MSS = True
except ImportError:
    HAS_MSS = False
try:
    from pynput import mouse, keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
try:
    import wmi
    wmi_obj = wmi.WMI(namespace='root\\wmi')
    HAS_WMI = True
except Exception:
    HAS_WMI = False
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QSlider, QColorDialog, QGroupBox, QGridLayout, QSpacerItem, QSizePolicy, QStackedLayout, QCheckBox, QSystemTrayIcon, QMenu, QStyle, QComboBox, QInputDialog, QMessageBox, QDialog, QPlainTextEdit, QProgressDialog, QTextBrowser, QGraphicsOpacityEffect, QGraphicsDropShadowEffect, QFrame
from PySide6.QtCore import Qt, QSize, QTimer, QPoint, QSettings, Signal, QThread, QPropertyAnimation, QEasingCurve, QVariantAnimation
from PySide6.QtGui import QColor, QFont, QPalette, QIcon, QMouseEvent, QAction, QPainter
import winreg
from python_controller import L5PKeyboard
import threading
from threading import Lock
from collections import deque
import urllib.request
import urllib.error
import tempfile
import traceback

CURRENT_VERSION = "v2.1"

def _resolve_original_exe_path():
    if not getattr(sys, 'frozen', False):
        return None
    candidates = []
    if getattr(sys, 'executable', None):
        candidates.append(os.path.abspath(sys.executable))
    if len(sys.argv) > 0 and sys.argv[0]:
        candidates.append(os.path.abspath(sys.argv[0]))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return candidates[0] if candidates else None

def _ps_escape(value):
    # Escape content for use in PowerShell double-quoted strings.
    return str(value).replace('`', '``').replace('"', '`"')

def sanitized_child_env(base_env=None, include_pythonpath=False):
    env = dict(base_env or os.environ)
    # PyInstaller one-file processes pass runtime extraction hints through
    # environment variables. If inherited by child processes after parent
    # teardown, they can reference deleted _MEI temp folders and trigger
    # "Failed to load Python DLL" errors.
    env.pop('_MEIPASS', None)
    env.pop('_MEIPASS2', None)
    for key in [k for k in env if k.startswith('_PYI_')]:
        env.pop(key, None)

    # Remove the temp folder from PATH (crucial to avoid "Python DLL not found"
    # if the child process inherits a PATH pointing to a deleted _MEI folder)
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            # Find the PATH key (case-insensitive search for Windows compat)
            path_key = next((k for k in env if k.lower() == 'path'), None)
            if path_key:
                path_sep = os.pathsep
                current_path_list = env[path_key].split(path_sep)

                # Normalize paths for comparison
                mei_normalized = os.path.normcase(os.path.abspath(meipass))

                new_path_list = []
                for p in current_path_list:
                    # Guard against empty paths which abspath might resolve to CWD
                    if not p.strip():
                        continue
                    p_normalized = os.path.normcase(os.path.abspath(p))
                    if p_normalized != mei_normalized:
                        new_path_list.append(p)

                env[path_key] = path_sep.join(new_path_list)

    if include_pythonpath:
        env['PYTHONPATH'] = os.pathsep.join(sys.path)
    else:
        env.pop('PYTHONPATH', None)
    # Ensure frozen child re-exec starts with a fresh extraction context.
    env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    return env

# Simple in-memory log buffer that mirrors stdout/stderr and retains recent output
class LogBuffer:
    def __init__(self, orig_stream, max_chars=1_000_000):
        self.orig = orig_stream
        self.lock = Lock()
        self.lines = deque()
        self.max_chars = max_chars
        self.current_chars = 0
    def write(self, s):
        with self.lock:
            self.lines.append(s)
            self.current_chars += len(s)
            while self.current_chars > self.max_chars and self.lines:
                self.current_chars -= len(self.lines.popleft())
        try:
            self.orig.write(s)
        except Exception:
            pass
    def flush(self):
        try:
            self.orig.flush()
        except Exception:
            pass
    def get_text(self):
        with self.lock:
            return ''.join(self.lines)
    def clear(self):
        with self.lock:
            self.lines.clear()
            self.current_chars = 0

# Install global buffers so prints and errors are captured
_ORIG_STDOUT = sys.stdout
_ORIG_STDERR = sys.stderr
_STDOUT_BUFFER = LogBuffer(_ORIG_STDOUT)
_STDERR_BUFFER = LogBuffer(_ORIG_STDERR)
sys.stdout = _STDOUT_BUFFER
sys.stderr = _STDERR_BUFFER
from PySide6.QtWidgets import QStyleOptionSlider

class FadeDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(200)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in.start()

    def closeEvent(self, event):
        if not hasattr(self, '_closing'):
            self._closing = True
            event.ignore()
            self.fade_out = QPropertyAnimation(self, b"windowOpacity")
            self.fade_out.setDuration(150)
            self.fade_out.setStartValue(1.0)
            self.fade_out.setEndValue(0.0)
            self.fade_out.finished.connect(self.close)
            self.fade_out.start()
        else:
            event.accept()

class AnimatedSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            if not sr.contains(event.pos()):
                # Jump to click position smoothly
                val = self.minimum() + ((self.maximum() - self.minimum()) * event.pos().x()) / self.width()
                self.set_animated_value(int(val))
                event.accept()
                return
        super().mousePressEvent(event)

    def set_animated_value(self, val):
        if not hasattr(self, 'anim'):
            self.anim = QPropertyAnimation(self, b"value")
            self.anim.setDuration(150)
            self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.stop()
        self.anim.setStartValue(self.value())
        self.anim.setEndValue(val)
        self.anim.start()

class GlowButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.effect = QGraphicsOpacityEffect(self)
        self.effect.setOpacity(1.0)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity")
        self.anim.setDuration(150)

    def mousePressEvent(self, event):
        self.anim.stop()
        self.anim.setEndValue(0.5)
        self.anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.anim.stop()
        self.anim.setEndValue(1.0)
        self.anim.start()
        super().mouseReleaseEvent(event)

class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(35)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(8)
        self.btn_close = QPushButton()
        self.setup_button(self.btn_close, '#FF605C', '#FF0000')
        self.btn_close.clicked.connect(self.parent.close)
        self.btn_settings = QPushButton()
        self.btn_settings.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'assets', 'settings.svg')))
        self.btn_settings.setIconSize(QSize(18, 18))
        self.btn_settings.setFixedSize(24, 24)
        self.btn_settings.setStyleSheet('\n            QPushButton {\n                background: transparent;\n                border: none;\n                margin-bottom: 2px;\n            }\n            QPushButton:hover {\n                background-color: rgba(255, 255, 255, 30);\n                border-radius: 4px;\n            }\n        ')
        self.btn_settings.clicked.connect(self.parent.toggle_settings)
        
        self.btn_help = QPushButton('Help')
        self.btn_help.setFixedHeight(22)
        self.btn_help.setCursor(Qt.PointingHandCursor)
        self.btn_help.setToolTip('Help / Report Issue')
        self.btn_help.setStyleSheet('''
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 4px;
                color: #00E5FF;
                font-size: 11px;
                font-weight: bold;
                padding: 0 10px;
                margin-bottom: 2px;
            }
            QPushButton:hover {
                background-color: rgba(0, 229, 255, 0.1);
            }
        ''')
        self.btn_live_preview = GlowButton('Live Preview')
        self.btn_live_preview.setFixedHeight(22)
        self.btn_live_preview.setCursor(Qt.PointingHandCursor)
        self.btn_live_preview.setStyleSheet('''
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 4px;
                color: #00E5FF;
                font-size: 11px;
                font-weight: bold;
                padding: 0 10px;
                margin-bottom: 2px;
            }
            QPushButton:hover {
                background-color: rgba(0, 229, 255, 0.1);
            }
        ''')
        self.btn_live_preview.clicked.connect(self.parent.toggle_preview)
        
        self.btn_help.clicked.connect(self.parent.show_help_dialog)
        
        layout.addWidget(self.btn_live_preview)
        layout.addWidget(self.btn_help)
        layout.addWidget(self.btn_settings)
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addItem(spacer)
        self.btn_minimize = QPushButton()
        self.setup_button(self.btn_minimize, '#FFBD44', '#FFA500')
        self.btn_minimize.clicked.connect(self.parent.minimize_app)
        self.btn_maximize = QPushButton()
        self.setup_button(self.btn_maximize, '#00CA4E', '#008000')
        self.btn_maximize.clicked.connect(self.toggle_maximize)
        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_maximize)
        layout.addWidget(self.btn_close)
        self.start_pos = None
    def setup_button(self, btn, color, hover_color):
        # ***<module>.CustomTitleBar.setup_button: Failure: Compilation Error
        btn.setFixedSize(14, 14)
        btn.setStyleSheet(f'''\n            QPushButton {{\n                background-color: {color};\n                border-radius: 7px;\n                border: none;\n            }}\n            QPushButton:hover {{\n                background-color: {hover_color};\n            }}\n        ''')
    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            try:
                import ctypes
                ctypes.windll.user32.ReleaseCapture()
                hwnd = int(self.parent.winId())
                ctypes.windll.user32.SendMessageW(hwnd, 161, 2, 0)
            except Exception:
                return None
    def mouseMoveEvent(self, event: QMouseEvent):
        return


class LogsDialog(FadeDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Application Logs')
        self.setMinimumSize(700, 400)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        layout = QVBoxLayout(self)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        button_layout = QHBoxLayout()
        self.btn_clear = QPushButton('Clear')
        self.btn_copy = QPushButton('Copy All')
        self.btn_close = QPushButton('Close')
        self.btn_clear.clicked.connect(self.clear_logs)
        self.btn_copy.clicked.connect(self.copy_logs)
        self.btn_close.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_clear)
        button_layout.addWidget(self.btn_copy)
        button_layout.addWidget(self.btn_close)
        layout.addLayout(button_layout)
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.refresh)
        self.update_timer.start(500)
    def refresh(self):
        try:
            text = _STDOUT_BUFFER.get_text() + _STDERR_BUFFER.get_text()
            self.log_view.setPlainText(text)
            self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
        except Exception:
            pass
    def clear_logs(self):
        try:
            _STDOUT_BUFFER.clear()
            _STDERR_BUFFER.clear()
            self.log_view.clear()
        except Exception:
            pass
    def copy_logs(self):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.log_view.toPlainText())
        except Exception:
            pass

class KeyboardPreviewWindow(FadeDialog):
    def __init__(self, parent_app):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.setWindowTitle('Keyboard Real-Time Preview')
        self.setFixedSize(400, 100)
        self.setWindowFlags(self.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        self.zone_widgets = []
        for i in range(4):
            w = QWidget()
            w.setStyleSheet("background-color: black; border-radius: 5px; border: 1px solid #333;")
            layout.addWidget(w)
            self.zone_widgets.append(w)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_colors)
        self.timer.start(50)

    def update_colors(self):
        try:
            colors = self.parent_app.custom_colors
            if len(colors) >= 12:
                for i in range(4):
                    r = max(0, min(255, int(colors[i*3])))
                    g = max(0, min(255, int(colors[i*3+1])))
                    b = max(0, min(255, int(colors[i*3+2])))
                    self.zone_widgets[i].setStyleSheet(f"background-color: rgb({r},{g},{b}); border-radius: 5px; border: 1px solid #333;")
        except Exception:
            pass



class UpdateDownloader(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                total_size = int(response.headers.get('content-length', 0))
                tmp_dir = tempfile.gettempdir()
                dest_path = os.path.join(tmp_dir, "4_Zone_Rgb_Toolkit_Updated.exe")
                
                with open(dest_path, 'wb') as f:
                    downloaded = 0
                    while True:
                        chunk = response.read(65536)
                        if not chunk: break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.progress.emit(percent)
                self.finished.emit(dest_path)
        except Exception as e:
            self.error.emit(str(e))

class RGBControllerApp(QMainWindow):
    # ***<module>.RGBControllerApp: Failure: Different bytecode
    update_available = Signal(str, str, str)

    def __init__(self):
        # ***<module>.RGBControllerApp.__init__: Failure: Compilation Error
        super().__init__()
        self.setWindowTitle('4 Zone Rgb Toolkit')
        self.original_exe_path = _resolve_original_exe_path()
        self.setMinimumSize(500, 480)
        self.icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'rgb_wheel.ico')
        self.setWindowIcon(QIcon(self.icon_path))
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        try:
            hwnd = int(self.winId())
            margins = RECT(1, 1, 1, 1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
        except Exception:
            pass
        self.setStyleSheet('\n            QMainWindow {\n                background-color: transparent;\n            }\n            #MainContainer {\n                background-color: #0E0E12;\n                border: 1px solid rgba(255, 255, 255, 0.08);\n                border-radius: 12px;\n            }\n            QLabel {\n                color: #E2E2E2;\n                font-family: \'Segoe UI Variable\', \'Segoe UI\', sans-serif;\n                font-size: 14px;\n            }\n            QGroupBox {\n                color: #00E5FF;\n                font-weight: 600;\n                font-family: \'Segoe UI Variable\', \'Segoe UI\', sans-serif;\n                font-size: 13px;\n                border: 1px solid rgba(255, 255, 255, 0.05);\n                border-radius: 10px;\n                background-color: rgba(255, 255, 255, 0.02);\n                margin-top: 24px;\n                padding-top: 15px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 12px;\n                padding: 0 6px 0 6px;\n                background-color: transparent;\n            }\n            QListWidget {\n                background-color: #1A1A1E;\n                color: #FFFFFF;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n                border-radius: 8px;\n                padding: 4px;\n                font-family: \'Segoe UI Variable\', \'Segoe UI\', sans-serif;\n                font-size: 13px;\n                outline: none;\n            }\n            QListWidget::item {\n                padding: 10px;\n                border-radius: 4px;\n                margin-bottom: 2px;\n            }\n            QListWidget::item:hover {\n                background-color: rgba(0, 229, 255, 0.1);\n            }\n            QListWidget::item:selected {\n                background-color: #00E5FF;\n                color: #0E0E12;\n                font-weight: 600;\n            }\n            QPushButton {\n                background-color: #1A1A1E;\n                color: white;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n                border-radius: 6px;\n                padding: 8px 16px;\n                font-family: \'Segoe UI Variable\', \'Segoe UI\', sans-serif;\n                font-size: 13px;\n                font-weight: 500;\n            }\n            QPushButton:hover {\n                background-color: #00E5FF;\n                color: black;\n                font-weight: 600;\n                border: 1px solid #00E5FF;\n            }\n            QPushButton:pressed {\n                background-color: #00B3CC;\n                border: 1px solid #00B3CC;\n            }\n            QSlider::groove:horizontal {\n                border: none;\n                height: 6px;\n                background: #2A2A2E;\n                border-radius: 3px;\n            }\n            QSlider::sub-page:horizontal {\n                background: #00E5FF;\n                border-radius: 3px;\n            }\n            QSlider::handle:horizontal {\n                background: #FFFFFF;\n                border: 2px solid #00E5FF;\n                width: 14px;\n                height: 14px;\n                margin: -4px 0;\n                border-radius: 7px;\n            }\n            QSlider::handle:horizontal:hover {\n                background: #00E5FF;\n            }\n            QSlider::sub-page:horizontal:disabled {\n                background: #444444;\n            }\n            QSlider::handle:horizontal:disabled {\n                border: 2px solid #555555;\n                background: #666666;\n            }\n        ')
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        master_layout = QVBoxLayout(central_widget)
        master_layout.setContentsMargins(0, 0, 0, 0)
        main_container = QWidget()
        main_container.setObjectName('MainContainer')
        master_layout.addWidget(main_container)
        app_layout = QVBoxLayout(main_container)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(0)
        self.title_bar = CustomTitleBar(self)
        app_layout.addWidget(self.title_bar)
        self.stack = QStackedLayout()
        app_layout.addLayout(self.stack)
        main_view = QWidget()
        main_layout = QVBoxLayout(main_view)
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(15)
        self.stack.addWidget(main_view)
        self.settings_view = QWidget()
        settings_layout = QVBoxLayout(self.settings_view)
        settings_layout.setContentsMargins(20, 10, 20, 20)
        settings_header = QHBoxLayout()
        settings_header.addStretch()
        self.btn_close_settings = QPushButton('✕')
        self.btn_close_settings.setFixedSize(30, 30)
        self.btn_close_settings.setStyleSheet('QPushButton { background: transparent; color: white; font-weight: bold; font-size: 18px; border: none; } QPushButton:hover { color: #FF605C; }')
        self.btn_close_settings.clicked.connect(self.toggle_settings)
        settings_header.addWidget(self.btn_close_settings)
        settings_layout.addLayout(settings_header)
        settings_layout.addWidget(QLabel('Settings', styleSheet='color: #00E5FF; font-size: 20px; font-weight: bold;'))
        on_icon_path  = os.path.join(os.path.dirname(__file__), 'assets', 'toggle_on.svg').replace('\\', '/')
        off_icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'toggle_off.svg').replace('\\', '/')
        toggle_css = f'\n            QCheckBox {{ color: white; font-size: 14px; spacing: 10px; }}\n            QCheckBox::indicator {{ width: 40px; height: 24px; }}\n            QCheckBox::indicator:unchecked {{ image: url("{off_icon_path}"); }}\n            QCheckBox::indicator:checked {{ image: url("{on_icon_path}"); }}\n        '
        self.minimize_to_tray_cb = QCheckBox('Minimize to Tray')
        self.minimize_to_tray_cb.setStyleSheet(toggle_css)
        self.minimize_to_tray_cb.toggled.connect(self.save_settings)
        settings_layout.addWidget(self.minimize_to_tray_cb)
        self.launch_on_start_cb = QCheckBox('Launch on Startup (Hidden in Tray)')
        self.launch_on_start_cb.setStyleSheet(toggle_css)
        self.launch_on_start_cb.toggled.connect(self.save_settings)
        settings_layout.addWidget(self.launch_on_start_cb)
        settings_layout.addWidget(QLabel('Startup Preset:', styleSheet='color: #00E5FF; font-weight: bold; margin-top: 15px;'))
        self.startup_preset_combo = QComboBox()
        self.startup_preset_combo.setStyleSheet('\n            QComboBox { background-color: #1A1A1E; color: white; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 6px; font-family: \'Segoe UI Variable\'; }\n            QComboBox::drop-down { border: none; }\n        ')
        self.startup_preset_combo.currentTextChanged.connect(self.save_settings)
        settings_layout.addWidget(self.startup_preset_combo)
        settings_layout.addSpacing(20)
        self.btn_clear_cache = GlowButton('Clear Cache && Reset')
        self.btn_clear_cache.setFixedHeight(35)
        self.btn_clear_cache.setCursor(Qt.PointingHandCursor)
        self.btn_clear_cache.setStyleSheet('QPushButton { background-color: rgba(255, 85, 85, 0.1); color: #FF5555; border: 1px solid #FF5555; border-radius: 6px; font-weight: bold; font-family: \'Segoe UI Variable\'; font-size: 13px; } QPushButton:hover { background-color: #FF5555; color: white; }')
        self.btn_clear_cache.clicked.connect(self.clear_cache)
        settings_layout.addWidget(self.btn_clear_cache)

        # Logs viewer button
        self.btn_view_logs = GlowButton('View Logs')
        self.btn_view_logs.setFixedHeight(35)
        self.btn_view_logs.setCursor(Qt.PointingHandCursor)
        self.btn_view_logs.setStyleSheet('QPushButton { background-color: rgba(255, 255, 255, 0.03); color: #E2E2E2; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 6px; font-family: \'Segoe UI Variable\'; font-size: 13px; } QPushButton:hover { background-color: rgba(0, 229, 255, 0.08); color: white; }')
        self.btn_view_logs.clicked.connect(self.show_logs)
        settings_layout.addWidget(self.btn_view_logs)

        self.btn_clear_update_cache = GlowButton('Clear Update Cache')
        self.btn_clear_update_cache.setFixedHeight(35)
        self.btn_clear_update_cache.setCursor(Qt.PointingHandCursor)
        self.btn_clear_update_cache.setStyleSheet('QPushButton { background-color: rgba(255, 255, 255, 0.03); color: #AAAAAA; border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; font-family: \'Segoe UI Variable\'; font-size: 13px; } QPushButton:hover { background-color: rgba(0, 229, 255, 0.08); color: white; }')
        self.btn_clear_update_cache.clicked.connect(self.clear_update_cache)
        settings_layout.addWidget(self.btn_clear_update_cache)
        
        version_label = QLabel(f'Version: {CURRENT_VERSION}')
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet('color: #666666; margin-top: 15px; font-size: 11px; font-weight: bold; font-family: "Segoe UI Variable", sans-serif;')
        settings_layout.addWidget(version_label)
        
        settings_layout.addStretch()
        self.stack.addWidget(self.settings_view)
        
        # --- Pomodoro Fullscreen View ---
        self.pomo_fullscreen_view = QWidget()
        self.pomo_fullscreen_view.setStyleSheet("background-color: black;")
        pomo_fs_layout = QVBoxLayout(self.pomo_fullscreen_view)
        pomo_fs_layout.setAlignment(Qt.AlignCenter)
        
        self.pomo_fs_label = QLabel("00:00:00")
        self.pomo_fs_label.setStyleSheet("color: white; font-size: 150px; font-weight: bold; font-family: 'Segoe UI Variable';")
        self.pomo_fs_label.setAlignment(Qt.AlignCenter)
        
        self.btn_pomo_fs_stop = GlowButton("Stop Timer")
        self.btn_pomo_fs_stop.setCursor(Qt.PointingHandCursor)
        self.btn_pomo_fs_stop.setFixedSize(250, 60)
        self.btn_pomo_fs_stop.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 85, 85, 0.1);
                color: #FF5555;
                border: 2px solid rgba(255, 85, 85, 0.3);
                border-radius: 12px;
                font-size: 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(255, 85, 85, 0.2);
            }
        """)
        self.btn_pomo_fs_stop.clicked.connect(self.stop_pomodoro)
        
        pomo_fs_layout.addStretch()
        pomo_fs_layout.addWidget(self.pomo_fs_label, alignment=Qt.AlignCenter)
        pomo_fs_layout.addSpacing(40)
        pomo_fs_layout.addWidget(self.btn_pomo_fs_stop, alignment=Qt.AlignCenter)
        pomo_fs_layout.addStretch()
        
        self.stack.addWidget(self.pomo_fullscreen_view)

        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.icon_path))
        tray_menu = QMenu()
        restore_action = QAction('Restore', self)
        restore_action.triggered.connect(self.restore_app)
        quit_action = QAction('Quit', self)
        quit_action.triggered.connect(self.tray_quit)
        tray_menu.addAction(restore_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        title_label = QLabel('4 ZONE RGB TOOLKIT')
        title_font = QFont('Segoe UI Variable', 24, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet('color: #00E5FF; margin-bottom: 2px; letter-spacing: 2px;')
        main_layout.addWidget(title_label)
        subtitle = QLabel('Hardware & Software RGB Customization')
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet('color: #666666; margin-bottom: 12px; font-size: 12px; font-weight: 500; font-family: \'Segoe UI Variable\', sans-serif;')
        main_layout.addWidget(subtitle)
        self.disclaimer_widget = QWidget()
        self.disclaimer_widget.setStyleSheet('\n            QWidget {\n                background-color: rgba(255, 170, 0, 0.05);\n                border: 1px solid rgba(255, 170, 0, 0.2);\n                border-radius: 8px;\n            }\n            QLabel { background: transparent; border: none; }\n        ')
        disclaimer_layout = QHBoxLayout(self.disclaimer_widget)
        disclaimer_layout.setContentsMargins(10, 8, 10, 8)
        warn_icon = QLabel('⚠️')
        warn_icon.setStyleSheet('font-size: 20px; color: #FFAA00;')
        disclaimer_text_layout = QVBoxLayout()
        disclaimer_text_layout.setSpacing(2)
        disclaimer_title = QLabel('Hardware Compatibility Notice')
        disclaimer_title.setStyleSheet('color: #FFAA00; font-weight: bold; font-size: 13px;')
        disclaimer_body = QLabel('This software is specifically built and tested for Lenovo LOQ and Legion laptops with 4-Zone RGB keyboards. Using it on unsupported hardware may result in unexpected behavior.')
        disclaimer_body.setWordWrap(True)
        disclaimer_body.setStyleSheet('color: #CCCCCC; font-size: 11px;')
        self.dnd_checkbox = QCheckBox('Do not show again')
        self.dnd_checkbox.setStyleSheet('QCheckBox { color: #888888; font-size: 11px; font-weight: 500; background: transparent; border: none; }')
        self.dnd_checkbox.toggled.connect(self.save_dnd_preference)
        disclaimer_text_layout.addWidget(disclaimer_title)
        disclaimer_text_layout.addWidget(disclaimer_body)
        disclaimer_text_layout.addWidget(self.dnd_checkbox)
        self.btn_close_disclaimer = QPushButton('✕')
        self.btn_close_disclaimer.setFixedSize(24, 24)
        self.btn_close_disclaimer.setCursor(Qt.PointingHandCursor)
        self.btn_close_disclaimer.setStyleSheet('QPushButton { color: #FFAA00; background: transparent; border: none; font-size: 16px; font-weight: bold; } QPushButton:hover { color: #FFFFFF; background: rgba(255,255,255,0.1); border-radius: 4px; }')
        self.btn_close_disclaimer.clicked.connect(self.close_disclaimer)
        disclaimer_layout.addWidget(warn_icon, 0, Qt.AlignTop)
        disclaimer_layout.addLayout(disclaimer_text_layout, stretch=1)
        disclaimer_layout.addWidget(self.btn_close_disclaimer, 0, Qt.AlignTop)
        main_layout.addWidget(self.disclaimer_widget)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(15)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)
        self.effects_panel_spacing = right_layout.spacing()
        split_layout.addLayout(left_layout, stretch=2)
        split_layout.addLayout(right_layout, stretch=1)
        main_layout.addLayout(split_layout)
        controls_title = QLabel('Main Controls')
        controls_title.setStyleSheet('color: #00E5FF; font-weight: bold; font-family: "Segoe UI Variable", "Segoe UI", sans-serif; font-size: 16px; margin-left: 12px; margin-top: 8px;')
        left_layout.addWidget(controls_title)

        controls_group = QFrame()
        controls_group.setObjectName("MainControlsFrame")
        controls_group.setStyleSheet("QFrame#MainControlsFrame { border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; background-color: rgba(255, 255, 255, 0.02); }")
        controls_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        controls_layout = QGridLayout(controls_group)
        controls_layout.setSpacing(15)
        controls_layout.setColumnStretch(2, 1) # Make slider column stretch
        controls_layout.setAlignment(Qt.AlignTop)
        controls_layout.setRowStretch(7, 1) # Add an empty stretching row at the bottom so contents stay at the top
        
        plus_icon_path  = os.path.join(os.path.dirname(__file__), 'assets', 'plus.svg').replace('\\', '/')
        minus_icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'minus.svg').replace('\\', '/')
        icon_css = 'QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); }'
        
        # Row 0: Brightness
        self.bright_label = QLabel('Brightness: 100%')
        self.bright_label.setFixedWidth(180)
        self.btn_bright_minus = QPushButton()
        self.btn_bright_minus.setIcon(QIcon(minus_icon_path))
        self.btn_bright_minus.setFixedSize(24, 24)
        self.btn_bright_minus.setStyleSheet(icon_css)
        self.btn_bright_minus.setCursor(Qt.PointingHandCursor)
        self.btn_bright_minus.clicked.connect(lambda: self.bright_slider.set_animated_value(max(0, self.bright_slider.value() - 5)))
        self.bright_slider = AnimatedSlider(Qt.Horizontal)
        self.bright_slider.setRange(0, 100)
        self.bright_slider.setValue(100)
        self.bright_slider.setTickPosition(QSlider.TicksBelow)
        self.bright_slider.setTickInterval(10)
        self.bright_slider.valueChanged.connect(self.on_bright_changed)
        self.btn_bright_plus = QPushButton()
        self.btn_bright_plus.setIcon(QIcon(plus_icon_path))
        self.btn_bright_plus.setFixedSize(24, 24)
        self.btn_bright_plus.setStyleSheet(icon_css)
        self.btn_bright_plus.setCursor(Qt.PointingHandCursor)
        self.btn_bright_plus.clicked.connect(lambda: self.bright_slider.set_animated_value(min(100, self.bright_slider.value() + 5)))
        controls_layout.addWidget(self.bright_label, 0, 0)
        controls_layout.addWidget(self.btn_bright_minus, 0, 1)
        controls_layout.addWidget(self.bright_slider, 0, 2)
        controls_layout.addWidget(self.btn_bright_plus, 0, 3)

        self.bright_widgets = [self.bright_label, self.btn_bright_minus, self.bright_slider, self.btn_bright_plus]
        
        # Row 1: Vibrance
        self.vibrance_label = QLabel('Vibrance: 1.5x')
        self.vibrance_label.setFixedWidth(180)
        self.btn_vib_minus = QPushButton()
        self.btn_vib_minus.setIcon(QIcon(minus_icon_path))
        self.btn_vib_minus.setFixedSize(24, 24)
        self.btn_vib_minus.setStyleSheet(icon_css)
        self.btn_vib_minus.setCursor(Qt.PointingHandCursor)
        self.btn_vib_minus.clicked.connect(lambda: self.vibrance_slider.set_animated_value(max(5, self.vibrance_slider.value() - 5)))
        self.vibrance_slider = AnimatedSlider(Qt.Horizontal)
        self.vibrance_slider.setRange(5, 30) # 0.5x to 3.0x max vibrance
        self.vibrance_slider.setValue(15) 
        self.vibrance_slider.setTickPosition(QSlider.TicksBelow)
        self.vibrance_slider.setTickInterval(5)
        self.vibrance_slider.valueChanged.connect(self.on_vibrance_changed)
        self.btn_vib_plus = QPushButton()
        self.btn_vib_plus.setIcon(QIcon(plus_icon_path))
        self.btn_vib_plus.setFixedSize(24, 24)
        self.btn_vib_plus.setStyleSheet(icon_css)
        self.btn_vib_plus.setCursor(Qt.PointingHandCursor)
        self.btn_vib_plus.clicked.connect(lambda: self.vibrance_slider.set_animated_value(min(30, self.vibrance_slider.value() + 5)))
        controls_layout.addWidget(self.vibrance_label, 1, 0)
        controls_layout.addWidget(self.btn_vib_minus, 1, 1)
        controls_layout.addWidget(self.vibrance_slider, 1, 2)
        controls_layout.addWidget(self.btn_vib_plus, 1, 3)
        
        self.vibrance_widgets = [self.vibrance_label, self.btn_vib_minus, self.vibrance_slider, self.btn_vib_plus]
        for w in self.vibrance_widgets:
            w.hide()

        # Pomodoro Timer UI
        self.pomo_widget = QWidget()
        pomo_layout = QVBoxLayout(self.pomo_widget)
        pomo_layout.setContentsMargins(10, 5, 10, 5)
        
        time_layout = QHBoxLayout()
        spin_style = """
            QSpinBox {
                background-color: #1A1A1E;
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 5px;
                font-size: 16px;
                font-weight: bold;
                min-width: 60px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                width: 0px;
            }
        """
        
        from PySide6.QtWidgets import QSpinBox
        self.pomo_hours = QSpinBox()
        self.pomo_hours.setRange(0, 99)
        self.pomo_hours.setSuffix("h")
        self.pomo_hours.setStyleSheet(spin_style)
        
        self.pomo_minutes = QSpinBox()
        self.pomo_minutes.setRange(0, 59)
        self.pomo_minutes.setSuffix("m")
        self.pomo_minutes.setStyleSheet(spin_style)
        
        self.pomo_seconds = QSpinBox()
        self.pomo_seconds.setRange(0, 59)
        self.pomo_seconds.setSuffix("s")
        self.pomo_seconds.setStyleSheet(spin_style)
        
        time_layout.addWidget(self.pomo_hours)
        time_layout.addWidget(self.pomo_minutes)
        time_layout.addWidget(self.pomo_seconds)
        pomo_layout.addLayout(time_layout)
        
        btn_pomo_layout = QHBoxLayout()
        self.btn_pomo_start = GlowButton("Start Focus")
        self.btn_pomo_start.setCursor(Qt.PointingHandCursor)
        self.btn_pomo_start.setStyleSheet("""
            QPushButton {
                background-color: #00E5FF;
                color: black;
                font-weight: bold;
            }
            QPushButton:disabled {
                background-color: #2A2A2E;
                color: #555555;
            }
        """)
        self.btn_pomo_start.clicked.connect(self.start_pomodoro)
        
        self.btn_pomo_stop = QPushButton("Stop")
        self.btn_pomo_stop.setCursor(Qt.PointingHandCursor)
        self.btn_pomo_stop.setEnabled(False)
        self.btn_pomo_stop.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 85, 85, 0.1);
                color: #FF5555;
                border: 1px solid rgba(255, 85, 85, 0.3);
            }
            QPushButton:hover {
                background-color: rgba(255, 85, 85, 0.2);
            }
            QPushButton:disabled {
                background-color: #2A2A2E;
                color: #555555;
                border: 1px solid transparent;
            }
        """)
        self.btn_pomo_stop.clicked.connect(self.stop_pomodoro)
        
        btn_pomo_layout.addWidget(self.btn_pomo_start)
        btn_pomo_layout.addWidget(self.btn_pomo_stop)
        pomo_layout.addLayout(btn_pomo_layout)
        
        self.pomo_widget.hide()
        controls_layout.addWidget(self.pomo_widget, 2, 0, 1, 4)

        # Row 3: Speed
        self.speed_label = QLabel('Animation Speed: 20%')
        self.speed_label.setFixedWidth(180)
        self.btn_speed_minus = QPushButton()
        self.btn_speed_minus.setIcon(QIcon(minus_icon_path))
        self.btn_speed_minus.setFixedSize(24, 24)
        self.btn_speed_minus.setStyleSheet(icon_css)
        self.btn_speed_minus.setCursor(Qt.PointingHandCursor)
        self.btn_speed_minus.clicked.connect(lambda: self.speed_slider.set_animated_value(max(1, self.speed_slider.value() - 5)))
        self.speed_slider = AnimatedSlider(Qt.Horizontal)
        self.speed_slider.setRange(1, 100)
        self.speed_slider.setValue(20)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setTickInterval(10)
        self.speed_slider.valueChanged.connect(self.on_speed_changed)
        self.btn_speed_plus = QPushButton()
        self.btn_speed_plus.setIcon(QIcon(plus_icon_path))
        self.btn_speed_plus.setFixedSize(24, 24)
        self.btn_speed_plus.setStyleSheet(icon_css)
        self.btn_speed_plus.setCursor(Qt.PointingHandCursor)
        self.btn_speed_plus.clicked.connect(lambda: self.speed_slider.set_animated_value(min(100, self.speed_slider.value() + 5)))
        controls_layout.addWidget(self.speed_label, 3, 0)
        controls_layout.addWidget(self.btn_speed_minus, 3, 1)
        controls_layout.addWidget(self.speed_slider, 3, 2)
        controls_layout.addWidget(self.btn_speed_plus, 3, 3)
        
        self.speed_widgets = [self.speed_label, self.btn_speed_minus, self.speed_slider, self.btn_speed_plus]

        # Row 4: Storm Intensity (Lightning)
        self.storm_label = QLabel('Storm Intensity: 50%')
        self.storm_label.setFixedWidth(180)
        self.btn_storm_minus = QPushButton()
        self.btn_storm_minus.setIcon(QIcon(minus_icon_path))
        self.btn_storm_minus.setFixedSize(24, 24)
        self.btn_storm_minus.setStyleSheet(icon_css)
        self.btn_storm_minus.setCursor(Qt.PointingHandCursor)
        self.btn_storm_minus.clicked.connect(lambda: self.storm_slider.set_animated_value(max(1, self.storm_slider.value() - 5)))
        self.storm_slider = AnimatedSlider(Qt.Horizontal)
        self.storm_slider.setRange(1, 100)
        self.storm_slider.setValue(50)
        self.storm_slider.setTickPosition(QSlider.TicksBelow)
        self.storm_slider.setTickInterval(5)
        self.storm_slider.valueChanged.connect(self.on_storm_changed)
        self.btn_storm_plus = QPushButton()
        self.btn_storm_plus.setIcon(QIcon(plus_icon_path))
        self.btn_storm_plus.setFixedSize(24, 24)
        self.btn_storm_plus.setStyleSheet(icon_css)
        self.btn_storm_plus.setCursor(Qt.PointingHandCursor)
        self.btn_storm_plus.clicked.connect(lambda: self.storm_slider.set_animated_value(min(100, self.storm_slider.value() + 5)))
        controls_layout.addWidget(self.storm_label, 4, 0)
        controls_layout.addWidget(self.btn_storm_minus, 4, 1)
        controls_layout.addWidget(self.storm_slider, 4, 2)
        controls_layout.addWidget(self.btn_storm_plus, 4, 3)

        self.storm_widgets = [self.storm_label, self.btn_storm_minus, self.storm_slider, self.btn_storm_plus]
        for w in self.storm_widgets:
            w.hide()
        
        # Random mode removed — related controls were deleted
        
        self.ambient_fps_layout = QHBoxLayout()
        self.ambient_fps_label = QLabel('Ambient FPS: 30')
        self.ambient_fps_label.setFixedWidth(180)
        self.btn_ambient_fps_minus = QPushButton()
        self.btn_ambient_fps_minus.setIcon(QIcon(minus_icon_path))
        self.btn_ambient_fps_minus.setFixedSize(24, 24)
        self.btn_ambient_fps_minus.setStyleSheet(icon_css)
        self.btn_ambient_fps_minus.setCursor(Qt.PointingHandCursor)
        self.btn_ambient_fps_minus.clicked.connect(lambda: self.ambient_fps_slider.set_animated_value(max(5, self.ambient_fps_slider.value() - 5)))
        self.ambient_fps_slider = AnimatedSlider(Qt.Horizontal)
        self.ambient_fps_slider.setRange(5, 60)
        self.ambient_fps_slider.setValue(30)
        self.ambient_fps_slider.setTickPosition(QSlider.TicksBelow)
        self.ambient_fps_slider.setTickInterval(5)
        self.ambient_fps_slider.valueChanged.connect(self.on_ambient_fps_changed)
        self.btn_ambient_fps_plus = QPushButton()
        self.btn_ambient_fps_plus.setIcon(QIcon(plus_icon_path))
        self.btn_ambient_fps_plus.setFixedSize(24, 24)
        self.btn_ambient_fps_plus.setStyleSheet(icon_css)
        self.btn_ambient_fps_plus.setCursor(Qt.PointingHandCursor)
        self.btn_ambient_fps_plus.clicked.connect(lambda: self.ambient_fps_slider.set_animated_value(min(60, self.ambient_fps_slider.value() + 5)))
        controls_layout.addWidget(self.ambient_fps_label, 5, 0)
        controls_layout.addWidget(self.btn_ambient_fps_minus, 5, 1)
        controls_layout.addWidget(self.ambient_fps_slider, 5, 2)
        controls_layout.addWidget(self.btn_ambient_fps_plus, 5, 3)
        
        self.ambient_fps_widgets = [self.ambient_fps_label, self.btn_ambient_fps_minus, self.ambient_fps_slider, self.btn_ambient_fps_plus]
        for w in self.ambient_fps_widgets:
            w.hide()

        # Row 6: Flicker Reduction (Audio Visualizer)
        self.flicker_label = QLabel('Flicker Reduction: 0')
        self.flicker_label.setFixedWidth(180)
        self.btn_flicker_minus = QPushButton()
        self.btn_flicker_minus.setIcon(QIcon(minus_icon_path))
        self.btn_flicker_minus.setFixedSize(24, 24)
        self.btn_flicker_minus.setStyleSheet(icon_css)
        self.btn_flicker_minus.setCursor(Qt.PointingHandCursor)
        self.btn_flicker_minus.clicked.connect(lambda: self.flicker_slider.set_animated_value(max(0, self.flicker_slider.value() - 5)))
        self.flicker_slider = AnimatedSlider(Qt.Horizontal)
        self.flicker_slider.setRange(0, 50)
        self.flicker_slider.setValue(0)
        self.flicker_slider.setTickPosition(QSlider.TicksBelow)
        self.flicker_slider.setTickInterval(5)
        self.flicker_slider.valueChanged.connect(self.on_flicker_changed)
        self.btn_flicker_plus = QPushButton()
        self.btn_flicker_plus.setIcon(QIcon(plus_icon_path))
        self.btn_flicker_plus.setFixedSize(24, 24)
        self.btn_flicker_plus.setStyleSheet(icon_css)
        self.btn_flicker_plus.setCursor(Qt.PointingHandCursor)
        self.btn_flicker_plus.clicked.connect(lambda: self.flicker_slider.set_animated_value(min(50, self.flicker_slider.value() + 5)))
        controls_layout.addWidget(self.flicker_label, 6, 0)
        controls_layout.addWidget(self.btn_flicker_minus, 6, 1)
        controls_layout.addWidget(self.flicker_slider, 6, 2)
        controls_layout.addWidget(self.btn_flicker_plus, 6, 3)

        self.flicker_widgets = [self.flicker_label, self.btn_flicker_minus, self.flicker_slider, self.btn_flicker_plus]
        for w in self.flicker_widgets:
            w.hide()

        # Wave direction toggle (for hardware Wave mode)
        self.wave_dir_widget = QWidget()
        wave_dir_layout = QHBoxLayout(self.wave_dir_widget)
        wave_dir_layout.setContentsMargins(0, 0, 0, 0)
        wave_dir_layout.setSpacing(6)
        self.wave_dir_left_btn = QPushButton('Left')
        self.wave_dir_right_btn = QPushButton('Right')
        btn_style = (
            'QPushButton { padding: 6px 10px; min-width: 48px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; }'
            'QPushButton:hover { background-color: rgba(0, 229, 255, 0.1); }'
            'QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }'
        )
        for btn in (self.wave_dir_left_btn, self.wave_dir_right_btn):
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(btn_style)
        self.wave_dir_left_btn.setChecked(True)
        self.wave_dir_left_btn.clicked.connect(lambda: self.set_wave_direction('left'))
        self.wave_dir_right_btn.clicked.connect(lambda: self.set_wave_direction('right'))
        wave_dir_layout.addWidget(self.wave_dir_left_btn)
        wave_dir_layout.addWidget(self.wave_dir_right_btn)
        wave_dir_layout.addStretch()
        self.wave_dir_widget.hide()

        # Smooth Wave direction toggle (software Smooth Wave)
        self.smooth_wave_dir_widget = QWidget()
        smooth_wave_dir_layout = QHBoxLayout(self.smooth_wave_dir_widget)
        smooth_wave_dir_layout.setContentsMargins(0, 0, 0, 0)
        smooth_wave_dir_layout.setSpacing(6)
        self.smooth_wave_dir_left_btn = QPushButton('Left')
        self.smooth_wave_dir_right_btn = QPushButton('Right')
        sw_btn_style = (
            'QPushButton { padding: 6px 10px; min-width: 48px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; }'
            'QPushButton:hover { background-color: rgba(0, 229, 255, 0.1); }'
            'QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }'
        )
        for btn in (self.smooth_wave_dir_left_btn, self.smooth_wave_dir_right_btn):
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(sw_btn_style)
        self.smooth_wave_dir_left_btn.setChecked(True)
        self.smooth_wave_dir_left_btn.clicked.connect(lambda: self.set_smooth_wave_direction('left'))
        self.smooth_wave_dir_right_btn.clicked.connect(lambda: self.set_smooth_wave_direction('right'))
        smooth_wave_dir_layout.addWidget(self.smooth_wave_dir_left_btn)
        smooth_wave_dir_layout.addWidget(self.smooth_wave_dir_right_btn)
        smooth_wave_dir_layout.addStretch()
        self.smooth_wave_dir_widget.hide()

        # Scanner rainbow toggle (placed bottom-left for Scanner mode)
        self.scanner_rainbow_cb = QPushButton('Rainbow Sweep')
        self.scanner_rainbow_cb.setCheckable(True)
        self.scanner_rainbow_cb.setCursor(Qt.PointingHandCursor)
        self.scanner_rainbow_cb.setStyleSheet(
            'QPushButton { padding: 6px 12px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; font-weight: 700; }'
            'QPushButton:hover { background-color: rgba(0,229,255,0.12); }'
            'QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; }'
        )
        self.scanner_rainbow_cb.hide()

        # Fill mode toggle (bottom-right for Smooth Wave)
        self.wave_fill_cb = QPushButton('Fill Mode')
        self.wave_fill_cb.setCheckable(True)
        self.wave_fill_cb.setCursor(Qt.PointingHandCursor)
        self.wave_fill_cb.setStyleSheet(
            'QPushButton { padding: 6px 12px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; font-weight: 600; }'
            'QPushButton:hover { background-color: rgba(0,229,255,0.08); }'
            'QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }'
        )
        self.wave_fill_cb.clicked.connect(self.apply_effect)
        self.wave_fill_cb.hide()

        # Bottom controls row: wave dirs left, fill toggle right
        bottom_row = QWidget()
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)
        bottom_layout.addWidget(self.scanner_rainbow_cb)
        bottom_layout.addWidget(self.wave_dir_widget)
        bottom_layout.addWidget(self.smooth_wave_dir_widget)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.wave_fill_cb)
        controls_layout.addWidget(bottom_row, 7, 0, 1, 4)

        left_layout.addWidget(controls_group)
        
        # ─── Visualizer Color Mode Buttons (Under effects list in right panel) ─────────
        self.visualizer_color_mode_custom = True  # Track which mode is active
        self.visualizer_buttons_group = QWidget()
        visualizer_buttons_layout = QHBoxLayout(self.visualizer_buttons_group)
        visualizer_buttons_layout.setContentsMargins(0, 0, 0, 0)
        visualizer_buttons_layout.setSpacing(4)
        
        self.visualizer_custom_btn = QPushButton('Custom Colors')
        self.visualizer_custom_btn.setCheckable(True)
        self.visualizer_custom_btn.setChecked(True)
        self.visualizer_custom_btn.setCursor(Qt.PointingHandCursor)
        self.visualizer_custom_btn.setStyleSheet(
            'QPushButton { padding: 4px 8px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.12); border-radius: 4px; font-size: 11px; font-weight: 600; }'
            'QPushButton:hover { background-color: rgba(0,229,255,0.12); }'
            'QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }'
        )
        self.visualizer_custom_btn.setMinimumWidth(0)
        self.visualizer_custom_btn.setFixedHeight(30)
        self.visualizer_custom_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.visualizer_custom_btn.clicked.connect(self.switch_to_custom_colors)
        
        self.visualizer_ambient_btn = QPushButton('Ambient Colors')
        self.visualizer_ambient_btn.setCheckable(True)
        self.visualizer_ambient_btn.setCursor(Qt.PointingHandCursor)
        self.visualizer_ambient_btn.setStyleSheet(
            'QPushButton { padding: 4px 8px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.12); border-radius: 4px; font-size: 11px; font-weight: 600; }'
            'QPushButton:hover { background-color: rgba(0,229,255,0.12); }'
            'QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }'
        )
        self.visualizer_ambient_btn.setMinimumWidth(0)
        self.visualizer_ambient_btn.setFixedHeight(30)
        self.visualizer_ambient_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.visualizer_ambient_btn.clicked.connect(self.switch_to_ambient_colors)
        
        visualizer_buttons_layout.addWidget(self.visualizer_custom_btn, 1)
        visualizer_buttons_layout.addWidget(self.visualizer_ambient_btn, 1)
        
        # Hide buttons by default (only show in Live Audio Visualizer mode)
        self.visualizer_buttons_group.hide()
        
        self.colors_group = QGroupBox('Zone Colors')
        self.colors_group.setStyleSheet('QGroupBox { color: #00E5FF; font-size: 16px; font-weight: bold; }')
        colors_layout = QGridLayout(self.colors_group)
        colors_layout.setSpacing(10)
        
        self.zone_colors = [[255, 252, 247], [255, 252, 247], [255, 252, 247], [255, 252, 247]]
        self.color_buttons = []
        for i in range(4):
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(100, 40)
            self.update_button_color(btn, self.zone_colors[i])
            btn.clicked.connect(lambda checked, idx=i: self.pick_color(idx))
            self.color_buttons.append(btn)
            colors_layout.addWidget(btn, 0, i)
        self.global_color = [255, 252, 247]
        self.global_color_btn = QPushButton()
        self.global_color_btn.setCursor(Qt.PointingHandCursor)
        self.global_color_btn.setFixedHeight(25)
        self.update_button_color(self.global_color_btn, self.global_color)
        self.global_color_btn.clicked.connect(self.pick_global_color)
        colors_layout.addWidget(self.global_color_btn, 1, 0, 1, 4)
        
        # ─── Ambient Controls Widget for Visualizer ───────────────────────────────────
        self.visualizer_ambient_controls = QWidget()
        ambient_controls_layout = QVBoxLayout(self.visualizer_ambient_controls)
        ambient_controls_layout.setContentsMargins(0, 0, 0, 0)
        ambient_controls_layout.setSpacing(10)
        
        # Vibrance control for visualizer ambient mode
        vibrance_row = QHBoxLayout()
        vibrance_row.setSpacing(5)
        visualizer_vib_label = QLabel('Vibrance:')
        visualizer_vib_label.setFixedWidth(80)
        visualizer_vib_slider = AnimatedSlider(Qt.Horizontal)
        visualizer_vib_slider.setRange(5, 30)
        visualizer_vib_slider.setValue(self.vibrance_slider.value())
        visualizer_vib_slider.setTickPosition(QSlider.TicksBelow)
        visualizer_vib_slider.setTickInterval(5)
        visualizer_vib_slider.valueChanged.connect(lambda val: self.vibrance_slider.setValue(val))
        self.vibrance_slider.valueChanged.connect(lambda val: visualizer_vib_slider.setValue(val))
        vibrance_row.addWidget(visualizer_vib_label)
        vibrance_row.addWidget(visualizer_vib_slider)
        ambient_controls_layout.addLayout(vibrance_row)
        
        # FPS control for visualizer ambient mode
        fps_row = QHBoxLayout()
        fps_row.setSpacing(5)
        visualizer_fps_label = QLabel('FPS:')
        visualizer_fps_label.setFixedWidth(80)
        visualizer_fps_slider = AnimatedSlider(Qt.Horizontal)
        visualizer_fps_slider.setRange(1, 60)
        visualizer_fps_slider.setValue(self.ambient_fps_slider.value())
        visualizer_fps_slider.setTickPosition(QSlider.TicksBelow)
        visualizer_fps_slider.setTickInterval(10)
        visualizer_fps_slider.valueChanged.connect(lambda val: self.ambient_fps_slider.setValue(val))
        self.ambient_fps_slider.valueChanged.connect(lambda val: visualizer_fps_slider.setValue(val))
        fps_row.addWidget(visualizer_fps_label)
        fps_row.addWidget(visualizer_fps_slider)
        ambient_controls_layout.addLayout(fps_row)

        # Keep ambient controls inside the Zone Colors container so this view
        # replaces the color pickers in-place.
        colors_layout.addWidget(self.visualizer_ambient_controls, 0, 0, 2, 4)
        
        # Hide ambient controls by default
        self.visualizer_ambient_controls.hide()
        
        left_layout.addWidget(self.colors_group)
        self.SOFTWARE_MODES = ['Smooth Wave', 'Lightning', 'Party', 'Realistic Fire', 'Scanner (Cylon)', 'Aurora Borealis', 'Meteor Shower', 'Ambient Screen Color', 'Battery Visualizer', 'Mouse-Reactive Aura', 'Pomodoro Timer', 'Live Audio Visualizer']
        self.HARDWARE_MODES = ['Off', 'Static', 'Breath', 'Smooth', 'Wave']
        self.default_control_settings = {
            'brightness': 100,
            'speed': 20,
            'storm_intensity': 50,
            'vibrance': 15,
            'ambient_fps': 30,
            'flicker': 0,
        }
        self.mode_settings = {m: dict(self.default_control_settings) for m in (self.HARDWARE_MODES + self.SOFTWARE_MODES)}
        self.wave_direction = 'left'
        self.smooth_wave_direction = 'left'
        self.mode_list = QListWidget()
        self.mode_list.addItems(self.HARDWARE_MODES + self.SOFTWARE_MODES)
        self.mode_list.setCurrentRow(0)
        self.mode_list.currentTextChanged.connect(self.on_mode_changed)
        right_layout.addWidget(self.mode_list)
        # Live Audio mode uses a compact effects list so the visualizer color
        # mode buttons can sit directly below by shrinking only the needed amount.
        self.mode_list_default_min_height = self.mode_list.minimumHeight()
        self.mode_list_default_max_height = self.mode_list.maximumHeight()
        self.is_live_audio_menu_compact = False
        self.visualizer_buttons_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        right_layout.addWidget(self.visualizer_buttons_group)
        
        self.presets = {}
        preset_group = QGroupBox('Custom Presets')
        preset_layout = QHBoxLayout(preset_group)
        preset_layout.setSpacing(10)
        self.preset_combo = QComboBox()
        self.preset_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_combo.setStyleSheet('\n            QComboBox { background-color: #1A1A1E; color: white; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 6px; }\n            QComboBox::drop-down { border: none; }\n        ')
        self.preset_combo.activated.connect(self.apply_preset_from_ui)
        self.btn_save_preset = QPushButton()
        self.btn_save_preset.setIcon(QIcon(plus_icon_path))
        self.btn_save_preset.setFixedSize(30, 30)
        self.btn_save_preset.setCursor(Qt.PointingHandCursor)
        self.btn_save_preset.setStyleSheet('QPushButton { background-color: rgba(255, 255, 255, 0.05); border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); } QPushButton:hover { background-color: rgba(0, 229, 255, 0.2); border: 1px solid #00E5FF; }')
        self.btn_save_preset.clicked.connect(self.save_new_preset)
        self.btn_delete_preset = QPushButton()
        self.btn_delete_preset.setIcon(QIcon(minus_icon_path))
        self.btn_delete_preset.setFixedSize(30, 30)
        self.btn_delete_preset.setCursor(Qt.PointingHandCursor)
        self.btn_delete_preset.setStyleSheet('QPushButton { background-color: rgba(255, 255, 255, 0.05); border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); } QPushButton:hover { background-color: rgba(255, 85, 85, 0.2); border: 1px solid #FF5555; }')
        self.btn_delete_preset.clicked.connect(self.delete_preset)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addWidget(self.btn_save_preset)
        preset_layout.addWidget(self.btn_delete_preset)
        right_layout.addWidget(preset_group)
        self.kb = None
        self.visualizer_process = None
        self.custom_timer = QTimer(self)
        self.custom_timer.timeout.connect(self.update_custom_effects)
        self.timer_interval_active_ms = 33
        self.timer_interval_idle_ms = 90
        self.current_timer_base_ms = self.timer_interval_active_ms
        self.is_window_active = True
        self.custom_colors = [0] * 12
        self.transition_ticks = 0
        self.last_activity = time.monotonic()
        self.sct = None
        self.preview_window = None
        self.pomo_running = False
        self.pomo_total_seconds = 0
        self.pomo_remaining_seconds = 0
        self.pomo_is_finished = False
        self.pomo_last_tick = 0
        self.pomo_flash_on = False
        try:
            self.kb = L5PKeyboard()
        except ValueError as e:
            print(f'Error initializing keyboard: {e}')
        self.force_quit = False
        self.load_settings()
        self.apply_effect()

        self.update_available.connect(self.prompt_update)
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def check_for_updates(self):
        url = "https://api.github.com/repos/AFcoder10/4-Zone-Keyboard-RGB-Toolkit/releases/latest"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get("tag_name", "")
                if latest_version and latest_version != CURRENT_VERSION:
                    exe_url = ""
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith(".exe"):
                            exe_url = asset.get("browser_download_url")
                            break
                    if exe_url:
                        self.update_available.emit(latest_version, exe_url, data.get("body", "Bug fixes and improvements."))
        except Exception as e:
            print("Update check failed:", e)

    def prompt_update(self, latest_version, exe_url, release_notes):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Update Available: {latest_version}")
        dialog.setFixedSize(980, 500)
        
        layout = QVBoxLayout(dialog)
        
        lbl = QLabel(f"A new version of 4 Zone RGB Toolkit ({latest_version}) is available!\n\nRelease Notes:")
        lbl.setStyleSheet("font-weight: bold; font-size: 18px; color: #E2E2E2;")
        layout.addWidget(lbl)
        
        browser = QTextBrowser()
        browser.setMarkdown(release_notes)
        browser.setStyleSheet("background-color: #1E1E1E; color: #E2E2E2; border: 1px solid #333; padding: 15px; font-size: 16px; line-height: 1.5;")
        layout.addWidget(browser)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_remind = QPushButton("Remind Me Later")
        btn_remind.setCursor(Qt.PointingHandCursor)
        btn_remind.setStyleSheet("padding: 8px 15px; background: #333333; color: white; border-radius: 4px;")
        btn_remind.clicked.connect(dialog.reject)
        
        btn_install = QPushButton("Install Now")
        btn_install.setCursor(Qt.PointingHandCursor)
        btn_install.setStyleSheet("padding: 8px 15px; background: #00E5FF; color: black; font-weight: bold; border-radius: 4px;")
        btn_install.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(btn_remind)
        btn_layout.addWidget(btn_install)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.Accepted:
            self.perform_update_download(exe_url, latest_version)

    def perform_update_download(self, url, version):
        self.progress_dlg = QProgressDialog("Downloading update...", "Cancel", 0, 100, self)
        self.progress_dlg.setWindowTitle("Update")
        self.progress_dlg.setWindowModality(Qt.WindowModal)
        self.progress_dlg.setAutoClose(True)
        self.progress_dlg.show()
        
        self.downloader = UpdateDownloader(url)
        self.downloader.progress.connect(self.progress_dlg.setValue)
        self.downloader.finished.connect(self.apply_update_and_restart)
        self.downloader.error.connect(lambda e: QMessageBox.critical(self, "Update Failed", f"Failed to download update:\n{e}"))
        self.downloader.start()

    def apply_update_and_restart(self, downloaded_exe):
        if hasattr(self, 'progress_dlg'):
            self.progress_dlg.close()
            
        current_exe = self.original_exe_path or (sys.executable if getattr(sys, 'frozen', False) else __file__)
        if not getattr(sys, 'frozen', False):
             QMessageBox.information(self, "Update Downloaded", f"Update downloaded to {downloaded_exe}. Since you are running from source, you must manually replace your files.")
             return

        restart_exe = self.original_exe_path or current_exe
        ps_path = os.path.join(tempfile.gettempdir(), "updater.ps1")
        pid = os.getpid()
        ppid = os.getppid() # Get parent PID (the PyInstaller bootstrapper)

        with open(ps_path, "w") as f:
            f.write(f'$pid = {pid}\n')
            f.write(f'$ppid = {ppid}\n')
            f.write('$src  = "' + _ps_escape(downloaded_exe) + '"\n')
            f.write('$dest = "' + _ps_escape(current_exe) + '"\n')
            f.write('$restart = "' + _ps_escape(restart_exe) + '"\n')
            f.write('\n# Wait for both processes to terminate to avoid DLL lock errors\n')
            f.write('try { Wait-Process -Id $pid -Timeout 30 -ErrorAction SilentlyContinue } catch {}\n')
            f.write('try { Wait-Process -Id $ppid -Timeout 30 -ErrorAction SilentlyContinue } catch {}\n')
            f.write('Start-Sleep -Seconds 2\n')
            f.write('\n# Perform the update\n')
            f.write('Copy-Item -Path $src -Destination $dest -Force -ErrorAction SilentlyContinue\n')
            f.write('\n# Cleanup and restart\n')
            f.write('Remove-Item -Path $src -Force -ErrorAction SilentlyContinue\n')
            f.write('\n# Clear PyInstaller environment variables so the new process extracts cleanly\n')
            f.write('Remove-Item env:_MEIPASS2 -ErrorAction SilentlyContinue\n')
            f.write('Remove-Item env:_MEIPASS -ErrorAction SilentlyContinue\n')
            f.write('Get-ChildItem env: | Where-Object {$_.Name -like "_PYI_*"} | ForEach-Object { Remove-Item "env:$($_.Name)" -ErrorAction SilentlyContinue }\n')
            f.write('$env:PYINSTALLER_RESET_ENVIRONMENT = "1"\n')
            f.write('if (Test-Path $restart) { Start-Process -FilePath $restart } elseif (Test-Path $dest) { Start-Process -FilePath $dest }\n')
            f.write('Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue\n')

        updater_env = sanitized_child_env(os.environ, include_pythonpath=False)
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-ExecutionPolicy", "Bypass", "-File", ps_path],
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=updater_env
        )
        self.force_quit = True
        QApplication.quit()

    def toggle_preview(self):
        if self.preview_window is None or not self.preview_window.isVisible():
            self.preview_window = KeyboardPreviewWindow(self)
            self.preview_window.show()
        else:
            self.preview_window.close()
            self.preview_window = None

    def clear_update_cache(self):
        tmp = tempfile.gettempdir()
        deleted = 0
        patterns = ["4_Zone_Rgb_Toolkit_Updated.exe", "updater.ps1", "updater.bat"]
        for name in patterns:
            path = os.path.join(tmp, name)
            if os.path.exists(path):
                try:
                    os.remove(path)
                    deleted += 1
                except Exception:
                    pass
        if deleted > 0:
            QMessageBox.information(self, "Update Cache Cleared", f"Removed {deleted} leftover update file(s) from your Temp folder.")
        else:
            QMessageBox.information(self, "Update Cache", "No leftover update files found. Nothing to clear!")

    def load_settings(self):
        settings = QSettings('4ZoneRgbToolkit', 'Preferences')
        self.minimize_to_tray_cb.blockSignals(True)
        self.launch_on_start_cb.blockSignals(True)
        try:
            self.startup_preset_combo.blockSignals(True)
        except:
            pass
        min_val = settings.value('minimize_to_tray', False)
        min_to_tray = str(min_val).lower() == 'true' if isinstance(min_val, str) else bool(min_val)
        self.minimize_to_tray_cb.setChecked(min_to_tray)
        launch_val = settings.value('launch_on_start', False)
        launch_start = str(launch_val).lower() == 'true' if isinstance(launch_val, str) else bool(launch_val)
        self.launch_on_start_cb.setChecked(launch_start)
        presets_json = settings.value('saved_presets', '{}')
        if isinstance(presets_json, str) and presets_json:
                try:
                    self.presets = json.loads(presets_json)
                except Exception:
                    self.presets = {}
        self.update_preset_combos()
        startup_p = settings.value('startup_preset', 'None (Use Last State)')
        if startup_p in self.presets or startup_p == 'None (Use Last State)':
            self.startup_preset_combo.setCurrentText(startup_p)
        hide_warn_val = settings.value('hide_hardware_warning', False)
        hide_warn = str(hide_warn_val).lower() == 'true' if isinstance(hide_warn_val, str) else bool(hide_warn_val)
        if hide_warn:
            self.disclaimer_widget.hide()
            self.dnd_checkbox.setChecked(True)
        else:
            self.disclaimer_widget.show()
        try:
            self.startup_preset_combo.blockSignals(False)
        except:
            pass
        self.minimize_to_tray_cb.blockSignals(False)
        self.launch_on_start_cb.blockSignals(False)
        if startup_p in self.presets:
            self.apply_preset_logic(startup_p)
    def save_settings(self, *args):
        settings = QSettings('4ZoneRgbToolkit', 'Preferences')
        settings.setValue('minimize_to_tray', self.minimize_to_tray_cb.isChecked())
        settings.setValue('startup_preset', self.startup_preset_combo.currentText())
        settings.setValue('saved_presets', json.dumps(self.presets))
        launch_start = self.launch_on_start_cb.isChecked()
        settings.setValue('launch_on_start', launch_start)
        self.manage_startup_registry(launch_start)
    def save_dnd_preference(self, checked):
        settings = QSettings('4ZoneRgbToolkit', 'Preferences')
        settings.setValue('hide_hardware_warning', checked)
    def close_disclaimer(self):
        self.disclaimer_widget.hide()
    def clear_cache(self):
        reply = QMessageBox.warning(self, 'Clear Cache & Reset', 'WARNING: This will permanently delete all your saved presets, startup configurations, and reset the application to factory defaults.\n\nAre you absolutely sure you want to proceed?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            settings = QSettings('4ZoneRgbToolkit', 'Preferences')
            settings.clear()
            self.manage_startup_registry(False)
            self.minimize_to_tray_cb.blockSignals(True)
            self.launch_on_start_cb.blockSignals(True)
            self.startup_preset_combo.blockSignals(True)
            self.minimize_to_tray_cb.setChecked(False)
            self.launch_on_start_cb.setChecked(False)
            self.presets = {}
            self.mode_settings = {m: dict(self.default_control_settings) for m in (self.HARDWARE_MODES + self.SOFTWARE_MODES)}
            self.wave_direction = 'left'
            self.smooth_wave_direction = 'left'
            self.update_preset_combos()
            self.minimize_to_tray_cb.blockSignals(False)
            self.launch_on_start_cb.blockSignals(False)
            self.startup_preset_combo.blockSignals(False)
            self.bright_slider.setValue(100)
            self.vibrance_slider.setValue(15)
            self.speed_slider.setValue(20)
            self.storm_slider.setValue(50)
            self.mode_list.setCurrentRow(0)
            items = self.mode_list.findItems('Static', Qt.MatchExactly)
            if items:
                self.mode_list.setCurrentItem(items[0])
            self.on_mode_changed('Static')
            QMessageBox.information(self, 'Cache Cleared', 'The application cache has been successfully reset to default settings.')
            self.toggle_settings()
    def show_logs(self):
        try:
            if not hasattr(self, 'logs_dialog') or self.logs_dialog is None:
                self.logs_dialog = LogsDialog(self)
            self.logs_dialog.show()
            self.logs_dialog.raise_()
        except Exception:
            pass
    def apply_preset_from_ui(self, index):
        preset_name = self.preset_combo.itemText(index)
        self.apply_preset_logic(preset_name)
    def apply_preset_logic(self, preset_name):
        if preset_name not in self.presets:
            return
        else:
            p = self.presets[preset_name]
            self.mode_list.blockSignals(True)
            self.bright_slider.blockSignals(True)
            self.speed_slider.blockSignals(True)
            preset_mode = p.get('mode', 'Static')
            if preset_mode in ('Wave (Left)', 'Wave (Right)'):
                self.wave_direction = 'left' if 'Left' in preset_mode else 'right'
                preset_mode = 'Wave'
            if preset_mode in ('Smooth Wave (Left)', 'Smooth Wave (Right)'):
                self.smooth_wave_direction = 'left' if 'Left' in preset_mode else 'right'
                preset_mode = 'Smooth Wave'
            items = self.mode_list.findItems(preset_mode, Qt.MatchExactly)
            if items:
                self.mode_list.setCurrentItem(items[0])
            self.bright_slider.setValue(p.get('brightness', 100))
            self.vibrance_slider.setValue(p.get('vibrance', 15))
            self.speed_slider.setValue(p.get('speed', 20))
            self.storm_slider.setValue(p.get('storm_intensity', self.default_control_settings['storm_intensity']))
            self.ambient_fps_slider.setValue(p.get('ambient_fps', self.default_control_settings['ambient_fps']))
            self.flicker_slider.setValue(p.get('flicker', self.default_control_settings['flicker']))
            self.zone_colors = p.get('colors', [[255, 0, 0]] * 4)
            for i in range(4):
                self.update_button_color(self.color_buttons[i], self.zone_colors[i])
            if 'global_color' in p:
                self.global_color = p['global_color']
                self.update_button_color(self.global_color_btn, self.global_color)
            if 'scanner_rainbow' in p:
                self.scanner_rainbow_cb.setChecked(p['scanner_rainbow'])
            if 'wave_dir' in p:
                self.set_wave_direction(p['wave_dir'])
            else:
                if p.get('mode') in ('Wave (Left)', 'Wave (Right)'):
                    self.set_wave_direction('left' if 'Left' in p.get('mode') else 'right')
            if 'smooth_wave_dir' in p:
                self.set_smooth_wave_direction(p['smooth_wave_dir'])
            else:
                if p.get('mode') in ('Smooth Wave (Left)', 'Smooth Wave (Right)'):
                    self.set_smooth_wave_direction('left' if 'Left' in p.get('mode') else 'right')
            mode_key = preset_mode
            self.mode_settings.setdefault(mode_key, dict(self.default_control_settings))
            self.mode_settings[mode_key].update({
                'brightness': self.bright_slider.value(),
                'vibrance': self.vibrance_slider.value(),
                'speed': self.speed_slider.value(),
                'storm_intensity': self.storm_slider.value(),
                'ambient_fps': self.ambient_fps_slider.value(),
                'flicker': self.flicker_slider.value(),
            })
            self.mode_list.blockSignals(False)
            self.bright_slider.blockSignals(False)
            self.speed_slider.blockSignals(False)
            self.on_mode_changed(preset_mode)
    def save_new_preset(self):
        name, ok = QInputDialog.getText(self, 'Save Preset', 'Enter a name for this preset:')
        if ok and name.strip():
                name = name.strip()
                current_mode = self.mode_list.currentItem().text() if self.mode_list.currentItem() else 'Static'
                self.presets[name] = {
                    'mode': current_mode,
                    'brightness': self.bright_slider.value(),
                    'vibrance': self.vibrance_slider.value(),
                    'speed': self.speed_slider.value(),
                    'storm_intensity': self.storm_slider.value(),
                    'ambient_fps': self.ambient_fps_slider.value(),
                    'flicker': self.flicker_slider.value(),
                    'colors': list(self.zone_colors),
                    'global_color': list(self.global_color),
                    'scanner_rainbow': self.scanner_rainbow_cb.isChecked(),
                    'wave_dir': self.wave_direction,
                    'smooth_wave_dir': self.smooth_wave_direction
                }
                self.update_preset_combos()
                self.save_settings()
                self.preset_combo.setCurrentText(name)
    def delete_preset(self):
        name = self.preset_combo.currentText()
        if not name:
            return
        else:
            reply = QMessageBox.question(self, 'Delete Preset', f'Are you sure you want to delete the preset \'{name}\'?', QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                if name in self.presets:
                    del self.presets[name]
                self.update_preset_combos()
                self.save_settings()
    def update_preset_combos(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(self.presets.keys())
        self.preset_combo.blockSignals(False)
        curr_startup = self.startup_preset_combo.currentText()
        self.startup_preset_combo.blockSignals(True)
        self.startup_preset_combo.clear()
        self.startup_preset_combo.addItem('None (Use Last State)')
        self.startup_preset_combo.addItems(self.presets.keys())
        if curr_startup in self.presets or curr_startup == 'None (Use Last State)':
            self.startup_preset_combo.setCurrentText(curr_startup)
        self.startup_preset_combo.blockSignals(False)
    def manage_startup_registry(self, enabled):
        key_path = 'Software\\Microsoft\\Windows\\CurrentVersion\\Run'
        key_name = '4ZoneRgbToolkit'
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enabled:
                if getattr(sys, 'frozen', False):
                    exe_path = sys.executable
                    target = f'\"{exe_path}\" --hidden'
                else:
                    pythonw_path = sys.executable.replace('python.exe', 'pythonw.exe')
                    if not os.path.exists(pythonw_path):
                        pythonw_path = sys.executable
                    script_path = os.path.abspath(__file__)
                    target = f'\"{pythonw_path}\" \"{script_path}\" --hidden'
                winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, target)
            else:
                try:
                    winreg.DeleteValue(key, key_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f'Failed to modify startup registry: {e}')

    def load_mode_controls(self, mode_name):
        settings = self.mode_settings.get(mode_name, dict(self.default_control_settings))
        self.mode_settings.setdefault(mode_name, dict(settings))
        slider_map = [
            (self.bright_slider, 'brightness'),
            (self.vibrance_slider, 'vibrance'),
            (self.speed_slider, 'speed'),
            (self.storm_slider, 'storm_intensity'),
            (self.ambient_fps_slider, 'ambient_fps'),
            (self.flicker_slider, 'flicker'),
        ]
        for slider, key in slider_map:
            if slider is None:
                continue
            slider.blockSignals(True)
            slider.setValue(settings.get(key, self.default_control_settings.get(key, slider.value())))
            slider.blockSignals(False)

    def update_mode_setting(self, key, value):
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else None
        if not mode_name:
            return
        if mode_name not in self.mode_settings:
            self.mode_settings[mode_name] = dict(self.default_control_settings)
        self.mode_settings[mode_name][key] = value

    def set_wave_direction(self, direction):
        self.wave_direction = direction
        self.wave_dir_left_btn.setChecked(direction == 'left')
        self.wave_dir_right_btn.setChecked(direction == 'right')
        if self.mode_list.currentItem() and self.mode_list.currentItem().text() == 'Wave':
            self.apply_effect()

    def set_smooth_wave_direction(self, direction):
        self.smooth_wave_direction = direction
        self.smooth_wave_dir_left_btn.setChecked(direction == 'left')
        self.smooth_wave_dir_right_btn.setChecked(direction == 'right')
        if self.mode_list.currentItem() and self.mode_list.currentItem().text() == 'Smooth Wave':
            self.apply_effect()
    def update_button_color(self, btn, rgb):
        # ***<module>.RGBControllerApp.update_button_color: Failure: Compilation Error
        r, g, b = rgb
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        text_color = 'black' if luminance > 0.5 else 'white'
        btn.setStyleSheet(f'''\n            QPushButton {{\n                background-color: rgb({int(r)}, {int(g)}, {int(b)});\n                color: {text_color};\n                border: 2px solid rgba(255, 255, 255, 0.2);\n                border-radius: 6px;\n                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;\n                font-weight: 600;\n            }}\n            QPushButton:hover {{\n                border: 2px solid #FFFFFF;\n                background-color: rgb({min(255, int(r * 1.1))}, {min(255, int(g * 1.1))}, {min(255, int(b * 1.1))});\n            }}\n        ''')
    def pick_color(self, zone_idx):
        r, g, b = self.zone_colors[zone_idx]
        current_color = QColor(r, g, b)
        color = QColorDialog.getColor(current_color, self, f'Select Color for Zone {zone_idx + 1}')
        if color.isValid():
            self.zone_colors[zone_idx] = [color.red(), color.green(), color.blue()]
            # Sync manual pick to custom_colors for smooth transition
            self.custom_colors[zone_idx * 3] = color.red()
            self.custom_colors[zone_idx * 3 + 1] = color.green()
            self.custom_colors[zone_idx * 3 + 2] = color.blue()
            self.update_button_color(self.color_buttons[zone_idx], self.zone_colors[zone_idx])
            self.apply_effect()
    def pick_global_color(self):
        r, g, b = self.global_color
        current_color = QColor(r, g, b)
        color = QColorDialog.getColor(current_color, self, 'Select Master Keyboard Color')
        if color.isValid():
            r, g, b = (color.red(), color.green(), color.blue())
            self.global_color = [r, g, b]
            self.update_button_color(self.global_color_btn, self.global_color)
            for i in range(4):
                self.zone_colors[i] = [r, g, b]
                # Sync manual pick to custom_colors for smooth transition
                self.custom_colors[i * 3] = r
                self.custom_colors[i * 3 + 1] = g
                self.custom_colors[i * 3 + 2] = b
                self.update_button_color(self.color_buttons[i], [r, g, b])
            self.apply_effect()
    
    def switch_to_custom_colors(self):
        """Switch to custom zone colors mode in Live Audio Visualizer"""
        self.visualizer_color_mode_custom = True
        self.visualizer_custom_btn.setChecked(True)
        self.visualizer_ambient_btn.setChecked(False)
        # Show zone colors, hide ambient controls
        for btn in self.color_buttons:
            btn.show()
        self.global_color_btn.show()
        self.visualizer_ambient_controls.hide()
    
    def switch_to_ambient_colors(self):
        """Switch to ambient screen color mode in Live Audio Visualizer"""
        self.visualizer_color_mode_custom = False
        self.visualizer_custom_btn.setChecked(False)
        self.visualizer_ambient_btn.setChecked(True)
        # Hide zone colors, show ambient controls
        for btn in self.color_buttons:
            btn.hide()
        self.global_color_btn.hide()
        self.visualizer_ambient_controls.show()

    def set_live_audio_menu_compact(self, compact: bool):
        """Shorten effects list just enough to fit visualizer mode buttons below it."""
        if compact:
            if self.is_live_audio_menu_compact:
                return
            full_height = self.mode_list.height()
            if full_height <= 1:
                row_h = self.mode_list.sizeHintForRow(0)
                if row_h <= 0:
                    row_h = 34
                # Estimate visible list height if layout hasn't settled yet.
                full_height = min(480, row_h * self.mode_list.count() + 2 * self.mode_list.frameWidth() + 8)

            buttons_h = self.visualizer_buttons_group.sizeHint().height()
            compact_height = max(140, full_height - buttons_h - self.effects_panel_spacing)
            self.mode_list.setMinimumHeight(compact_height)
            self.mode_list.setMaximumHeight(compact_height)
            self.is_live_audio_menu_compact = True
            return

        if not self.is_live_audio_menu_compact:
            return
        self.mode_list.setMinimumHeight(self.mode_list_default_min_height)
        self.mode_list.setMaximumHeight(self.mode_list_default_max_height)
        self.is_live_audio_menu_compact = False
    
    def minimize_app(self):
        if self.minimize_to_tray_cb.isChecked():
            self.hide()
        else:
            self.showMinimized()
    def restore_app(self):
        self.show()
        self.activateWindow()

    def focusInEvent(self, event):
        self.is_window_active = True
        self.update_timer_interval()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.is_window_active = False
        self.update_timer_interval()
        super().focusOutEvent(event)

    def reset_mode_state(self):
        self.lightning_strikes = []
        self.next_lightning_time = 0.0
        self.party_state = None
        for attr in ['meteor_last_tick', 'meteor_pos', 'meteor_dir', 'fire_state', 'scanner_pos', 'scanner_dir']:
            if hasattr(self, attr):
                delattr(self, attr)
    def tray_quit(self):
        self.force_quit = True
        try:
            if self.kb:
                self.kb.set_effect('static')
                self.kb.set_solid_color(0, 0, 0)
        except Exception as e:
            pass
        self.stop_visualizer()
        QApplication.instance().quit()
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_app()
    def switch_view_animated(self, index):
        if self.stack.currentIndex() == index:
            return
        
        self.stack.setCurrentIndex(index)
        new_widget = self.stack.currentWidget()
        
        effect = QGraphicsOpacityEffect(new_widget)
        new_widget.setGraphicsEffect(effect)
        
        self.fade_anim = QPropertyAnimation(effect, b"opacity")
        self.fade_anim.setDuration(250)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_anim.finished.connect(lambda: new_widget.setGraphicsEffect(None))
        self.fade_anim.start()

    def toggle_settings(self):
        if self.stack.currentIndex() == 0:
            self.switch_view_animated(1)
        else:
            self.switch_view_animated(0)

    def show_help_dialog(self):
        dialog = FadeDialog(self)
        dialog.setWindowTitle("Help & Support")
        dialog.setFixedSize(380, 160)
        # Match app aesthetic
        dialog.setStyleSheet("""
            QDialog {
                background-color: #121212;
                border: 1px solid #333;
            }
            QLabel {
                color: #E2E2E2;
                font-size: 14px;
                font-family: 'Segoe UI Variable', sans-serif;
            }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        label = QLabel("Having issues? Report them on GitHub.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_issues = GlowButton("Report Issue")
        btn_issues.setCursor(Qt.PointingHandCursor)
        btn_issues.setFixedHeight(35)
        btn_issues.setStyleSheet('''
            QPushButton {
                background-color: #00E5FF;
                color: black;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #00B2CC;
            }
        ''')
        btn_issues.clicked.connect(lambda: webbrowser.open('https://github.com/AFcoder10/4-Zone-Keyboard-RGB-Toolkit/issues'))
        btn_issues.clicked.connect(dialog.accept)
        
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(35)
        btn_close.setStyleSheet('''
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #E2E2E2;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 0 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
            }
        ''')
        btn_close.clicked.connect(dialog.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_issues)
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        dialog.exec()
    def nativeEvent(self, eventType, message):
        if eventType == b'windows_generic_MSG':
            msg = MSG.from_address(message.__int__())
            if msg.message == 131 and msg.wParam:
                return (True, 0)
        return super().nativeEvent(eventType, message)
    def stop_visualizer(self):
        if self.visualizer_process:
            self.visualizer_process.terminate()
            self.visualizer_process.wait()
            self.visualizer_process = None

    def start_pomodoro(self):
        h = self.pomo_hours.value()
        m = self.pomo_minutes.value()
        s = self.pomo_seconds.value()
        total = h * 3600 + m * 60 + s
        if total <= 0:
            return
            
        self.pomo_total_seconds = total
        self.pomo_remaining_seconds = total
        self.pomo_running = True
        self.pomo_is_finished = False
        self.pomo_last_tick = time.monotonic()
        
        self.btn_pomo_start.setEnabled(False)
        self.btn_pomo_stop.setEnabled(True)
        self.pomo_hours.setEnabled(False)
        self.pomo_minutes.setEnabled(False)
        self.pomo_seconds.setEnabled(False)
        
        # Switch to fullscreen
        self.pre_pomo_window_state = self.windowState()
        self.switch_view_animated(2)
        self.title_bar.hide()
        main_cont = self.findChild(QWidget, 'MainContainer')
        if main_cont:
            main_cont.setStyleSheet("""
                #MainContainer {
                    background-color: black;
                    border: none;
                    border-radius: 0px;
                }
            """)
        self.showFullScreen()
        
        # Update label immediately
        self.pomo_fs_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def stop_pomodoro(self):
        self.pomo_running = False
        self.pomo_is_finished = False
        self.btn_pomo_start.setEnabled(True)
        self.btn_pomo_stop.setEnabled(False)
        self.pomo_hours.setEnabled(True)
        self.pomo_minutes.setEnabled(True)
        self.pomo_seconds.setEnabled(True)
        
        # Restore normal window view
        self.switch_view_animated(0) # Main view
        self.title_bar.show()
        main_cont = self.findChild(QWidget, 'MainContainer')
        if main_cont:
            main_cont.setStyleSheet("""
                #MainContainer {
                    background-color: #0E0E12;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                }
            """)
        if hasattr(self, 'pre_pomo_window_state'):
            self.setWindowState(self.pre_pomo_window_state)
        else:
            self.showNormal()
        # Reset colors when stopping? handled in loop if running=False
        
    def on_mode_changed(self, mode_name):
        if mode_name is None:
            return
        else:
            if getattr(self, 'current_mode_name', None) != mode_name:
                self.reset_mode_state()
            self.current_mode_name = mode_name
            self.load_mode_controls(mode_name)
            is_zones_enabled = mode_name in ('Static', 'Breath', 'Mouse-Reactive Aura', 'Scanner (Cylon)')
            self.colors_group.setEnabled(is_zones_enabled)
            if is_zones_enabled:
                self.colors_group.setStyleSheet('QGroupBox { color: #00E5FF; font-size: 16px; font-weight: bold; }')
            else:
                self.colors_group.setStyleSheet('QGroupBox { color: #555555; font-size: 16px; font-weight: bold; }')
            is_speed_enabled = mode_name not in ['Off', 'Static', '[Beta] CPU Temperature', 'Ambient Screen Color']
            for w in self.speed_widgets:
                w.setEnabled(is_speed_enabled)
                
            self.speed_label.setStyleSheet('color: #E2E2E2;' if is_speed_enabled else 'color: #555555;')
            
            is_bright_enabled = (mode_name not in self.SOFTWARE_MODES and mode_name != 'Off') or 'Scanner' in mode_name
            # For Live Audio Visualizer, we repurpose the brightness slider as Smoothness
            is_smooth_mode = 'Live Audio Visualizer' in mode_name
            if is_smooth_mode:
                self.bright_slider.setEnabled(True)
                self.bright_label.setText(f'Smoothness: {self.bright_slider.value()}%')
                self.bright_label.setStyleSheet('color: #E2E2E2;')
            else:
                self.bright_slider.setEnabled(is_bright_enabled)
                self.bright_label.setText(f'Brightness: {self.bright_slider.value()}%')
                self.bright_label.setStyleSheet('color: #E2E2E2;' if is_bright_enabled else 'color: #555555;')

            if 'Lightning' in mode_name:
                for w in self.storm_widgets: w.show()
                self.storm_label.setText(f'Storm Intensity: {self.storm_slider.value()}%')
            else:
                for w in self.storm_widgets: w.hide()
            
            if mode_name == 'Ambient Screen Color':
                # Show vibrance slider only in Ambient Screen Color mode
                for w in self.vibrance_widgets: w.show()
                for w in self.speed_widgets: w.hide()
                for w in self.ambient_fps_widgets: w.show()
                for w in self.flicker_widgets: w.hide()
            elif 'Live Audio Visualizer' in mode_name:
                # In Live Audio Visualizer mode, hide vibrance (brightness boost) UI
                for w in self.vibrance_widgets: w.hide()
                self.speed_label.setText(f'Visualizer Sensitivity: {self.speed_slider.value()}%')
                self.speed_label.setStyleSheet('color: #E2E2E2;')
                # Make sure the speed control is visible and interactive (it may have been hidden
                # by Ambient mode). Also hide ambient-only controls.
                for w in self.speed_widgets: 
                    w.show()
                    w.setEnabled(True)
                for w in self.ambient_fps_widgets: w.hide()
                for w in self.flicker_widgets: w.show()
                # (random mode removed)
                # Enable zone color pickers so user can choose their static colors
                self.colors_group.setEnabled(True)
                self.colors_group.setStyleSheet('QGroupBox { color: #00E5FF; font-size: 16px; font-weight: bold; }')
                
                # ─── Show visualizer color mode buttons ─────────────────────────
                self.visualizer_buttons_group.show()
                self.set_live_audio_menu_compact(True)
                # Reset to custom colors mode by default
                self.switch_to_custom_colors()
            else:
                # Hide vibrance for all other modes
                for w in self.vibrance_widgets: w.hide()
                for w in self.speed_widgets: w.show()
                for w in self.ambient_fps_widgets: w.hide()
                for w in self.flicker_widgets: w.hide()
                
                # ─── Hide visualizer color mode buttons when leaving Live Audio ───
                self.visualizer_buttons_group.hide()
                self.set_live_audio_menu_compact(False)
                # Show zone colors and hide ambient controls when leaving visualizer
                for btn in self.color_buttons:
                    btn.show()
                self.global_color_btn.show()
                self.visualizer_ambient_controls.hide()

            if mode_name == 'Pomodoro Timer':
                # Hide all standard controls to isolate timer
                for w in self.speed_widgets: w.hide()
                for w in self.bright_widgets: w.hide()
                self.pomo_widget.show()
                # Disable zone color pickers during timer? 
                # (Plan implies manual colors aren't used for progress calculation)
            else:
                for w in self.bright_widgets: w.show()
                self.pomo_widget.hide()
                if mode_name != 'Ambient Screen Color':
                    for w in self.speed_widgets: w.show()
            
            if mode_name == 'Wave':
                self.wave_dir_widget.show()
                self.set_wave_direction(self.wave_direction)
            else:
                self.wave_dir_widget.hide()

            if mode_name == 'Smooth Wave':
                self.smooth_wave_dir_widget.show()
                self.set_smooth_wave_direction(self.smooth_wave_direction)
            else:
                self.smooth_wave_dir_widget.hide()

            if 'Lightning' in mode_name:
                self.speed_label.setText(f'Lightning Frequency: {self.speed_slider.value()}%')
            elif 'Party' in mode_name:
                self.speed_label.setText(f'Party Tempo: {self.speed_slider.value()}%')
            elif 'Live Audio Visualizer' in mode_name:
                self.speed_label.setText(f'Visualizer Sensitivity: {self.speed_slider.value()}%')
            elif 'Realistic Fire' in mode_name:
                self.speed_label.setText(f'Fire Flicker Speed: {self.speed_slider.value()}%')
            elif 'Scanner (Cylon)' in mode_name:
                self.speed_label.setText(f'Scanner Sweep Speed: {self.speed_slider.value()}%')
            else:
                self.speed_label.setText(f'Animation Speed: {self.speed_slider.value()}%')
            
            if 'Smooth Wave' in mode_name:
                self.wave_fill_cb.show()
            else:
                self.wave_fill_cb.hide()
                
            if 'Scanner (Cylon)' in mode_name:
                self.scanner_rainbow_cb.show()
            else:
                self.scanner_rainbow_cb.hide()
                
            self.transition_ticks = 15
            self.apply_effect()
    def closeEvent(self, event):
        if self.minimize_to_tray_cb.isChecked() and (not self.force_quit):
            event.ignore()
            self.hide()
            return
        else:
            self.stop_visualizer()
            self.custom_timer.stop()
            if self.sct:
                self.sct.close()
            try:
                if self.kb:
                    self.kb.set_effect('static')
                    self.kb.set_solid_color(0, 0, 0)
            except Exception as e:
                print(f'Failed to turn off keyboard LEDs: {e}')
            if hasattr(self, 'tray_icon'):
                self.tray_icon.hide()
            super().closeEvent(event)
    def on_bright_changed(self, value):
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else ''
        if 'Live Audio Visualizer' in mode_name:
            self.bright_label.setText(f'Smoothness: {value}%')
            # Restart visualizer with new smoothness value
            self.apply_effect()
        else:
            self.bright_label.setText(f'Brightness: {value}%')
            self.apply_effect()
        self.update_mode_setting('brightness', value)
    def on_speed_changed(self, value):
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else ''
        if 'Lightning' in mode_name:
            self.speed_label.setText(f'Lightning Frequency: {value}%')
        elif 'Party' in mode_name:
            self.speed_label.setText(f'Party Tempo: {value}%')
        elif 'Starry Night' in mode_name:
            self.speed_label.setText(f'Twinkle Speed: {value}%')
        elif 'Live Audio Visualizer' in mode_name:
            self.speed_label.setText(f'Visualizer Sensitivity: {value}%')
        elif 'Realistic Fire' in mode_name:
            self.speed_label.setText(f'Fire Flicker Speed: {value}%')
        elif 'Scanner (Cylon)' in mode_name:
            self.speed_label.setText(f'Scanner Sweep Speed: {value}%')
        elif 'Aurora Borealis' in mode_name:
            self.speed_label.setText(f'Aurora Shift Speed: {value}%')
        elif 'Meteor Shower' in mode_name:
            self.speed_label.setText(f'Meteor Speed: {value}%')
        else:
            self.speed_label.setText(f'Animation Speed: {value}%')
        self.apply_effect()
        self.update_mode_setting('speed', value)

    def on_storm_changed(self, value):
        self.storm_label.setText(f'Storm Intensity: {value}%')
        self.apply_effect()
        self.update_mode_setting('storm_intensity', value)
    # Random mode removed; handler deleted
    def on_vibrance_changed(self, value):
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else ''
        if 'Live Audio Visualizer' in mode_name:
            self.vibrance_label.setText(f'Brightness Boost: {value}%')
            self.apply_effect()  # restart with new brightness boost
        else:
            self.vibrance_label.setText(f'Vibrance: {value/10.0}x')
            # Does not need immediate effect replay - calculates frame by frame
        self.update_mode_setting('vibrance', value)

    def on_ambient_fps_changed(self, value):
        self.ambient_fps_label.setText(f'Ambient FPS: {value}')
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else ''
        if 'Ambient Screen Color' in mode_name:
            # Update timer to reflect the exact new target framerate
            self.current_timer_base_ms = self.compute_base_timer_interval(mode_name)
            self.update_timer_interval()
        self.update_mode_setting('ambient_fps', value)
            
    def on_flicker_changed(self, value):
        self.flicker_label.setText(f'Flicker Reduction: {value}')
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else ''
        if 'Live Audio Visualizer' in mode_name:
            self.apply_effect()
        self.update_mode_setting('flicker', value)
    def stop_visualizer(self):
        if hasattr(self, 'visualizer_process') and self.visualizer_process:
            try:
                import subprocess
                # Forcefully kill the process tree (/T) to ensure the actual Python child
                # spawned by the PyInstaller wrapper is terminated, preventing background leakage.
                subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.visualizer_process.pid)], 
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
                self.visualizer_process.wait(timeout=1.0)
            except Exception as e:
                pass
            finally:
                self.visualizer_process = None

    def apply_effect(self):
        # Stop the custom timer before applying a new effect
        self.custom_timer.stop()
        if not self.mode_list.currentItem():
            return
        else:
            mode_name = self.mode_list.currentItem().text()
            if self.sct:
                self.sct.close()
                self.sct = None
            if 'Live Audio Visualizer' not in mode_name:
                self.stop_visualizer()
            if self.kb is None and 'Live Audio Visualizer' not in mode_name:
                    try:
                        self.kb = L5PKeyboard()
                    except ValueError:
                        return None
            if 'Live Audio Visualizer' in mode_name:
                self.stop_visualizer()
                print('Launching visualizer...')
                if self.kb:
                    self.kb.close()
                    self.kb = None

                env = sanitized_child_env(
                    os.environ,
                    include_pythonpath=(not getattr(sys, 'frozen', False))
                )
                sensitivity_val  = str(self.speed_slider.value())
                smoothness_val   = str(self.bright_slider.value())
                flicker_val      = str(self.flicker_slider.value())
                # Ambient mode flag and settings
                ambient_mode_val = '1' if not self.visualizer_color_mode_custom else '0'
                vibrance_val     = str(self.vibrance_slider.value())
                fps_val          = str(self.ambient_fps_slider.value())
                
                # Pass zone colors as individual R G B args for all 4 zones
                color_args = []
                for c in self.zone_colors:
                    color_args.extend([str(c[0]), str(c[1]), str(c[2])])

                # When running from a bundled EXE (PyInstaller), there is no separate
                # audio_visualizer.py file on disk. Use a special flag to tell the
                # frozen executable to run the visualizer code path instead of
                # attempting to execute a script file.
                if getattr(sys, 'frozen', False):
                    cmd = [sys.executable, '--run-visualizer', sensitivity_val, smoothness_val, flicker_val] + color_args + [ambient_mode_val, vibrance_val, fps_val]
                else:
                    script_cmd = os.path.join(os.path.dirname(__file__), 'audio_visualizer.py')
                    cmd = [sys.executable, script_cmd, sensitivity_val, smoothness_val, flicker_val] + color_args + [ambient_mode_val, vibrance_val, fps_val]

                import threading
                flags = 0
                if sys.platform == "win32":
                    flags = subprocess.CREATE_NO_WINDOW
                
                self.visualizer_process = subprocess.Popen(
                    cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                    text=True, creationflags=flags, bufsize=1
                )
                
                def read_proc(proc):
                    for line in iter(proc.stdout.readline, ''):
                        if line:
                            # Use sys.stdout.write instead of print to avoid recursion or extra newlines
                            sys.stdout.write(line)
                            sys.stdout.flush()
                
                threading.Thread(target=read_proc, args=(self.visualizer_process,), daemon=True).start()
                return
            else:
                if mode_name in self.SOFTWARE_MODES:
                    if self.kb:
                        self.kb.set_effect('static')
                        self.kb.set_brightness(2)
                    if 'Ambient Screen Color' in mode_name and HAS_MSS:
                        self.sct = mss.mss()
                    base_interval = self.compute_base_timer_interval(mode_name)
                    self.current_timer_base_ms = base_interval
                    self.custom_timer.start(self.get_effective_timer_interval())
                    return
                else:
                    if mode_name == 'Off':
                        if self.kb:
                            self.kb.set_effect('static')
                            self.kb.set_solid_color(0, 0, 0)
                        return
                    effect = 'static'
                    wave_dir = self.wave_direction
                    if 'Breath' in mode_name:
                        effect = 'breath'
                    else:
                        if 'Smooth' in mode_name:
                            effect = 'smooth'
                        else:
                            if 'Wave' in mode_name:
                                effect = 'wave'
                    if self.kb:
                        self.kb.set_effect(effect)
                        hw_bright = 1 if self.bright_slider.value() <= 50 else 2
                        hw_speed = max(1, min(4, math.ceil(self.speed_slider.value() / 25.0)))
                        self.kb.set_brightness(hw_bright)
                        self.kb.set_speed(hw_speed)
                        if effect == 'wave':
                            self.kb.wave_direction = wave_dir
                        flat_colors = []
                        b_mult = self.bright_slider.value() / 100.0
                        for c in self.zone_colors:
                            flat_colors.extend([int(c[0] * b_mult), int(c[1] * b_mult), int(c[2] * b_mult)])
                        self.kb.set_colors(flat_colors)
    def compute_base_timer_interval(self, mode_name):
        if 'Ambient Screen Color' in mode_name:
            fps = max(1, self.ambient_fps_slider.value())
            return max(5, 1000 // fps)
        return self.timer_interval_active_ms

    def get_effective_timer_interval(self, base=None):
        base_interval = base if base is not None else (self.current_timer_base_ms or self.timer_interval_active_ms)
        if self.is_window_active:
            return int(base_interval)
        return int(max(base_interval * 2.5, base_interval + 50, self.timer_interval_idle_ms))

    def update_timer_interval(self):
        if self.custom_timer.isActive():
            self.custom_timer.setInterval(self.get_effective_timer_interval())

    def get_cpu_temp(self):
        temp = 40.0
        if not HAS_WMI:
            return temp
        try:
            temp_info = wmi_obj.MSAcpi_ThermalZoneTemperature()[0]
            return temp_info.CurrentTemperature / 10.0 - 273.15
        except Exception:
            try:
                c = wmi.WMI()
                tz = c.Win32_PerfFormattedData_Counters_ThermalZoneInformation()[0]
                t = float(tz.Temperature) - 273.15
                if t == 27.85 or t == 27.8:
                    return 'REQUIRES_ADMIN'
                return t
            except Exception:
                pass
        return temp
    def update_custom_effects(self):
        # ***<module>.RGBControllerApp.update_custom_effects: Failure: Compilation Error
        if not self.kb:
            return
        else:
            if not self.mode_list.currentItem():
                return
            else:
                mode_name = self.mode_list.currentItem().text()
                # (random mode removed) — continue with normal effect updates
                
                speed_mult = self.speed_slider.value() / 50.0
                t = time.monotonic()
                target_colors = list(self.custom_colors)
                smooth_amount = 0.5
                try:
                    if 'Smooth Wave' in mode_name:
                        smooth_amount = 0.1
                        t *= speed_mult
                        dir_mult = (-0.15) if self.smooth_wave_direction == 'left' else 0.15
                        if self.wave_fill_cb.isChecked():
                            total_cycles = int(t)
                            phase = t % 1.0
                            hue_prev = total_cycles * 0.1 % 1.0
                            hue_next = (total_cycles + 1) * 0.1 % 1.0
                            r_prev, g_prev, b_prev = colorsys.hsv_to_rgb(hue_prev, 1.0, 1.0)
                            r_next, g_next, b_next = colorsys.hsv_to_rgb(hue_next, 1.0, 1.0)
                            for i in range(4):
                                zone_pos = i * 0.25 if self.smooth_wave_direction == 'left' else (3 - i) * 0.25
                                margin = 0.2
                                diff = phase - zone_pos
                                if diff >= margin:
                                    R, G, B = (r_next, g_next, b_next)
                                else:
                                    if diff <= 0:
                                        R, G, B = (r_prev, g_prev, b_prev)
                                    else:
                                        blend = diff / margin
                                        R = r_prev * (1 - blend) + r_next * blend
                                        G = g_prev * (1 - blend) + g_next * blend
                                        B = b_prev * (1 - blend) + b_next * blend
                                target_colors[i * 3] = R * 255
                                target_colors[i * 3 + 1] = G * 255
                                target_colors[i * 3 + 2] = B * 255
                        else:
                            for i in range(4):
                                hue = (t + i * dir_mult) % 1.0
                                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                                target_colors[i * 3] = r * 255
                                target_colors[i * 3 + 1] = g * 255
                                target_colors[i * 3 + 2] = b * 255
                    else:
                        if 'Lightning' in mode_name:
                            if not hasattr(self, 'lightning_strikes'):
                                self.lightning_strikes = []
                            if not hasattr(self, 'next_lightning_time'):
                                self.next_lightning_time = 0.0

                            speed_factor = max(0.2, self.speed_slider.value() / 100.0)
                            storm_factor = max(0.05, self.storm_slider.value() / 100.0) if hasattr(self, 'storm_slider') else 0.5

                            storm_wave = 0.35 + 0.15 * math.sin(t * 0.6)
                            base_r = 4 + int(6 * storm_wave)
                            base_g = 9 + int(14 * storm_wave)
                            base_b = 24 + int(32 * storm_wave)
                            for i in range(4):
                                target_colors[i * 3] = base_r
                                target_colors[i * 3 + 1] = base_g
                                target_colors[i * 3 + 2] = base_b

                            if t >= self.next_lightning_time:
                                spawn_chance = (0.35 + 0.55 * speed_factor) * (0.5 + 1.5 * storm_factor)
                                spawn_chance = min(0.98, spawn_chance)
                                if random.random() < spawn_chance:
                                    primary_zone = random.randrange(4)

                                    strike_type = 'small'
                                    r = random.random()
                                    if r > 0.85:
                                        strike_type = 'huge'
                                    elif r > 0.45:
                                        strike_type = 'medium'

                                    if strike_type == 'small':
                                        branch_count = random.choice([1, 1, 2])
                                        pre_ticks = random.randint(1, 2)
                                        flash_ticks = random.randint(1, 2)
                                        flicker_ticks = random.randint(1, 3)
                                        after_ticks = random.randint(4, 10)
                                        bleed_mult = 0.14
                                        colors = {
                                            'main': [235, 245, 255],
                                            'pre': [80, 130, 200],
                                            'after': [45, 130, 245]
                                        }
                                    elif strike_type == 'medium':
                                        branch_count = random.choice([1, 2, 2, 3])
                                        pre_ticks = random.randint(2, 3)
                                        flash_ticks = random.randint(2, 4)
                                        flicker_ticks = random.randint(3, 6)
                                        after_ticks = random.randint(8, 18)
                                        bleed_mult = 0.2
                                        colors = {
                                            'main': [255, 255, 255],
                                            'pre': [95, 150, 215],
                                            'after': [55, 150, 255]
                                        }
                                    else:
                                        branch_count = random.choice([2, 3, 3, 4])
                                        pre_ticks = random.randint(3, 5)
                                        flash_ticks = random.randint(3, 8)
                                        flicker_ticks = random.randint(6, 14)
                                        after_ticks = random.randint(15, 40)
                                        linger_boost = 1.0 + 1.8 * storm_factor
                                        flash_ticks = max(1, int(round(flash_ticks * linger_boost)))
                                        flicker_ticks = max(1, int(round(flicker_ticks * linger_boost)))
                                        after_ticks = max(1, int(round(after_ticks * linger_boost)))
                                        if random.random() < (0.35 + 0.45 * storm_factor):
                                            flash_ticks += random.randint(8, 50)
                                            flicker_ticks += random.randint(10, 60)
                                            after_ticks += random.randint(10, 50)
                                        bleed_mult = 0.28
                                        colors = {
                                            'main': [255, 255, 255],
                                            'pre': [110, 175, 235],
                                            'after': [70, 165, 255]
                                        }

                                    zones = {primary_zone}
                                    while len(zones) < branch_count:
                                        zones.add((primary_zone + random.choice([-1, 1, 2, -2])) % 4)

                                    strike = {
                                        'zones': list(zones),
                                        'type': strike_type,
                                        'stage': 'pre',
                                        'ticks_left': pre_ticks,
                                        'flash_ticks': flash_ticks,
                                        'flicker_ticks': flicker_ticks,
                                        'after_ticks': after_ticks,
                                        'after_total': None,
                                        'main_color': colors['main'],
                                        'pre_color': colors['pre'],
                                        'after_color': colors['after'],
                                        'bleed': bleed_mult
                                    }
                                    strike['after_total'] = strike['after_ticks']
                                    self.lightning_strikes.append(strike)

                                    base_gap = max(0.35, (2.1 - 1.5 * speed_factor) * (1.2 - 0.7 * storm_factor))
                                    self.next_lightning_time = t + random.uniform(base_gap * 0.6, base_gap * 1.3)

                            smooth_amount = 0.9
                            active_strikes = []

                            for strike in self.lightning_strikes:
                                # Staged strike: pre-flash -> flash -> flicker -> blue afterglow
                                stage = strike['stage']
                                color = strike['pre_color']
                                intensity = 0.3

                                if stage == 'pre':
                                    intensity = 0.35 + random.random() * 0.25
                                    strike['ticks_left'] -= 1
                                    if strike['ticks_left'] <= 0:
                                        strike['stage'] = 'flash'
                                        strike['ticks_left'] = strike['flash_ticks']
                                elif stage == 'flash':
                                    color = strike['main_color']
                                    intensity = 1.0
                                    strike['ticks_left'] -= 1
                                    if strike['ticks_left'] <= 0:
                                        strike['stage'] = 'flicker'
                                        strike['ticks_left'] = strike['flicker_ticks']
                                elif stage == 'flicker':
                                    color = [200, 220, 255]
                                    intensity = random.uniform(0.55, 1.0)
                                    strike['ticks_left'] -= 1
                                    if strike['ticks_left'] <= 0:
                                        strike['stage'] = 'after'
                                        strike['ticks_left'] = strike['after_ticks']
                                else:
                                    color = strike['after_color']
                                    decay = strike['ticks_left'] / float(strike['after_total'])
                                    intensity = 0.25 + 0.5 * decay
                                    strike['ticks_left'] -= 1

                                if stage in ('flash', 'flicker'):
                                    stage_smooth = 0.05 if strike['type'] != 'huge' else 0.03
                                else:
                                    stage_smooth = 0.35 if strike['type'] != 'huge' else 0.3
                                smooth_amount = min(smooth_amount, stage_smooth)

                                for z in strike['zones']:
                                    idx = z * 3
                                    target_colors[idx] = max(target_colors[idx], color[0] * intensity)
                                    target_colors[idx + 1] = max(target_colors[idx + 1], color[1] * intensity)
                                    target_colors[idx + 2] = max(target_colors[idx + 2], color[2] * intensity)

                                if stage in ('flash', 'flicker'):
                                    bleed = strike['bleed'] if stage == 'flash' else strike['bleed'] * 0.55
                                    for i in range(4):
                                        idx = i * 3
                                        target_colors[idx] = max(target_colors[idx], 160 * bleed)
                                        target_colors[idx + 1] = max(target_colors[idx + 1], 190 * bleed)
                                        target_colors[idx + 2] = max(target_colors[idx + 2], 255 * bleed)

                                if strike['ticks_left'] > 0:
                                    active_strikes.append(strike)

                            self.lightning_strikes = active_strikes
                        else:
                            if 'Party' in mode_name:
                                speed_factor = max(0.2, self.speed_slider.value() / 100.0)
                                bpm = 90 + 120 * speed_factor  # 90–210 BPM mapped to speed
                                beat_len = 60.0 / bpm
                                smooth_amount = 0.12

                                if not hasattr(self, 'party_state') or not self.party_state:
                                    self.party_state = {
                                        'last_t': t,
                                        'acc': 0.0,
                                        'palette': [255, 0, 0] * 4,
                                        'strobe': 0,
                                        'zone_pops': [1.0] * 4
                                    }

                                # Time bookkeeping
                                dt = max(0.0, t - self.party_state['last_t'])
                                self.party_state['last_t'] = t
                                self.party_state['acc'] += dt

                                # Spawn a new beat palette when we cross the beat boundary
                                while self.party_state['acc'] >= beat_len:
                                    self.party_state['acc'] -= beat_len
                                    base_hue = random.random()
                                    spread = 0.12 + 0.25 * random.random()
                                    palette = []
                                    for i in range(4):
                                        hue = (base_hue + spread * i + random.uniform(-0.05, 0.05)) % 1.0
                                        sat = 0.8 + 0.2 * random.random()
                                        val = 0.9 + 0.1 * random.random()
                                        r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
                                        palette.extend([r * 255, g * 255, b * 255])
                                    self.party_state['palette'] = palette

                                    # Chance to trigger a short strobe burst on beat
                                    if random.random() < 0.18 * speed_factor:
                                        self.party_state['strobe'] = random.randint(1, 3)

                                # Pulse brightness within the beat (saw wave for pump feel)
                                beat_phase = self.party_state['acc'] / max(beat_len, 1e-6)
                                pulse = 0.55 + 0.45 * (1.0 - abs(beat_phase * 2 - 1))

                                # Strobe override when active
                                if self.party_state['strobe'] > 0:
                                    smooth_amount = 0.04
                                    pulse = 1.0
                                    self.party_state['strobe'] -= 1

                                # Apply palette with pulse and per-zone confetti pops that decay
                                if 'zone_pops' not in self.party_state:
                                    self.party_state['zone_pops'] = [1.0] * 4
                                zone_pops = self.party_state['zone_pops']
                                decay = 0.82 + 0.12 * speed_factor
                                max_pop = 1.32

                                for i in range(4):
                                    base_r = self.party_state['palette'][i * 3]
                                    base_g = self.party_state['palette'][i * 3 + 1]
                                    base_b = self.party_state['palette'][i * 3 + 2]

                                    # Decay any prior pop
                                    zone_pops[i] = 1.0 + (zone_pops[i] - 1.0) * decay

                                    if random.random() < 0.06 * speed_factor:
                                        zone_pops[i] = max(zone_pops[i], 1.18 + 0.18 * random.random())
                                        smooth_amount = min(smooth_amount, 0.08)

                                    pop = min(zone_pops[i], max_pop)

                                    target_colors[i * 3] = min(255, base_r * pulse * pop)
                                    target_colors[i * 3 + 1] = min(255, base_g * pulse * pop)
                                    target_colors[i * 3 + 2] = min(255, base_b * pulse * pop)

                                self.party_state['zone_pops'] = zone_pops
                            elif 'Realistic Fire' in mode_name:
                                # Fire flickers intensely and independently per zone
                                smooth_amount = max(0.01, 0.25 - (self.speed_slider.value() / 100.0) * 0.2)
                                
                                if not hasattr(self, 'fire_state'):
                                    self.fire_state = [random.random() for _ in range(4)]
                                
                                for i in range(4):
                                    # Simulate fire flickering with random jitter (wider swings)
                                    jitter = (random.random() - 0.5) * 0.9 * speed_mult
                                    self.fire_state[i] = max(0.1, min(1.0, self.fire_state[i] + jitter))
                                    
                                    intensity = self.fire_state[i]
                                    
                                    if random.random() < 0.12 * speed_mult:
                                        # Frequent, powerful bright pops (embers)
                                        intensity = min(1.0, intensity + 0.6)
                                        self.fire_state[i] = intensity
                                        
                                    # Deep Red/Orange Fire: Maximize R, sharply limit G (to keep orange sparse), near zero B
                                    r = 255 * min(1.0, intensity * 2.0)  # Pushed harder for saturated red
                                    g = 60 * intensity * (0.3 + 0.6 * random.random()) # Halved G to suppress bright yellow/orange
                                    b = 5 * intensity * random.random() # Almost completely kill B
                                    
                                    target_colors[i * 3] = r
                                    target_colors[i * 3 + 1] = g
                                    target_colors[i * 3 + 2] = b
                            elif 'Scanner (Cylon)' in mode_name:
                                # Speed slider controls sweep speed
                                smooth_amount = 0.85 - (self.speed_slider.value() / 100.0) * 0.4
                                
                                if not hasattr(self, 'scanner_pos'):
                                    self.scanner_pos = 0.0
                                    self.scanner_dir = 1.0 # 1 for right, -1 for left
                                    
                                # Move scanner position
                                sweep_speed = 0.05 + (self.speed_slider.value() / 100.0) * 0.15
                                self.scanner_pos += self.scanner_dir * sweep_speed
                                
                                # Bounce logic considering there are 4 zones (index 0 to 3)
                                if self.scanner_pos > 3.0:
                                    self.scanner_pos = 3.0
                                    self.scanner_dir = -1.0
                                elif self.scanner_pos < 0.0:
                                    self.scanner_pos = 0.0
                                    self.scanner_dir = 1.0
                                    
                                for i in range(4):
                                    # Calculate distance from current scanner position
                                    dist = abs(self.scanner_pos - i)
                                    
                                    # Gaussian falloff for the trail
                                    intensity = max(0.0, 1.0 - dist * 0.8)
                                    
                                    # Apply brightness slider
                                    brightness_factor = self.bright_slider.value() / 100.0
                                    intensity *= brightness_factor
                                    
                                    if self.scanner_rainbow_cb.isChecked():
                                        # Use a sweeping rainbow hue independent of scanner position
                                        hue = (t * 0.5) % 1.0
                                        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                                        target_colors[i * 3] = r * 255 * intensity
                                        target_colors[i * 3 + 1] = g * 255 * intensity
                                        target_colors[i * 3 + 2] = b * 255 * intensity
                                    else:
                                        target_colors[i * 3] = self.zone_colors[i][0] * intensity
                                        target_colors[i * 3 + 1] = self.zone_colors[i][1] * intensity
                                        target_colors[i * 3 + 2] = self.zone_colors[i][2] * intensity
                            elif 'Aurora Borealis' in mode_name:
                                smooth_amount = 0.05
                                brightness = self.bright_slider.value() / 100.0
                                speed = (self.speed_slider.value() / 100.0) * 0.5 + 0.1
                                
                                # Aurora colors: Deep Purples, Teals, and Greens
                                aurora_hues = [0.45, 0.55, 0.70, 0.85] # Green to Purple
                                
                                for i in range(4):
                                    # Slowly shifting sine wave across time and space
                                    wave = math.sin(t * speed + (i * 1.5)) * 0.5 + 0.5
                                    # Slowly shifting hue index
                                    hue_idx = (t * speed * 0.3 + (i * 0.2)) % len(aurora_hues)
                                    h1 = aurora_hues[int(hue_idx)]
                                    h2 = aurora_hues[(int(hue_idx) + 1) % len(aurora_hues)]
                                    blend = hue_idx - int(hue_idx)
                                    
                                    # Interpolate hue
                                    final_hue = h1 * (1 - blend) + h2 * blend
                                    r, g, b = colorsys.hsv_to_rgb(final_hue, 1.0, wave * brightness)
                                    
                                    target_colors[i * 3] = int(r * 255)
                                    target_colors[i * 3 + 1] = int(g * 255)
                                    target_colors[i * 3 + 2] = int(b * 255)
                            elif 'Meteor Shower' in mode_name:
                                smooth_amount = 0.8 # Very fast transition
                                brightness = self.bright_slider.value() / 100.0
                                
                                if not hasattr(self, 'meteor_last_tick'):
                                    self.meteor_last_tick = time.monotonic()
                                    self.meteor_pos = -1.0
                                    self.meteor_dir = 1.0
                                
                                # Meteor moves fast, with long periods of darkness
                                # Speed determines how often a meteor strikes
                                strike_freq = (self.speed_slider.value() / 100.0) * 2.0 + 0.5
                                
                                now = time.monotonic()
                                dt = now - self.meteor_last_tick
                                self.meteor_last_tick = now
                                
                                # Meteor movement
                                if self.meteor_pos < -2.0 or self.meteor_pos > 5.0:
                                    # Random chance to spawn a meteor if one isn't active
                                    if random.random() < strike_freq * dt:
                                        self.meteor_dir = random.choice([-1.0, 1.0])
                                        self.meteor_pos = -1.0 if self.meteor_dir == 1.0 else 4.0
                                else:
                                    # Move active meteor very fast
                                    meteor_speed = 15.0 # Units per second
                                    self.meteor_pos += self.meteor_dir * meteor_speed * dt
                                
                                for i in range(4):
                                    # Calculate distance to meteor head
                                    dist = self.meteor_dir * (self.meteor_pos - i)
                                    
                                    # Default to off
                                    r, g, b = 0, 0, 0
                                    
                                    # Only light up if meteor has passed this zone (forming a tail behind it)
                                    if dist > 0 and dist < 3.0: 
                                        # Sharp falloff for the tail
                                        intensity = max(0.0, 1.0 - (dist / 2.0)**2)
                                        # Tail transitions from Yellow -> Orange -> Deep Red based on distance
                                        if dist < 1.0:
                                            # Yellowish-Orange
                                            r, g, b = 255, int(200 * (1.0 - dist * 0.5)), 0
                                        else:
                                            # Orange to Red fading out
                                            r, g, b = 255, int(100 * max(0.0, 1.0 - (dist-1.0)/2.0)), 0
                                            
                                        # Apply tail fade intensity
                                        r, g, b = r * intensity, g * intensity, b * intensity
                                        
                                    elif dist > -0.5 and dist <= 0:
                                        # The glowing head leading the meteor (Bright White/Cyan core)
                                        r, g, b = 255, 255, 200
                                    
                                    target_colors[i * 3] = int(r * brightness)
                                    target_colors[i * 3 + 1] = int(g * brightness)
                                    target_colors[i * 3 + 2] = int(b * brightness)
                            else:
                                if 'Battery Visualizer' in mode_name:
                                    smooth_amount = 0.5
                                    if HAS_PSUTIL:
                                        battery = psutil.sensors_battery()
                                        if battery:
                                            percent = battery.percent
                                            charging = battery.power_plugged
                                            
                                            # Determine the base color and active zones count
                                            if charging:
                                                if percent >= 100:
                                                    base_color = [0, 255, 0] # Green when full
                                                    active_zones_max = 4
                                                else:
                                                    base_color = [0, 0, 255] # Blue when charging
                                                    active_zones_max = (percent // 25) + 1
                                            else:
                                                if percent <= 25:
                                                    base_color = [255, 0, 0] # Red
                                                    active_zones_max = 1
                                                elif percent <= 50:
                                                    base_color = [255, 128, 0] # Orange
                                                    active_zones_max = 2
                                                else:
                                                    base_color = [255, 255, 255] # White
                                                    active_zones_max = 3 if percent <= 75 else 4
                                            
                                            for i in range(4):
                                                # Percentage within this specific zone's range (0-25 per zone)
                                                zone_min = i * 25
                                                zone_max = (i + 1) * 25
                                                
                                                if percent >= zone_max:
                                                    # Fully charged zone
                                                    brightness_mult = 1.0
                                                elif percent > zone_min:
                                                    # Partial zone filling
                                                    brightness_mult = (percent - zone_min) / 25.0
                                                else:
                                                    # Not reached yet
                                                    brightness_mult = 0.0
                                                
                                                # Apply the "tier" color logically
                                                # Lower zones inherit the color of the current active tier
                                                if i < active_zones_max:
                                                    target_colors[i * 3] = base_color[0] * brightness_mult
                                                    target_colors[i * 3 + 1] = base_color[1] * brightness_mult
                                                    target_colors[i * 3 + 2] = base_color[2] * brightness_mult
                                                else:
                                                    target_colors[i * 3] = 0
                                                    target_colors[i * 3 + 1] = 0
                                                    target_colors[i * 3 + 2] = 0
                                elif 'Mouse-Reactive Aura' in mode_name:
                                    smooth_amount = 0.8
                                    try:
                                        from PySide6.QtGui import QCursor
                                        
                                        cursor_pos = QCursor.pos()
                                        screen = QApplication.primaryScreen()
                                        if screen:
                                            screen_width = screen.size().width()
                                            # Clamp mouse X to screen bounds
                                            mouse_x = max(0, min(screen_width, cursor_pos.x()))
                                            
                                            # Create a point illumination at the mouse position
                                            for i in range(4):
                                                # Coordinate of this zone's center on the screen (0.0 to 1.0 range)
                                                zone_center_ratio = (i + 0.5) / 4.0
                                                mouse_ratio = mouse_x / screen_width
                                                
                                                # Calculate distance (0.0 to 1.0)
                                                dist = abs(zone_center_ratio - mouse_ratio)
                                                
                                                # Intensity falls off based on distance
                                                # 0.25 is the width of one zone; a 0.4 falloff gives a soft aura
                                                intensity = max(0.0, 1.0 - (dist / 0.4))
                                                
                                                # Use current zone color with intensity
                                                target_colors[i * 3] = self.zone_colors[i][0] * intensity
                                                target_colors[i * 3 + 1] = self.zone_colors[i][1] * intensity
                                                target_colors[i * 3 + 2] = self.zone_colors[i][2] * intensity
                                    except Exception as e:
                                        print(f"Mouse aura calculation error: {e}")
                                elif 'Pomodoro Timer' in mode_name:
                                    if self.pomo_running:
                                        now = time.monotonic()
                                        if now - self.pomo_last_tick >= 1.0:
                                            self.pomo_last_tick = now
                                            if self.pomo_remaining_seconds > 0:
                                                self.pomo_remaining_seconds -= 1
                                                # Update UI live
                                                h = self.pomo_remaining_seconds // 3600
                                                m = (self.pomo_remaining_seconds % 3600) // 60
                                                s = self.pomo_remaining_seconds % 60
                                                self.pomo_hours.setValue(h)
                                                self.pomo_minutes.setValue(m)
                                                self.pomo_seconds.setValue(s)
                                                self.pomo_fs_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
                                            else:
                                                self.pomo_is_finished = True
                                        
                                        if self.pomo_is_finished:
                                            # Sharp blink every half second (not smooth)
                                            smooth_amount = 0.0 
                                            self.pomo_flash_on = int(now * 2) % 2 == 0
                                            f = 1 if self.pomo_flash_on else 0
                                            for i in range(4):
                                                target_colors[i*3] = 255 * f
                                                target_colors[i*3+1] = 252 * f
                                                target_colors[i*3+2] = 248 * f
                                        elif self.pomo_remaining_seconds <= 5:
                                            # Final Countdown (Last 5 Seconds): Smooth pulse every alternate second
                                            # Sine wave pulse (period 2s)
                                            pulse = 0.5 + 0.5 * math.sin(now * math.pi)
                                            for i in range(4):
                                                target_colors[i*3] = 255 * pulse
                                                target_colors[i*3+1] = 252 * pulse
                                                target_colors[i*3+2] = 248 * pulse
                                            # Slower smoothing for the "smooth" pulse feel
                                            smooth_amount = 0.3
                                        else:
                                            # Animation completes at 5 seconds remaining
                                            # progress goes from 0.0 to 1.0 as remaining goes from total to 5
                                            effective_total = max(1, self.pomo_total_seconds - 5)
                                            progress = 1.0 - ((self.pomo_remaining_seconds - 5) / effective_total)
                                            
                                            # Zonal Draining (Left to Right)
                                            for i in range(4):
                                                zone_start = i * 0.25
                                                zone_end = (i + 1) * 0.25
                                                
                                                if progress <= zone_start:
                                                    intensity = 1.0
                                                elif progress >= zone_end:
                                                    intensity = 0.0
                                                else:
                                                    # Partial draining
                                                    intensity = 1.0 - ((progress - zone_start) / 0.25)
                                                
                                                target_colors[i * 3] = 255 * intensity
                                                target_colors[i * 3 + 1] = 252 * intensity
                                                target_colors[i * 3 + 2] = 248 * intensity
                                    else:
                                        for i in range(12):
                                            target_colors[i] = 0
                                else:
                                    if 'Ambient Screen Color' in mode_name:
                                        # Fast mode lowers the smoothing amount so it transitions immediately
                                        # Calculate smoothing per frame depending on requested update speed
                                        smooth_amount = max(0.01, min(1.0, 15.0 / self.ambient_fps_slider.value()))
                                        vib_mult = self.vibrance_slider.value() / 10.0
                                        if self.sct:
                                            monitor = self.sct.monitors[1]
                                            sct_img = self.sct.grab(monitor)
                                            img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
                                            img = img.resize((4, 1), Image.Resampling.BOX)
                                            pixels = list(img.getdata())
                                            for i in range(4):
                                                r, g, b = pixels[i]
                                                h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                                                # Apply user vibrance setting
                                                r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * vib_mult), v)
                                                target_colors[i * 3] = r * 255
                                                target_colors[i * 3 + 1] = g * 255
                                                target_colors[i * 3 + 2] = b * 255
                    final_colors = []
                    # Force slower smoothing during mode transitions
                    if self.transition_ticks > 0:
                        smooth_amount = 0.9
                        self.transition_ticks -= 1
                        
                    bright_mult = self.bright_slider.value() / 100.0
                    for i in range(12):
                        new_val = self.custom_colors[i] * smooth_amount + target_colors[i] * (1.0 - smooth_amount)
                        self.custom_colors[i] = new_val
                        final_val = new_val * bright_mult
                        final_colors.append(int(max(0, min(255, final_val))))
                    self.kb.set_colors(final_colors)
                except Exception as e:
                    print(f'Effect calculation error: {e}')
if __name__ == '__main__':
    # Support two ways to launch the audio visualizer:
    # 1) Development: executing the script file directly (audio_visualizer.py)
    # 2) Bundled EXE: re-invoke the frozen executable with `--run-visualizer` flag
    if '--run-visualizer' in sys.argv or (len(sys.argv) > 1 and 'audio_visualizer.py' in sys.argv[1]):
            if '--run-visualizer' in sys.argv:
                sys.argv.remove('--run-visualizer')
            if len(sys.argv) > 1 and 'audio_visualizer.py' in sys.argv[1]:
                sys.argv.remove(sys.argv[1])
            from audio_visualizer import AudioVisualizer
            try:
                visualizer = AudioVisualizer()
                visualizer.run()
            except Exception as e:
                import traceback
                traceback.print_exc()
            sys.exit(0)
    if sys.platform == 'win32':
        import ctypes
        myappid = 'adityafere.4zonergbtoolkit.app.1'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
    app = QApplication(sys.argv)

    from PySide6.QtWidgets import QMessageBox
    import ctypes

    mutex_name = "4ZoneRGBToolkit_SingleInstanceLock"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    last_error = ctypes.windll.kernel32.GetLastError()
    
    if last_error == 183: # ERROR_ALREADY_EXISTS
        QMessageBox.critical(None, "Already Running", "Another instance of 4 Zone RGB Toolkit is already running.")
        sys.exit(0)

    app.setStyle('Fusion')
    window = RGBControllerApp()
    if '--hidden' not in sys.argv:
        window.show()
    sys.exit(app.exec())
    