
import sys
import subprocess
import os
import platform
from utils.system_info import get_laptop_model
import time
import colorsys
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
    from pynput import keyboard  # noqa: F401

    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False
try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QColorDialog,
    QGroupBox,
    QGridLayout,
    QSizePolicy,
    QStackedLayout,
    QCheckBox,
    QSystemTrayIcon,
    QMenu,
    QComboBox,
    QInputDialog,
    QMessageBox,
    QDialog,
    QProgressDialog,
    QTextBrowser,
    QGraphicsOpacityEffect,
    QFrame,
    QFileDialog,
    QTabWidget,
    QScrollArea,
    QLineEdit,
    QSpinBox,
    QAbstractItemView,
)
from PySide6.QtCore import (
    Qt,
    QSize,
    QTimer,
    QSettings,
    Signal,
    QThread,
    QPropertyAnimation,
    QEasingCurve,
    QVariantAnimation,
    QUrl,
    Slot,
)
from PySide6.QtGui import QColor, QFont, QIcon, QAction, QDesktopServices
from mobile_server import MobileServer
import winreg
from core.keyboard import RGBKeyboard
from core.manager import EffectManager
from custom_builder_gui import (
    _normalize_hotkey_key_name,
    FadeDialog,
    AnimatedSlider,
    AnimatedInfoIcon,
    GlowButton,
    CustomTitleBar,
    LogsDialog,
    KeyboardPreviewWidget,
    HotkeyDialog,
    GifSplashScreen,
    EffectStudioDialog,
)
import threading
from threading import Lock
from collections import deque
import urllib.request
import urllib.error
import tempfile
import traceback


CURRENT_VERSION = "v3.2"


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
        ("BatteryLifeTime", ctypes.c_uint),
        ("BatteryFullLifeTime", ctypes.c_uint),
    ]


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


# Windows power mode overlay GUID for "Best power efficiency" (aka Energy Saver mode)
GUID_OVERLAY_BEST_POWER_EFFICIENCY = GUID(
    0x961CC777,
    0x2547,
    0x4F9D,
    (ctypes.c_ubyte * 8)(0x81, 0x74, 0x7D, 0x86, 0x18, 0x1B, 0x8A, 0x7A),
)


def _guid_equals(a, b):
    return (
        a.Data1 == b.Data1
        and a.Data2 == b.Data2
        and a.Data3 == b.Data3
        and bytes(a.Data4) == bytes(b.Data4)
    )


# Battery cache: updated every 500ms to avoid expensive repeated calls in tight loops
_battery_cache = {"percent": 0, "charging": True, "last_update": 0}





def _resolve_original_exe_path():
    if not getattr(sys, "frozen", False):
        return None
    candidates = []
    if getattr(sys, "executable", None):
        candidates.append(os.path.abspath(sys.executable))
    if len(sys.argv) > 0 and sys.argv[0]:
        candidates.append(os.path.abspath(sys.argv[0]))
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return candidates[0] if candidates else None


def _ps_escape(value):
    # Escape content for use in PowerShell double-quoted strings.
    return str(value).replace("`", "``").replace('"', '`"').replace("$", "`$")


def sanitized_child_env(base_env=None, include_pythonpath=False, force_re_extract=False):
    env = dict(base_env or os.environ)
    if force_re_extract:
        # PyInstaller one-file processes pass runtime extraction hints through
        # environment variables. If inherited by child processes after parent
        # teardown, they can reference deleted _MEI temp folders and trigger
        # "Failed to load Python DLL" errors.
        env.pop("_MEIPASS", None)
        env.pop("_MEIPASS2", None)
        for key in [k for k in env if k.startswith("_PYI_")]:
            env.pop(key, None)

        # Remove the temp folder from PATH (crucial to avoid "Python DLL not found"
        # if the child process inherits a PATH pointing to a deleted _MEI folder)
        if getattr(sys, "frozen", False):
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                # Find the PATH key (case-insensitive search for Windows compat)
                path_key = next((k for k in env if k.lower() == "path"), None)
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

        # Ensure frozen child re-exec starts with a fresh extraction context.
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

    if include_pythonpath:
        env["PYTHONPATH"] = os.pathsep.join(sys.path)
    else:
        env.pop("PYTHONPATH", None)
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
            return "".join(self.lines)

    def clear(self):
        with self.lock:
            self.lines.clear()
            self.current_chars = 0

    def isatty(self):
        if hasattr(self.orig, 'isatty'):
            return self.orig.isatty()
        return False


# Install global buffers so prints and errors are captured
_ORIG_STDOUT = sys.stdout
_ORIG_STDERR = sys.stderr
_STDOUT_BUFFER = LogBuffer(_ORIG_STDOUT)
_STDERR_BUFFER = LogBuffer(_ORIG_STDERR)
sys.stdout = _STDOUT_BUFFER
sys.stderr = _STDERR_BUFFER





class GlobalHotkeyListener(QThread):
    hotkey_triggered = Signal(str)

    def __init__(self, hotkeys_dict, parent=None):
        super().__init__(parent)
        import threading
        self.lock = threading.Lock()
        self.hotkeys_dict = hotkeys_dict
        self.modifiers = set()
        self.running = True
        self.paused = False
        self.listener = None
        self.trigger_cooldown_ms = 220
        self.last_trigger_times = {}

    def run(self):
        if not HAS_PYNPUT:
            return
        from pynput import keyboard

        def on_press(key):
            if not self.running:
                return False
            if self.paused:
                return

            # Map modifier keys
            with self.lock:
                if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                    self.modifiers.add("ctrl")
                elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                    self.modifiers.add("alt")
                elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                    self.modifiers.add("shift")
                elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                    self.modifiers.add("win")
                else:
                    # Regular key pressed, build combination
                    parts = []
                    # Ensure the same order as the recorder: ctrl, alt, shift, win
                    if "ctrl" in self.modifiers:
                        parts.append("ctrl")
                    if "alt" in self.modifiers:
                        parts.append("alt")
                    if "shift" in self.modifiers:
                        parts.append("shift")
                    if "win" in self.modifiers:
                        parts.append("win")

                # Whether or not it was a modifier, we want to know if shift is active
                # for the normalization later
                shift_active = "shift" in self.modifiers

            if key not in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r, keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr, keyboard.Key.shift_l, keyboard.Key.shift_r, keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):

                char = None
                try:
                    # Use canonical to get the unmodified character
                    # This avoids issues where Ctrl+A becomes \x01
                    if self.listener:
                        base_key = self.listener.canonical(key)
                        if hasattr(base_key, "char") and base_key.char:
                            char = base_key.char.lower()
                        elif hasattr(base_key, "name") and base_key.name:
                            char = base_key.name.lower()
                except Exception:
                    pass

                # Fallback to standard pynput key detection if canonical failed
                if not char:
                    try:
                        if hasattr(key, "char") and key.char:
                            char = key.char.lower()
                        elif hasattr(key, "name") and key.name:
                            char = key.name.lower()
                        elif hasattr(key, "vk") and key.vk:
                            # Final fallback for some Windows letters
                            if 65 <= key.vk <= 90:
                                char = chr(key.vk + 32)
                            else:
                                char = str(key.vk)
                    except Exception:
                        pass

                if char:
                    char = _normalize_hotkey_key_name(char, shift_active)

                    parts.append(char)
                    combo = "+".join(parts)
                    if combo in self.hotkeys_dict:
                        now = time.monotonic()
                        last_time = self.last_trigger_times.get(combo, 0)
                        if (now - last_time) * 1000 >= self.trigger_cooldown_ms:
                            self.last_trigger_times[combo] = now
                            self.hotkey_triggered.emit(combo)

        def on_release(key):
            with self.lock:
                if key in (keyboard.Key.ctrl_l, keyboard.Key.ctrl_r):
                    self.modifiers.discard("ctrl")
                elif key in (keyboard.Key.alt_l, keyboard.Key.alt_r, keyboard.Key.alt_gr):
                    self.modifiers.discard("alt")
                elif key in (keyboard.Key.shift_l, keyboard.Key.shift_r):
                    self.modifiers.discard("shift")
                elif key in (keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r):
                    self.modifiers.discard("win")

        self.listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        with self.listener:
            try:
                self.listener.join()
            except Exception as e:
                print(f"Hotkey listener thread error: {e}")

    def update_hotkeys(self, new_hotkeys):
        self.hotkeys_dict = dict(new_hotkeys)

    def set_paused(self, paused):
        self.paused = bool(paused)
        if self.paused:
            with self.lock:
                self.modifiers.clear()

    def stop(self):
        self.running = False
        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass
        self.quit()
        # Give the thread a moment to finish, but don't hang indefinitely
        if not self.wait(1000):
            # If it didn't finish, we might need to be more aggressive,
            # but usually quit/wait is enough if listener stopped.
            pass


class UpdateDownloader(QThread):
    progress = Signal(int)
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url
        self._is_canceled = False
        
    def cancel(self):
        self._is_canceled = True

    def run(self):
        try:
            req = urllib.request.Request(
                self.url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("content-length", 0))
                tmp_dir = tempfile.gettempdir()
                dest_path = os.path.join(tmp_dir, "4_Zone_Rgb_Toolkit_Updated.exe")

                with open(dest_path, "wb") as f:
                    downloaded = 0
                    while True:
                        if self._is_canceled:
                            return
                        chunk = response.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.progress.emit(percent)
                if not self._is_canceled:
                    if total_size > 0 and downloaded != total_size:
                        self.error.emit(f"Download incomplete: {downloaded}/{total_size} bytes")
                        return
                    try:
                        with open(dest_path, "rb") as bf:
                            if bf.read(2) != b"MZ":
                                self.error.emit("Downloaded file is corrupt (invalid executable).")
                                return
                    except Exception as e:
                        self.error.emit(f"Could not verify executable: {e}")
                        return
                    self.finished.emit(dest_path)
        except Exception as e:
            if not self._is_canceled:
                self.error.emit(str(e))

