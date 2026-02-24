import sys
import subprocess
import os
import time
import colorsys
import math
import random
import ctypes
import json
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
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QSlider, QColorDialog, QGroupBox, QGridLayout, QSpacerItem, QSizePolicy, QStackedLayout, QCheckBox, QSystemTrayIcon, QMenu, QStyle, QComboBox, QInputDialog, QMessageBox, QDialog, QPlainTextEdit
from PySide6.QtCore import Qt, QSize, QTimer, QPoint, QSettings
from PySide6.QtGui import QColor, QFont, QPalette, QIcon, QMouseEvent, QAction
import winreg
from python_controller import L5PKeyboard
from threading import Lock

# Simple in-memory log buffer that mirrors stdout/stderr and retains recent output
class LogBuffer:
    def __init__(self, orig_stream):
        self.orig = orig_stream
        self.lock = Lock()
        self.lines = []
    def write(self, s):
        with self.lock:
            self.lines.append(s)
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

# Install global buffers so prints and errors are captured
_ORIG_STDOUT = sys.stdout
_ORIG_STDERR = sys.stderr
_STDOUT_BUFFER = LogBuffer(_ORIG_STDOUT)
_STDERR_BUFFER = LogBuffer(_ORIG_STDERR)
sys.stdout = _STDOUT_BUFFER
sys.stderr = _STDERR_BUFFER
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


class LogsDialog(QDialog):
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
class RGBControllerApp(QMainWindow):
    # ***<module>.RGBControllerApp: Failure: Different bytecode
    def __init__(self):
        # ***<module>.RGBControllerApp.__init__: Failure: Compilation Error
        super().__init__()
        self.setWindowTitle('4 Zone Rgb Toolkit')
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
        self.btn_clear_cache = QPushButton('Clear Cache && Reset')
        self.btn_clear_cache.setFixedHeight(35)
        self.btn_clear_cache.setCursor(Qt.PointingHandCursor)
        self.btn_clear_cache.setStyleSheet('QPushButton { background-color: rgba(255, 85, 85, 0.1); color: #FF5555; border: 1px solid #FF5555; border-radius: 6px; font-weight: bold; font-family: \'Segoe UI Variable\'; font-size: 13px; } QPushButton:hover { background-color: #FF5555; color: white; }')
        self.btn_clear_cache.clicked.connect(self.clear_cache)
        settings_layout.addWidget(self.btn_clear_cache)

        # Logs viewer button
        self.btn_view_logs = QPushButton('View Logs')
        self.btn_view_logs.setFixedHeight(35)
        self.btn_view_logs.setCursor(Qt.PointingHandCursor)
        self.btn_view_logs.setStyleSheet('QPushButton { background-color: rgba(255, 255, 255, 0.03); color: #E2E2E2; border: 1px solid rgba(255, 255, 255, 0.06); border-radius: 6px; font-family: \'Segoe UI Variable\'; font-size: 13px; } QPushButton:hover { background-color: rgba(0, 229, 255, 0.08); color: white; }')
        self.btn_view_logs.clicked.connect(self.show_logs)
        settings_layout.addWidget(self.btn_view_logs)
        settings_layout.addStretch()
        self.stack.addWidget(self.settings_view)
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
        split_layout.addLayout(left_layout, stretch=2)
        split_layout.addLayout(right_layout, stretch=1)
        main_layout.addLayout(split_layout)
        controls_group = QGroupBox('Main Controls')
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(15)
        plus_icon_path  = os.path.join(os.path.dirname(__file__), 'assets', 'plus.svg').replace('\\', '/')
        minus_icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'minus.svg').replace('\\', '/')
        icon_css = 'QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); }'
        bright_layout = QHBoxLayout()
        self.bright_label = QLabel('Brightness: 100%')
        self.bright_label.setFixedWidth(180)
        self.btn_bright_minus = QPushButton()
        self.btn_bright_minus.setIcon(QIcon(minus_icon_path))
        self.btn_bright_minus.setFixedSize(24, 24)
        self.btn_bright_minus.setStyleSheet(icon_css)
        self.btn_bright_minus.setCursor(Qt.PointingHandCursor)
        self.btn_bright_minus.clicked.connect(lambda: self.bright_slider.setValue(max(0, self.bright_slider.value() - 5)))
        self.bright_slider = QSlider(Qt.Horizontal)
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
        self.btn_bright_plus.clicked.connect(lambda: self.bright_slider.setValue(min(100, self.bright_slider.value() + 5)))
        bright_layout.addWidget(self.bright_label)
        bright_layout.addWidget(self.btn_bright_minus)
        bright_layout.addWidget(self.bright_slider, stretch=1)
        bright_layout.addWidget(self.btn_bright_plus)
        self.bright_widget = QWidget()
        self.bright_widget.setLayout(bright_layout)
        controls_layout.addWidget(self.bright_widget)
        
        self.vibrance_layout = QHBoxLayout()
        self.vibrance_label = QLabel('Vibrance: 1.5x')
        self.vibrance_label.setFixedWidth(180)
        self.btn_vib_minus = QPushButton()
        self.btn_vib_minus.setIcon(QIcon(minus_icon_path))
        self.btn_vib_minus.setFixedSize(24, 24)
        self.btn_vib_minus.setStyleSheet(icon_css)
        self.btn_vib_minus.setCursor(Qt.PointingHandCursor)
        self.btn_vib_minus.clicked.connect(lambda: self.vibrance_slider.setValue(max(5, self.vibrance_slider.value() - 5)))
        self.vibrance_slider = QSlider(Qt.Horizontal)
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
        self.btn_vib_plus.clicked.connect(lambda: self.vibrance_slider.setValue(min(30, self.vibrance_slider.value() + 5)))
        self.vibrance_layout.addWidget(self.vibrance_label)
        self.vibrance_layout.addWidget(self.btn_vib_minus)
        self.vibrance_layout.addWidget(self.vibrance_slider, stretch=1)
        self.vibrance_layout.addWidget(self.btn_vib_plus)
        
        self.vibrance_widget = QWidget()
        self.vibrance_widget.setLayout(self.vibrance_layout)
        self.vibrance_widget.hide()
        controls_layout.addWidget(self.vibrance_widget)
        speed_layout = QHBoxLayout()
        self.speed_label = QLabel('Animation Speed: 20%')
        self.speed_label.setFixedWidth(180)
        self.btn_speed_minus = QPushButton()
        self.btn_speed_minus.setIcon(QIcon(minus_icon_path))
        self.btn_speed_minus.setFixedSize(24, 24)
        self.btn_speed_minus.setStyleSheet(icon_css)
        self.btn_speed_minus.setCursor(Qt.PointingHandCursor)
        self.btn_speed_minus.clicked.connect(lambda: self.speed_slider.setValue(max(1, self.speed_slider.value() - 5)))
        self.speed_slider = QSlider(Qt.Horizontal)
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
        self.btn_speed_plus.clicked.connect(lambda: self.speed_slider.setValue(min(100, self.speed_slider.value() + 5)))
        speed_layout.addWidget(self.speed_label)
        speed_layout.addWidget(self.btn_speed_minus)
        speed_layout.addWidget(self.speed_slider, stretch=1)
        speed_layout.addWidget(self.btn_speed_plus)
        
        self.speed_widget = QWidget()
        self.speed_widget.setLayout(speed_layout)
        controls_layout.addWidget(self.speed_widget)
        
        # Random mode removed — related controls were deleted
        
        self.ambient_speed_layout = QHBoxLayout()
        self.ambient_speed_layout.setContentsMargins(145, 0, 0, 0) # align with slider
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        self.radio_slow = QRadioButton("Slow (Smooth)")
        self.radio_slow.setStyleSheet("color: white;")
        self.radio_fast = QRadioButton("Fast (Responsive)")
        self.radio_fast.setStyleSheet("color: white;")
        self.radio_slow.setChecked(True)
        self.ambient_speed_group = QButtonGroup()
        self.ambient_speed_group.addButton(self.radio_slow)
        self.ambient_speed_group.addButton(self.radio_fast)
        self.ambient_speed_layout.addWidget(self.radio_slow)
        self.ambient_speed_layout.addWidget(self.radio_fast)
        self.ambient_speed_layout.addStretch()
        self.ambient_speed_widget = QWidget()
        self.ambient_speed_widget.setLayout(self.ambient_speed_layout)
        self.ambient_speed_widget.hide()
        controls_layout.addWidget(self.ambient_speed_widget)

        left_layout.addWidget(controls_group)
        self.colors_group = QGroupBox('Zone Colors')
        colors_layout = QGridLayout(self.colors_group)
        colors_layout.setSpacing(10)
        self.zone_colors = [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]]
        self.color_buttons = []
        for i in range(4):
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(100, 40)
            self.update_button_color(btn, self.zone_colors[i])
            btn.clicked.connect(lambda checked, idx=i: self.pick_color(idx))
            self.color_buttons.append(btn)
            colors_layout.addWidget(btn, 0, i)
        self.global_color = [255, 255, 255]
        self.global_color_btn = QPushButton()
        self.global_color_btn.setCursor(Qt.PointingHandCursor)
        self.global_color_btn.setFixedHeight(25)
        self.update_button_color(self.global_color_btn, self.global_color)
        self.global_color_btn.clicked.connect(self.pick_global_color)
        colors_layout.addWidget(self.global_color_btn, 1, 0, 1, 4)
        left_layout.addWidget(self.colors_group)
        self.SOFTWARE_MODES = ['Smooth Wave (Left)', 'Smooth Wave (Right)', 'Lightning', 'Party', 'Ambient Screen Color', '[Beta] Live Audio Visualizer']
        self.HARDWARE_MODES = ['Off', 'Static', 'Breath', 'Smooth', 'Wave (Left)', 'Wave (Right)']
        self.mode_list = QListWidget()
        self.mode_list.addItems(self.HARDWARE_MODES + self.SOFTWARE_MODES)
        self.mode_list.setCurrentRow(0)
        self.mode_list.currentTextChanged.connect(self.on_mode_changed)
        right_layout.addWidget(self.mode_list)
        self.wave_fill_cb = QCheckBox('Fill Mode')
        self.wave_fill_cb.setStyleSheet('\n            QCheckBox { color: #E2E2E2; font-size: 13px; font-weight: bold; background: transparent; border: none; }\n            QCheckBox::indicator { width: 18px; height: 18px; background: rgba(0, 0, 0, 0.4); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 4px; }\n            QCheckBox::indicator:checked { background: #00E5FF; }\n        ')
        self.wave_fill_cb.setCursor(Qt.PointingHandCursor)
        self.wave_fill_cb.hide()
        right_layout.addWidget(self.wave_fill_cb)
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
        self.custom_colors = [0] * 12
        self.last_activity = time.time()
        self.sct = None
        if HAS_PYNPUT:
            def on_activity(*args, **kwargs):
                self.last_activity = time.time()
            self.mouse_listener = mouse.Listener(on_move=on_activity, on_click=on_activity, on_scroll=on_activity)
            self.mouse_listener.start()
            self.kbd_listener = keyboard.Listener(on_press=on_activity)
            self.kbd_listener.start()
        try:
            self.kb = L5PKeyboard()
        except ValueError as e:
            print(f'Error initializing keyboard: {e}')
        self.force_quit = False
        self.load_settings()
        self.apply_effect()
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
            self.update_preset_combos()
            self.minimize_to_tray_cb.blockSignals(False)
            self.launch_on_start_cb.blockSignals(False)
            self.startup_preset_combo.blockSignals(False)
            self.bright_slider.setValue(100)
            self.vibrance_slider.setValue(15)
            self.speed_slider.setValue(20)
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
            items = self.mode_list.findItems(p.get('mode', 'Static'), Qt.MatchExactly)
            if items:
                self.mode_list.setCurrentItem(items[0])
            self.bright_slider.setValue(p.get('brightness', 100))
            self.vibrance_slider.setValue(p.get('vibrance', 15))
            self.speed_slider.setValue(p.get('speed', 20))
            self.zone_colors = p.get('colors', [[255, 0, 0]] * 4)
            for i in range(4):
                self.update_button_color(self.color_buttons[i], self.zone_colors[i])
            if 'global_color' in p:
                self.global_color = p['global_color']
                self.update_button_color(self.global_color_btn, self.global_color)
            self.mode_list.blockSignals(False)
            self.bright_slider.blockSignals(False)
            self.speed_slider.blockSignals(False)
            self.on_mode_changed(p.get('mode', 'Static'))
    def save_new_preset(self):
        name, ok = QInputDialog.getText(self, 'Save Preset', 'Enter a name for this preset:')
        if ok and name.strip():
                name = name.strip()
                self.presets[name] = {'mode': self.mode_list.currentItem().text() if self.mode_list.currentItem() else 'Static', 'brightness': self.bright_slider.value(), 'vibrance': self.vibrance_slider.value(), 'speed': self.speed_slider.value(), 'colors': list(self.zone_colors), 'global_color': list(self.global_color)}
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
                self.update_button_color(self.color_buttons[i], [r, g, b])
            self.apply_effect()
    def minimize_app(self):
        if self.minimize_to_tray_cb.isChecked():
            self.hide()
        else:
            self.showMinimized()
    def restore_app(self):
        self.show()
        self.activateWindow()
    def tray_quit(self):
        self.force_quit = True
        try:
            if self.kb:
                self.kb.set_effect('static')
                self.kb.set_solid_color(0, 0, 0)
        except Exception as e:
            pass
        QApplication.instance().quit()
    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_app()
    def toggle_settings(self):
        if self.stack.currentIndex() == 0:
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)
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
    def on_mode_changed(self, mode_name):
        if mode_name is None:
            return
        else:
            is_zones_enabled = mode_name in ('Static', 'Breath')
            self.colors_group.setEnabled(is_zones_enabled)
            if is_zones_enabled:
                self.colors_group.setStyleSheet('QGroupBox { color: #00E5FF; }')
            else:
                self.colors_group.setStyleSheet('QGroupBox { color: #555555; }')
            is_speed_enabled = mode_name not in ['Off', 'Static', '[Beta] CPU Temperature', 'Ambient Screen Color']
            self.speed_widget.setEnabled(is_speed_enabled)
            self.speed_label.setStyleSheet('color: #E2E2E2;' if is_speed_enabled else 'color: #555555;')
            
            is_bright_enabled = mode_name not in self.SOFTWARE_MODES and mode_name != 'Off'
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
            
            if mode_name == 'Ambient Screen Color':
                # Show vibrance slider only in Ambient Screen Color mode
                self.vibrance_widget.show()
                self.speed_widget.hide()
                self.ambient_speed_widget.show()
            elif 'Live Audio Visualizer' in mode_name:
                # In Live Audio Visualizer mode, hide vibrance (brightness boost) UI
                self.vibrance_widget.hide()
                self.speed_label.setText(f'Visualizer Sensitivity: {self.speed_slider.value()}%')
                self.speed_label.setStyleSheet('color: #E2E2E2;')
                # Make sure the speed control is visible and interactive (it may have been hidden
                # by Ambient mode). Also hide ambient-only controls.
                self.speed_widget.show()
                self.speed_widget.setEnabled(True)
                self.ambient_speed_widget.hide()
                # (random mode removed)
                # Enable zone color pickers so user can choose their static colors
                self.colors_group.setEnabled(True)
                self.colors_group.setStyleSheet('QGroupBox { color: #00E5FF; }')
            else:
                # Hide vibrance for all other modes
                self.vibrance_widget.hide()
                self.speed_widget.show()
                self.ambient_speed_widget.hide()
                # (random mode removed)
            
            if 'Lightning' in mode_name:
                self.speed_label.setText(f'Lightning Frequency: {self.speed_slider.value()}%')
            elif 'Live Audio Visualizer' in mode_name:
                self.speed_label.setText(f'Visualizer Sensitivity: {self.speed_slider.value()}%')
            else:
                self.speed_label.setText(f'Animation Speed: {self.speed_slider.value()}%')
            
            if 'Smooth Wave' in mode_name:
                self.wave_fill_cb.show()
            else:
                self.wave_fill_cb.hide()
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
            if HAS_PYNPUT:
                try:
                    self.mouse_listener.stop()
                    self.kbd_listener.stop()
                except:
                    pass
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
    def on_speed_changed(self, value):
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else ''
        if 'Lightning' in mode_name:
            self.speed_label.setText(f'Lightning Frequency: {value}%')
        elif 'Live Audio Visualizer' in mode_name:
            self.speed_label.setText(f'Visualizer Sensitivity: {value}%')
        else:
            self.speed_label.setText(f'Animation Speed: {value}%')
        self.apply_effect()
    # Random mode removed; handler deleted
    def on_vibrance_changed(self, value):
        mode_name = self.mode_list.currentItem().text() if self.mode_list.currentItem() else ''
        if 'Live Audio Visualizer' in mode_name:
            self.vibrance_label.setText(f'Brightness Boost: {value}%')
            self.apply_effect()  # restart with new brightness boost
        else:
            self.vibrance_label.setText(f'Vibrance: {value/10.0}x')
            # Does not need immediate effect replay - calculates frame by frame
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

                env = os.environ.copy()
                env['PYTHONPATH'] = os.pathsep.join(sys.path)
                sensitivity_val  = str(self.speed_slider.value())
                smoothness_val   = str(self.bright_slider.value())
                flicker_val      = str(0)
                # Pass zone colors as individual R G B args for all 4 zones
                color_args = []
                for c in self.zone_colors:
                    color_args.extend([str(c[0]), str(c[1]), str(c[2])])

                # When running from a bundled EXE (PyInstaller), there is no separate
                # audio_visualizer.py file on disk. Use a special flag to tell the
                # frozen executable to run the visualizer code path instead of
                # attempting to execute a script file.
                if getattr(sys, 'frozen', False):
                    cmd = [sys.executable, '--run-visualizer', sensitivity_val, smoothness_val, flicker_val] + color_args
                else:
                    script_cmd = os.path.join(os.path.dirname(__file__), 'audio_visualizer.py')
                    cmd = [sys.executable, script_cmd, sensitivity_val, smoothness_val, flicker_val] + color_args

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
                    self.custom_timer.start(33)
                    return
                else:
                    if mode_name == 'Off':
                        if self.kb:
                            self.kb.set_effect('static')
                            self.kb.set_solid_color(0, 0, 0)
                        return
                    effect = 'static'
                    wave_dir = 'left'
                    if 'Breath' in mode_name:
                        effect = 'breath'
                    else:
                        if 'Smooth' in mode_name:
                            effect = 'smooth'
                        else:
                            if 'Wave (Left)' in mode_name:
                                effect = 'wave'
                                wave_dir = 'left'
                            else:
                                if 'Wave (Right)' in mode_name:
                                    effect = 'wave'
                                    wave_dir = 'right'
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
                t = time.time()
                target_colors = list(self.custom_colors)
                smooth_amount = 0.5
                try:
                    if 'Smooth Wave' in mode_name:
                        smooth_amount = 0.1
                        t *= speed_mult
                        dir_mult = (-0.15) if 'Left' in mode_name else 0.15
                        if self.wave_fill_cb.isChecked():
                            total_cycles = int(t)
                            phase = t % 1.0
                            hue_prev = total_cycles * 0.1 % 1.0
                            hue_next = (total_cycles + 1) * 0.1 % 1.0
                            r_prev, g_prev, b_prev = colorsys.hsv_to_rgb(hue_prev, 1.0, 1.0)
                            r_next, g_next, b_next = colorsys.hsv_to_rgb(hue_next, 1.0, 1.0)
                            for i in range(4):
                                zone_pos = i * 0.25 if 'Right' not in mode_name else (3 - i) * 0.25
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
                            for i in range(4):
                                target_colors[i * 3] = 4
                                target_colors[i * 3 + 1] = 8
                                target_colors[i * 3 + 2] = 25
                            if len(self.lightning_strikes) == 0 and random.random() < 0.04 * speed_mult:
                                    num_strikes = random.choice([1, 2])
                                    zones = random.sample(range(4), num_strikes)
                                    for z in zones:
                                        duration_ticks = random.randint(1, 6)
                                        if random.random() > 0.4:
                                            color = [255, 255, 255]
                                        else:
                                            color = [80, 200, 255]
                                        self.lightning_strikes.append({'zone': z, 'color': color, 'life': duration_ticks})
                            smooth_amount = 0.92
                            active_strikes = []
                            for strike in self.lightning_strikes:
                                z = strike['zone']
                                col = strike['color']
                                target_colors[z * 3] = col[0]
                                target_colors[z * 3 + 1] = col[1]
                                target_colors[z * 3 + 2] = col[2]
                                smooth_amount = 0.05
                                strike['life'] -= 1
                                if strike['life'] > 0:
                                    active_strikes.append(strike)
                            self.lightning_strikes = active_strikes
                        else:
                            if 'Party' in mode_name:
                                smooth_amount = 0.05
                                if not hasattr(self, 'party_colors') or random.random() < 0.15 * speed_mult:
                                    self.party_colors = []
                                    for _ in range(4):
                                        h = random.random()
                                        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
                                        self.party_colors.extend([r * 255, g * 255, b * 255])
                                for i in range(12):
                                    target_colors[i] = self.party_colors[i]
                            else:
                                if 'Ambient Screen Color' in mode_name:
                                    # Fast mode lowers the smoothing amount so it transitions immediately
                                    smooth_amount = 0.8 if self.radio_slow.isChecked() else 0.15
                                    vib_mult = self.vibrance_slider.value() / 10.0
                                    if self.sct:
                                        monitor = self.sct.monitors[1]
                                        sct_img = self.sct.grab(monitor)
                                        img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
                                        img = img.resize((4, 1), Image.Resampling.LANCZOS)
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
    app.setStyle('Fusion')
    window = RGBControllerApp()
    if '--hidden' not in sys.argv:
        window.show()
    sys.exit(app.exec())