class TelemetryClient:
    def __init__(self, app_ref, endpoint_url="https://rgb-toolkit-telemetry.vercel.app/api"):
        self.app_ref = app_ref
        self.endpoint_url = endpoint_url
        self.laptop_name = platform.node()
        self.laptop_model = get_laptop_model()
        self.running = False
        self.thread = None

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        threading.Thread(target=self._send_status, args=("offline",), daemon=True).start()
        if self.thread:
            self.thread.join(timeout=0.1)

    def _loop(self):
        self._send_status("online")
        while self.running:
            for _ in range(300): # 5 minutes sleep in 1s increments to allow fast shutdown
                if not self.running: return
                time.sleep(1)
            self._send_status("online")

    def _send_status(self, status):
        try:
            from PySide6.QtCore import QSettings
            settings = QSettings("4ZoneRgbToolkit", "Preferences")
            val = settings.value("telemetry_enabled", True)
            enabled = str(val).lower() == "true" if isinstance(val, str) else bool(val)
            if not enabled:
                return
        except Exception:
            pass
        try:
            current_effect = "Unknown"
            if hasattr(self.app_ref, "current_mode_name") and self.app_ref.current_mode_name:
                current_effect = self.app_ref.current_mode_name
            data = json.dumps({
                "laptopName": self.laptop_name,
                "model": self.laptop_model,
                "status": status,
                "effect": current_effect
            }).encode('utf-8')
            req = urllib.request.Request(self.endpoint_url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
            urllib.request.urlopen(req, timeout=5.0)
        except Exception:
            pass


class RGBControllerApp(QMainWindow):
    # ***<module>.RGBControllerApp: Failure: Different bytecode
    update_available = Signal(str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("4 Zone Rgb Toolkit")
        
        self.laptop_model = get_laptop_model()
        self.telemetry = TelemetryClient(self)
        self.custom_colors = [0] * 12
        self.telemetry.start()
        
        self.mobile_server = MobileServer(self, port=6767)
        self.mobile_server.start()
        
        try:
            from fastapi_server import FastAPIThread
            self.fastapi_server = FastAPIThread(self, port=8000)
            self.fastapi_server.start()
        except Exception as e:
            print(f"Failed to start FastAPI server: {e}")
        
        self.original_exe_path = _resolve_original_exe_path()
        self.setMinimumSize(500, 480)
        self.icon_path = os.path.join(
            os.path.dirname(__file__), "assets", "rgb_wheel.ico"
        )
        self.setWindowIcon(QIcon(self.icon_path))
        self.setWindowFlags(
            Qt.Window
            | Qt.CustomizeWindowHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        try:
            hwnd = int(self.winId())
            margins = RECT(1, 1, 1, 1)
            ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
                hwnd, ctypes.byref(margins)
            )
        except Exception:
            pass
        self.setStyleSheet(
            "\n            QMainWindow {\n                background-color: transparent;\n            }\n            #MainContainer {\n                background-color: #0E0E12;\n                border: 1px solid rgba(255, 255, 255, 0.08);\n                border-radius: 12px;\n            }\n            QLabel {\n                color: #E2E2E2;\n                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;\n                font-size: 14px;\n            }\n            QGroupBox {\n                color: #00E5FF;\n                font-weight: 600;\n                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;\n                font-size: 13px;\n                border: 1px solid rgba(255, 255, 255, 0.05);\n                border-radius: 10px;\n                background-color: rgba(255, 255, 255, 0.02);\n                margin-top: 24px;\n                padding-top: 15px;\n            }\n            QGroupBox::title {\n                subcontrol-origin: margin;\n                left: 12px;\n                padding: 0 6px 0 6px;\n                background-color: transparent;\n            }\n            QListWidget {\n                background-color: #1A1A1E;\n                color: #FFFFFF;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n                border-radius: 8px;\n                padding: 4px;\n                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;\n                font-size: 13px;\n                outline: none;\n            }\n            QListWidget::item {\n                padding: 10px;\n                border-radius: 4px;\n                margin-bottom: 2px;\n            }\n            QListWidget::item:hover {\n                background-color: rgba(0, 229, 255, 0.1);\n            }\n            QListWidget::item:selected {\n                background-color: #00E5FF;\n                color: #0E0E12;\n                font-weight: 600;\n            }\n            QPushButton {\n                background-color: #1A1A1E;\n                color: white;\n                border: 1px solid rgba(255, 255, 255, 0.1);\n                border-radius: 6px;\n                padding: 8px 16px;\n                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;\n                font-size: 13px;\n                font-weight: 500;\n            }\n            QPushButton:hover {\n                background-color: #00E5FF;\n                color: black;\n                font-weight: 600;\n                border: 1px solid #00E5FF;\n            }\n            QPushButton:pressed {\n                background-color: #00B3CC;\n                border: 1px solid #00B3CC;\n            }\n            QSlider::groove:horizontal {\n                border: none;\n                height: 6px;\n                background: #2A2A2E;\n                border-radius: 3px;\n            }\n            QSlider::sub-page:horizontal {\n                background: #00E5FF;\n                border-radius: 3px;\n            }\n            QSlider::handle:horizontal {\n                background: #FFFFFF;\n                border: 2px solid #00E5FF;\n                width: 14px;\n                height: 14px;\n                margin: -4px 0;\n                border-radius: 7px;\n            }\n            QSlider::handle:horizontal:hover {\n                background: #00E5FF;\n            }\n            QSlider::sub-page:horizontal:disabled {\n                background: #444444;\n            }\n            QSlider::handle:horizontal:disabled {\n                border: 2px solid #555555;\n                background: #666666;\n            }\n        "
        )
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        master_layout = QVBoxLayout(central_widget)
        master_layout.setContentsMargins(0, 0, 0, 0)
        main_container = QWidget()
        main_container.setObjectName("MainContainer")
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
        QApplication.processEvents()
        main_layout.setContentsMargins(20, 10, 20, 20)
        main_layout.setSpacing(15)
        self.stack.addWidget(main_view)
        self.settings_view = QWidget()
        settings_layout = QVBoxLayout(self.settings_view)
        settings_layout.setContentsMargins(20, 10, 20, 20)
        settings_header = QHBoxLayout()
        settings_header.addWidget(
            QLabel(
                "Settings",
                styleSheet="color: #00E5FF; font-size: 20px; font-weight: bold;",
            )
        )
        settings_header.addStretch()
        self.btn_close_settings = QPushButton("✕")
        self.btn_close_settings.setFixedSize(30, 30)
        self.btn_close_settings.setStyleSheet(
            "QPushButton { background: transparent; color: white; font-weight: bold; font-size: 18px; border: none; } QPushButton:hover { color: #FF605C; }"
        )
        self.btn_close_settings.clicked.connect(self.toggle_settings)
        settings_header.addWidget(self.btn_close_settings)
        settings_layout.addLayout(settings_header)
        self.settings_tabs = QTabWidget()
        self.settings_tabs.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid rgba(255, 255, 255, 0.05); 
                background: rgba(255, 255, 255, 0.02);
                border-radius: 8px;
                margin-top: -1px;
            }
            QTabBar::tab {
                background: transparent; 
                color: #888888; 
                padding: 10px 20px; 
                border-bottom: 2px solid transparent;
                font-family: 'Segoe UI Variable'; 
                font-size: 13px;
                font-weight: 500;
                margin-right: 4px;
            }
            QTabBar::tab:selected { 
                color: #00E5FF; 
                border-bottom: 2px solid #00E5FF;
                font-weight: bold; 
                background: rgba(0, 229, 255, 0.05);
            }
            QTabBar::tab:hover:!selected { 
                color: #E2E2E2;
                background: rgba(255, 255, 255, 0.05); 
            }
        """)

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        general_layout.setContentsMargins(0, 10, 0, 0)
        gen_scroll = QScrollArea()
        gen_scroll.setWidgetResizable(True)
        gen_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; } QWidget#GenScrollContent { background: transparent; }"
        )
        gen_content = QWidget()
        gen_content.setObjectName("GenScrollContent")
        gen_content_layout = QVBoxLayout(gen_content)
        gen_content_layout.setContentsMargins(0, 0, 10, 0)

        on_icon_path = os.path.join(
            os.path.dirname(__file__), "assets", "toggle_on.svg"
        ).replace("\\", "/")
        off_icon_path = os.path.join(
            os.path.dirname(__file__), "assets", "toggle_off.svg"
        ).replace("\\", "/")
        toggle_css = f'\n            QCheckBox {{ color: #E2E2E2; font-size: 13px; spacing: 12px; padding: 4px; }}\n            QCheckBox::indicator {{ width: 36px; height: 20px; }}\n            QCheckBox::indicator:unchecked {{ image: url("{off_icon_path}"); }}\n            QCheckBox::indicator:checked {{ image: url("{on_icon_path}"); }}\n        '

        def create_section_header(title):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 15, 0, 5)
            label = QLabel(title.upper())
            label.setStyleSheet(
                "color: #00E5FF; font-size: 11px; font-weight: 800; letter-spacing: 1px;"
            )
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setStyleSheet(
                "background: rgba(0, 229, 255, 0.15); height: 1px; border: none;"
            )
            layout.addWidget(label)
            layout.addWidget(line)
            layout.setStretch(1, 1)
            return container

        # --- Section: Behavior ---
        gen_content_layout.addWidget(create_section_header("Application Behavior"))
        behavior_card = QFrame()
        behavior_card.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 0.03); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.05); }"
        )
        behavior_layout = QVBoxLayout(behavior_card)

        min_tray_row = QHBoxLayout()
        min_tray_row.setContentsMargins(0, 0, 0, 0)
        self.minimize_to_tray_cb = QCheckBox("Minimize to Tray")
        self.minimize_to_tray_cb.setStyleSheet(toggle_css)
        self.minimize_to_tray_cb.toggled.connect(self.save_settings)
        min_tray_row.addWidget(self.minimize_to_tray_cb)
        min_tray_row.addWidget(AnimatedInfoIcon("Keeps the app running in the background system tray\nwhen you close the main window."))
        min_tray_row.addStretch()
        behavior_layout.addLayout(min_tray_row)

        launch_row = QHBoxLayout()
        launch_row.setContentsMargins(0, 0, 0, 0)
        self.launch_on_start_cb = QCheckBox("Launch on Windows Startup")
        self.launch_on_start_cb.setStyleSheet(toggle_css)
        self.launch_on_start_cb.toggled.connect(self.save_settings)
        launch_row.addWidget(self.launch_on_start_cb)
        launch_row.addWidget(AnimatedInfoIcon("Automatically starts the RGB toolkit silently\nwhen you log into Windows."))
        launch_row.addStretch()
        behavior_layout.addLayout(launch_row)

        start_min_row = QHBoxLayout()
        start_min_row.setContentsMargins(0, 0, 0, 0)
        self.start_minimized_cb = QCheckBox("Start Minimized (System Tray)")
        self.start_minimized_cb.setStyleSheet(toggle_css)
        self.start_minimized_cb.toggled.connect(self.on_start_minimized_toggled)
        start_min_row.addWidget(self.start_minimized_cb)
        start_min_row.addWidget(AnimatedInfoIcon("Launches the application silently into the system tray without showing the main window."))
        start_min_row.addStretch()
        behavior_layout.addLayout(start_min_row)

        boot_gif_row = QHBoxLayout()
        boot_gif_row.setContentsMargins(0, 0, 0, 0)
        self.boot_gif_cb = QCheckBox("Show Splash Screen on Boot")
        self.boot_gif_cb.setStyleSheet(toggle_css)
        self.boot_gif_cb.toggled.connect(self.on_boot_gif_toggled)
        boot_gif_row.addWidget(self.boot_gif_cb)
        boot_gif_row.addWidget(AnimatedInfoIcon("Plays the boot GIF animation when launching the app."))
        boot_gif_row.addStretch()
        behavior_layout.addLayout(boot_gif_row)

        auto_update_row = QHBoxLayout()
        auto_update_row.setContentsMargins(0, 0, 0, 0)
        self.auto_update_cb = QCheckBox("Auto-Update (Silent)")
        self.auto_update_cb.setStyleSheet(toggle_css)
        self.auto_update_cb.toggled.connect(self.save_settings)
        auto_update_row.addWidget(self.auto_update_cb)
        auto_update_row.addWidget(AnimatedInfoIcon("When enabled, the app will automatically download and apply\nnew updates on startup without prompting you."))
        auto_update_row.addStretch()
        behavior_layout.addLayout(auto_update_row)

        gen_content_layout.addWidget(behavior_card)

        # --- Section: Telemetry ---
        gen_content_layout.addWidget(create_section_header("Telemetry"))
        telemetry_card = QFrame()
        telemetry_card.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 0.03); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.05); }"
        )
        telemetry_layout = QVBoxLayout(telemetry_card)

        telemetry_row = QHBoxLayout()
        telemetry_row.setContentsMargins(0, 0, 0, 0)
        
        self.telemetry_cb = QCheckBox("Enable Telemetry")
        self.telemetry_cb.setStyleSheet(toggle_css)
        self.telemetry_cb.toggled.connect(self.save_settings)
        telemetry_row.addWidget(self.telemetry_cb)
        
        telemetry_row.addWidget(AnimatedInfoIcon("When enabled, the app periodically sends an anonymous ping\ncontaining your device model to the dashboard\nto display the total active user count."))
        telemetry_row.addStretch()
        
        telemetry_layout.addLayout(telemetry_row)

        model_row = QHBoxLayout()
        model_row.setContentsMargins(2, 6, 2, 2)
        model_title = QLabel("Device Model:")
        model_title.setStyleSheet("color: #888888; font-size: 12px; font-weight: 500;")
        model_val = QLabel(self.laptop_model)
        model_val.setStyleSheet("color: #00E5FF; font-size: 12px; font-weight: 700; background: rgba(0, 229, 255, 0.08); border-radius: 4px; padding: 2px 8px; border: 1px solid rgba(0, 229, 255, 0.2);")
        model_row.addWidget(model_title)
        model_row.addWidget(model_val)
        model_row.addStretch()
        telemetry_layout.addLayout(model_row)

        gen_content_layout.addWidget(telemetry_card)

        # --- Section: Power ---
        gen_content_layout.addWidget(create_section_header("Power Management"))
        power_card = QFrame()
        power_card.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 0.03); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.05); }"
        )
        power_layout = QVBoxLayout(power_card)

        unplugged_row = QHBoxLayout()
        unplugged_row.setContentsMargins(0, 0, 0, 0)
        self.turn_off_unplugged_cb = QCheckBox("Eco Mode: Turn off when unplugged")
        self.turn_off_unplugged_cb.setStyleSheet(toggle_css)
        self.turn_off_unplugged_cb.toggled.connect(self.on_power_policy_setting_changed)
        unplugged_row.addWidget(self.turn_off_unplugged_cb)
        unplugged_row.addWidget(AnimatedInfoIcon("Automatically turns off all RGB lighting to save power\nwhen the laptop charger is disconnected."))
        unplugged_row.addStretch()
        power_layout.addLayout(unplugged_row)

        saver_row = QHBoxLayout()
        saver_row.setContentsMargins(0, 0, 0, 0)
        self.turn_off_battery_saver_cb = QCheckBox("Eco Mode: Turn off on Battery Saver")
        self.turn_off_battery_saver_cb.setStyleSheet(toggle_css)
        self.turn_off_battery_saver_cb.toggled.connect(self.on_power_policy_setting_changed)
        saver_row.addWidget(self.turn_off_battery_saver_cb)
        saver_row.addWidget(AnimatedInfoIcon("Turns off RGB lighting when Windows\nenters Battery Saver mode."))
        saver_row.addStretch()
        power_layout.addLayout(saver_row)

        gen_content_layout.addWidget(power_card)

        # --- Section: Startup ---
        gen_content_layout.addWidget(create_section_header("Startup Configuration"))
        startup_box = QFrame()
        startup_box.setStyleSheet(
            "QFrame { background: rgba(255, 255, 255, 0.03); border-radius: 10px; border: 1px solid rgba(255, 255, 255, 0.05); }"
        )
        startup_layout = QVBoxLayout(startup_box)
        startup_layout.addWidget(
            QLabel(
                "Default Startup Preset:",
                styleSheet="color: #AAAAAA; font-size: 12px; font-weight: 500;",
            )
        )
        self.startup_preset_combo = QComboBox()
        self.startup_preset_combo.setFixedHeight(32)
        self.startup_preset_combo.setStyleSheet(
            "\n            QComboBox { background-color: #1A1A1E; color: white; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 4px 10px; font-family: 'Segoe UI Variable'; }\n            QComboBox::drop-down { border: none; }\n        "
        )
        self.startup_preset_combo.currentTextChanged.connect(self.save_settings)
        startup_layout.addWidget(self.startup_preset_combo)
        gen_content_layout.addWidget(startup_box)

        # --- Section: Maintenance ---
        gen_content_layout.addWidget(create_section_header("Maintenance & Tools"))
        maintenance_grid = QGridLayout()
        maintenance_grid.setSpacing(10)

        self.btn_view_logs = GlowButton("View Logs")
        self.btn_view_logs.setFixedHeight(35)
        self.btn_view_logs.setStyleSheet(
            "QPushButton { background-color: rgba(0, 229, 255, 0.06); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.2); border-radius: 6px; font-weight: 600; } QPushButton:hover { background-color: rgba(0, 229, 255, 0.12); }"
        )
        self.btn_view_logs.clicked.connect(self.show_logs)
        maintenance_grid.addWidget(self.btn_view_logs, 0, 0)

        self.btn_clear_update_cache = GlowButton("Update Cache")
        self.btn_clear_update_cache.setFixedHeight(35)
        self.btn_clear_update_cache.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.03); color: #AAAAAA; border: 1px solid rgba(255,255,255,0.08); border-radius: 6px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.08); }"
        )
        self.btn_clear_update_cache.clicked.connect(self.clear_update_cache)
        maintenance_grid.addWidget(self.btn_clear_update_cache, 0, 1)

        self.btn_clear_cache = GlowButton("Reset Application")
        self.btn_clear_cache.setFixedHeight(40)
        self.btn_clear_cache.setStyleSheet(
            "QPushButton { background-color: rgba(255, 85, 85, 0.1); color: #FF5555; border: 1px solid rgba(255, 85, 85, 0.3); border-radius: 6px; font-size: 13px; font-weight: bold; } QPushButton:hover { background-color: #FF5555; color: white; }"
        )
        self.btn_clear_cache.clicked.connect(self.clear_cache)
        maintenance_grid.addWidget(self.btn_clear_cache, 1, 0, 1, 2)

        gen_content_layout.addLayout(maintenance_grid)

        version_label = QLabel(f"Version: {CURRENT_VERSION}  •  Model: {self.laptop_model}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet(
            'color: #444444; margin-top: 20px; font-size: 10px; font-weight: bold; font-family: "Segoe UI Variable";'
        )
        gen_content_layout.addWidget(version_label)

        gen_content_layout.addStretch()
        gen_scroll.setWidget(gen_content)
        general_layout.addWidget(gen_scroll)
        self.settings_tabs.addTab(general_tab, "General")
        # --- Hotkeys Tab ---
        hotkeys_tab = QWidget()
        hotkeys_tab_layout = QVBoxLayout(hotkeys_tab)
        hotkeys_tab_layout.setContentsMargins(0, 0, 0, 0)
        hotkeys_tab_layout.setSpacing(0)

        hotkeys_scroll = QScrollArea()
        hotkeys_scroll.setWidgetResizable(True)
        hotkeys_scroll.setFrameShape(QFrame.NoFrame)
        hotkeys_scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        hotkeys_content = QWidget()
        hotkeys_layout = QVBoxLayout(hotkeys_content)
        hotkeys_layout.setContentsMargins(10, 10, 10, 10)
        hotkeys_layout.setSpacing(10)

        self.hotkeys_filter_input = QLineEdit()
        self.hotkeys_filter_input.setPlaceholderText("Search hotkeys...")
        self.hotkeys_filter_input.setClearButtonEnabled(True)
        self.hotkeys_filter_input.setFixedHeight(32)
        self.hotkeys_filter_input.setStyleSheet(
            "QLineEdit { background: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 6px; padding: 4px 10px; }"
        )
        self.hotkeys_filter_input.textChanged.connect(self.apply_hotkeys_filter)
        hotkeys_layout.addWidget(self.hotkeys_filter_input)

        self.hotkeys_list = QListWidget()
        self.hotkeys_list.setMinimumHeight(130)
        self.hotkeys_list.setMaximumHeight(300)
        self.hotkeys_list.setSpacing(2)
        self.hotkeys_list.setStyleSheet("""
            QListWidget {
                background: rgba(0, 0, 0, 0.25);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
            }
            QListWidget::item {
                background: rgba(255, 255, 255, 0.03);
                border-radius: 4px;
                padding: 10px;
                color: #FFFFFF;
                margin: 2px 5px;
            }
            QListWidget::item:selected {
                background: rgba(0, 229, 255, 0.15);
                color: #00E5FF;
                border: 1px solid rgba(0, 229, 255, 0.3);
            }
        """)
        self.hotkeys_list.itemDoubleClicked.connect(self.on_hotkey_item_activated)
        hotkeys_layout.addWidget(self.hotkeys_list)

        plus_icon_path = os.path.join(
            os.path.dirname(__file__), "assets", "plus.svg"
        ).replace("\\", "/")
        minus_icon_path = os.path.join(
            os.path.dirname(__file__), "assets", "minus.svg"
        ).replace("\\", "/")

        hotkey_btns_row = QHBoxLayout()
        hotkey_btns_row.setSpacing(10)

        self.btn_add_hotkey = GlowButton(" Add Hotkey")
        self.btn_add_hotkey.setIcon(QIcon(plus_icon_path))
        self.btn_add_hotkey.setFixedHeight(35)
        self.btn_add_hotkey.clicked.connect(self.add_hotkey)
        self.btn_add_hotkey.setStyleSheet(
            "QPushButton { background-color: rgba(0, 229, 255, 0.1); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.3); border-radius: 6px; font-weight: bold; }"
        )

        self.btn_remove_hotkey = GlowButton(" Remove Selected")
        self.btn_remove_hotkey.setIcon(QIcon(minus_icon_path))
        self.btn_remove_hotkey.setFixedHeight(35)
        self.btn_remove_hotkey.clicked.connect(self.remove_hotkey)
        self.btn_remove_hotkey.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.04); color: #AAAAAA; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; }"
        )

        self.btn_clear_hotkeys = GlowButton(" Clear All")
        self.btn_clear_hotkeys.setFixedHeight(35)
        self.btn_clear_hotkeys.clicked.connect(self.clear_all_hotkeys)
        self.btn_clear_hotkeys.setStyleSheet(
            "QPushButton { background-color: rgba(255, 85, 85, 0.08); color: #FF7777; border: 1px solid rgba(255, 85, 85, 0.25); border-radius: 6px; } QPushButton:hover { background-color: rgba(255, 85, 85, 0.16); color: #FFAAAA; }"
        )

        hotkey_btns_row.addWidget(self.btn_add_hotkey)
        hotkey_btns_row.addWidget(self.btn_remove_hotkey)
        hotkey_btns_row.addWidget(self.btn_clear_hotkeys)
        hotkeys_layout.addLayout(hotkey_btns_row)

        hotkey_io_row = QHBoxLayout()
        hotkey_io_row.setSpacing(10)

        self.btn_export_hotkeys = GlowButton("Export Hotkeys")
        self.btn_export_hotkeys.setFixedHeight(32)
        self.btn_export_hotkeys.clicked.connect(self.export_hotkeys)
        self.btn_export_hotkeys.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.04); color: #AAAAAA; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.08); color: #E2E2E2; }"
        )

        self.btn_import_hotkeys = GlowButton("Import Hotkeys")
        self.btn_import_hotkeys.setFixedHeight(32)
        self.btn_import_hotkeys.clicked.connect(self.import_hotkeys)
        self.btn_import_hotkeys.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.04); color: #AAAAAA; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; } QPushButton:hover { background-color: rgba(255, 255, 255, 0.08); color: #E2E2E2; }"
        )

        hotkey_io_row.addWidget(self.btn_export_hotkeys)
        hotkey_io_row.addWidget(self.btn_import_hotkeys)
        hotkeys_layout.addLayout(hotkey_io_row)

        hotkeys_layout.addStretch()
        if not HAS_PYNPUT:
            hotkeys_layout.addWidget(
                QLabel(
                    "⚠️ 'pynput' not installed. Hotkeys will not work globally.",
                    styleSheet="color: #FF5555; font-size: 12px; margin-top: 10px;",
                )
            )
        else:
            hotkeys_layout.addWidget(
                QLabel(
                    "ⓘ Hotkeys work globally, even when minimized.",
                    styleSheet="color: #AAAAAA; font-size: 11px; margin-top: 10px;",
                )
            )

        hotkeys_scroll.setWidget(hotkeys_content)
        hotkeys_tab_layout.addWidget(hotkeys_scroll)

        self.update_hotkeys_list_height()

        self.settings_tabs.addTab(hotkeys_tab, "Hotkeys")
        settings_layout.addWidget(self.settings_tabs)
        self.stack.addWidget(self.settings_view)

        # --- Pomodoro Fullscreen View ---
        QApplication.processEvents()
        self.pomo_fullscreen_view = QWidget()
        self.pomo_fullscreen_view.setStyleSheet("background-color: black;")
        pomo_fs_layout = QVBoxLayout(self.pomo_fullscreen_view)
        pomo_fs_layout.setAlignment(Qt.AlignCenter)

        self.pomo_fs_label = QLabel("00:00:00")
        self.pomo_fs_label.setStyleSheet(
            "color: white; font-size: 150px; font-weight: bold; font-family: 'Segoe UI Variable';"
        )
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
        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.restore_app)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.tray_quit)
        tray_menu.addAction(restore_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(6)
        title_layout.addStretch()

        logo_label = QLabel()
        logo_pixmap = QIcon(self.icon_path).pixmap(32, 32)
        logo_label.setPixmap(logo_pixmap)
        title_layout.addWidget(logo_label)

        title_label = QLabel("4 ZONE RGB TOOLKIT")
        title_font = QFont("Segoe UI Variable", 24, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setStyleSheet(
            "color: #00E5FF; margin-bottom: 2px; letter-spacing: 2px;"
        )
        title_layout.addWidget(title_label)
        
        title_layout.addStretch()
        main_layout.addWidget(title_container)
        subtitle = QLabel("Hardware & Software RGB Customization")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            "color: #666666; margin-bottom: 12px; font-size: 12px; font-weight: 500; font-family: 'Segoe UI Variable', sans-serif;"
        )
        main_layout.addWidget(subtitle)
        split_layout = QHBoxLayout()
        split_layout.setSpacing(15)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(5)
        # Lift the Main Controls section up by an additional 25px total.
        left_layout.insertSpacing(0, -25)
        right_panel = QWidget()
        right_panel.setMaximumWidth(340)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)
        split_layout.addLayout(left_layout, stretch=3)
        split_layout.addWidget(right_panel, stretch=1)
        main_layout.addLayout(split_layout)
        controls_title = QLabel("Main Controls")
        controls_title.setStyleSheet(
            'color: #00E5FF; font-weight: bold; font-family: "Segoe UI Variable", "Segoe UI", sans-serif; font-size: 16px; margin-left: 12px; margin-top: -2px;'
        )
        left_layout.addWidget(controls_title)

        controls_group = QFrame()
        controls_group.setObjectName("MainControlsFrame")
        controls_group.setStyleSheet(
            "QFrame#MainControlsFrame { border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; background-color: rgba(255, 255, 255, 0.02); }"
        )
        controls_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.controls_slot = QWidget()
        self.controls_slot.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.controls_slot.setMinimumHeight(185)
        controls_slot_layout = QVBoxLayout(self.controls_slot)
        controls_slot_layout.setContentsMargins(0, 0, 0, 0)
        controls_slot_layout.setSpacing(0)
        controls_slot_layout.addWidget(controls_group)
        controls_slot_layout.addStretch(1)
        controls_layout = QGridLayout(controls_group)
        controls_layout.setHorizontalSpacing(8)
        controls_layout.setVerticalSpacing(12)
        controls_layout.setContentsMargins(14, 12, 14, 10)
        controls_layout.setColumnStretch(2, 1)  # Make slider column stretch
        controls_layout.setAlignment(Qt.AlignTop)

        def add_control_row(row, label, minus_btn, slider, plus_btn):
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            controls_layout.addWidget(label, row, 0, Qt.AlignVCenter | Qt.AlignLeft)
            controls_layout.addWidget(minus_btn, row, 1, Qt.AlignVCenter)
            controls_layout.addWidget(slider, row, 2, Qt.AlignVCenter)
            controls_layout.addWidget(plus_btn, row, 3, Qt.AlignVCenter)

        icon_css = "QPushButton { background: transparent; border: none; border-radius: 4px; } QPushButton:hover { background: rgba(255, 255, 255, 0.1); }"

        # Row 0: Brightness
        self.bright_label = QLabel("Brightness: 100%")
        self.btn_bright_minus = QPushButton()
        self.btn_bright_minus.setIcon(QIcon(minus_icon_path))
        self.btn_bright_minus.setFixedSize(24, 24)
        self.btn_bright_minus.setStyleSheet(icon_css)
        self.btn_bright_minus.setCursor(Qt.PointingHandCursor)
        self.btn_bright_minus.clicked.connect(
            lambda: self.bright_slider.set_animated_value(
                max(0, self.bright_slider.value() - 5)
            )
        )
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
        self.btn_bright_plus.clicked.connect(
            lambda: self.bright_slider.set_animated_value(
                min(100, self.bright_slider.value() + 5)
            )
        )
        add_control_row(
            0,
            self.bright_label,
            self.btn_bright_minus,
            self.bright_slider,
            self.btn_bright_plus,
        )

        self.bright_widgets = [
            self.bright_label,
            self.btn_bright_minus,
            self.bright_slider,
            self.btn_bright_plus,
        ]

        # Row 1: Vibrance
        self.vibrance_label = QLabel("Vibrance: 1.5x")
        self.btn_vib_minus = QPushButton()
        self.btn_vib_minus.setIcon(QIcon(minus_icon_path))
        self.btn_vib_minus.setFixedSize(24, 24)
        self.btn_vib_minus.setStyleSheet(icon_css)
        self.btn_vib_minus.setCursor(Qt.PointingHandCursor)
        self.btn_vib_minus.clicked.connect(
            lambda: self.vibrance_slider.set_animated_value(
                max(5, self.vibrance_slider.value() - 5)
            )
        )
        self.vibrance_slider = AnimatedSlider(Qt.Horizontal)
        self.vibrance_slider.setRange(5, 30)  # 0.5x to 3.0x max vibrance
        self.vibrance_slider.setValue(15)
        self.vibrance_slider.setTickPosition(QSlider.TicksBelow)
        self.vibrance_slider.setTickInterval(5)
        self.vibrance_slider.valueChanged.connect(self.on_vibrance_changed)
        self.btn_vib_plus = QPushButton()
        self.btn_vib_plus.setIcon(QIcon(plus_icon_path))
        self.btn_vib_plus.setFixedSize(24, 24)
        self.btn_vib_plus.setStyleSheet(icon_css)
        self.btn_vib_plus.setCursor(Qt.PointingHandCursor)
        self.btn_vib_plus.clicked.connect(
            lambda: self.vibrance_slider.set_animated_value(
                min(30, self.vibrance_slider.value() + 5)
            )
        )
        add_control_row(
            1,
            self.vibrance_label,
            self.btn_vib_minus,
            self.vibrance_slider,
            self.btn_vib_plus,
        )

        self.vibrance_widgets = [
            self.vibrance_label,
            self.btn_vib_minus,
            self.vibrance_slider,
            self.btn_vib_plus,
        ]
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

        self.pomo_hours = QSpinBox()
        self.pomo_hours.setRange(0, 99)
        self.pomo_hours.setSuffix("h")
        self.pomo_hours.setStyleSheet(spin_style)

        self.pomo_minutes = QSpinBox()
        self.pomo_minutes.setRange(0, 59)
        self.pomo_minutes.setValue(25)
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
        self.speed_label = QLabel("Animation Speed: 20%")
        self.btn_speed_minus = QPushButton()
        self.btn_speed_minus.setIcon(QIcon(minus_icon_path))
        self.btn_speed_minus.setFixedSize(24, 24)
        self.btn_speed_minus.setStyleSheet(icon_css)
        self.btn_speed_minus.setCursor(Qt.PointingHandCursor)
        self.btn_speed_minus.clicked.connect(
            lambda: self.speed_slider.set_animated_value(
                max(1, self.speed_slider.value() - 5)
            )
        )
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
        self.btn_speed_plus.clicked.connect(
            lambda: self.speed_slider.set_animated_value(
                min(100, self.speed_slider.value() + 5)
            )
        )
        add_control_row(
            3,
            self.speed_label,
            self.btn_speed_minus,
            self.speed_slider,
            self.btn_speed_plus,
        )

        self.speed_widgets = [
            self.speed_label,
            self.btn_speed_minus,
            self.speed_slider,
            self.btn_speed_plus,
        ]

        # Row 4: Storm Intensity (Lightning)
        self.storm_label = QLabel("Storm Intensity: 50%")
        self.btn_storm_minus = QPushButton()
        self.btn_storm_minus.setIcon(QIcon(minus_icon_path))
        self.btn_storm_minus.setFixedSize(24, 24)
        self.btn_storm_minus.setStyleSheet(icon_css)
        self.btn_storm_minus.setCursor(Qt.PointingHandCursor)
        self.btn_storm_minus.clicked.connect(
            lambda: self.storm_slider.set_animated_value(
                max(1, self.storm_slider.value() - 5)
            )
        )
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
        self.btn_storm_plus.clicked.connect(
            lambda: self.storm_slider.set_animated_value(
                min(100, self.storm_slider.value() + 5)
            )
        )
        add_control_row(
            4,
            self.storm_label,
            self.btn_storm_minus,
            self.storm_slider,
            self.btn_storm_plus,
        )

        self.storm_widgets = [
            self.storm_label,
            self.btn_storm_minus,
            self.storm_slider,
            self.btn_storm_plus,
        ]
        for w in self.storm_widgets:
            w.hide()


        self.ambient_fps_layout = QHBoxLayout()
        self.ambient_fps_label = QLabel("Ambient FPS: 30")
        self.btn_ambient_fps_minus = QPushButton()
        self.btn_ambient_fps_minus.setIcon(QIcon(minus_icon_path))
        self.btn_ambient_fps_minus.setFixedSize(24, 24)
        self.btn_ambient_fps_minus.setStyleSheet(icon_css)
        self.btn_ambient_fps_minus.setCursor(Qt.PointingHandCursor)
        self.btn_ambient_fps_minus.clicked.connect(
            lambda: self.ambient_fps_slider.set_animated_value(
                max(5, self.ambient_fps_slider.value() - 5)
            )
        )
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
        self.btn_ambient_fps_plus.clicked.connect(
            lambda: self.ambient_fps_slider.set_animated_value(
                min(60, self.ambient_fps_slider.value() + 5)
            )
        )
        add_control_row(
            5,
            self.ambient_fps_label,
            self.btn_ambient_fps_minus,
            self.ambient_fps_slider,
            self.btn_ambient_fps_plus,
        )

        self.ambient_fps_widgets = [
            self.ambient_fps_label,
            self.btn_ambient_fps_minus,
            self.ambient_fps_slider,
            self.btn_ambient_fps_plus,
        ]
        for w in self.ambient_fps_widgets:
            w.hide()

        # Row 6: Flicker Reduction (Audio Visualizer)
        self.flicker_label = QLabel("Flicker Reduction: 0")
        self.btn_flicker_minus = QPushButton()
        self.btn_flicker_minus.setIcon(QIcon(minus_icon_path))
        self.btn_flicker_minus.setFixedSize(24, 24)
        self.btn_flicker_minus.setStyleSheet(icon_css)
        self.btn_flicker_minus.setCursor(Qt.PointingHandCursor)
        self.btn_flicker_minus.clicked.connect(
            lambda: self.flicker_slider.set_animated_value(
                max(0, self.flicker_slider.value() - 5)
            )
        )
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
        self.btn_flicker_plus.clicked.connect(
            lambda: self.flicker_slider.set_animated_value(
                min(50, self.flicker_slider.value() + 5)
            )
        )
        add_control_row(
            6,
            self.flicker_label,
            self.btn_flicker_minus,
            self.flicker_slider,
            self.btn_flicker_plus,
        )

        self.flicker_widgets = [
            self.flicker_label,
            self.btn_flicker_minus,
            self.flicker_slider,
            self.btn_flicker_plus,
        ]
        for w in self.flicker_widgets:
            w.hide()

        self.control_value_labels = [
            self.bright_label,
            self.vibrance_label,
            self.speed_label,
            self.storm_label,
            self.ambient_fps_label,
            self.flicker_label,
        ]
        self.sync_control_label_widths()

        # Wave direction toggle (for hardware Wave mode)
        self.wave_dir_widget = QWidget()
        wave_dir_layout = QHBoxLayout(self.wave_dir_widget)
        wave_dir_layout.setContentsMargins(0, 0, 0, 0)
        wave_dir_layout.setSpacing(6)
        self.wave_dir_left_btn = QPushButton("Left")
        self.wave_dir_right_btn = QPushButton("Right")
        btn_style = (
            "QPushButton { padding: 6px 10px; min-width: 48px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; }"
            "QPushButton:hover { background-color: rgba(0, 229, 255, 0.1); }"
            "QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }"
        )
        for btn in (self.wave_dir_left_btn, self.wave_dir_right_btn):
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(btn_style)
        self.wave_dir_left_btn.setChecked(True)
        self.wave_dir_left_btn.clicked.connect(lambda: self.set_wave_direction("left"))
        self.wave_dir_right_btn.clicked.connect(
            lambda: self.set_wave_direction("right")
        )
        wave_dir_layout.addWidget(self.wave_dir_left_btn)
        wave_dir_layout.addWidget(self.wave_dir_right_btn)
        wave_dir_layout.addStretch()
        self.wave_dir_widget.hide()

        # Smooth Wave direction toggle (software Smooth Wave)
        self.smooth_wave_dir_widget = QWidget()
        smooth_wave_dir_layout = QHBoxLayout(self.smooth_wave_dir_widget)
        smooth_wave_dir_layout.setContentsMargins(0, 0, 0, 0)
        smooth_wave_dir_layout.setSpacing(6)
        self.smooth_wave_dir_left_btn = QPushButton("Left")
        self.smooth_wave_dir_right_btn = QPushButton("Right")
        sw_btn_style = (
            "QPushButton { padding: 6px 10px; min-width: 48px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; }"
            "QPushButton:hover { background-color: rgba(0, 229, 255, 0.1); }"
            "QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }"
        )
        for btn in (self.smooth_wave_dir_left_btn, self.smooth_wave_dir_right_btn):
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(sw_btn_style)
        self.smooth_wave_dir_left_btn.setChecked(True)
        self.smooth_wave_dir_left_btn.clicked.connect(
            lambda: self.set_smooth_wave_direction("left")
        )
        self.smooth_wave_dir_right_btn.clicked.connect(
            lambda: self.set_smooth_wave_direction("right")
        )
        smooth_wave_dir_layout.addWidget(self.smooth_wave_dir_left_btn)
        smooth_wave_dir_layout.addWidget(self.smooth_wave_dir_right_btn)
        smooth_wave_dir_layout.addStretch()
        self.smooth_wave_dir_widget.hide()

        # Scanner rainbow toggle (placed bottom-left for Scanner mode)
        self.scanner_rainbow_cb = QPushButton("Rainbow Sweep")
        self.scanner_rainbow_cb.setCheckable(True)
        self.scanner_rainbow_cb.setCursor(Qt.PointingHandCursor)
        self.scanner_rainbow_cb.setStyleSheet(
            "QPushButton { padding: 6px 12px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; font-weight: 700; }"
            "QPushButton:hover { background-color: rgba(0,229,255,0.12); }"
            "QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; }"
        )
        self.scanner_rainbow_cb.clicked.connect(self.on_scanner_rainbow_toggled)
        self.scanner_rainbow_cb.hide()

        self.reactive_rainbow_cb = QPushButton("Rainbow Reactive")
        self.reactive_rainbow_cb.setCheckable(True)
        self.reactive_rainbow_cb.setCursor(Qt.PointingHandCursor)
        self.reactive_rainbow_cb.setStyleSheet(
            "QPushButton { padding: 6px 12px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.12); border-radius: 6px; font-weight: 700; }"
            "QPushButton:hover { background-color: rgba(0,229,255,0.12); }"
            "QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; }"
        )
        self.reactive_rainbow_cb.clicked.connect(self.on_reactive_rainbow_toggled)
        self.reactive_rainbow_cb.hide()

        # Fill mode toggle (bottom-right for Smooth Wave)
        self.wave_fill_cb = QPushButton("Fill Mode")
        self.wave_fill_cb.setCheckable(True)
        self.wave_fill_cb.setCursor(Qt.PointingHandCursor)
        self.wave_fill_cb.setStyleSheet(
            "QPushButton { padding: 6px 12px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; font-weight: 600; }"
            "QPushButton:hover { background-color: rgba(0,229,255,0.08); }"
            "QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; font-weight: 700; }"
        )
        self.wave_fill_cb.clicked.connect(self.on_wave_fill_toggled)
        self.wave_fill_cb.hide()

        self.smooth_wave_palette_combo = QComboBox()
        self.smooth_wave_palette_combo.addItems(["RGBW", "Pastel", "Custom 4-Color"])
        self.smooth_wave_palette_combo.setCurrentText("RGBW")
        self.smooth_wave_palette_combo.setFixedWidth(150)
        self.smooth_wave_palette_combo.setCursor(Qt.PointingHandCursor)
        self.smooth_wave_palette_combo.setStyleSheet(
            "QComboBox { background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; padding: 6px 8px; font-weight: 600; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background-color: #1A1A1E; color: #E2E2E2; selection-background-color: #00E5FF; selection-color: #0E0E12; }"
        )
        self.smooth_wave_palette_combo.currentTextChanged.connect(
            self.on_smooth_wave_palette_changed
        )
        self.smooth_wave_palette_combo.hide()

        self.reactive_style_combo = QComboBox()
        self.reactive_style_combo.addItems(["Fade", "Ripple"])
        self.reactive_style_combo.setCurrentText("Fade")
        self.reactive_style_combo.setFixedWidth(150)
        self.reactive_style_combo.setCursor(Qt.PointingHandCursor)
        self.reactive_style_combo.setStyleSheet(
            "QComboBox { background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; padding: 6px 8px; font-weight: 600; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background-color: #1A1A1E; color: #E2E2E2; selection-background-color: #00E5FF; selection-color: #0E0E12; }"
        )
        self.reactive_style_combo.currentTextChanged.connect(
            self.on_reactive_style_changed
        )
        self.reactive_style_combo.hide()

        # Bottom controls row: wave dirs left, fill toggle right
        bottom_row = QWidget()
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)
        bottom_layout.addWidget(self.scanner_rainbow_cb)
        bottom_layout.addWidget(self.reactive_rainbow_cb)
        bottom_layout.addWidget(self.wave_dir_widget)
        bottom_layout.addWidget(self.smooth_wave_dir_widget)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.smooth_wave_palette_combo)
        bottom_layout.addWidget(self.reactive_style_combo)
        bottom_layout.addWidget(self.wave_fill_cb)
        controls_layout.addWidget(bottom_row, 7, 0, 1, 4, Qt.AlignVCenter)

        # Valorant Spike Timer specific controls
        self.spike_timer_widget = QWidget()
        spike_layout = QVBoxLayout(self.spike_timer_widget)
        spike_layout.setContentsMargins(0, 10, 0, 0)
        
        self.spike_info_label = QLabel("The app is automatically scanning the top center of your screen for the Spike icon.\nPlay in Borderless Windowed mode for screen capture to work.")
        self.spike_info_label.setWordWrap(True)
        self.spike_info_label.setStyleSheet("color: #E2E2E2; margin-bottom: 5px;")
        
        spike_controls_layout = QHBoxLayout()
        self.spike_res_combo = QComboBox()
        self.spike_res_combo.addItems(["1920x1080 (16:9)", "2560x1440 (16:9)", "3840x2160 (16:9)"])
        self.spike_res_combo.setStyleSheet(
            "QComboBox { background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.1); border-radius: 4px; padding: 6px 8px; font-weight: 600; }"
            "QComboBox::drop-down { border: none; width: 20px; }"
            "QComboBox QAbstractItemView { background-color: #1A1A1E; color: #E2E2E2; selection-background-color: #00E5FF; selection-color: #0E0E12; }"
        )
        
        self.btn_spike_calibrate = QPushButton("Calibrate UI Red")
        self.btn_spike_calibrate.setCursor(Qt.PointingHandCursor)
        self.btn_spike_calibrate.setStyleSheet("QPushButton { padding: 6px 12px; background-color: #E03C31; color: white; border-radius: 4px; font-weight: bold; } QPushButton:hover { background-color: #FF4A3D; }")
        self.btn_spike_calibrate.clicked.connect(self.calibrate_spike_red)
        self.btn_spike_calibrate.setToolTip("Go to a custom game, plant the spike, and click this to learn the exact Red color of the Spike UI.")
        
        self.btn_spike_test = QPushButton("Test 45s Detonation")
        self.btn_spike_test.setCursor(Qt.PointingHandCursor)
        self.btn_spike_test.setStyleSheet("QPushButton { padding: 6px 12px; background-color: #1A1A1E; color: #E2E2E2; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; } QPushButton:hover { background-color: rgba(255,255,255,0.1); }")
        self.btn_spike_test.clicked.connect(self.test_spike_timer)
        
        spike_controls_layout.addWidget(self.spike_res_combo)
        spike_controls_layout.addWidget(self.btn_spike_calibrate)
        spike_controls_layout.addWidget(self.btn_spike_test)
        spike_controls_layout.addStretch()
        
        spike_layout.addWidget(self.spike_info_label)
        spike_layout.addLayout(spike_controls_layout)
        self.spike_timer_widget.hide()

        left_layout.addWidget(self.controls_slot)
        left_layout.addSpacing(-52)

        self.colors_group = QGroupBox("Zone Colors")
        self.colors_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.colors_group.setStyleSheet(
            "QGroupBox { color: #00E5FF; font-size: 16px; font-weight: bold; padding-top: 22px; }"
        )
        colors_layout = QGridLayout(self.colors_group)
        colors_layout.setSpacing(8)
        colors_layout.setContentsMargins(10, 4, 10, 10)

        self.zone_colors = [
            [255, 252, 247],
            [255, 252, 247],
            [255, 252, 247],
            [255, 252, 247],
        ]
        self.color_buttons = []
        for i in range(4):
            btn = QPushButton()
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(100, 40)
            self.update_button_color(btn, self.zone_colors[i])
            btn.clicked.connect(lambda *args, idx=i: self.pick_color(idx))
            self.color_buttons.append(btn)
            colors_layout.addWidget(btn, 0, i)
        self.global_color = [255, 252, 247]
        self.global_color_btn = QPushButton()
        self.global_color_btn.setCursor(Qt.PointingHandCursor)
        self.global_color_btn.setFixedHeight(25)
        self.update_button_color(self.global_color_btn, self.global_color)
        self.global_color_btn.clicked.connect(self.pick_global_color)
        colors_layout.addWidget(self.global_color_btn, 1, 0, 1, 4)

        left_layout.addWidget(self.colors_group)

        self.preview_panel = QFrame()
        self.preview_panel.setObjectName("EmbeddedPreviewFrame")
        self.preview_panel.setStyleSheet(
            "QFrame#EmbeddedPreviewFrame { border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px; background-color: rgba(255, 255, 255, 0.02); }"
        )
        self.preview_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_panel_layout = QVBoxLayout(self.preview_panel)
        preview_panel_layout.setContentsMargins(12, 10, 12, 12)
        preview_panel_layout.setSpacing(8)

        self.preview_header_widget = QWidget(self.preview_panel)
        preview_header_layout = QHBoxLayout(self.preview_header_widget)
        preview_header_layout.setContentsMargins(0, 0, 0, 0)
        preview_header_layout.setSpacing(8)
        preview_title = QLabel("Live Preview")
        preview_title.setStyleSheet(
            "color: #00E5FF; font-size: 13px; font-weight: bold;"
        )
        self.btn_preview_toggle_small = QPushButton("On")
        self.btn_preview_toggle_small.setCheckable(True)
        self.btn_preview_toggle_small.setChecked(True)
        self.btn_preview_toggle_small.setCursor(Qt.PointingHandCursor)
        self.btn_preview_toggle_small.setFixedSize(44, 22)
        self.btn_preview_toggle_small.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.04); color: #8F97A3; border: 1px solid rgba(255,255,255,0.10); border-radius: 11px; font-size: 10px; font-weight: 700; padding: 0 6px; }"
            "QPushButton:hover { background-color: rgba(0, 229, 255, 0.08); color: #E2E2E2; }"
            "QPushButton:checked { background-color: #00E5FF; color: #0E0E12; border: 1px solid #00E5FF; }"
        )
        self.btn_preview_toggle_small.setToolTip("Toggle live preview")
        self.btn_preview_toggle_small.clicked.connect(self.set_preview_visible)
        preview_header_layout.addWidget(preview_title)
        preview_header_layout.addStretch()
        preview_header_layout.addWidget(self.btn_preview_toggle_small)
        preview_panel_layout.addWidget(self.preview_header_widget)

        self.embedded_preview = KeyboardPreviewWidget(self, self.preview_panel)
        self.embedded_preview.setMinimumHeight(0)
        self.embedded_preview.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        preview_panel_layout.addWidget(self.embedded_preview, 1)
        self.preview_opacity_effect = QGraphicsOpacityEffect(self.embedded_preview)
        self.embedded_preview.setGraphicsEffect(self.preview_opacity_effect)
        self.preview_opacity_effect.setOpacity(1.0)
        self.preview_anim = QVariantAnimation(self)
        self.preview_anim.setDuration(220)
        self.preview_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.preview_anim.valueChanged.connect(self.on_preview_anim_value)
        self.preview_anim.finished.connect(self.on_preview_anim_finished)
        self.preview_anim_start_height = 0
        self.preview_enabled = True
        self.preview_user_enabled = True
        self.preview_forced_by_mode = False

        left_layout.addWidget(self.spike_timer_widget)
        left_layout.addWidget(self.preview_panel)
        from core.config import SOFTWARE_MODES, HARDWARE_MODES, DEFAULT_CONTROL_SETTINGS, DEFAULT_MODE_SETTINGS
        self.SOFTWARE_MODES = list(SOFTWARE_MODES)
        self.HARDWARE_MODES = HARDWARE_MODES
        self.default_control_settings = dict(DEFAULT_CONTROL_SETTINGS)
        self.DEFAULT_MODE_SETTINGS = DEFAULT_MODE_SETTINGS
        self.mode_settings = self.build_default_mode_settings()
        self.wave_direction = "left"
        self.smooth_wave_direction = "left"
        self.mode_list = QListWidget()
        self.mode_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.mode_list.verticalScrollBar().setSingleStep(15)
        self.mode_list.addItems(self.HARDWARE_MODES + self.SOFTWARE_MODES)
        self.mode_list.setCurrentRow(0)
        self.mode_list.currentTextChanged.connect(self.on_mode_changed)
        right_layout.addWidget(self.mode_list)

        self.mode_description_label = QLabel(
            "Select an effect to see a quick description."
        )
        self.mode_description_label.setWordWrap(True)
        self.mode_description_label.setStyleSheet(
            "color: #8F97A3; font-size: 11px; line-height: 1.4; padding: 2px 2px 0 2px;"
        )
        self.mode_description_label.setMinimumHeight(48)
        self.mode_description_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        right_layout.addWidget(self.mode_description_label)



        self.presets = {}
        preset_group = QGroupBox("Custom Presets")
        self.preset_group = preset_group
        self.preset_layout = QGridLayout(preset_group)
        self.preset_layout.setContentsMargins(10, 8, 10, 8)
        self.preset_layout.setHorizontalSpacing(8)
        self.preset_layout.setVerticalSpacing(6)
        self.preset_combo = QComboBox()
        self.preset_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.preset_combo.setStyleSheet(
            "\n            QComboBox { background-color: #1A1A1E; color: white; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 6px; }\n            QComboBox::drop-down { border: none; }\n        "
        )
        self.preset_combo.activated.connect(self.apply_preset_from_ui)
        self.btn_save_preset = QPushButton()
        self.btn_save_preset.setIcon(QIcon(plus_icon_path))
        self.btn_save_preset.setFixedSize(30, 30)
        self.btn_save_preset.setCursor(Qt.PointingHandCursor)
        self.btn_save_preset.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.05); border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); } QPushButton:hover { background-color: rgba(0, 229, 255, 0.2); border: 1px solid #00E5FF; }"
        )
        self.btn_save_preset.clicked.connect(self.save_new_preset)
        self.btn_delete_preset = QPushButton()
        self.btn_delete_preset.setIcon(QIcon(minus_icon_path))
        self.btn_delete_preset.setFixedSize(30, 30)
        self.btn_delete_preset.setCursor(Qt.PointingHandCursor)
        self.btn_delete_preset.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.05); border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); } QPushButton:hover { background-color: rgba(255, 85, 85, 0.2); border: 1px solid #FF5555; }"
        )
        self.btn_delete_preset.clicked.connect(self.delete_preset)
        tool_btn_css = "QPushButton { background-color: rgba(255, 255, 255, 0.05); color: #E2E2E2; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); padding: 0 10px; font-weight: 600; } QPushButton:hover { background-color: rgba(0, 229, 255, 0.12); border: 1px solid #00E5FF; }"
        self.btn_import_presets = QPushButton("Import")
        self.btn_import_presets.setFixedHeight(30)
        self.btn_import_presets.setCursor(Qt.PointingHandCursor)
        self.btn_import_presets.setStyleSheet(tool_btn_css)
        self.btn_import_presets.clicked.connect(self.import_presets)
        self.btn_export_presets = QPushButton("Export")
        self.btn_export_presets.setFixedHeight(30)
        self.btn_export_presets.setCursor(Qt.PointingHandCursor)
        self.btn_export_presets.setStyleSheet(tool_btn_css)
        self.btn_export_presets.clicked.connect(self.export_presets)
        self.update_preset_toolbar_layout(force=True)

        self.btn_reset_mode = QPushButton("Reset This Mode")
        self.btn_reset_mode.setCursor(Qt.PointingHandCursor)
        self.btn_reset_mode.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.04); color: #E2E2E2; border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 8px 12px; font-weight: 700; }"
            "QPushButton:hover { background-color: rgba(255, 170, 0, 0.10); border: 1px solid rgba(255, 170, 0, 0.45); color: #FFD27A; }"
        )
        self.btn_reset_mode.clicked.connect(self.reset_current_mode_settings)
        right_layout.addWidget(self.btn_reset_mode)

        self.btn_effect_studio = QPushButton("Effect Builder (Beta)")
        self.btn_effect_studio.setCursor(Qt.PointingHandCursor)
        self.btn_effect_studio.setStyleSheet(
            "QPushButton { background-color: rgba(0, 229, 255, 0.12); color: #00F2FF; border: 1px solid #00F2FF; border-radius: 8px; padding: 8px 12px; font-weight: 700; }"
            "QPushButton:hover { background-color: #00E5FF; color: #0B0C10; }"
        )
        self.btn_effect_studio.clicked.connect(self.open_effect_studio)
        right_layout.addWidget(self.btn_effect_studio)

        right_layout.addWidget(preset_group)
        self.reload_custom_effects()
        self.kb = None
        self.visualizer_process = None
        self.visualizer_script_path = os.path.normcase(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "audio_visualizer.py")
            )
        )
        self.visualizer_launch_signature = None
        self.temperature_worker_process = None
        self.temperature_worker_script_path = os.path.normcase(
            os.path.abspath(
                os.path.join(os.path.dirname(__file__), "temperature_worker.py")
            )
        )
        self.timer_interval_active_ms = 33
        self.timer_interval_idle_ms = 150
        
        # Valorant Spike Timer states
        self.spike_active = False
        self.spike_start_time = 0
        self.spike_cooldown_until = 0
        self.last_spike_scan = 0
        self.spike_target_red = (224, 60, 49)
        
        # Thread safety lock for custom_colors
        self.color_lock = threading.Lock()

        self.current_timer_base_ms = self.timer_interval_active_ms
        self.is_window_active = True
        self.turn_off_when_unplugged = False
        self.turn_off_when_battery_saver = False
        self._is_power_policy_forcing_off = False
        self.power_policy_timer = QTimer(self)
        self.power_policy_timer.setInterval(2000)
        self.power_policy_timer.timeout.connect(self.poll_power_policy)
        # Power policy timer will start conditionally based on settings when they're loaded
        self.battery_cache_timer = QTimer(self)
        self.battery_cache_timer.setInterval(500)
        self.battery_cache_timer.timeout.connect(self.update_battery_cache)
        self.battery_cache_timer.start()
        self.last_activity = time.monotonic()
        self.sct = None
        self.preview_window = None
        self.frames_editor = None
        self.pomo_running = False
        self.pomo_total_seconds = 0
        self.pomo_remaining_seconds = 0
        self.pomo_is_finished = False
        self.pomo_flash_on = False
        
        self.pomo_ui_timer = QTimer(self)
        self.pomo_ui_timer.setInterval(1000)
        self.pomo_ui_timer.timeout.connect(self._tick_pomo_ui)
        self.pomo_ui_timer.start()
        QApplication.processEvents()
        try:
            self.effect_manager = EffectManager()
            self.effect_manager.start()
            self.kb = self.effect_manager.kb
        except ValueError as e:
            print(f"Error initializing keyboard: {e}")
        self.force_quit = False
        self.hotkeys = {}
        self.hotkey_listener = GlobalHotkeyListener(self.hotkeys)
        self.hotkey_listener.hotkey_triggered.connect(self.on_global_hotkey_triggered)
        self.hotkey_listener.start()
        

        
        self.load_settings()
        self.apply_effect()

        self.update_available.connect(self.prompt_update)
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    def check_for_updates(self):
        url = "https://api.github.com/repos/AFcoder10/4-Zone-Keyboard-RGB-Toolkit/releases/latest"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                latest_version = data.get("tag_name", "")
                
                def _to_tuple(v):
                    import re
                    return tuple(map(int, re.findall(r'\d+', v)))
                    
                if latest_version and _to_tuple(latest_version) > _to_tuple(CURRENT_VERSION):
                    exe_url = ""
                    for asset in data.get("assets", []):
                        if asset.get("name", "").endswith(".exe"):
                            exe_url = asset.get("browser_download_url")
                            break
                    if exe_url:
                        self.update_available.emit(
                            latest_version,
                            exe_url,
                            data.get("body", "Bug fixes and improvements."),
                        )
        except Exception as e:
            print("Update check failed:", e)

    def prompt_update(self, latest_version, exe_url, release_notes):
        if self.auto_update_cb.isChecked():
            self.perform_update_download(exe_url, latest_version)
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Update Available: {latest_version}")
        dialog.setFixedSize(980, 500)

        layout = QVBoxLayout(dialog)

        lbl = QLabel(
            f"A new version of 4 Zone RGB Toolkit ({latest_version}) is available!\n"
            f"You are currently running {CURRENT_VERSION}.\n\nRelease Notes:"
        )
        lbl.setStyleSheet("font-weight: bold; font-size: 18px; color: #E2E2E2;")
        layout.addWidget(lbl)

        browser = QTextBrowser()
        browser.setMarkdown(release_notes)
        browser.setStyleSheet(
            "background-color: #1E1E1E; color: #E2E2E2; border: 1px solid #333; padding: 15px; font-size: 16px; line-height: 1.5;"
        )
        layout.addWidget(browser)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_remind = QPushButton("Remind Me Later")
        btn_remind.setCursor(Qt.PointingHandCursor)
        btn_remind.setStyleSheet(
            "padding: 8px 15px; background: #333333; color: white; border-radius: 4px;"
        )
        btn_remind.clicked.connect(dialog.reject)

        btn_install = QPushButton("Install Now")
        btn_install.setCursor(Qt.PointingHandCursor)
        btn_install.setStyleSheet(
            "padding: 8px 15px; background: #00E5FF; color: black; font-weight: bold; border-radius: 4px;"
        )
        btn_install.clicked.connect(dialog.accept)

        btn_layout.addWidget(btn_remind)
        btn_layout.addWidget(btn_install)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.Accepted:
            self.perform_update_download(exe_url, latest_version)

    def perform_update_download(self, url, version):
        self.progress_dlg = QProgressDialog(
            f"Downloading update ({CURRENT_VERSION} -> {version})...", "Cancel", 0, 100, None
        )
        self.progress_dlg.setWindowTitle("Update")
        self.progress_dlg.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.progress_dlg.setWindowModality(Qt.ApplicationModal)
        self.progress_dlg.setAutoClose(True)
        self.progress_dlg.show()

        self.downloader = UpdateDownloader(url)
        self.downloader.progress.connect(self.progress_dlg.setValue)
        self.downloader.finished.connect(self.apply_update_and_restart)
        def on_download_error(e):
            if hasattr(self, 'progress_dlg') and self.progress_dlg:
                self.progress_dlg.reset()
                self.progress_dlg.hide()
                self.progress_dlg.close()
            QMessageBox.critical(self, "Update Failed", f"Failed to download update:\n{e}")
        self.downloader.error.connect(on_download_error)
        self.progress_dlg.canceled.connect(self._handle_download_cancel)
        self.downloader.start()

    def _handle_download_cancel(self):
        self.downloader.cancel()
        try:
            self.downloader.progress.disconnect(self.progress_dlg.setValue)
            self.downloader.finished.disconnect(self.apply_update_and_restart)
        except Exception:
            pass
        self.progress_dlg.reset()
        self.progress_dlg.deleteLater()
        self.progress_dlg.hide()
        self.progress_dlg.deleteLater()

    def apply_update_and_restart(self, downloaded_exe):
        if hasattr(self, "progress_dlg"):
            self.progress_dlg.close()

        current_exe = self.original_exe_path or (
            sys.executable if getattr(sys, "frozen", False) else __file__
        )
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self,
                "Update Downloaded",
                f"Update downloaded to {downloaded_exe}. Since you are running from source, you must manually replace your files.",
            )
            return

        restart_exe = self.original_exe_path or current_exe
        ps_path = os.path.join(tempfile.gettempdir(), "updater.ps1")
        pid = os.getpid()

        with open(ps_path, "w") as f:
            f.write(f"$appPid = {pid}\n")
            f.write('$src  = "' + _ps_escape(downloaded_exe) + '"\n')
            f.write('$dest = "' + _ps_escape(current_exe) + '"\n')
            f.write('$restart = "' + _ps_escape(restart_exe) + '"\n')
            f.write(
                "\n# Wait for the process to terminate to avoid DLL lock errors\n"
            )
            f.write(
                "try { if ($appPid -ne (Get-Process explorer).Id) { Wait-Process -Id $appPid -Timeout 30 -ErrorAction SilentlyContinue } } catch {}\n"
            )
            f.write("Start-Sleep -Seconds 2\n")
            f.write("\n# Perform the update with retry loop in case of prolonged file locks\n")
            f.write(
                "$copySuccess = $false\n"
                "for ($i = 0; $i -lt 10; $i++) {\n"
                "    try {\n"
                "        Copy-Item -Path $src -Destination $dest -Force -ErrorAction Stop\n"
                "        $copySuccess = $true\n"
                "        break\n"
                "    } catch {\n"
                "        Start-Sleep -Milliseconds 500\n"
                "    }\n"
                "}\n"
            )
            f.write("\n# Cleanup and restart\n")
            f.write("if ($copySuccess) {\n")
            f.write("    Remove-Item -Path $src -Force -ErrorAction SilentlyContinue\n")
            f.write("}\n")
            f.write(
                "\n# Clear PyInstaller environment variables so the new process extracts cleanly\n"
            )
            f.write("Remove-Item env:_MEIPASS2 -ErrorAction SilentlyContinue\n")
            f.write("Remove-Item env:_MEIPASS -ErrorAction SilentlyContinue\n")
            f.write(
                'Get-ChildItem env: | Where-Object {$_.Name -like "_PYI_*"} | ForEach-Object { Remove-Item "env:$($_.Name)" -ErrorAction SilentlyContinue }\n'
            )
            f.write('$env:PYINSTALLER_RESET_ENVIRONMENT = "1"\n')
            f.write(
                "if (Test-Path $restart) { Start-Process -FilePath $restart } elseif (Test-Path $dest) { Start-Process -FilePath $dest }\n"
            )
            f.write(
                "Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue\n"
            )

        updater_env = sanitized_child_env(os.environ, include_pythonpath=False, force_re_extract=True)
        subprocess.Popen(
            [
                "powershell",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                ps_path,
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
            env=updater_env,
        )
        self.force_quit = True
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.stop()
        self.close()
        if QApplication.instance():
            QApplication.instance().quit()
        os._exit(0)

    def _get_preview_open_height(self):
        if not hasattr(self, "preview_panel"):
            return 88
        panel_layout = self.preview_panel.layout()
        if panel_layout is None:
            return 88
        margins = panel_layout.contentsMargins()
        header_height = (
            self.preview_header_widget.sizeHint().height()
            if hasattr(self, "preview_header_widget")
            else 24
        )
        available = (
            self.preview_panel.height()
            - margins.top()
            - margins.bottom()
            - header_height
            - panel_layout.spacing()
        )
        return max(88, available)

    def on_preview_anim_value(self, value):
        if not hasattr(self, "embedded_preview"):
            return
        ratio = max(0.0, min(1.0, float(value)))
        new_height = int(self.preview_anim_start_height * ratio)
        self.embedded_preview.setMaximumHeight(max(0, new_height))
        if hasattr(self, "preview_opacity_effect"):
            self.preview_opacity_effect.setOpacity(ratio)

    def on_preview_anim_finished(self):
        if not hasattr(self, "embedded_preview"):
            return
        if self.preview_enabled:
            target_height = self._get_preview_open_height()
            self.embedded_preview.setMaximumHeight(target_height)
            self.embedded_preview.setVisible(True)
            if hasattr(self, "preview_opacity_effect"):
                self.preview_opacity_effect.setOpacity(1.0)
        else:
            self.embedded_preview.setMaximumHeight(0)
            self.embedded_preview.setVisible(False)
        self._sync_preview_toggle_button()

    def _sync_preview_toggle_button(self):
        if not hasattr(self, "btn_preview_toggle_small"):
            return
        self.btn_preview_toggle_small.blockSignals(True)
        self.btn_preview_toggle_small.setChecked(bool(self.preview_enabled))
        self.btn_preview_toggle_small.setText("On" if self.preview_enabled else "Off")
        forced_off = bool(getattr(self, "preview_forced_by_mode", False))
        self.btn_preview_toggle_small.setEnabled(not forced_off)
        if forced_off:
            self.btn_preview_toggle_small.setToolTip(
                "Preview is auto-disabled for this mode."
            )
        else:
            self.btn_preview_toggle_small.setToolTip("Toggle live preview")
        self.btn_preview_toggle_small.blockSignals(False)

    def save_preview_preference(self):
        settings = QSettings("4ZoneRgbToolkit", "Preferences")
        settings.setValue(
            "preview_user_enabled", bool(getattr(self, "preview_user_enabled", True))
        )

    def _set_preview_visible_internal(self, visible):
        requested_visible = bool(visible)

        if getattr(self, "preview_window", None) is not None:
            self.preview_window.close()
            self.preview_window = None

        if not hasattr(self, "embedded_preview"):
            self.preview_enabled = requested_visible
            self._sync_preview_toggle_button()
            return

        if hasattr(self, "preview_anim"):
            self.preview_anim.stop()

        if requested_visible:
            self.preview_enabled = True
            self.embedded_preview.setVisible(True)
            self.embedded_preview.setMaximumHeight(self._get_preview_open_height())
            if hasattr(self, "preview_opacity_effect"):
                self.preview_opacity_effect.setOpacity(1.0)
        else:
            self.preview_enabled = False
            self.embedded_preview.setVisible(True)
            self.preview_anim_start_height = max(
                1, self.embedded_preview.height(), self.embedded_preview.maximumHeight()
            )
            if hasattr(self, "preview_anim"):
                self.preview_anim.setStartValue(1.0)
                self.preview_anim.setEndValue(0.0)
                self.preview_anim.start()
            else:
                self.embedded_preview.setMaximumHeight(0)
                self.embedded_preview.setVisible(False)

        self._sync_preview_toggle_button()

    def apply_preview_mode_policy(self, mode_name):
        restricted_mode = (
            mode_name in self.HARDWARE_MODES or mode_name == "Live Audio Visualizer"
        )
        self.preview_forced_by_mode = restricted_mode
        if restricted_mode:
            if self.preview_enabled:
                self._set_preview_visible_internal(False)
            else:
                self._sync_preview_toggle_button()
        else:
            desired_visible = bool(getattr(self, "preview_user_enabled", True))
            if self.preview_enabled != desired_visible:
                self._set_preview_visible_internal(desired_visible)
            else:
                self._sync_preview_toggle_button()

    def set_preview_visible(self, visible):
        self.preview_user_enabled = bool(visible)
        self.save_preview_preference()
        if getattr(self, "preview_forced_by_mode", False):
            self._set_preview_visible_internal(False)
        else:
            self._set_preview_visible_internal(self.preview_user_enabled)

    def toggle_preview(self):
        self.set_preview_visible(not getattr(self, "preview_user_enabled", True))

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
                except Exception as e:
                    print(f"Failed to remove update cache file {path}: {e}")
        if deleted > 0:
            QMessageBox.information(
                self,
                "Update Cache Cleared",
                f"Removed {deleted} leftover update file(s) from your Temp folder.",
            )
        else:
            QMessageBox.information(
                self,
                "Update Cache",
                "No leftover update files found. Nothing to clear!",
            )

    def build_default_mode_settings(self):
        defaults = {}
        for m in (self.HARDWARE_MODES + self.SOFTWARE_MODES):
            mode_dict = dict(self.default_control_settings)
            if hasattr(self, "DEFAULT_MODE_SETTINGS") and m in self.DEFAULT_MODE_SETTINGS:
                mode_dict.update(self.DEFAULT_MODE_SETTINGS[m])
            defaults[m] = mode_dict
        return defaults

    def save_runtime_state_settings(self):
        settings = QSettings("4ZoneRgbToolkit", "Preferences")
        settings.setValue("mode_settings", json.dumps(self.mode_settings))
        current_mode = (
            self.mode_list.currentItem().text()
            if self.mode_list.currentItem()
            else "Off"
        )
        settings.setValue("last_mode", current_mode)
        settings.setValue(
            "preview_user_enabled", bool(getattr(self, "preview_user_enabled", True))
        )

    def update_mode_description(self, mode_name):
        descriptions = {
            "Off": "Turns all keyboard lighting off.",
            "Static": "Applies one solid color to each zone.",
            "Breath": "Pulses the selected zone colors in and out.",
            "Smooth": "Runs the keyboard firmware smooth transition effect.",
            "Wave": "Uses the hardware wave effect with selectable direction.",
            "Smooth Wave": "Software gradient sweep across zones. Fill Mode can cycle fixed palettes.",
            "Lightning": "Cinematic storm flashes with staged strikes, flicker, and afterglow.",
            "Party": "Beat-style party lighting with tempo-driven color bursts.",
            "Realistic Fire": "Hot ember-style flicker with deep red and orange motion.",
            "Scanner (Cylon)": "A bouncing scanner eye with optional rainbow sweep.",
            "Aurora Borealis": "Flowing cool-toned waves drifting softly across the zones.",
            "Meteor Shower": "Fast streaks with bright heads and fading tails.",
            "Ambient Screen Color": "Mirrors the display onto the keyboard with adjustable FPS and vibrance.",
            "Battery Visualizer": "Maps battery level across the four keyboard zones.",
            "Mouse-Reactive Aura": "Shifts lighting in response to mouse movement.",
            "Pomodoro Timer": "Turns the keyboard into a full-session progress indicator.",
            "Live Audio Visualizer": "A 4-band audio-reactive equalizer using your selected zone colors.",
            "Temperature Mode": "Displays CPU average core temp on Zones 1 & 2, and GPU core temp on Zones 3 & 4. Colors range from Blue (<40°C) to Flashing Red (>100°C).",
            "Valorant Spike Timer": "Scans the top-center of the screen for the Spike Planted icon and automatically runs a perfectly timed 45s visual detonation countdown.",
        }
        self.mode_description_label.setText(
            descriptions.get(
                mode_name,
                "Configure the selected effect using the controls on the left.",
            )
        )

    def sync_control_label_widths(self):
        if not hasattr(self, "control_value_labels") or not self.control_value_labels:
            return
        samples = [
            "Brightness: 100%",
            "Smoothness: 100%",
            "Vibrance: 3.0x",
            "Animation Speed: 100%",
            "Lightning Frequency: 100%",
            "Party Tempo: 100%",
            "Visualizer Sensitivity: 100%",
            "Fire Flicker Speed: 100%",
            "Scanner Sweep Speed: 100%",
            "Aurora Shift Speed: 100%",
            "Meteor Speed: 100%",
            "Storm Intensity: 100%",
            "Ambient FPS: 60",
            "Flicker Reduction: 50",
        ]
        samples.extend(label.text() for label in self.control_value_labels)
        fm = self.control_value_labels[0].fontMetrics()
        target_width = max(fm.horizontalAdvance(text) for text in samples) + 14
        for label in self.control_value_labels:
            label.setMinimumWidth(target_width)
            label.setMaximumWidth(target_width)
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

    def update_preset_toolbar_layout(self, force=False):
        if not all(
            hasattr(self, name)
            for name in (
                "preset_layout",
                "preset_group",
                "preset_combo",
                "btn_save_preset",
                "btn_delete_preset",
                "btn_import_presets",
                "btn_export_presets",
            )
        ):
            return
        group_width = self.preset_group.width() or (self.width() // 3)
        compact = group_width < 430
        if (not force) and getattr(self, "_preset_toolbar_compact", None) == compact:
            return
        self._preset_toolbar_compact = compact

        while self.preset_layout.count():
            self.preset_layout.takeAt(0)

        for col in range(5):
            self.preset_layout.setColumnStretch(col, 0)

        if compact:
            self.preset_layout.addWidget(self.preset_combo, 0, 0, 1, 5)
            self.preset_layout.addWidget(self.btn_save_preset, 1, 0)
            self.preset_layout.addWidget(self.btn_delete_preset, 1, 1)
            self.preset_layout.addWidget(self.btn_import_presets, 1, 3)
            self.preset_layout.addWidget(self.btn_export_presets, 1, 4)
            self.preset_layout.setColumnStretch(2, 1)
        else:
            self.preset_layout.addWidget(self.preset_combo, 0, 0)
            self.preset_layout.addWidget(self.btn_save_preset, 0, 1)
            self.preset_layout.addWidget(self.btn_delete_preset, 0, 2)
            self.preset_layout.addWidget(self.btn_import_presets, 0, 3)
            self.preset_layout.addWidget(self.btn_export_presets, 0, 4)
            self.preset_layout.setColumnStretch(0, 1)

    def update_zone_color_controls_state(self, mode_name=None):
        mode_name = mode_name or (
            self.mode_list.currentItem().text()
            if self.mode_list.currentItem()
            else None
        )
        smooth_wave_custom = (
            mode_name == "Smooth Wave"
            and self.smooth_wave_palette_combo.currentText() == "Custom 4-Color"
        )
        is_zones_enabled = (
            mode_name in ("Static", "Breath", "Mouse-Reactive Aura", "Scanner (Cylon)", "Reactive Typing", "Live Audio Visualizer")
            or smooth_wave_custom
        )
        self.colors_group.setEnabled(is_zones_enabled)
        if is_zones_enabled:
            self.colors_group.setStyleSheet(
                "QGroupBox { color: #00E5FF; font-size: 16px; font-weight: bold; padding-top: 22px; }"
            )
        else:
            self.colors_group.setStyleSheet(
                "QGroupBox { color: #555555; font-size: 16px; font-weight: bold; padding-top: 22px; }"
            )

    # --- Hotkeys UI Logic ---
    def refresh_hotkeys_ui(self):
        self.hotkeys_list.clear()
        for k, v in self.hotkeys.items():
            item = QListWidgetItem(f"{k}  →  [{v['type'].title()}] {v['target']}")
            item.setData(Qt.UserRole, k)
            self.hotkeys_list.addItem(item)
        self.apply_hotkeys_filter()

    def apply_hotkeys_filter(self):
        query = ""
        if hasattr(self, "hotkeys_filter_input"):
            query = self.hotkeys_filter_input.text().strip().lower()
        for i in range(self.hotkeys_list.count()):
            item = self.hotkeys_list.item(i)
            visible = query in item.text().lower() if query else True
            item.setHidden(not visible)

    def update_hotkeys_list_height(self):
        if not hasattr(self, "hotkeys_list"):
            return
        # Keep the list comfortably sized based on current window height.
        target_height = int(self.height() * 0.24)
        target_height = max(130, min(300, target_height))
        self.hotkeys_list.setMinimumHeight(target_height)

    def on_hotkey_item_activated(self, item):
        key = item.data(Qt.UserRole)
        data = self.hotkeys.get(key)
        if data:
            dialog = HotkeyDialog(self, key, data)
            if dialog.exec():
                new_data = dialog.get_data()
                if new_data:
                    self._do_update_hotkey(key, *new_data)

    def validate_hotkey_combo(self, combo):
        parts = [p.strip().lower() for p in str(combo or "").split("+") if p.strip()]
        if not parts:
            return False, "Please record a valid key combination first."

        modifiers = {"ctrl", "alt", "shift", "win"}
        has_modifier = any(part in modifiers for part in parts)
        has_trigger_key = any(part not in modifiers for part in parts)

        if not has_modifier:
            return False, "Use at least one modifier key (Ctrl, Alt, Shift, or Win)."
        if not has_trigger_key:
            return (
                False,
                "Add a non-modifier key (recommended: Ctrl+Shift+1 to Ctrl+Shift+9).",
            )

        return True, ""

    def get_reserved_hotkey_warnings(self, combo):
        key = str(combo or "").strip().lower()
        warnings = []

        exact_reserved = {
            "ctrl+alt+delete": "Secure Attention Sequence and cannot be captured reliably.",
            "alt+tab": "Windows task switcher shortcut and may conflict with normal app usage.",
            "alt+f4": "Close window shortcut and may close the active application.",
            "win+l": "Locks Windows session.",
            "win+d": "Shows desktop and may interrupt focus.",
        }

        if key in exact_reserved:
            warnings.append(f"{combo}: {exact_reserved[key]}")

        if key.startswith("win+"):
            warnings.append(
                f"{combo}: Windows key combinations are often reserved by the OS."
            )

        return warnings

    def sanitize_hotkeys_data(self, raw_hotkeys):
        cleaned = {}
        changed = False

        if not isinstance(raw_hotkeys, dict):
            return {}, True

        for raw_key, raw_value in raw_hotkeys.items():
            key = str(raw_key or "").strip().lower()
            if not key:
                changed = True
                continue

            if not isinstance(raw_value, dict):
                changed = True
                continue

            h_type = str(raw_value.get("type", "")).strip().lower()
            target = str(raw_value.get("target", "")).strip()
            if h_type not in ("mode", "preset") or not target:
                changed = True
                continue

            is_valid_combo, _ = self.validate_hotkey_combo(key)
            if not is_valid_combo:
                changed = True
                continue

            normalized = {"type": h_type, "target": target}
            if key in cleaned and cleaned[key] != normalized:
                changed = True

            cleaned[key] = normalized
            if raw_key != key:
                changed = True
            if raw_value.get("type") != h_type or raw_value.get("target") != target:
                changed = True

        return cleaned, changed

    def add_hotkey(self):
        dialog = HotkeyDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                self._do_update_hotkey(None, *data)

    def _do_update_hotkey(self, old_key, new_key, h_type, target):
        if old_key and old_key in self.hotkeys:
            del self.hotkeys[old_key]

        self.hotkeys[new_key] = {"type": h_type, "target": target}
        self.refresh_hotkeys_ui()
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.update_hotkeys(self.hotkeys)
        self.save_settings()

    def clear_all_hotkeys(self):
        if not self.hotkeys:
            QMessageBox.information(self, "Clear Hotkeys", "No hotkeys to clear.")
            return
        reply = QMessageBox.question(
            self,
            "Clear Hotkeys",
            "Remove all hotkeys?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.hotkeys.clear()
        self.refresh_hotkeys_ui()
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.update_hotkeys(self.hotkeys)
        self.save_settings()

    def remove_hotkey(self):
        items = self.hotkeys_list.selectedItems()
        if items:
            key_part = items[0].data(Qt.UserRole) or items[0].text().split("  →  ")[0]
            if key_part in self.hotkeys:
                del self.hotkeys[key_part]
            self.refresh_hotkeys_ui()
            if hasattr(self, "hotkey_listener"):
                self.hotkey_listener.update_hotkeys(self.hotkeys)
            self.save_settings()

    def export_hotkeys(self):
        if not self.hotkeys:
            QMessageBox.information(
                self, "Export Hotkeys", "There are no hotkeys to export yet."
            )
            return
        default_name = f"4_zone_rgb_hotkeys_{CURRENT_VERSION}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Hotkeys", default_name, "JSON Files (*.json)"
        )
        if not file_path:
            return
        payload = {
            "version": CURRENT_VERSION,
            "exported_at": int(time.time()),
            "hotkeys": self.hotkeys,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            QMessageBox.information(
                self,
                "Export Hotkeys",
                f"Exported {len(self.hotkeys)} hotkey(s) successfully.",
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Export Hotkeys", f"Failed to export hotkeys:\n{e}"
            )

    def import_hotkeys(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Hotkeys", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            imported = (
                payload.get("hotkeys", payload) if isinstance(payload, dict) else None
            )
            cleaned, _ = self.sanitize_hotkeys_data(imported)
            if not cleaned:
                raise ValueError("File does not contain any valid hotkey bindings.")
            self.hotkeys.update(cleaned)
            self.refresh_hotkeys_ui()
            self.hotkey_listener.update_hotkeys(self.hotkeys)
            self.save_settings()
            QMessageBox.information(
                self,
                "Import Hotkeys",
                f"Imported {len(cleaned)} hotkey(s) successfully.",
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Import Hotkeys", f"Failed to import hotkeys:\n{e}"
            )

    def on_global_hotkey_triggered(self, hotkey_id):
        # Called from background thread signal
        data = self.hotkeys.get(hotkey_id)
        if not data:
            return

        target = data["target"]
        if data["type"] == "mode":
            items = self.mode_list.findItems(target, Qt.MatchExactly)
            if items:
                self.mode_list.setCurrentItem(items[0])
                self.on_mode_changed(target)
        elif data["type"] == "preset":
            self.apply_preset_logic(target)
            idx = self.preset_combo.findText(target)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)

    def load_settings(self):
        settings = QSettings("4ZoneRgbToolkit", "Preferences")

        self.hotkeys = {}

        # 1. Load existing flat hotkeys if any
        hotkeys_json = settings.value("hotkeys", "{}")
        if isinstance(hotkeys_json, (str, bytes, bytearray)) and hotkeys_json:
            try:
                loaded = json.loads(hotkeys_json)
                self.hotkeys, _ = self.sanitize_hotkeys_data(loaded)
            except Exception:
                pass

        # 2. Check for profiles and migrate the active one if it exists
        profiles_json = settings.value("hotkey_profiles", "")
        if isinstance(profiles_json, (str, bytes, bytearray)) and profiles_json:
            try:
                profiles = json.loads(profiles_json)
                active_profile_name = settings.value("active_hotkey_profile", "Default")

                migration_data = None
                if active_profile_name in profiles:
                    migration_data = profiles[active_profile_name]
                elif profiles:
                    migration_data = list(profiles.values())[0]

                if migration_data:
                    cleaned_migration, _ = self.sanitize_hotkeys_data(migration_data)
                    # Profiles take precedence during migration if flat hotkeys were empty
                    if not self.hotkeys:
                        self.hotkeys = cleaned_migration
                    else:
                        self.hotkeys.update(cleaned_migration)

                # Cleanup legacy keys after migration check
                settings.remove("hotkey_profiles")
                settings.remove("active_hotkey_profile")
            except Exception:
                pass

        self.refresh_hotkeys_ui()
        if hasattr(self, "hotkey_listener"):
            self.hotkey_listener.update_hotkeys(self.hotkeys)

        self.minimize_to_tray_cb.blockSignals(True)
        self.launch_on_start_cb.blockSignals(True)
        self.start_minimized_cb.blockSignals(True)
        self.boot_gif_cb.blockSignals(True)
        self.telemetry_cb.blockSignals(True)
        self.auto_update_cb.blockSignals(True)
        self.turn_off_unplugged_cb.blockSignals(True)
        self.turn_off_battery_saver_cb.blockSignals(True)
        if hasattr(self, "startup_preset_combo"):
            self.startup_preset_combo.blockSignals(True)
        min_val = settings.value("minimize_to_tray", False)
        min_to_tray = (
            str(min_val).lower() == "true"
            if isinstance(min_val, str)
            else bool(min_val)
        )
        self.minimize_to_tray_cb.setChecked(min_to_tray)
        launch_val = settings.value("launch_on_start", True)
        launch_start = (
            str(launch_val).lower() == "true"
            if isinstance(launch_val, str)
            else bool(launch_val)
        )
        self.launch_on_start_cb.setChecked(launch_start)
        self.start_minimized_cb.setChecked(
            settings.value("start_minimized", False, type=bool)
        )
        self.boot_gif_cb.setChecked(
            settings.value("show_boot_gif", False, type=bool)
        )
        self.telemetry_cb.setChecked(
            settings.value("telemetry_enabled", True, type=bool)
        )
        self.auto_update_cb.setChecked(
            settings.value("auto_update", False, type=bool)
        )
        unplugged_val = settings.value("turn_off_when_unplugged", False)
        self.turn_off_when_unplugged = (
            str(unplugged_val).lower() == "true"
            if isinstance(unplugged_val, str)
            else bool(unplugged_val)
        )
        self.turn_off_unplugged_cb.setChecked(self.turn_off_when_unplugged)
        battery_saver_val = settings.value("turn_off_when_battery_saver", False)
        self.turn_off_when_battery_saver = (
            str(battery_saver_val).lower() == "true"
            if isinstance(battery_saver_val, str)
            else bool(battery_saver_val)
        )
        self.turn_off_battery_saver_cb.setChecked(self.turn_off_when_battery_saver)
        # Start power policy timer if either setting is enabled
        if self.turn_off_when_unplugged or self.turn_off_when_battery_saver:
            self.power_policy_timer.start()
        presets_json = settings.value("saved_presets", "{}")
        if isinstance(presets_json, (str, bytes, bytearray)) and presets_json:
            try:
                self.presets = json.loads(presets_json)
            except Exception:
                self.presets = {}
        mode_settings_json = settings.value("mode_settings", "")
        loaded_mode_settings = self.build_default_mode_settings()
        if isinstance(mode_settings_json, (str, bytes, bytearray)) and mode_settings_json:
            try:
                parsed_mode_settings = json.loads(mode_settings_json)
                if isinstance(parsed_mode_settings, dict):
                    for mode_name, mode_data in parsed_mode_settings.items():
                        if mode_name in loaded_mode_settings and isinstance(
                            mode_data, dict
                        ):
                            loaded_mode_settings[mode_name].update(mode_data)
            except Exception as e:
                print(f"Failed to load mode settings: {e}")
                settings.setValue("mode_settings_backup_corrupted", mode_settings_json)
                try:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(self, "Settings Error", "Your mode settings were corrupted. They have been backed up and defaults restored.")
                except Exception:
                    pass
        self.mode_settings = loaded_mode_settings
        preview_val = settings.value("preview_user_enabled", True)
        self.preview_user_enabled = (
            str(preview_val).lower() == "true"
            if isinstance(preview_val, str)
            else bool(preview_val)
        )
        self.update_preset_combos()
        startup_p = settings.value("startup_preset", "None (Use Last State)")
        if startup_p in self.presets or startup_p == "None (Use Last State)":
            self.startup_preset_combo.setCurrentText(startup_p)
        last_mode = settings.value("last_mode", "Off")
        if hasattr(self, "startup_preset_combo"):
            self.startup_preset_combo.blockSignals(False)
        self.minimize_to_tray_cb.blockSignals(False)
        self.launch_on_start_cb.blockSignals(False)
        self.boot_gif_cb.blockSignals(False)
        self.telemetry_cb.blockSignals(False)
        self.auto_update_cb.blockSignals(False)
        self.turn_off_unplugged_cb.blockSignals(False)
        self.turn_off_battery_saver_cb.blockSignals(False)
        if startup_p in self.presets:
            if self.presets[startup_p].get("mode") == "Temperature Mode":
                startup_p = "None (Use Last State)"
                last_mode = "Off"

        if startup_p in self.presets:
            self.apply_preset_logic(startup_p)
        else:
            if last_mode == "Temperature Mode":
                last_mode = "Off"
            items = self.mode_list.findItems(last_mode, Qt.MatchExactly)
            if items:
                self.mode_list.setCurrentItem(items[0])
                self.on_mode_changed(last_mode)
        current_mode = (
            self.mode_list.currentItem().text()
            if self.mode_list.currentItem()
            else "Off"
        )
        self.apply_preview_mode_policy(current_mode)
        self.refresh_power_policy_state()

    def save_settings(self, *args):
        settings = QSettings("4ZoneRgbToolkit", "Preferences")
        settings.setValue("hotkeys", json.dumps(self.hotkeys))
        settings.setValue("minimize_to_tray", self.minimize_to_tray_cb.isChecked())
        settings.setValue("show_boot_gif", self.boot_gif_cb.isChecked())
        settings.setValue("startup_preset", self.startup_preset_combo.currentText())
        settings.setValue("saved_presets", json.dumps(self.presets))
        settings.setValue("mode_settings", json.dumps(self.mode_settings))
        current_mode = (
            self.mode_list.currentItem().text()
            if self.mode_list.currentItem()
            else "Off"
        )
        settings.setValue("last_mode", current_mode)
        settings.setValue(
            "preview_user_enabled", bool(getattr(self, "preview_user_enabled", True))
        )
        launch_start = self.launch_on_start_cb.isChecked()
        settings.setValue("launch_on_start", launch_start)
        settings.setValue("start_minimized", self.start_minimized_cb.isChecked())
        settings.setValue("telemetry_enabled", self.telemetry_cb.isChecked())
        settings.setValue("auto_update", self.auto_update_cb.isChecked())
        settings.setValue(
            "turn_off_when_unplugged", self.turn_off_unplugged_cb.isChecked()
        )
        settings.setValue(
            "turn_off_when_battery_saver", self.turn_off_battery_saver_cb.isChecked()
        )
        self.manage_startup_registry(launch_start)

    def on_power_policy_setting_changed(self, *args):
        self.turn_off_when_unplugged = self.turn_off_unplugged_cb.isChecked()
        self.turn_off_when_battery_saver = self.turn_off_battery_saver_cb.isChecked()
        self.save_settings()
        # Start/stop timer based on whether either setting is enabled
        either_enabled = (
            self.turn_off_when_unplugged or self.turn_off_when_battery_saver
        )
        if either_enabled and not self.power_policy_timer.isActive():
            self.power_policy_timer.start()
        elif not either_enabled and self.power_policy_timer.isActive():
            self.power_policy_timer.stop()
            self._is_power_policy_forcing_off = False
        self.refresh_power_policy_state()
        self.apply_effect()

    def _is_energy_saver_overlay_enabled(self):
        try:
            overlay_guid = GUID()
            rc = ctypes.windll.powrprof.PowerGetEffectiveOverlayScheme(
                ctypes.byref(overlay_guid)
            )
            if rc == 0:
                return _guid_equals(overlay_guid, GUID_OVERLAY_BEST_POWER_EFFICIENCY)
        except Exception:
            pass
        return False

    def _read_system_power_status(self):
        status = SYSTEM_POWER_STATUS()
        try:
            ok = ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
        except Exception:
            ok = 0
        if ok:
            # ACLineStatus: 0=offline, 1=online, 255=unknown
            unplugged = status.ACLineStatus == 0
            # SystemStatusFlag bit 0 indicates Battery Saver status on Windows.
            battery_saver = bool(status.SystemStatusFlag & 0x01)
            # Windows 11 Energy Saver can be exposed through power overlay mode.
            battery_saver = battery_saver or self._is_energy_saver_overlay_enabled()
            return unplugged, battery_saver
        if HAS_PSUTIL:
            try:
                battery = psutil.sensors_battery()
                if battery is not None:
                    return (
                        not bool(battery.power_plugged),
                        self._is_energy_saver_overlay_enabled(),
                    )
            except Exception:
                pass
        return False, self._is_energy_saver_overlay_enabled()

    def refresh_power_policy_state(self):
        self.turn_off_when_unplugged = bool(self.turn_off_unplugged_cb.isChecked())
        self.turn_off_when_battery_saver = bool(
            self.turn_off_battery_saver_cb.isChecked()
        )
        unplugged, battery_saver = self._read_system_power_status()
        self._is_power_policy_forcing_off = (
            self.turn_off_when_unplugged and unplugged
        ) or (self.turn_off_when_battery_saver and battery_saver)
        return self._is_power_policy_forcing_off

    def poll_power_policy(self):
        old_state = bool(getattr(self, "_is_power_policy_forcing_off", False))
        new_state = self.refresh_power_policy_state()
        if old_state != new_state:
            self.apply_effect()

    def update_battery_cache(self):
        """Update battery cache every 500ms to avoid expensive repeated calls in tight loops."""
        try:
            if HAS_PSUTIL:
                battery = psutil.sensors_battery()
                if battery:
                    _battery_cache["percent"] = battery.percent
                    _battery_cache["charging"] = battery.power_plugged
                    _battery_cache["last_update"] = time.monotonic()
                    if hasattr(self, "effect_manager"):
                        self.effect_manager.update_config("battery_percent", battery.percent)
                        self.effect_manager.update_config("battery_charging", battery.power_plugged)
        except Exception:
            pass

    def clear_cache(self):
        reply = QMessageBox.warning(
            self,
            "Clear Cache & Reset",
            "WARNING: This will permanently delete all your saved presets, startup configurations, and reset the application to factory defaults.\n\nAre you absolutely sure you want to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            settings = QSettings("4ZoneRgbToolkit", "Preferences")
            settings.clear()
            self.manage_startup_registry(True)
            self.minimize_to_tray_cb.blockSignals(True)
            self.launch_on_start_cb.blockSignals(True)
            self.start_minimized_cb.blockSignals(True)
            self.boot_gif_cb.blockSignals(True)
            self.turn_off_unplugged_cb.blockSignals(True)
            self.turn_off_battery_saver_cb.blockSignals(True)
            self.startup_preset_combo.blockSignals(True)
            self.minimize_to_tray_cb.setChecked(False)
            self.launch_on_start_cb.setChecked(True)
            self.start_minimized_cb.setChecked(False)
            self.boot_gif_cb.setChecked(False)
            self.turn_off_unplugged_cb.setChecked(False)
            self.turn_off_battery_saver_cb.setChecked(False)
            self.turn_off_when_unplugged = False
            self.turn_off_when_battery_saver = False
            self._is_power_policy_forcing_off = False
            self.presets = {}
            self.hotkeys = {}
            if hasattr(self, "hotkey_listener"):
                self.hotkey_listener.update_hotkeys(self.hotkeys)
            if hasattr(self, "refresh_hotkeys_ui"):
                self.refresh_hotkeys_ui()
            self.mode_settings = self.build_default_mode_settings()
            self.wave_direction = "left"
            self.smooth_wave_direction = "left"
            self.preview_user_enabled = True
            self.preview_forced_by_mode = False
            self.wave_fill_cb.setChecked(False)
            self.scanner_rainbow_cb.setChecked(False)
            self.smooth_wave_palette_combo.setCurrentText("RGBW")
            self.update_preset_combos()
            self.minimize_to_tray_cb.blockSignals(False)
            self.launch_on_start_cb.blockSignals(False)
            self.start_minimized_cb.blockSignals(False)
            self.turn_off_unplugged_cb.blockSignals(False)
            self.turn_off_battery_saver_cb.blockSignals(False)
            self.startup_preset_combo.blockSignals(False)
            self.bright_slider.setValue(100)
            self.vibrance_slider.setValue(15)
            self.speed_slider.setValue(20)
            self.storm_slider.setValue(50)
            self.mode_list.setCurrentRow(0)
            items = self.mode_list.findItems("Static", Qt.MatchExactly)
            if items:
                self.mode_list.setCurrentItem(items[0])
            self.on_mode_changed("Static")
            self.save_preview_preference()
            QMessageBox.information(
                self,
                "Cache Cleared",
                "The application cache has been successfully reset to default settings.",
            )
            self.toggle_settings()

    def show_logs(self):
        try:
            if not hasattr(self, "logs_dialog") or self.logs_dialog is None:
                self.logs_dialog = LogsDialog(self)
            self.logs_dialog.show()
            self.logs_dialog.raise_()
        except Exception as e:
            print(f"Failed to show logs dialog: {e}")

    def fade_out_lights(self):
        if not self.kb:
            return
        
        with self.color_lock:
            start_colors = list(self.custom_colors)
        if sum(start_colors) == 0:
            # If current custom color buffer is black, we just use a dim white as a starting point to fade from
            # if we were previously in a hardware effect.
            start_colors = [100] * 12
            
        steps = 5
        delay = 0.01
        
        for step in range(steps):
            factor = 1.0 - (step / float(steps - 1))
            faded = [int(c * factor) for c in start_colors]
            try:
                self.kb.set_colors(faded)
            except Exception:
                pass
            time.sleep(delay)
            # Process events so the UI doesn't completely freeze during the 0.4s fade
            QApplication.processEvents()
            
        try:
            self.kb.set_effect("static")
            self.kb.set_solid_color(0, 0, 0)
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
            blocked_widgets = [
                self.mode_list,
                self.bright_slider,
                self.vibrance_slider,
                self.speed_slider,
                self.storm_slider,
                self.ambient_fps_slider,
                self.flicker_slider,
                self.wave_fill_cb,
                self.scanner_rainbow_cb,
                self.smooth_wave_palette_combo,
            ]
            for widget in blocked_widgets:
                widget.blockSignals(True)
            try:
                preset_mode = p.get("mode", "Static")
                if preset_mode in ("Wave (Left)", "Wave (Right)"):
                    self.wave_direction = "left" if "Left" in preset_mode else "right"
                    preset_mode = "Wave"
                if preset_mode in ("Smooth Wave (Left)", "Smooth Wave (Right)"):
                    self.smooth_wave_direction = (
                        "left" if "Left" in preset_mode else "right"
                    )
                    preset_mode = "Smooth Wave"
                items = self.mode_list.findItems(preset_mode, Qt.MatchExactly)
                if items:
                    self.mode_list.setCurrentItem(items[0])
                self.bright_slider.setValue(p.get("brightness", 100))
                self.vibrance_slider.setValue(p.get("vibrance", 15))
                self.speed_slider.setValue(p.get("speed", 20))
                self.storm_slider.setValue(
                    p.get(
                        "storm_intensity",
                        self.default_control_settings["storm_intensity"],
                    )
                )
                self.ambient_fps_slider.setValue(
                    p.get("ambient_fps", self.default_control_settings["ambient_fps"])
                )
                self.flicker_slider.setValue(
                    p.get("flicker", self.default_control_settings["flicker"])
                )
                self.zone_colors = p.get("colors", [[255, 0, 0] for _ in range(4)])
                for i in range(4):
                    self.update_button_color(self.color_buttons[i], self.zone_colors[i])
                if "global_color" in p:
                    self.global_color = p["global_color"]
                    self.update_button_color(self.global_color_btn, self.global_color)
                self.scanner_rainbow_cb.setChecked(
                    bool(p.get("scanner_rainbow", False))
                )
                self.wave_fill_cb.setChecked(bool(p.get("wave_fill", False)))
                palette_name = p.get(
                    "smooth_wave_palette",
                    self.default_control_settings["smooth_wave_palette"],
                )
                if self.smooth_wave_palette_combo.findText(palette_name) == -1:
                    palette_name = self.default_control_settings["smooth_wave_palette"]
                self.smooth_wave_palette_combo.setCurrentText(palette_name)
                if "wave_dir" in p:
                    self.set_wave_direction(p["wave_dir"], apply_now=False)
                elif p.get("mode") in ("Wave (Left)", "Wave (Right)"):
                    self.set_wave_direction(
                        "left" if "Left" in p.get("mode") else "right", apply_now=False
                    )
                if "smooth_wave_dir" in p:
                    self.set_smooth_wave_direction(
                        p["smooth_wave_dir"], apply_now=False
                    )
                elif p.get("mode") in ("Smooth Wave (Left)", "Smooth Wave (Right)"):
                    self.set_smooth_wave_direction(
                        "left" if "Left" in p.get("mode") else "right", apply_now=False
                    )
                mode_key = preset_mode
                self.mode_settings.setdefault(
                    mode_key, dict(self.default_control_settings)
                )
                self.mode_settings[mode_key].update(
                    {
                        "brightness": self.bright_slider.value(),
                        "vibrance": self.vibrance_slider.value(),
                        "speed": self.speed_slider.value(),
                        "storm_intensity": self.storm_slider.value(),
                        "ambient_fps": self.ambient_fps_slider.value(),
                        "flicker": self.flicker_slider.value(),
                        "wave_fill": self.wave_fill_cb.isChecked(),
                        "scanner_rainbow": self.scanner_rainbow_cb.isChecked(),
                        "smooth_wave_palette": self.smooth_wave_palette_combo.currentText(),
                        "wave_direction": self.wave_direction,
                        "smooth_wave_direction": self.smooth_wave_direction,
                    }
                )
            finally:
                for widget in blocked_widgets:
                    widget.blockSignals(False)
            self.on_mode_changed(preset_mode)

    def save_new_preset(self):
        name, ok = QInputDialog.getText(
            self, "Save Preset", "Enter a name for this preset:"
        )
        if ok and name.strip():
            name = name.strip()
            current_mode = (
                self.mode_list.currentItem().text()
                if self.mode_list.currentItem()
                else "Static"
            )
            self.presets[name] = {
                "mode": current_mode,
                "brightness": self.bright_slider.value(),
                "vibrance": self.vibrance_slider.value(),
                "speed": self.speed_slider.value(),
                "storm_intensity": self.storm_slider.value(),
                "ambient_fps": self.ambient_fps_slider.value(),
                "flicker": self.flicker_slider.value(),
                "colors": list(self.zone_colors),
                "global_color": list(self.global_color),
                "scanner_rainbow": self.scanner_rainbow_cb.isChecked(),
                "wave_fill": self.wave_fill_cb.isChecked(),
                "smooth_wave_palette": self.smooth_wave_palette_combo.currentText(),
                "wave_dir": self.wave_direction,
                "smooth_wave_dir": self.smooth_wave_direction,
            }
            self.update_preset_combos()
            self.save_settings()
            self.preset_combo.setCurrentText(name)

    def delete_preset(self):
        name = self.preset_combo.currentText()
        if not name:
            return
        else:
            reply = QMessageBox.question(
                self,
                "Delete Preset",
                f"Are you sure you want to delete the preset '{name}'?",
                QMessageBox.Yes | QMessageBox.No,
            )
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
        self.startup_preset_combo.addItem("None (Use Last State)")
        self.startup_preset_combo.addItems(self.presets.keys())
        if curr_startup in self.presets or curr_startup == "None (Use Last State)":
            self.startup_preset_combo.setCurrentText(curr_startup)
        self.startup_preset_combo.blockSignals(False)
        # Auto-refresh logic if relevant

    @Slot(bool)
    def on_start_minimized_toggled(self, checked):
        if checked:
            self.boot_gif_cb.blockSignals(True)
            self.boot_gif_cb.setChecked(False)
            self.boot_gif_cb.blockSignals(False)
        self.save_settings()

    @Slot(bool)
    def on_boot_gif_toggled(self, checked):
        if checked:
            self.start_minimized_cb.blockSignals(True)
            self.start_minimized_cb.setChecked(False)
            self.start_minimized_cb.blockSignals(False)
        self.save_settings()

    def manage_startup_registry(self, enabled):
        key_path = "Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        key_name = "4ZoneRgbToolkit"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS
            )
            if enabled:
                if getattr(sys, "frozen", False):
                    exe_path = sys.executable
                    target = f'"{exe_path}" --hidden'
                else:
                    pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
                    if not os.path.exists(pythonw_path):
                        pythonw_path = sys.executable
                    script_path = os.path.abspath(__file__)
                    target = f'"{pythonw_path}" "{script_path}" --hidden'
                winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, target)
            else:
                try:
                    winreg.DeleteValue(key, key_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Failed to modify startup registry: {e}")

    def load_mode_controls(self, mode_name):
        settings = dict(self.default_control_settings)
        settings.update(self.mode_settings.get(mode_name, {}))
        self.mode_settings[mode_name] = dict(settings)
        slider_map = [
            (self.bright_slider, "brightness"),
            (self.vibrance_slider, "vibrance"),
            (self.speed_slider, "speed"),
            (self.storm_slider, "storm_intensity"),
            (self.ambient_fps_slider, "ambient_fps"),
            (self.flicker_slider, "flicker"),
        ]

        def _coerce_slider_setting(slider, key):
            default_value = self.default_control_settings.get(key, slider.value())
            raw_value = settings.get(key, default_value)
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                value = int(default_value)
            # If persisted data is out-of-range (for example from older builds),
            # fall back to the current default instead of snapping to slider max.
            if value < slider.minimum() or value > slider.maximum():
                value = int(default_value)
            return value

        for slider, key in slider_map:
            if slider is None:
                continue
            slider.blockSignals(True)
            normalized_value = _coerce_slider_setting(slider, key)
            slider.setValue(normalized_value)
            slider.blockSignals(False)
            settings[key] = normalized_value
        self.mode_settings[mode_name] = dict(settings)
        self.bright_label.setText(f"Brightness: {self.bright_slider.value()}%")
        self.vibrance_label.setText(f"Vibrance: {self.vibrance_slider.value() / 10.0}x")
        self.speed_label.setText(f"Animation Speed: {self.speed_slider.value()}%")
        self.storm_label.setText(f"Storm Intensity: {self.storm_slider.value()}%")
        self.ambient_fps_label.setText(
            f"Ambient FPS: {self.ambient_fps_slider.value()}"
        )
        self.flicker_label.setText(f"Flicker Reduction: {self.flicker_slider.value()}")
        self.wave_fill_cb.blockSignals(True)
        self.wave_fill_cb.setChecked(bool(settings.get("wave_fill", False)))
        self.wave_fill_cb.blockSignals(False)
        self.scanner_rainbow_cb.blockSignals(True)
        self.scanner_rainbow_cb.setChecked(bool(settings.get("scanner_rainbow", False)))
        self.scanner_rainbow_cb.blockSignals(False)
        self.reactive_rainbow_cb.blockSignals(True)
        self.reactive_rainbow_cb.setChecked(bool(settings.get("reactive_rainbow", False)))
        self.reactive_rainbow_cb.blockSignals(False)
        self.smooth_wave_palette_combo.blockSignals(True)
        palette_name = settings.get(
            "smooth_wave_palette", self.default_control_settings["smooth_wave_palette"]
        )
        if self.smooth_wave_palette_combo.findText(palette_name) == -1:
            palette_name = self.default_control_settings["smooth_wave_palette"]
        self.smooth_wave_palette_combo.setCurrentText(palette_name)
        self.smooth_wave_palette_combo.blockSignals(False)
        self.reactive_style_combo.blockSignals(True)
        style_name = settings.get(
            "reactive_style", self.default_control_settings["reactive_style"]
        )
        if self.reactive_style_combo.findText(style_name) == -1:
            style_name = self.default_control_settings["reactive_style"]
        self.reactive_style_combo.setCurrentText(style_name)
        self.reactive_style_combo.blockSignals(False)
        self.wave_direction = settings.get(
            "wave_direction", self.default_control_settings["wave_direction"]
        )
        self.wave_dir_left_btn.setChecked(self.wave_direction == "left")
        self.wave_dir_right_btn.setChecked(self.wave_direction == "right")
        self.smooth_wave_direction = settings.get(
            "smooth_wave_direction",
            self.default_control_settings["smooth_wave_direction"],
        )
        self.smooth_wave_dir_left_btn.setChecked(self.smooth_wave_direction == "left")
        self.smooth_wave_dir_right_btn.setChecked(self.smooth_wave_direction == "right")
        self.update_zone_color_controls_state(mode_name)

    def update_mode_setting(self, key, value):
        mode_name = (
            self.mode_list.currentItem().text()
            if self.mode_list.currentItem()
            else None
        )
        if not mode_name:
            return
        if mode_name not in self.mode_settings:
            self.mode_settings[mode_name] = dict(self.default_control_settings)
        self.mode_settings[mode_name][key] = value
        self.save_runtime_state_settings()

    @Slot(str)
    def set_wave_direction(self, direction, apply_now=True):
        self.wave_direction = direction
        self.wave_dir_left_btn.setChecked(direction == "left")
        self.wave_dir_right_btn.setChecked(direction == "right")
        self.mode_settings.setdefault("Wave", dict(self.default_control_settings))
        self.mode_settings["Wave"]["wave_direction"] = direction
        self.save_runtime_state_settings()
        if (
            apply_now
            and self.mode_list.currentItem()
            and self.mode_list.currentItem().text() == "Wave"
        ):
            self.apply_effect()

    @Slot(str)
    def set_smooth_wave_direction(self, direction, apply_now=True):
        self.smooth_wave_direction = direction
        self.smooth_wave_dir_left_btn.setChecked(direction == "left")
        self.smooth_wave_dir_right_btn.setChecked(direction == "right")
        self.mode_settings.setdefault(
            "Smooth Wave", dict(self.default_control_settings)
        )
        self.mode_settings["Smooth Wave"]["smooth_wave_direction"] = direction
        self.save_runtime_state_settings()
        if (
            apply_now
            and self.mode_list.currentItem()
            and self.mode_list.currentItem().text() == "Smooth Wave"
        ):
            self.apply_effect()

    def update_button_color(self, btn, rgb):
        r, g, b = rgb
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        text_color = "black" if luminance > 0.5 else "white"
        btn.setStyleSheet(
            f"""\n            QPushButton {{\n                background-color: rgb({int(r)}, {int(g)}, {int(b)});\n                color: {text_color};\n                border: 2px solid rgba(255, 255, 255, 0.2);\n                border-radius: 6px;\n                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;\n                font-weight: 600;\n            }}\n            QPushButton:hover {{\n                border: 2px solid #FFFFFF;\n                background-color: rgb({min(255, int(r * 1.1))}, {min(255, int(g * 1.1))}, {min(255, int(b * 1.1))});\n            }}\n        """
        )

    def pick_color(self, zone_idx):
        r, g, b = self.zone_colors[zone_idx]
        current_color = QColor(r, g, b)
        color = QColorDialog.getColor(
            current_color, self, f"Select Color for Zone {zone_idx + 1}",
            options=QColorDialog.DontUseNativeDialog
        )
        if color.isValid():
            self.zone_colors[zone_idx] = [color.red(), color.green(), color.blue()]
            with self.color_lock:
                self.custom_colors[zone_idx * 3] = color.red()
                self.custom_colors[zone_idx * 3 + 1] = color.green()
                self.custom_colors[zone_idx * 3 + 2] = color.blue()
            self.update_button_color(
                self.color_buttons[zone_idx], self.zone_colors[zone_idx]
            )
            self.apply_effect()

    def pick_global_color(self):
        r, g, b = self.global_color
        current_color = QColor(r, g, b)
        color = QColorDialog.getColor(
            current_color, self, "Select Master Keyboard Color",
            options=QColorDialog.DontUseNativeDialog
        )
        if color.isValid():
            r, g, b = (color.red(), color.green(), color.blue())
            self.global_color = [r, g, b]
            self.update_button_color(self.global_color_btn, self.global_color)
            for i in range(4):
                self.zone_colors[i] = [r, g, b]
                with self.color_lock:
                    self.custom_colors[i * 3] = r
                    self.custom_colors[i * 3 + 1] = g
                    self.custom_colors[i * 3 + 2] = b
                self.update_button_color(self.color_buttons[i], [r, g, b])
            self.apply_effect()

    @Slot(bool)
    def on_scanner_rainbow_toggled(self, checked):
        self.update_mode_setting("scanner_rainbow", bool(checked))
        self.apply_effect()

    def on_reactive_rainbow_toggled(self, checked):
        self.update_mode_setting("reactive_rainbow", bool(checked))
        if hasattr(self, 'effect_manager'):
            self.effect_manager.update_config("reactive_rainbow", bool(checked))

    @Slot(bool)
    def on_wave_fill_toggled(self, checked):
        self.update_mode_setting("wave_fill", bool(checked))
        if checked:
            # Save the user's previous speed before enforcing 40%
            self._pre_fill_speed = self.speed_slider.value()
            self.speed_slider.set_animated_value(40)
            self.update_mode_setting("speed", 40)
        else:
            # Restore the user's previous speed if we saved one
            if hasattr(self, "_pre_fill_speed"):
                self.speed_slider.set_animated_value(self._pre_fill_speed)
                self.update_mode_setting("speed", self._pre_fill_speed)
        self.apply_effect()

    def on_smooth_wave_palette_changed(self, palette_name):
        self.update_mode_setting("smooth_wave_palette", palette_name)
        self.apply_effect()
        self.update_zone_color_controls_state()

    def on_reactive_style_changed(self, style_name):
        self.update_mode_setting("reactive_style", style_name)
        if hasattr(self, 'effect_manager'):
            self.effect_manager.update_config("reactive_style", style_name.lower())
        self.update_zone_color_controls_state(
            "Smooth Wave"
            if self.mode_list.currentItem()
            and self.mode_list.currentItem().text() == "Smooth Wave"
            else None
        )
        if (
            self.mode_list.currentItem()
            and self.mode_list.currentItem().text() == "Smooth Wave"
        ):
            self.apply_effect()

    def get_smooth_wave_fill_palette(self):
        palette_name = self.smooth_wave_palette_combo.currentText()
        if palette_name == "Pastel":
            return [
                (255.0, 179.0, 186.0),
                (186.0, 255.0, 201.0),
                (186.0, 225.0, 255.0),
                (255.0, 252.0, 249.0),
            ]
        if palette_name == "Custom 4-Color":
            return [
                tuple(float(channel) for channel in color) for color in self.zone_colors
            ]
        return [
            (255.0, 0.0, 0.0),
            (0.0, 255.0, 0.0),
            (0.0, 0.0, 255.0),
            (255.0, 252.0, 249.0),
        ]

    def open_effect_studio(self):
        try:
            dialog = EffectStudioDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Effect Studio:\n{str(e)}")

    def reload_custom_effects(self):
        try:
            from core.config import SOFTWARE_MODES as BASE_SOFTWARE_MODES
            from core.custom_effects_io import list_custom_effects
            custom_list = list_custom_effects()
            valid_custom_names = {eff.get("name") for eff in custom_list if eff.get("name")}

            # Remove deleted custom effects from self.SOFTWARE_MODES and self.mode_list
            self.SOFTWARE_MODES = list(BASE_SOFTWARE_MODES)
            for name in list(self.SOFTWARE_MODES):
                if name not in BASE_SOFTWARE_MODES and name not in valid_custom_names:
                    try: self.SOFTWARE_MODES.remove(name)
                    except ValueError: pass
                    if hasattr(self, "mode_list") and self.mode_list:
                        items = self.mode_list.findItems(name, Qt.MatchExactly)
                        for item in items:
                            row = self.mode_list.row(item)
                            self.mode_list.takeItem(row)

            # Add new custom effects to self.SOFTWARE_MODES and self.mode_list
            for name in valid_custom_names:
                if name not in self.SOFTWARE_MODES:
                    self.SOFTWARE_MODES.append(name)
                    if hasattr(self, "mode_list") and self.mode_list:
                        items = self.mode_list.findItems(name, Qt.MatchExactly)
                        if not items:
                            self.mode_list.addItem(name)
        except Exception as e:
            print(f"Failed loading custom effects into software modes: {e}")

    def open_cloud_hub(self):
        try:
            from cloud_hub import MarketplaceDialog
            dialog = MarketplaceDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Marketplace:\n{str(e)}")

    def export_presets(self):
        if not self.presets:
            QMessageBox.information(
                self, "Export Presets", "There are no presets to export yet."
            )
            return
        default_name = f"4_zone_rgb_presets_{CURRENT_VERSION}.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Presets", default_name, "JSON Files (*.json)"
        )
        if not file_path:
            return
        payload = {
            "version": CURRENT_VERSION,
            "exported_at": int(time.time()),
            "presets": self.presets,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            QMessageBox.information(
                self,
                "Export Presets",
                f"Exported {len(self.presets)} preset(s) successfully.",
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Export Presets", f"Failed to export presets:\n{e}"
            )

    def import_presets(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Presets", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            imported = (
                payload.get("presets", payload) if isinstance(payload, dict) else None
            )
            if not isinstance(imported, dict):
                raise ValueError("File does not contain a valid preset dictionary.")
            imported_count = 0
            for name, preset in imported.items():
                if isinstance(name, str) and isinstance(preset, dict):
                    self.presets[name] = preset
                    imported_count += 1
            self.update_preset_combos()
            self.save_settings()
            QMessageBox.information(
                self,
                "Import Presets",
                f"Imported {imported_count} preset(s) successfully.",
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Import Presets", f"Failed to import presets:\n{e}"
            )

    def reset_current_mode_settings(self):
        mode_name = (
            self.mode_list.currentItem().text()
            if self.mode_list.currentItem()
            else None
        )
        if not mode_name:
            return
        self.mode_settings[mode_name] = dict(self.default_control_settings)
        if mode_name == "Wave":
            self.wave_direction = self.default_control_settings["wave_direction"]
        if mode_name == "Smooth Wave":
            self.smooth_wave_direction = self.default_control_settings[
                "smooth_wave_direction"
            ]
        self.load_mode_controls(mode_name)
        self.on_mode_changed(mode_name)
        self.save_runtime_state_settings()

    def minimize_app(self):
        if self.minimize_to_tray_cb.isChecked():
            self.hide()
        else:
            self.showMinimized()

    def restore_app(self):
        self.show()
        self.activateWindow()

    def update_timer_interval(self):
        if hasattr(self, 'preview_timer'):
            self.preview_timer.setInterval(33 if getattr(self, 'is_window_active', True) else 100)

    def focusInEvent(self, event):
        self.is_window_active = True
        self.update_timer_interval()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.is_window_active = False
        self.update_timer_interval()
        super().focusOutEvent(event)

    def reset_mode_state(self):
        """Effect state is now managed inside each effect class — nothing to reset here."""
        pass

    def tray_quit(self):
        self.force_quit = True
        self.close()
        QApplication.instance().quit()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_app()

    def switch_view_animated(self, index):
        if self.stack.currentIndex() == index:
            return

        self.stack.setCurrentIndex(index)
        new_widget = self.stack.currentWidget()

        effect = new_widget.graphicsEffect()
        if not effect:
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


    def _set_mode_by_name(self, mode_name):
        if not hasattr(self, "mode_list"):
            return
        items = self.mode_list.findItems(mode_name, Qt.MatchExactly)
        if items:
            self.mode_list.setCurrentItem(items[0])
            self.reset_mode_state()

    @Slot(str)
    def set_mode_from_mobile(self, mode_name):
        items = self.mode_list.findItems(mode_name, Qt.MatchExactly)
        if items:
            self.mode_list.setCurrentItem(items[0])

    @Slot(int, QColor)
    def set_custom_color_from_mobile(self, zone_idx, color):
        if 0 <= zone_idx < 4:
            with self.color_lock:
                self.custom_colors[zone_idx * 3] = color.red()
                self.custom_colors[zone_idx * 3 + 1] = color.green()
                self.custom_colors[zone_idx * 3 + 2] = color.blue()
            # Update the button color
            btn = self.color_buttons[zone_idx]
            btn.setStyleSheet(f"background-color: {color.name()}; border: none;")
            if getattr(self, 'kb', None):
                self.kb.set_colors(self.custom_colors)

    def show_help_dialog(self):
        dialog = FadeDialog(self)
        dialog.setWindowTitle("Help & Support")
        dialog.setFixedSize(440, 160)
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

        label = QLabel("Having issues or want to connect? Reach out below.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_discord = QPushButton(" Discord")
        btn_discord.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "assets", "discord.svg")))
        btn_discord.setIconSize(QSize(18, 18))
        btn_discord.setCursor(Qt.PointingHandCursor)
        btn_discord.setFixedHeight(35)
        btn_discord.setStyleSheet("""
            QPushButton {
                background-color: #2C2F33;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 15px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #23272A;
            }
        """)
        btn_discord.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://discord.gg/ecKwmsDBXg")))
        btn_discord.clicked.connect(dialog.accept)

        btn_github = QPushButton(" GitHub Issues")
        btn_github.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "assets", "github.svg")))
        btn_github.setIconSize(QSize(18, 18))
        btn_github.setCursor(Qt.PointingHandCursor)
        btn_github.setFixedHeight(35)
        btn_github.setStyleSheet("""
            QPushButton {
                background-color: #24292F;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 0 15px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1a1e23;
            }
        """)
        btn_github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/AFcoder10/4-Zone-Keyboard-RGB-Toolkit/issues")))
        btn_github.clicked.connect(dialog.accept)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedHeight(35)
        btn_close.setStyleSheet("""
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
        """)
        btn_close.clicked.connect(dialog.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(btn_discord)
        btn_layout.addWidget(btn_github)
        btn_layout.addWidget(btn_close)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        dialog.exec()

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            msg = MSG.from_address(message.__int__())
            if msg.message == 131 and msg.wParam:
                return (True, 0)
        return super().nativeEvent(eventType, message)

    @Slot()
    def _tick_pomo_ui(self):
        if not hasattr(self, 'pomo_running') or not self.pomo_running:
            return
        
        if self.pomo_remaining_seconds > 0:
            self.pomo_remaining_seconds -= 1
            h = self.pomo_remaining_seconds // 3600
            m = (self.pomo_remaining_seconds % 3600) // 60
            s = self.pomo_remaining_seconds % 60
            
            self.pomo_hours.setValue(h)
            self.pomo_minutes.setValue(m)
            self.pomo_seconds.setValue(s)
            self.pomo_fs_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
            

        else:
            self.pomo_is_finished = True


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
        main_cont = self.findChild(QWidget, "MainContainer")
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
        


    @Slot()
    def stop_pomodoro(self):
        self.pomo_running = False
        self.pomo_is_finished = False
        self.btn_pomo_start.setEnabled(True)
        self.btn_pomo_stop.setEnabled(False)
        self.pomo_hours.setEnabled(True)
        self.pomo_minutes.setEnabled(True)
        self.pomo_seconds.setEnabled(True)

        # Restore normal window view
        self.switch_view_animated(0)  # Main view
        self.title_bar.show()
        main_cont = self.findChild(QWidget, "MainContainer")
        if main_cont:
            main_cont.setStyleSheet("""
                #MainContainer {
                    background-color: #0E0E12;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                }
            """)
        if hasattr(self, "pre_pomo_window_state"):
            self.setWindowState(self.pre_pomo_window_state)
        else:
            self.showNormal()
        # Reset colors when stopping? handled in loop if running=False

    def start_temperature_worker(self):
        stop_flag = os.path.join(tempfile.gettempdir(), "4zone_temp_worker_stop.flag")
        if os.path.exists(stop_flag):
            try:
                os.remove(stop_flag)
            except Exception:
                pass

        pid_file = os.path.join(tempfile.gettempdir(), "4zone_temp_worker.pid")
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    worker_pid = int(f.read().strip())
                if psutil.pid_exists(worker_pid):
                    return  # Elevated worker is still alive
            except Exception:
                pass

        if hasattr(sys, "_MEIPASS"):
            cmd = [sys.executable, "--run-temperature-worker", str(os.getpid())]
        else:
            cmd = [
                sys.executable,
                self.temperature_worker_script_path,
                str(os.getpid()),
            ]

        env = os.environ.copy()
        if "PYTHONPATH" not in env:
            env["PYTHONPATH"] = os.path.dirname(os.path.normpath(__file__))

        try:
            self.temperature_worker_process = subprocess.Popen(
                cmd,
                creationflags=0x00000008,  # DETACHED_PROCESS
                env=env,
            )
        except Exception as e:
            print(f"Failed to start temperature worker: {e}")

    def stop_temperature_worker(self):
        stop_flag = os.path.join(tempfile.gettempdir(), "4zone_temp_worker_stop.flag")
        try:
            with open(stop_flag, "w") as f:
                f.write("stop")
        except Exception:
            pass
            
        if self.temperature_worker_process:
            try:
                self.temperature_worker_process.terminate()
            except Exception:
                pass
            self.temperature_worker_process = None

    def on_mode_changed(self, mode_name):
        if mode_name is None:
            return
        else:
            if getattr(self, "current_mode_name", None) != mode_name:
                self.reset_mode_state()
            self.current_mode_name = mode_name

            if mode_name == "Smooth Wave":
                # Set default brightness to 100 for Smooth Wave if it's very low (e.g. 0)
                if self.bright_slider.value() < 10:
                    self.bright_slider.setValue(100)

            if mode_name == "Temperature Mode":
                self.start_temperature_worker()
                # Use the new TemperatureMode effect instead of the legacy subprocess worker
                if hasattr(self, "effect_manager"):
                    self.effect_manager.set_effect("Temperature Mode")
            else:
                self.stop_temperature_worker()

            if mode_name == "Reactive Typing":
                self.update_reactive_typing_settings()
            
            self.load_mode_controls(mode_name)
            self.update_mode_description(mode_name)
            self.update_zone_color_controls_state(mode_name)
            is_speed_enabled = mode_name not in [
                "Off",
                "Static",
                "Ambient Screen Color",
            ]
            for w in self.speed_widgets:
                w.setEnabled(is_speed_enabled)

            self.speed_label.setStyleSheet(
                "color: #E2E2E2;" if is_speed_enabled else "color: #555555;"
            )

            is_bright_enabled = (
                mode_name not in self.SOFTWARE_MODES and mode_name != "Off"
            ) or "Scanner" in mode_name or mode_name == "Smooth Wave" or "Wave" in mode_name
            # For Live Audio Visualizer, we repurpose the brightness slider as Smoothness
            is_smooth_mode = "Live Audio Visualizer" in mode_name
            if is_smooth_mode:
                self.bright_slider.setEnabled(True)
                self.bright_label.setText(f"Smoothness: {self.bright_slider.value()}%")
                self.bright_label.setStyleSheet("color: #E2E2E2;")
            else:
                self.bright_slider.setEnabled(is_bright_enabled)
                self.bright_label.setText(f"Brightness: {self.bright_slider.value()}%")
                self.bright_label.setStyleSheet(
                    "color: #E2E2E2;" if is_bright_enabled else "color: #555555;"
                )

            if "Lightning" in mode_name:
                for w in self.storm_widgets:
                    w.show()
                self.storm_label.setText(
                    f"Storm Intensity: {self.storm_slider.value()}%"
                )
            else:
                for w in self.storm_widgets:
                    w.hide()

            if mode_name == "Ambient Screen Color":
                # Show vibrance slider only in Ambient Screen Color mode
                for w in self.vibrance_widgets:
                    w.show()
                for w in self.speed_widgets:
                    w.hide()
                for w in self.ambient_fps_widgets:
                    w.show()
                for w in self.flicker_widgets:
                    w.hide()
            elif "Live Audio Visualizer" in mode_name:
                self.controls_slot.setEnabled(False)
                # In Live Audio Visualizer mode, hide vibrance (brightness boost) UI
                for w in self.vibrance_widgets:
                    w.hide()
                self.speed_label.setText(
                    f"Visualizer Sensitivity: {self.speed_slider.value()}%"
                )
                self.speed_label.setStyleSheet("color: #E2E2E2;")
                # Make sure the speed control is visible and interactive (it may have been hidden
                # by Ambient mode). Also hide ambient-only controls.
                for w in self.speed_widgets:
                    w.show()
                    w.setEnabled(True)
                for w in self.ambient_fps_widgets:
                    w.hide()
                for w in self.flicker_widgets:
                    w.show()
                # Enable zone color pickers so user can choose their static colors
                self.colors_group.setEnabled(True)
                self.colors_group.setStyleSheet(
                    "QGroupBox { color: #00E5FF; font-size: 16px; font-weight: bold; padding-top: 22px; }"
                )
            else:
                self.controls_slot.setEnabled(True)
                # Hide vibrance for all other modes
                for w in self.vibrance_widgets:
                    w.hide()
                for w in self.speed_widgets:
                    w.show()
                for w in self.ambient_fps_widgets:
                    w.hide()
                for w in self.flicker_widgets:
                    w.hide()

            if mode_name == "Pomodoro Timer":
                # Hide all standard controls to isolate timer
                for w in self.speed_widgets:
                    w.hide()
                for w in self.bright_widgets:
                    w.hide()
            is_pomo_mode = (mode_name == "Pomodoro Timer")
            if is_pomo_mode:
                self.pomo_widget.show()
                for w in self.speed_widgets:
                    w.hide()
            else:
                self.pomo_widget.hide()
                for w in self.bright_widgets:
                    w.show()
                if mode_name != "Ambient Screen Color" and mode_name != "Valorant Spike Timer":
                    for w in self.speed_widgets:
                        w.show()

            if mode_name == "Wave":
                self.wave_dir_widget.show()
                self.set_wave_direction(self.wave_direction, apply_now=False)
            else:
                self.wave_dir_widget.hide()

            if mode_name == "Smooth Wave":
                self.smooth_wave_dir_widget.show()
                self.set_smooth_wave_direction(
                    self.smooth_wave_direction, apply_now=False
                )
            else:
                self.smooth_wave_dir_widget.hide()

            if "Lightning" in mode_name:
                self.speed_label.setText(
                    f"Lightning Frequency: {self.speed_slider.value()}%"
                )
            elif "Party" in mode_name:
                self.speed_label.setText(f"Party Tempo: {self.speed_slider.value()}%")
            elif "Live Audio Visualizer" in mode_name:
                self.speed_label.setText(
                    f"Visualizer Sensitivity: {self.speed_slider.value()}%"
                )
            elif "Realistic Fire" in mode_name:
                self.speed_label.setText(
                    f"Fire Flicker Speed: {self.speed_slider.value()}%"
                )
            elif "Scanner (Cylon)" in mode_name:
                self.speed_label.setText(
                    f"Scanner Sweep Speed: {self.speed_slider.value()}%"
                )
            else:
                self.speed_label.setText(
                    f"Animation Speed: {self.speed_slider.value()}%"
                )

            if "Smooth Wave" in mode_name:
                self.wave_fill_cb.show()
                self.smooth_wave_palette_combo.show()
            else:
                self.wave_fill_cb.hide()
                self.smooth_wave_palette_combo.hide()
                
            if "Reactive Typing" in mode_name:
                self.reactive_style_combo.show()
                self.reactive_rainbow_cb.show()
            else:
                self.reactive_style_combo.hide()
                self.reactive_rainbow_cb.hide()

            if "Scanner (Cylon)" in mode_name:
                self.scanner_rainbow_cb.show()
            else:
                self.scanner_rainbow_cb.hide()

            if mode_name == "Valorant Spike Timer":
                self.spike_timer_widget.show()
                self.colors_group.hide()
            else:
                self.spike_timer_widget.hide()
                self.colors_group.show()

            self.apply_preview_mode_policy(mode_name)
            self.sync_control_label_widths()
            self.save_runtime_state_settings()
            self.apply_effect()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preset_toolbar_layout()
        self.sync_control_label_widths()
        self.update_hotkeys_list_height()
        if getattr(self, "preview_enabled", False) and hasattr(
            self, "embedded_preview"
        ):
            self.embedded_preview.setMaximumHeight(self._get_preview_open_height())

    def closeEvent(self, event):
        if self.minimize_to_tray_cb.isChecked() and (not self.force_quit):
            event.ignore()
            self.hide()
            return
        else:
            if hasattr(self, "telemetry"):
                self.telemetry.stop()
            if hasattr(self, "pomo_ui_timer"):
                self.pomo_ui_timer.stop()
            if hasattr(self, "mobile_server"):
                try:
                    self.mobile_server.stop()
                except Exception:
                    pass
            self.stop_temperature_worker()
            if hasattr(self, "hotkey_listener"):
                self.hotkey_listener.stop()
            if getattr(self, "sct", None) is not None:
                self.sct.close()
            try:
                if self.kb:
                    self.fade_out_lights()
            except Exception as e:
                print(f"Failed to turn off keyboard LEDs: {e}")

            # Stop the EffectManager — this turns off LEDs and releases HID
            if hasattr(self, 'effect_manager'):
                self.effect_manager.stop()
            if hasattr(self, "tray_icon"):
                self.tray_icon.hide()
            self.save_settings()
            super().closeEvent(event)

    def on_bright_changed(self, value):
        if hasattr(self, 'effect_manager'): self.effect_manager.update_config('brightness', value)
        mode_name = (
            self.mode_list.currentItem().text() if self.mode_list.currentItem() else ""
        )
        if "Live Audio Visualizer" in mode_name:
            self.bright_label.setText(f"Smoothness: {value}%")
        else:
            self.bright_label.setText(f"Brightness: {value}%")
            self.apply_effect()
        self.sync_control_label_widths()
        self.update_mode_setting("brightness", value)

    def on_speed_changed(self, value):
        if hasattr(self, 'effect_manager'): self.effect_manager.update_config('speed', value)
        mode_name = (
            self.mode_list.currentItem().text() if self.mode_list.currentItem() else ""
        )
        if "Lightning" in mode_name:
            self.speed_label.setText(f"Lightning Frequency: {value}%")
        elif "Live Audio Visualizer" in mode_name:
            self.speed_label.setText(f"Visualizer Sensitivity: {value}%")
        elif "Realistic Fire" in mode_name:
            self.speed_label.setText(f"Fire Flicker Speed: {value}%")
        elif "Scanner (Cylon)" in mode_name:
            self.speed_label.setText(f"Scanner Sweep Speed: {value}%")
        elif "Aurora Borealis" in mode_name:
            self.speed_label.setText(f"Aurora Shift Speed: {value}%")
        elif "Meteor Shower" in mode_name:
            self.speed_label.setText(f"Meteor Speed: {value}%")
        elif "Party" in mode_name:
            self.speed_label.setText(f"Party Tempo: {value}%")
        else:
            self.speed_label.setText(f"Animation Speed: {value}%")
        self.sync_control_label_widths()
        if "Live Audio Visualizer" in mode_name:
            pass
        else:
            self.apply_effect()
        self.update_mode_setting("speed", value)

    def on_storm_changed(self, value):
        self.storm_label.setText(f"Storm Intensity: {value}%")
        self.sync_control_label_widths()
        if hasattr(self, 'effect_manager'):
            self.effect_manager.update_config('storm_intensity', value)
        self.update_mode_setting("storm_intensity", value)
    def on_vibrance_changed(self, value):
        if hasattr(self, 'effect_manager'): self.effect_manager.update_config('vibrance', value)
        self.vibrance_label.setText(f"Vibrance: {value / 10.0}x")
        self.sync_control_label_widths()
        self.update_mode_setting("vibrance", value)

    def on_ambient_fps_changed(self, value):
        self.ambient_fps_label.setText(f"Ambient FPS: {value}")
        self.sync_control_label_widths()
        if hasattr(self, 'effect_manager'):
            self.effect_manager.update_config('ambient_fps', value)
        self.update_mode_setting("ambient_fps", value)

    def on_flicker_changed(self, value):
        self.flicker_label.setText(f"Flicker Reduction: {value}")
        self.sync_control_label_widths()
        if hasattr(self, 'effect_manager'):
            self.effect_manager.update_config('flicker', value)
        self.update_mode_setting("flicker", value)

    def _get_spike_bbox(self, monitor):
        res_text = self.spike_res_combo.currentText()
        w_center = monitor["left"] + monitor["width"] // 2
        
        # We need a very tight box that ONLY contains the red hexagon, dodging the enemy score banner.
        if "2560x1440" in res_text:
            return {"top": monitor["top"] + 40, "left": w_center - 13, "width": 26, "height": 33}
        elif "3840x2160" in res_text:
            return {"top": monitor["top"] + 60, "left": w_center - 20, "width": 40, "height": 50}
        else: # 1920x1080 default (16:9)
            return {"top": monitor["top"] + 30, "left": w_center - 10, "width": 20, "height": 25}

    def calibrate_spike_red(self):
        if not HAS_MSS:
            QMessageBox.warning(self, "Missing Library", "The 'mss' library is required for screen capture.")
            return
            
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                width, height = monitor["width"], monitor["height"]
                
                bbox = self._get_spike_bbox(monitor)
                
                # Dump to file for debugging
                sct_img = sct.grab(bbox)
                try:
                    img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    img.save(os.path.join(tempfile.gettempdir(), "spike_calib_debug.png"))
                except Exception:
                    pass

                
                sct_img = sct.grab(bbox)
                raw = sct_img.bgra
                red_pixels = []
                for i in range(0, len(raw), 4):
                    b, g, r = raw[i], raw[i+1], raw[i+2]
                    if r > 100 and r > g * 1.5 and r > b * 1.5:
                        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                        if (h > 0.92 or h < 0.08) and s > 0.4 and v > 0.4:
                            red_pixels.append((r, g, b))
                
                if len(red_pixels) > 5:
                    avg_r = sum(p[0] for p in red_pixels) / len(red_pixels)
                    avg_g = sum(p[1] for p in red_pixels) / len(red_pixels)
                    avg_b = sum(p[2] for p in red_pixels) / len(red_pixels)
                    self.spike_target_red = (avg_r, avg_g, avg_b)
                    self.update_mode_setting("spike_target_red", self.spike_target_red)
                    if hasattr(self, "effect_manager"):
                        self.effect_manager.update_config("spike_target_red", self.spike_target_red)
                    QMessageBox.information(self, "Calibration Success", f"Found Spike Red: ({int(avg_r)}, {int(avg_g)}, {int(avg_b)})")
                else:
                    QMessageBox.warning(self, "Calibration Failed", "Could not find a bright red Spike icon at the top center of the screen.\nMake sure the Spike is planted and you are in-game.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to calibrate: {e}")

    def test_spike_timer(self):
        if hasattr(self, 'effect_manager'):
            self.effect_manager.update_config("spike_test_active", True)


    def update_reactive_typing_settings(self):
        if not hasattr(self, 'effect_manager'): return
        self.effect_manager.update_config("speed", self.speed_slider.value())

    def apply_effect(self):
        if not self.mode_list.currentItem():
            return
        
        mode_name = self.mode_list.currentItem().text()
        self.current_mode_name = mode_name
        
        # Dispatch immediate telemetry ping so dashboard updates instantly
        if hasattr(self, "telemetry") and self.telemetry:
            import threading
            threading.Thread(target=self.telemetry._send_status, args=("online",), daemon=True).start()
        
        if self.refresh_power_policy_state():
            self.stop_temperature_worker()
            if hasattr(self, "effect_manager"):
                self.effect_manager.turn_off()
            return

        if self.kb is None:
            if hasattr(self, "effect_manager"):
                self.kb = self.effect_manager.reacquire_keyboard()
            else:
                try:
                    self.kb = RGBKeyboard()
                except Exception:
                    self.kb = None

        if hasattr(self, "effect_manager"):
            if mode_name in self.HARDWARE_MODES:
                self.effect_manager.set_effect(None)
                if not self.kb:
                    return
                try:
                    hw_speed = max(1, min(4, int(self.speed_slider.value() / 25) + 1))
                    hw_brightness = max(1, min(4, int(self.bright_slider.value() / 25) + 1))
                    bright_mult = self.bright_slider.value() / 100.0
                    colors = [int(c * bright_mult) for rgb in self.zone_colors for c in rgb]
                    if mode_name == "Static":
                        self.kb.set_effect("static")
                        self.kb.set_colors(colors)
                    elif mode_name == "Breath":
                        self.kb.set_effect("breath", speed=hw_speed, brightness=hw_brightness)
                        self.kb.set_colors(colors)
                    elif mode_name == "Wave":
                        self.kb.set_effect("wave", speed=hw_speed, brightness=hw_brightness, direction=self.wave_direction)
                    elif mode_name == "Smooth":
                        self.kb.set_effect("smooth", speed=hw_speed, brightness=hw_brightness)
                    elif mode_name == "Off":
                        self.kb.set_effect("static")
                        self.kb.set_solid_color(0, 0, 0)
                except Exception as ex:
                    print(f"Warning: Failed to set hardware mode: {ex}")
            else:
                if self.kb:
                    self.kb.set_effect("static")
                self.effect_manager.update_config("speed", self.speed_slider.value())
                self.effect_manager.update_config("brightness", self.bright_slider.value())
                self.effect_manager.update_config("zone_colors", self.zone_colors)
                self.effect_manager.update_config("vibrance", self.vibrance_slider.value())
                self.effect_manager.update_config("flicker", self.flicker_slider.value())
                
                self.effect_manager.update_config("storm_intensity", self.storm_slider.value())
                self.effect_manager.update_config("ambient_fps", self.ambient_fps_slider.value())
                
                self.effect_manager.update_config("wave_fill", self.wave_fill_cb.isChecked())
                self.effect_manager.update_config("wave_direction", self.wave_direction)
                self.effect_manager.update_config("smooth_wave_direction", self.smooth_wave_direction)
                self.effect_manager.update_config("smooth_wave_palette", self.smooth_wave_palette_combo.currentText())
                self.effect_manager.update_config("reactive_style", self.reactive_style_combo.currentText().lower())
                self.effect_manager.update_config("reactive_rainbow", self.reactive_rainbow_cb.isChecked())
                self.effect_manager.update_config("scanner_rainbow", self.scanner_rainbow_cb.isChecked())
                
                if _battery_cache.get("last_update", 0) > 0:
                    self.effect_manager.update_config("battery_percent", _battery_cache.get("percent", 100))
                    self.effect_manager.update_config("battery_charging", _battery_cache.get("charging", False))
                    
                self.effect_manager.set_effect(mode_name)



if __name__ == "__main__":
    # Support two ways to launch the audio visualizer:
    # 1) Development: executing the script file directly (audio_visualizer.py)
    # 2) Bundled EXE: re-invoke the frozen executable with `--run-visualizer` flag
    if "--run-visualizer" in sys.argv or (
        len(sys.argv) > 1 and "audio_visualizer.py" in sys.argv[1]
    ):
        if "--run-visualizer" in sys.argv:
            sys.argv.remove("--run-visualizer")
        if len(sys.argv) > 1 and "audio_visualizer.py" in sys.argv[1]:
            sys.argv.remove(sys.argv[1])
        from audio_visualizer import AudioVisualizer

        try:
            visualizer = AudioVisualizer()
            visualizer.run()
        except Exception:
            import traceback

            traceback.print_exc()
        sys.exit(0)
    if "--run-temperature-worker" in sys.argv or (
        len(sys.argv) > 1 and "temperature_worker.py" in sys.argv[1]
    ):
        if "--run-temperature-worker" in sys.argv:
            sys.argv.remove("--run-temperature-worker")
        if len(sys.argv) > 1 and "temperature_worker.py" in sys.argv[1]:
            sys.argv.remove(sys.argv[1])
        import temperature_worker

        try:
            temperature_worker.main()
        except Exception:
            import traceback

            traceback.print_exc()
        sys.exit(0)
    if sys.platform == "win32":
        import ctypes

        myappid = "adityafere.4zonergbtoolkit.app.1"
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

    if last_error == 183:  # ERROR_ALREADY_EXISTS
        QMessageBox.critical(
            None,
            "Already Running",
            "Another instance of 4 Zone RGB Toolkit is already running.",
        )
        sys.exit(0)

    app.setStyle("Fusion")
    
    splash = None
    from PySide6.QtCore import QSettings
    settings = QSettings("4ZoneRgbToolkit", "Preferences")
    start_min = settings.value("start_minimized", False, type=bool)
    
    if "--hidden" not in sys.argv and not start_min:
        if getattr(sys, "frozen", False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        gif_path = os.path.join(base_dir, "assets", "boot.gif")
        if os.path.exists(gif_path) and settings.value("show_boot_gif", False, type=bool):
            splash = GifSplashScreen(gif_path, None)
            splash.show()
            app.processEvents()  # Paint the splash screen instantly

    # Initialize the heavy main application
    window = RGBControllerApp()
    
    if splash:
        splash.main_window = window
    elif "--hidden" not in sys.argv and not start_min:
        window.show()
    sys.exit(app.exec())