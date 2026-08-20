# GUI components separated from main.py
import os
import sys
import ctypes
from ctypes import Structure, c_int
from PySide6.QtCore import (
    Qt,
    QThread,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    QPoint,
    QVariantAnimation,
    Signal,
    Slot,
    QSize,
)
from PySide6.QtGui import (
    QColor,
    QPalette,
    QIcon,
    QFont,
    QPainter,
    QLinearGradient,
    QBrush,
    QPen,
    QAction,
    QMouseEvent,
    QCursor,
    QMovie,
    QPixmap,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QSlider,
    QComboBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QApplication,
    QSystemTrayIcon,
    QMenu,
    QDialog,
    QAbstractItemView,
    QGraphicsOpacityEffect,
    QStackedLayout,
    QTabWidget,
    QScrollArea,
    QCheckBox,
    QLineEdit,
    QSpinBox,
    QGridLayout,
    QFrame,
    QSizePolicy,
    QPlainTextEdit,
    QFileDialog,
    QMessageBox,
    QColorDialog,
    QStyle,
    QStyleOptionSlider,
    QSpacerItem,
)

try:
    from pynput import keyboard as pynput_keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


class RECT(Structure):
    _fields_ = [
        ("left", c_int),
        ("top", c_int),
        ("right", c_int),
        ("bottom", c_int),
    ]

def _resolve_original_exe_path():
    try:
        raw = sys.argv[0]
        if os.path.exists(raw):
            return os.path.abspath(raw)
    except Exception:
        pass
    return None

def _normalize_hotkey_key_name(key_name, shift_active=False):
    if not key_name:
        return ""
    key_name = str(key_name).lower().strip()
    if shift_active:
        # Map shift-modified symbols back to their base number keys for consistency
        shift_map = {
            "!": "1",
            "@": "2",
            "#": "3",
            "£": "3",
            "$": "4",
            "₹": "4",
            "€": "4",
            "%": "5",
            "^": "6",
            "&": "7",
            "*": "8",
            "(": "9",
            ")": "0",
            "_": "-",
            "+": "=",
            "{": "[",
            "}": "]",
            ":": ";",
            '"': "'",
            "<": ",",
            ">": ".",
            "?": "/",
        }
        key_name = shift_map.get(key_name, key_name)
    return key_name

class FadeDialog(QDialog):
    def showEvent(self, event):
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(320)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in.start()

    def closeEvent(self, event):
        if not hasattr(self, "_closing"):
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
            sr = self.style().subControlRect(
                QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self
            )
            if not sr.contains(event.position().toPoint()):
                # Jump to click position smoothly
                val = (
                    self.minimum()
                    + ((self.maximum() - self.minimum()) * event.position().x())
                    / self.width()
                )
                self.set_animated_value(int(val))
                event.accept()
                return
        super().mousePressEvent(event)

    def set_animated_value(self, val):
        if not hasattr(self, "anim"):
            self.anim = QPropertyAnimation(self, b"value")
            self.anim.setDuration(150)
            self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.stop()
        self.anim.setStartValue(self.value())
        self.anim.setEndValue(val)
        self.anim.start()
class AnimatedInfoIcon(QLabel):
    def __init__(self, tooltip_text, parent=None):
        super().__init__("ⓘ", parent)
        self.setToolTip(tooltip_text)
        self.setCursor(Qt.PointingHandCursor)
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(150)
        self.anim.valueChanged.connect(self._on_color_change)
        self._on_color_change(QColor(122, 131, 143, 128))
        
    def _on_color_change(self, color):
        self.setStyleSheet(f"color: {color.name(QColor.HexArgb)}; font-size: 14px; font-weight: bold;")
        
    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(QColor(122, 131, 143, 128))
        self.anim.setEndValue(QColor(122, 131, 143, 255))
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(QColor(122, 131, 143, 255))
        self.anim.setEndValue(QColor(122, 131, 143, 128))
        self.anim.start()
        super().leaveEvent(event)


class GlowButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.PointingHandCursor)
        self.fade_effect = QGraphicsOpacityEffect(self)
        self.fade_effect.setOpacity(0.9)
        self.setGraphicsEffect(self.fade_effect)

    def enterEvent(self, event):
        self.fade_effect.setOpacity(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.fade_effect.setOpacity(0.9)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.fade_effect.setOpacity(0.7)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.fade_effect.setOpacity(1.0)
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
        self.setup_button(self.btn_close, "#FF605C", "#FF0000")
        self.btn_close.clicked.connect(self.parent.close)
        self.btn_settings = QPushButton()
        self.btn_settings.setIcon(
            QIcon(os.path.join(os.path.dirname(__file__), "assets", "settings.svg"))
        )
        self.btn_settings.setIconSize(QSize(18, 18))
        self.btn_settings.setFixedSize(24, 24)
        self.btn_settings.setStyleSheet(
            "\n            QPushButton {\n                background: transparent;\n                border: none;\n                margin-bottom: 2px;\n            }\n            QPushButton:hover {\n                background-color: rgba(255, 255, 255, 30);\n                border-radius: 4px;\n            }\n        "
        )
        self.btn_settings.clicked.connect(self.parent.toggle_settings)


        self.btn_help = QPushButton("Help")
        self.btn_help.setFixedHeight(22)
        self.btn_help.setCursor(Qt.PointingHandCursor)
        self.btn_help.setToolTip("Help / Report Issue")
        self.btn_help.setStyleSheet("""
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
        """)
        self.btn_help.clicked.connect(self.parent.show_help_dialog)

        self.btn_marketplace = QPushButton("Marketplace (Beta)")
        self.btn_marketplace.setFixedHeight(22)
        self.btn_marketplace.setCursor(Qt.PointingHandCursor)
        self.btn_marketplace.setToolTip("Community Marketplace (Beta)")
        self.btn_marketplace.setStyleSheet("""
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
        """)
        if hasattr(self.parent, "open_cloud_hub"):
            self.btn_marketplace.clicked.connect(self.parent.open_cloud_hub)

        layout.addWidget(self.btn_settings)
        layout.addWidget(self.btn_help)
        layout.addWidget(self.btn_marketplace)
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        layout.addItem(spacer)
        self.btn_minimize = QPushButton()
        self.setup_button(self.btn_minimize, "#FFBD44", "#FFA500")
        self.btn_minimize.clicked.connect(self.parent.minimize_app)
        self.btn_maximize = QPushButton()
        self.setup_button(self.btn_maximize, "#00CA4E", "#008000")
        self.btn_maximize.clicked.connect(self.toggle_maximize)
        layout.addWidget(self.btn_minimize)
        layout.addWidget(self.btn_maximize)
        layout.addWidget(self.btn_close)
        self.start_pos = None

    def setup_button(self, btn, color, hover_color):
        # ***<module>.CustomTitleBar.setup_button: Failure: Compilation Error
        btn.setFixedSize(14, 14)
        btn.setStyleSheet(
            f"""\n            QPushButton {{\n                background-color: {color};\n                border-radius: 7px;\n                border: none;\n            }}\n            QPushButton:hover {{\n                background-color: {hover_color};\n            }}\n        """
        )

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
        self.setWindowTitle("Application Logs")
        self.setMinimumSize(700, 400)
        self.setWindowFlags(self.windowFlags() | Qt.Window)
        layout = QVBoxLayout(self)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)
        button_layout = QHBoxLayout()
        self.btn_clear = QPushButton("Clear")
        self.btn_copy = QPushButton("Copy All")
        self.btn_close = QPushButton("Close")
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
        self.last_text_length = 0  # Track text length to avoid redundant updates

    def refresh(self):
        try:
            import sys
            text = ""
            if hasattr(sys.stdout, "get_text") and hasattr(sys.stderr, "get_text"):
                text = sys.stdout.get_text() + sys.stderr.get_text()
            # Only update if text actually grew (avoid full replacement on every tick)
            if len(text) > self.last_text_length:
                # Instead of full replacement, append new content
                old_text = self.log_view.toPlainText()
                if old_text != text:
                    self.log_view.setPlainText(text)
                    self.last_text_length = len(text)
            self.log_view.verticalScrollBar().setValue(
                self.log_view.verticalScrollBar().maximum()
            )
        except Exception:
            pass

    def clear_logs(self):
        try:
            import sys
            if hasattr(sys.stdout, "clear"): sys.stdout.clear()
            if hasattr(sys.stderr, "clear"): sys.stderr.clear()
            self.log_view.clear()
        except Exception:
            pass

    def copy_logs(self):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.log_view.toPlainText())
        except Exception:
            pass



class KeyboardPreviewWidget(QWidget):
    def __init__(self, parent_app, parent=None):
        super().__init__(parent)
        self.parent_app = parent_app
        self.last_colors = None  # Track last color state to avoid unnecessary repaints
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.zone_widgets = []
        for _ in range(4):
            w = QFrame()
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            w.setMinimumHeight(64)
            w.setStyleSheet(
                "background-color: black; border-radius: 8px; border: 1px solid rgba(255,255,255,0.12);"
            )
            layout.addWidget(w)
            self.zone_widgets.append(w)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_colors)
        self.timer.start(50)

    def update_colors(self):
        try:
            colors = None
            if hasattr(self.parent_app, "effect_manager"):
                with self.parent_app.effect_manager._lock:
                    colors = list(self.parent_app.effect_manager.current_colors)
            else:
                colors = getattr(self.parent_app, "custom_colors", [0] * 12)
                
            # Only update if colors changed to avoid expensive CSS recalculation
            if colors and colors != self.last_colors and len(colors) >= 12:
                self.last_colors = colors[:]  # Store copy
                for i in range(4):
                    r = max(0, min(255, int(colors[i * 3])))
                    g = max(0, min(255, int(colors[i * 3 + 1])))
                    b = max(0, min(255, int(colors[i * 3 + 2])))
                    self.zone_widgets[i].setStyleSheet(
                        f"background-color: rgb({r},{g},{b}); border-radius: 8px; border: 1px solid rgba(255,255,255,0.12);"
                    )
        except Exception:
            pass




class HotkeyDialog(FadeDialog):
    def __init__(self, parent_app, existing_key=None, existing_data=None):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.existing_key = existing_key
        self.setWindowTitle("Edit Hotkey" if existing_key else "Add Hotkey")
        self.setFixedWidth(400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        title = QLabel("Hotkey Configuration")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #00E5FF; margin-bottom: 5px;"
        )
        layout.addWidget(title)

        # Key Combination
        layout.addWidget(
            QLabel(
                "KEY COMBINATION:",
                styleSheet="color: #AAAAAA; font-size: 10px; font-weight: bold;",
            )
        )
        self.recorder = HotkeyRecorderButton(existing_key)
        self.recorder.setFixedHeight(35)
        self.recorder.setToolTip("Recommended: Ctrl+Shift+1 to Ctrl+Shift+9")
        layout.addWidget(self.recorder)
        layout.addWidget(
            QLabel(
                "Tip: Click and press your key combo (e.g., Ctrl+Shift+A)",
                styleSheet="color: #7A838F; font-size: 10px;",
            )
        )

        # Action Type
        layout.addWidget(
            QLabel(
                "TRIGGER ACTION:",
                styleSheet="color: #AAAAAA; font-size: 10px; font-weight: bold;",
            )
        )
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Mode", "Preset"])
        self.type_combo.setFixedHeight(35)
        self.type_combo.setStyleSheet(
            "QComboBox { background: #1A1A1E; color: white; border: 1px solid #333333; border-radius: 4px; padding: 2px 8px; }"
        )
        self.type_combo.currentTextChanged.connect(self.populate_targets)
        layout.addWidget(self.type_combo)

        # Action Target
        layout.addWidget(
            QLabel(
                "ACTION TARGET:",
                styleSheet="color: #AAAAAA; font-size: 10px; font-weight: bold;",
            )
        )
        self.target_combo = QComboBox()
        self.target_combo.setFixedHeight(35)
        self.target_combo.setStyleSheet(
            "QComboBox { background: #1A1A1E; color: white; border: 1px solid #333333; border-radius: 4px; padding: 2px 8px; }"
        )
        layout.addWidget(self.target_combo)

        # Spacer
        layout.addSpacing(10)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_cancel = GlowButton("Cancel")
        self.btn_cancel.setFixedHeight(35)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.05); color: #AAAAAA; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; }"
        )

        self.btn_save = GlowButton("Save Binding")
        self.btn_save.setFixedHeight(35)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_save.setStyleSheet(
            "QPushButton { background: #00E5FF; color: black; font-weight: bold; border-radius: 6px; } QPushButton:hover { background: #00D5FF; }"
        )

        btn_row.addWidget(self.btn_cancel, 1)
        btn_row.addWidget(self.btn_save, 2)
        layout.addLayout(btn_row)

        self.recorder.recording_state_changed.connect(self._toggle_global_listener)

        # Initialize
        if existing_data:
            self.type_combo.setCurrentText(existing_data.get("type", "Mode").title())
            self.populate_targets(existing_data.get("type", "Mode").title())
            self.target_combo.setCurrentText(existing_data.get("target", ""))
        else:
            self.populate_targets("Mode")

    def _toggle_global_listener(self, is_recording):
        if hasattr(self.parent_app, "hotkey_listener"):
            self.parent_app.hotkey_listener.set_paused(is_recording)

    def populate_targets(self, h_type):
        self.target_combo.clear()
        if h_type == "Mode":
            hardware = getattr(self.parent_app, "HARDWARE_MODES", [])
            software = getattr(self.parent_app, "SOFTWARE_MODES", [])
            self.target_combo.addItems(hardware + software)
        else:
            self.target_combo.addItems(
                list(getattr(self.parent_app, "presets", {}).keys())
            )

        has_targets = self.target_combo.count() > 0
        self.target_combo.setEnabled(has_targets)
        self.btn_save.setEnabled(has_targets)

    def on_save(self):
        key = self.recorder.key_combination
        if not key or key == "Click to record...":
            QMessageBox.warning(
                self, "Invalid Key", "Please record a key combination first."
            )
            return

        h_type = self.type_combo.currentText().lower()
        target = self.target_combo.currentText()

        is_valid, err = self.parent_app.validate_hotkey_combo(key)
        if not is_valid:
            QMessageBox.warning(self, "Invalid Hotkey", err)
            return

        # Reserved warnings
        warnings = self.parent_app.get_reserved_hotkey_warnings(key)
        if warnings:
            warn_msg = (
                "The following potential conflicts were detected:\n\n"
                + "\n".join(warnings)
                + "\n\nSave anyway?"
            )
            res = QMessageBox.warning(
                self,
                "System Shortcut Conflict",
                warn_msg,
                QMessageBox.Yes | QMessageBox.No,
            )
            if res == QMessageBox.No:
                return

        # Check for conflict if it's a NEW key or changed from existing
        if key != self.existing_key and key in self.parent_app.hotkeys:
            existing = self.parent_app.hotkeys[key]
            QMessageBox.warning(
                self,
                "Conflict",
                f"'{key}' is already assigned to [{existing['type'].title()}] {existing['target']}.",
            )
            return

        # Successful validation
        self.result_data = (key, h_type, target)
        self.accept()

    def get_data(self):
        return getattr(self, "result_data", None)


class HotkeyRecorderButton(QPushButton):
    recording_state_changed = Signal(bool)

    def __init__(self, key_combination="", parent=None):
        super().__init__(parent)
        self.key_combination = key_combination or "Click to record..."
        self.setText(self.key_combination)
        self.recording = False
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.05); color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; padding: 5px; } QWidget:focus { border: 1px solid #00E5FF; }"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.recording = True
            self.recording_state_changed.emit(True)
            self.setText("Recording... (Press keys)")
            self.setStyleSheet(
                "QPushButton { background-color: rgba(0, 229, 255, 0.2); color: #00E5FF; border: 1px solid #00E5FF; border-radius: 4px; padding: 5px; }"
            )
            self.setFocus()
            event.accept()
        else:
            super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if self.recording:
            if event.key() in (
                Qt.Key_Shift,
                Qt.Key_Control,
                Qt.Key_Meta,
                Qt.Key_Alt,
                Qt.Key_AltGr,
            ):
                return
            modifiers = event.modifiers()
            parts = []
            if modifiers & Qt.ControlModifier:
                parts.append("ctrl")
            if modifiers & Qt.AltModifier:
                parts.append("alt")
            if modifiers & Qt.ShiftModifier:
                parts.append("shift")
            if modifiers & Qt.MetaModifier:
                parts.append("win")

            # Get the key name from Qt
            key_name = QKeySequence(event.key()).toString()
            key_name = _normalize_hotkey_key_name(
                key_name, bool(modifiers & Qt.ShiftModifier)
            )

            if key_name:
                parts.append(key_name)
                combo = "+".join(parts)
            else:
                combo = ""

            self.key_combination = combo
            self.setText(combo if combo else "Click to record...")
            self.recording = False
            self.recording_state_changed.emit(False)
            self.setStyleSheet(
                "QPushButton { background-color: rgba(255, 255, 255, 0.05); color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; padding: 5px; }"
            )
            self.clearFocus()
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        if self.recording:
            self.recording = False
            self.recording_state_changed.emit(False)
            self.setText(self.key_combination or "Click to record...")
            self.setStyleSheet(
                "QPushButton { background-color: rgba(255, 255, 255, 0.05); color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 4px; padding: 5px; }"
            )
        super().focusOutEvent(event)




class GifSplashScreen(QWidget):
    def __init__(self, gif_path, main_window):
        super().__init__()
        self.main_window = main_window
        
        # Transparent, frameless window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)
        
        # Load GIF
        self.movie = QMovie(gif_path)
        self.movie.setSpeed(150)  # Make animation 50% faster
        # Lock splash screen to the exact fixed ratio of the main app window
        self.setFixedSize(700, 400)
        
        # Connect frame change to detect when it ends and render smoothly
        self.movie.frameChanged.connect(self.check_frame)
        self.movie.start()

    def check_frame(self, frameNumber):
        # Smoothly scale the current frame to fix pixelation
        img = self.movie.currentImage()
        scaled_img = img.scaled(self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(QPixmap.fromImage(scaled_img))
        
        # Stop at the very last frame
        if self.movie.frameCount() > 0 and frameNumber >= self.movie.frameCount() - 1:
            self.movie.stop()
            self.fade_out()
            
    def fade_out(self):
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(300)  # 300ms fade out (faster)
        self.animation.setStartValue(1.0)
        self.animation.setEndValue(0.0)
        self.animation.finished.connect(self.on_fade_finished)
        self.animation.start()

    def on_fade_finished(self):
        self.close()
        self.main_window.show()

class FrameCardWidget(QFrame):
    """Clean frame item widget for vertical sequence list with high visual polish and compact dimensions."""
    def __init__(self, index, frame_data, is_selected, on_click_callback, parent=None):
        super().__init__(parent)
        self.index = index
        self.on_click_callback = on_click_callback
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        self.setToolTip(f"Click to select and inspect Frame {index + 1} in the timeline sequence.")
        
        self.set_selected(is_selected)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)
        
        lbl = QLabel(f"Frame {index + 1}")
        lbl.setStyleSheet("font-weight: 600; color: #FFFFFF; font-size: 12px; border: none; background: transparent;")
        layout.addWidget(lbl)
        
        # 4 Zone Color previews
        swatch_layout = QHBoxLayout()
        swatch_layout.setSpacing(4)
        zones = frame_data.get("zones", [[0, 0, 0] for _ in range(4)])
        for z in range(4):
            z_rgb = zones[z] if z < len(zones) else [0, 0, 0]
            sw = QFrame()
            sw.setFixedSize(14, 14)
            sw.setStyleSheet(f"background-color: rgb({z_rgb[0]}, {z_rgb[1]}, {z_rgb[2]}); border: 1px solid rgba(255, 255, 255, 0.7); border-radius: 3px;")
            swatch_layout.addWidget(sw)
        layout.addLayout(swatch_layout)
        
        layout.addStretch()
        
        hold_ms = frame_data.get("hold_ms", 600)
        t_style = frame_data.get("transition_style", "smooth")
        self.info_lbl = QLabel(f"Hold: {hold_ms}ms | {t_style.capitalize()}")
        self.info_lbl.setStyleSheet("color: #9AA0A6; font-size: 10px; font-weight: 500; border: none; background: transparent;")
        layout.addWidget(self.info_lbl)

    def update_card(self, frame_data, is_selected):
        self.set_selected(is_selected)
        zones = frame_data.get("zones", [[0, 0, 0] for _ in range(4)])
        # update swatches
        swatch_layout = self.layout().itemAt(1).layout()
        for z in range(4):
            z_rgb = zones[z] if z < len(zones) else [0, 0, 0]
            sw = swatch_layout.itemAt(z).widget()
            sw.setStyleSheet(f"background-color: rgb({z_rgb[0]}, {z_rgb[1]}, {z_rgb[2]}); border: 1px solid rgba(255, 255, 255, 0.7); border-radius: 3px;")
        
        hold_ms = frame_data.get("hold_ms", 600)
        t_style = frame_data.get("transition_style", "smooth")
        self.info_lbl.setText(f"Hold: {hold_ms}ms | {t_style.capitalize()}")

    def set_selected(self, is_selected):
        if is_selected:
            style = """
                QFrame {
                    background-color: rgba(0, 229, 255, 0.14);
                    border: 1px solid rgba(0, 229, 255, 0.4);
                    border-left: 3px solid #00E5FF;
                    border-radius: 6px;
                }
            """
        else:
            style = """
                QFrame {
                    background-color: rgba(255, 255, 255, 0.03);
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-left: 3px solid transparent;
                    border-radius: 6px;
                }
                QFrame:hover {
                    background-color: rgba(255, 255, 255, 0.06);
                    border: 1px solid rgba(255, 255, 255, 0.15);
                    border-left: 3px solid rgba(255, 255, 255, 0.3);
                }
            """
        self.setStyleSheet(style)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.on_click_callback(self.index)
        super().mousePressEvent(event)


class EffectStudioDialog(QDialog):
    """
    Custom Effect Studio & Sequence Designer.
    Compact layout, interactive sliders for brightness & speed, fully visible controls.
    """
    def __init__(self, parent_app=None):
        super().__init__(parent_app)
        self.parent_app = parent_app
        self.setWindowTitle("Effect Builder (Beta)")
        self.setMinimumSize(920, 600)
        
        from core.custom_effects_io import list_custom_effects, save_custom_effect, delete_custom_effect, load_custom_effect_by_name
        self.list_custom_effects = list_custom_effects
        self.save_custom_effect = save_custom_effect
        self.delete_custom_effect = delete_custom_effect
        self.load_custom_effect_by_name = load_custom_effect_by_name

        # Compact Stylesheet with proper QGroupBox titling to eliminate vertical content hiding
        self.setStyleSheet("""
            QDialog {
                background-color: #0E0E12;
                color: #E2E2E2;
            }
            QLabel {
                color: #E2E2E2;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QGroupBox {
                color: #00E5FF;
                font-weight: 700;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                font-size: 12px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.02);
                margin-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
                background-color: #0E0E12;
            }
            QPushButton {
                background-color: #1A1A1E;
                color: white;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 5px;
                padding: 4px 12px;
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #00E5FF;
                color: black;
                font-weight: 700;
                border: 1px solid #00E5FF;
            }
            QPushButton:pressed {
                background-color: #00B3CC;
                border: 1px solid #00B3CC;
            }
            QPushButton:disabled {
                background-color: #12131A;
                color: #555555;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            QComboBox, QSpinBox, QLineEdit {
                background-color: #161822;
                color: #FFFFFF;
                border: 1px solid rgba(255, 255, 255, 0.14);
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QComboBox:disabled, QSpinBox:disabled, QLineEdit:disabled {
                background-color: #12131A;
                color: #555555;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            QSlider::groove:horizontal {
                border: none;
                height: 5px;
                background: #2A2A2E;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00E5FF;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid #00E5FF;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #00E5FF;
            }
            QSlider::sub-page:horizontal:disabled {
                background: #444444;
            }
            QSlider::handle:horizontal:disabled {
                border: 2px solid #555555;
                background: #666666;
            }
        """)

        # Initial clean sequence frames (no cyberpunk default)
        self.frames = [
            {
                "zones": [[0, 229, 255], [0, 180, 255], [140, 0, 255], [255, 50, 90]],
                "hold_ms": 600,
                "transition_style": "smooth",
                "transition_ms": 400,
            }
        ]
        self.selected_frame_idx = 0

        # Save previous active mode
        self.previous_mode = None
        self.pre_studio_custom_config = None
        if self.parent_app and hasattr(self.parent_app, "mode_list") and self.parent_app.mode_list.currentItem():
            self.previous_mode = self.parent_app.mode_list.currentItem().text()
            
        if self.previous_mode == "Custom Sequence" and self.parent_app and hasattr(self.parent_app, "effect_manager"):
            import copy
            self.pre_studio_custom_config = copy.deepcopy(self.parent_app.effect_manager.config)
            loaded_frames = self.pre_studio_custom_config.get("frames", [])
            if loaded_frames:
                self.frames = copy.deepcopy(loaded_frames)

        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(100)
        self._update_timer.timeout.connect(self._do_live_update_hardware)

        self._build_ui()
        
        if getattr(self, 'pre_studio_custom_config', None):
            if "speed" in self.pre_studio_custom_config:
                self.default_speed_slider.setValue(self.pre_studio_custom_config["speed"])
            if "brightness" in self.pre_studio_custom_config:
                self.default_bright_slider.setValue(self.pre_studio_custom_config["brightness"])
                
        self.refresh_saved_effects_combo()
        self.rebuild_frame_list()
        self.load_frame_into_inspector(0)

        # Force physical hardware to software static mode so stream is live
        if self.parent_app:
            if hasattr(self.parent_app, "kb") and self.parent_app.kb:
                try:
                    self.parent_app.kb.set_effect("static")
                except Exception:
                    pass
            if hasattr(self.parent_app, "effect_manager") and self.parent_app.effect_manager:
                self.parent_app.effect_manager.set_effect("Custom Sequence")
                self._do_live_update_hardware()

    def live_update_hardware(self):
        """Schedules a debounced hardware update to prevent flooding."""
        if hasattr(self, "_update_timer") and not self._update_timer.isActive():
            self._update_timer.start()

    def _do_live_update_hardware(self):
        """Pushes current sequence payload live to physical hardware. Emits black static out on 0 frames."""
        if self.parent_app and hasattr(self.parent_app, "effect_manager") and self.parent_app.effect_manager:
            if len(self.frames) == 0:
                black_sequence = [{
                    "zones": [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]],
                    "hold_ms": 1000,
                    "transition_style": "quick",
                    "transition_ms": 0
                }]
                self.parent_app.effect_manager.update_config("frames", black_sequence)
                self.parent_app.effect_manager.update_config("speed", 50)
                self.parent_app.effect_manager.update_config("brightness", 0)
            else:
                import copy
                self.parent_app.effect_manager.update_config("frames", copy.deepcopy(self.frames))
                self.parent_app.effect_manager.update_config("speed", self.default_speed_slider.value())
                self.parent_app.effect_manager.update_config("brightness", self.default_bright_slider.value())

    def closeEvent(self, event):
        if hasattr(self, "_update_timer"):
            self._update_timer.stop()
        self._restore_previous_effect()
        super().closeEvent(event)

    def reject(self):
        if hasattr(self, "_update_timer"):
            self._update_timer.stop()
        self._restore_previous_effect()
        super().reject()

    def accept(self):
        if hasattr(self, "_update_timer"):
            self._update_timer.stop()
        self.pre_studio_custom_config = None  # Don't restore if accepted!
        self._restore_previous_effect()
        super().accept()

    def _restore_previous_effect(self):
        if self.parent_app and hasattr(self.parent_app, "effect_manager") and getattr(self, "pre_studio_custom_config", None) is not None:
            if "frames" in self.pre_studio_custom_config:
                self.parent_app.effect_manager.update_config("frames", self.pre_studio_custom_config["frames"])
            if "speed" in self.pre_studio_custom_config:
                self.parent_app.effect_manager.update_config("speed", self.pre_studio_custom_config["speed"])
            if "brightness" in self.pre_studio_custom_config:
                self.parent_app.effect_manager.update_config("brightness", self.pre_studio_custom_config["brightness"])
        if getattr(self, "parent_app", None) and getattr(self, "previous_mode", None):
            try:
                items = self.parent_app.mode_list.findItems(self.previous_mode, Qt.MatchExactly)
                if items and len(items) > 0:
                    self.parent_app.mode_list.setCurrentItem(items[0])
                    if hasattr(self.parent_app, "apply_effect"):
                        self.parent_app.apply_effect()
            except Exception:
                pass

    def _build_ui(self):
        master_layout = QVBoxLayout(self)
        master_layout.setContentsMargins(14, 14, 14, 14)
        master_layout.setSpacing(12)

        # --- Top Header Toolbar Card ---
        header_card = QGroupBox("EFFECT CONFIGURATION AND PRESETS")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(12, 16, 12, 10)
        h_layout.setSpacing(10)

        # 2x4 Grid layout prevents horizontal text overlapping with compact sliders
        grid_inputs = QGridLayout()
        grid_inputs.setHorizontalSpacing(14)
        grid_inputs.setVerticalSpacing(8)

        lbl_name = QLabel("Effect Name:")
        grid_inputs.addWidget(lbl_name, 0, 0)
        self.name_input = QLineEdit("Custom Effect 1")
        self.name_input.setFixedHeight(26)
        self.name_input.setToolTip("Enter a unique title for this custom sequence effect.")
        self.name_input.textChanged.connect(self.live_update_hardware)
        grid_inputs.addWidget(self.name_input, 0, 1)

        lbl_load = QLabel("Load Saved Effect:")
        grid_inputs.addWidget(lbl_load, 0, 2)
        self.effect_selector_combo = QComboBox()
        self.effect_selector_combo.setFixedHeight(26)
        self.effect_selector_combo.setToolTip("Select and load a previously created custom effect from your library.")
        self.effect_selector_combo.activated.connect(self.on_load_effect_selected)
        grid_inputs.addWidget(self.effect_selector_combo, 0, 3)

        # Default Speed Slider & Value Label
        lbl_speed = QLabel("Default Speed:")
        grid_inputs.addWidget(lbl_speed, 1, 0)
        speed_box = QHBoxLayout()
        speed_box.setSpacing(8)
        self.default_speed_slider = AnimatedSlider(Qt.Horizontal)
        self.default_speed_slider.setRange(1, 100)
        self.default_speed_slider.setValue(50)
        self.default_speed_slider.setToolTip("Default animation playback speed percentage when applied.")
        self.default_speed_val_lbl = QLabel("50")
        self.default_speed_val_lbl.setMinimumWidth(24)
        self.default_speed_val_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        self.default_speed_slider.valueChanged.connect(lambda v: (self.default_speed_val_lbl.setText(str(v)), self.live_update_hardware()))
        speed_box.addWidget(self.default_speed_slider, stretch=1)
        speed_box.addWidget(self.default_speed_val_lbl)
        grid_inputs.addLayout(speed_box, 1, 1)

        # Default Brightness Slider & Value Label
        lbl_bright = QLabel("Default Brightness:")
        grid_inputs.addWidget(lbl_bright, 1, 2)
        bright_box = QHBoxLayout()
        bright_box.setSpacing(8)
        self.default_bright_slider = AnimatedSlider(Qt.Horizontal)
        self.default_bright_slider.setRange(0, 100)
        self.default_bright_slider.setValue(100)
        self.default_bright_slider.setToolTip("Default LED brightness intensity percentage when applied.")
        self.default_bright_val_lbl = QLabel("100")
        self.default_bright_val_lbl.setMinimumWidth(24)
        self.default_bright_val_lbl.setStyleSheet("color: #00E5FF; font-weight: bold;")
        self.default_bright_slider.valueChanged.connect(lambda v: (self.default_bright_val_lbl.setText(str(v)), self.live_update_hardware()))
        bright_box.addWidget(self.default_bright_slider, stretch=1)
        bright_box.addWidget(self.default_bright_val_lbl)
        grid_inputs.addLayout(bright_box, 1, 3)

        grid_inputs.setColumnStretch(1, 1)
        grid_inputs.setColumnStretch(3, 1)
        h_layout.addLayout(grid_inputs)

        # Action Buttons Row (Compact Height)
        r2_box = QHBoxLayout()
        r2_box.setSpacing(10)

        self.btn_save = QPushButton("Save Effect")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(28)
        self.btn_save.setToolTip("Save this complete animation sequence directly to your custom library.")
        self.btn_save.setStyleSheet("QPushButton { background: #00E5FF; color: #0E0E12; font-weight: 700; padding: 4px 16px; } QPushButton:hover { background: #00C8E0; }")
        self.btn_save.clicked.connect(self.save_effect_action)
        r2_box.addWidget(self.btn_save)

        self.btn_delete = QPushButton("Delete Effect")
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setFixedHeight(28)
        self.btn_delete.setToolTip("Permanently remove the selected custom effect from your library.")
        self.btn_delete.setStyleSheet("QPushButton { background: #23181D; color: #FF6B6B; border: 1px solid rgba(255, 107, 107, 0.4); padding: 4px 14px; } QPushButton:hover { background-color: #FF5252; color: white; border-color: #FF5252; }")
        self.btn_delete.clicked.connect(self.delete_effect_action)
        r2_box.addWidget(self.btn_delete)

        r2_box.addSpacing(12)

        self.btn_import = QPushButton("Import JSON")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.setFixedHeight(28)
        self.btn_import.setToolTip("Import a custom effect sequence from an external backup JSON file.")
        self.btn_import.clicked.connect(self.import_json_action)
        r2_box.addWidget(self.btn_import)

        self.btn_export = QPushButton("Export JSON")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setFixedHeight(28)
        self.btn_export.setToolTip("Export the current effect sequence as a standalone JSON file.")
        self.btn_export.clicked.connect(self.export_json_action)
        r2_box.addWidget(self.btn_export)

        r2_box.addStretch()
        h_layout.addLayout(r2_box)
        master_layout.addWidget(header_card, stretch=0)

        # --- Main Workspace Split ---
        workspace_layout = QHBoxLayout()
        workspace_layout.setSpacing(14)

        # Left Side: Compact Vertical Frame List
        left_box = QVBoxLayout()
        left_box.setSpacing(8)
        left_lbl = QLabel("SEQUENCE FRAMES")
        left_lbl.setStyleSheet("color: #00E5FF; font-weight: 700; font-size: 12px; letter-spacing: 1px;")
        left_box.addWidget(left_lbl)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumWidth(310)
        self.scroll_area.setMaximumWidth(350)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; background: rgba(255, 255, 255, 0.02); }")

        self.scroll_content = QWidget()
        self.frames_list_layout = QVBoxLayout(self.scroll_content)
        self.frames_list_layout.setContentsMargins(8, 8, 8, 8)
        self.frames_list_layout.setSpacing(6)
        self.frames_list_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        left_box.addWidget(self.scroll_area, stretch=1)

        self.btn_add_frame = QPushButton("+ Add New Frame")
        self.btn_add_frame.setCursor(Qt.PointingHandCursor)
        self.btn_add_frame.setFixedHeight(32)
        self.btn_add_frame.setToolTip("Append a brand new all-black RGB frame to the end of the timeline sequence.")
        self.btn_add_frame.setStyleSheet("QPushButton { background-color: rgba(0, 229, 255, 0.14); color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); font-weight: 700; font-size: 12px; } QPushButton:hover { background-color: #00E5FF; color: black; }")
        self.btn_add_frame.clicked.connect(self.add_frame_action)
        left_box.addWidget(self.btn_add_frame)

        workspace_layout.addLayout(left_box, stretch=0)

        # Right Side: Frame Inspector & Controls inside a transparent scroll area to guarantee full visibility
        right_box = QVBoxLayout()
        right_box.setSpacing(8)

        self.inspector_group = QGroupBox("FRAME INSPECT AND CONTROLS")
        ins_main_layout = QVBoxLayout(self.inspector_group)
        ins_main_layout.setContentsMargins(10, 18, 10, 10)
        ins_main_layout.setSpacing(10)

        # Transparent Scroll Area inside Inspector prevents any height compression/clipping of internal boxes
        ins_scroll = QScrollArea()
        ins_scroll.setWidgetResizable(True)
        ins_scroll.setFrameShape(QFrame.NoFrame)
        ins_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; } QWidget#InsContent { background: transparent; }")
        
        ins_content = QWidget()
        ins_content.setObjectName("InsContent")
        ins_layout = QVBoxLayout(ins_content)
        ins_layout.setContentsMargins(2, 2, 2, 2)
        ins_layout.setSpacing(12)

        self.inspector_lbl = QLabel("Frame 1 Inspector")
        self.inspector_lbl.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700;")
        ins_layout.addWidget(self.inspector_lbl)

        # 4 Zone Color Swatches & Quick Actions
        color_box = QGroupBox("Zone Colors and Quick Actions")
        color_box.setMinimumHeight(100) # Prevents compression to zero height
        c_layout = QVBoxLayout(color_box)
        c_layout.setContentsMargins(10, 16, 10, 10)
        c_layout.setSpacing(10)

        # Row 1: 4 Zone swatches
        z_row = QHBoxLayout()
        z_row.setSpacing(8)
        self.zone_buttons = []
        for i in range(4):
            btn = QPushButton(f"Zone {i+1}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(30)
            btn.setToolTip(f"Click to select an RGB color for Keyboard Zone {i+1} on this frame.")
            btn.setStyleSheet("QPushButton { background: #2A2D3A; color: white; border: 1px solid rgba(255,255,255,0.4); border-radius: 5px; font-weight: 700; font-size: 11px; margin: 0px; padding: 0px; }")
            btn.clicked.connect(lambda *args, z_idx=i: self.pick_zone_color(z_idx))
            self.zone_buttons.append(btn)
            z_row.addWidget(btn)
        c_layout.addLayout(z_row)

        # Row 2: Animation helpers in compact row
        a_row = QHBoxLayout()
        a_row.setSpacing(8)
        self.btn_set_all = QPushButton("Set All Zones")
        self.btn_set_all.setCursor(Qt.PointingHandCursor)
        self.btn_set_all.setFixedHeight(26)
        self.btn_set_all.setToolTip("Apply a single RGB color simultaneously across all 4 zones of this frame.")
        self.btn_set_all.setStyleSheet("QPushButton { background: #1C1E26; color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.4); font-weight: 600; padding: 2px 10px; } QPushButton:hover { background: #00E5FF; color: black; }")
        self.btn_set_all.clicked.connect(self.pick_all_zones_color)
        a_row.addWidget(self.btn_set_all, stretch=2)

        self.btn_shift_left = QPushButton("Shift Colors Left")
        self.btn_shift_left.setCursor(Qt.PointingHandCursor)
        self.btn_shift_left.setFixedHeight(26)
        self.btn_shift_left.setToolTip("Shift all zone colors one position leftwards across the keyboard layout.")
        self.btn_shift_left.setStyleSheet("QPushButton { background: #1C1E26; color: #E2E2E2; border: 1px solid rgba(255, 255, 255, 0.18); font-weight: 500; padding: 2px 8px; } QPushButton:hover { background: rgba(255, 255, 255, 0.12); }")
        self.btn_shift_left.clicked.connect(self.shift_colors_left)
        a_row.addWidget(self.btn_shift_left, stretch=1)

        self.btn_shift_right = QPushButton("Shift Colors Right")
        self.btn_shift_right.setCursor(Qt.PointingHandCursor)
        self.btn_shift_right.setFixedHeight(26)
        self.btn_shift_right.setToolTip("Shift all zone colors one position rightwards across the keyboard layout.")
        self.btn_shift_right.setStyleSheet("QPushButton { background: #1C1E26; color: #E2E2E2; border: 1px solid rgba(255, 255, 255, 0.18); font-weight: 500; padding: 2px 8px; } QPushButton:hover { background: rgba(255, 255, 255, 0.12); }")
        self.btn_shift_right.clicked.connect(self.shift_colors_right)
        a_row.addWidget(self.btn_shift_right, stretch=1)
        c_layout.addLayout(a_row)
        ins_layout.addWidget(color_box)

        # Consolidated Frame Timing & Transition Box
        time_box = QGroupBox("Frame Timing & Transition Settings")
        time_box.setMinimumHeight(92)
        t_layout = QVBoxLayout(time_box)
        t_layout.setContentsMargins(10, 16, 10, 10)
        t_layout.setSpacing(10)

        t_row1 = QHBoxLayout()
        t_row1.setSpacing(12)
        t_row1.addWidget(QLabel("Transition Style:"))
        self.trans_combo = QComboBox()
        self.trans_combo.addItems(["Smooth", "Quick (Instant)"])
        self.trans_combo.setFixedHeight(26)
        self.trans_combo.setMinimumWidth(125)
        self.trans_combo.setToolTip("Choose between smooth color blending or instant switching to the subsequent frame.")
        self.trans_combo.currentTextChanged.connect(self.on_trans_style_changed)
        t_row1.addWidget(self.trans_combo)

        t_row1.addWidget(QLabel("Hold Time (ms):"))
        self.hold_spin = QSpinBox()
        self.hold_spin.setRange(50, 20000)
        self.hold_spin.setSingleStep(50)
        self.hold_spin.setValue(600)
        self.hold_spin.setFixedHeight(26)
        self.hold_spin.setMinimumWidth(95)
        self.hold_spin.setToolTip("Duration (in milliseconds) to hold on this frame before starting transition.")
        self.hold_spin.valueChanged.connect(self.on_hold_time_changed)
        t_row1.addWidget(self.hold_spin)
        t_row1.addStretch()
        t_layout.addLayout(t_row1)

        t_row1b = QHBoxLayout()
        t_row1b.setSpacing(12)
        t_row1b.addWidget(QLabel("Transition Time (ms):"))
        self.trans_ms_spin = QSpinBox()
        self.trans_ms_spin.setRange(0, 10000)
        self.trans_ms_spin.setSingleStep(50)
        self.trans_ms_spin.setValue(400)
        self.trans_ms_spin.setFixedHeight(26)
        self.trans_ms_spin.setMinimumWidth(95)
        self.trans_ms_spin.setToolTip("Duration (in milliseconds) of the transition to the next frame.")
        self.trans_ms_spin.valueChanged.connect(self.on_trans_ms_changed)
        t_row1b.addWidget(self.trans_ms_spin)
        t_row1b.addStretch()
        t_layout.addLayout(t_row1b)

        t_row2 = QHBoxLayout()
        t_row2.setSpacing(10)
        self.btn_apply_trans_all = QPushButton("Apply Transition to All")
        self.btn_apply_trans_all.setFixedHeight(26)
        self.btn_apply_trans_all.setCursor(Qt.PointingHandCursor)
        self.btn_apply_trans_all.setToolTip("Instantly apply this Transition Style across every single frame in the timeline.")
        self.btn_apply_trans_all.setStyleSheet("QPushButton { background: #1C1E26; color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.35); font-weight: 600; padding: 2px 12px; } QPushButton:hover { background: #00E5FF; color: black; }")
        self.btn_apply_trans_all.clicked.connect(self.apply_trans_to_all)
        t_row2.addWidget(self.btn_apply_trans_all)

        self.btn_apply_hold_all = QPushButton("Apply Hold Time to All")
        self.btn_apply_hold_all.setFixedHeight(26)
        self.btn_apply_hold_all.setCursor(Qt.PointingHandCursor)
        self.btn_apply_hold_all.setToolTip("Instantly set this exact Hold Time (ms) across every single frame in the timeline.")
        self.btn_apply_hold_all.setStyleSheet("QPushButton { background: #1C1E26; color: #00E5FF; border: 1px solid rgba(0, 229, 255, 0.35); font-weight: 600; padding: 2px 12px; } QPushButton:hover { background: #00E5FF; color: black; }")
        self.btn_apply_hold_all.clicked.connect(self.apply_hold_to_all)
        t_row2.addWidget(self.btn_apply_hold_all)
        t_row2.addStretch()
        t_layout.addLayout(t_row2)
        ins_layout.addWidget(time_box)

        # Action Buttons
        act_row = QHBoxLayout()
        act_row.setSpacing(10)
        self.btn_dup_frame = QPushButton("Duplicate Frame")
        self.btn_dup_frame.setFixedHeight(28)
        self.btn_dup_frame.setCursor(Qt.PointingHandCursor)
        self.btn_dup_frame.setToolTip("Duplicate the currently selected frame into an identical new frame right after it.")
        self.btn_dup_frame.clicked.connect(self.duplicate_frame_action)
        act_row.addWidget(self.btn_dup_frame)

        self.btn_del_frame = QPushButton("Remove Frame")
        self.btn_del_frame.setFixedHeight(28)
        self.btn_del_frame.setCursor(Qt.PointingHandCursor)
        self.btn_del_frame.setToolTip("Delete the currently selected frame from the timeline sequence.")
        self.btn_del_frame.setStyleSheet("QPushButton { background: #23181D; color: #FF6B6B; border: 1px solid rgba(255, 107, 107, 0.4); padding: 4px 14px; } QPushButton:hover { background-color: #FF5252; color: white; border-color: #FF5252; }")
        self.btn_del_frame.clicked.connect(self.delete_frame_action)
        act_row.addWidget(self.btn_del_frame)

        act_row.addStretch()
        ins_layout.addLayout(act_row)
        ins_layout.addStretch()

        ins_scroll.setWidget(ins_content)
        ins_main_layout.addWidget(ins_scroll)

        right_box.addWidget(self.inspector_group, stretch=1)
        workspace_layout.addLayout(right_box, stretch=1)
        master_layout.addLayout(workspace_layout, stretch=1)

    def refresh_saved_effects_combo(self):
        self.effect_selector_combo.blockSignals(True)
        self.effect_selector_combo.clear()
        self.effect_selector_combo.addItem("-- Select Saved Effect --")
        effects = self.list_custom_effects()
        for eff in effects:
            self.effect_selector_combo.addItem(eff.get("name", "Untitled"), eff)
        self.effect_selector_combo.blockSignals(False)

    def rebuild_frame_list(self):
        if self.frames_list_layout.count() == len(self.frames):
            # Optimised update in place
            for idx, f_data in enumerate(self.frames):
                is_selected = (idx == self.selected_frame_idx)
                card = self.frames_list_layout.itemAt(idx).widget()
                if isinstance(card, FrameCardWidget):
                    card.update_card(f_data, is_selected)
            return

        while self.frames_list_layout.count():
            child = self.frames_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for idx, f_data in enumerate(self.frames):
            is_selected = (idx == self.selected_frame_idx)
            card = FrameCardWidget(idx, f_data, is_selected, self.select_frame)
            self.frames_list_layout.addWidget(card)

    def select_frame(self, index):
        if 0 <= index < len(self.frames):
            self.selected_frame_idx = index
            for i in range(self.frames_list_layout.count()):
                w = self.frames_list_layout.itemAt(i).widget()
                if isinstance(w, FrameCardWidget):
                    w.set_selected(w.index == index)
            self.load_frame_into_inspector(index)

    def load_frame_into_inspector(self, index):
        if index < 0 or index >= len(self.frames) or len(self.frames) == 0:
            self.inspector_lbl.setText("No Frames (Black Static Output)")
            for btn in self.zone_buttons:
                btn.setStyleSheet("background-color: #161822; color: #555555; border: 1px solid rgba(255,255,255,0.1); border-radius: 5px; margin: 0px; padding: 0px;")
                btn.setEnabled(False)
            self.btn_set_all.setEnabled(False)
            self.btn_shift_left.setEnabled(False)
            self.btn_shift_right.setEnabled(False)
            self.hold_spin.setEnabled(False)
            self.btn_apply_hold_all.setEnabled(False)
            self.trans_combo.setEnabled(False)
            self.btn_apply_trans_all.setEnabled(False)
            if hasattr(self, "trans_ms_spin"):
                self.trans_ms_spin.setEnabled(False)
            self.btn_dup_frame.setEnabled(False)
            self.btn_del_frame.setEnabled(False)
            return

        for btn in self.zone_buttons:
            btn.setEnabled(True)
        self.btn_set_all.setEnabled(True)
        self.btn_shift_left.setEnabled(True)
        self.btn_shift_right.setEnabled(True)
        self.hold_spin.setEnabled(True)
        self.btn_apply_hold_all.setEnabled(True)
        self.trans_combo.setEnabled(True)
        self.btn_apply_trans_all.setEnabled(True)
        if hasattr(self, "trans_ms_spin"):
            self.trans_ms_spin.setEnabled(True)
        self.btn_dup_frame.setEnabled(True)
        self.btn_del_frame.setEnabled(True)

        f = self.frames[index]
        self.inspector_lbl.setText(f"Frame {index + 1} Inspector")

        zones = f.get("zones", [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]])
        for z in range(4):
            z_rgb = zones[z] if z < len(zones) else [255, 252, 247]
            c = QColor(z_rgb[0], z_rgb[1], z_rgb[2])
            btn = self.zone_buttons[z]
            btn.setStyleSheet(f"background-color: {c.name()}; color: {'#000' if c.lightness() > 128 else '#FFF'}; font-weight: 700; border: 1px solid rgba(255, 255, 255, 0.6); border-radius: 5px; margin: 0px; padding: 0px;")

        self.hold_spin.blockSignals(True)
        self.hold_spin.setValue(f.get("hold_ms", 600))
        self.hold_spin.blockSignals(False)

        self.trans_combo.blockSignals(True)
        style = f.get("transition_style", "smooth")
        self.trans_combo.setCurrentText("Smooth" if style == "smooth" else "Quick (Instant)")
        self.trans_combo.blockSignals(False)
        
        if hasattr(self, "trans_ms_spin"):
            self.trans_ms_spin.blockSignals(True)
            self.trans_ms_spin.setValue(f.get("transition_ms", 400))
            self.trans_ms_spin.blockSignals(False)

    def pick_zone_color(self, zone_idx):
        if self.selected_frame_idx < 0 or self.selected_frame_idx >= len(self.frames):
            return
        curr_zones = self.frames[self.selected_frame_idx].get("zones", [[0, 0, 0] for _ in range(4)])
        c_rgb = curr_zones[zone_idx] if zone_idx < len(curr_zones) else [0, 0, 0]
        initial_color = QColor(c_rgb[0], c_rgb[1], c_rgb[2])

        color = QColorDialog.getColor(initial_color, self, f"Select Color for Zone {zone_idx+1}")
        if color.isValid():
            curr_zones[zone_idx] = [color.red(), color.green(), color.blue()]
            self.frames[self.selected_frame_idx]["zones"] = curr_zones
            self.load_frame_into_inspector(self.selected_frame_idx)
            self.rebuild_frame_list()
            self.live_update_hardware()

    def pick_all_zones_color(self):
        if self.selected_frame_idx < 0 or self.selected_frame_idx >= len(self.frames):
            return
        curr_zones = self.frames[self.selected_frame_idx].get("zones", [[0, 0, 0] for _ in range(4)])
        c_rgb = curr_zones[0] if len(curr_zones) > 0 else [0, 0, 0]
        initial_color = QColor(c_rgb[0], c_rgb[1], c_rgb[2])

        color = QColorDialog.getColor(initial_color, self, "Select Color for All Zones")
        if color.isValid():
            new_rgb = [color.red(), color.green(), color.blue()]
            self.frames[self.selected_frame_idx]["zones"] = [new_rgb[:] for _ in range(4)]
            self.load_frame_into_inspector(self.selected_frame_idx)
            self.rebuild_frame_list()
            self.live_update_hardware()

    def shift_colors_left(self):
        if self.selected_frame_idx < 0 or self.selected_frame_idx >= len(self.frames):
            return
        curr_zones = self.frames[self.selected_frame_idx].get("zones", [[0, 0, 0] for _ in range(4)])
        if len(curr_zones) == 4:
            shifted = [curr_zones[1], curr_zones[2], curr_zones[3], curr_zones[0]]
            self.frames[self.selected_frame_idx]["zones"] = shifted
            self.load_frame_into_inspector(self.selected_frame_idx)
            self.rebuild_frame_list()
            self.live_update_hardware()

    def shift_colors_right(self):
        if self.selected_frame_idx < 0 or self.selected_frame_idx >= len(self.frames):
            return
        curr_zones = self.frames[self.selected_frame_idx].get("zones", [[0, 0, 0] for _ in range(4)])
        if len(curr_zones) == 4:
            shifted = [curr_zones[3], curr_zones[0], curr_zones[1], curr_zones[2]]
            self.frames[self.selected_frame_idx]["zones"] = shifted
            self.load_frame_into_inspector(self.selected_frame_idx)
            self.rebuild_frame_list()
            self.live_update_hardware()

    def on_hold_time_changed(self, value):
        if 0 <= self.selected_frame_idx < len(self.frames):
            self.frames[self.selected_frame_idx]["hold_ms"] = value
            self.rebuild_frame_list()
            self.live_update_hardware()

    def on_trans_style_changed(self, text):
        if 0 <= self.selected_frame_idx < len(self.frames):
            style = "smooth" if "Smooth" in text else "quick"
            self.frames[self.selected_frame_idx]["transition_style"] = style
            self.rebuild_frame_list()
            self.live_update_hardware()

    def on_trans_ms_changed(self, value):
        if 0 <= self.selected_frame_idx < len(self.frames):
            self.frames[self.selected_frame_idx]["transition_ms"] = value
            # self.rebuild_frame_list() # Not strictly necessary to rebuild frame list since we don't show trans_ms on the card, but let's be consistent
            self.live_update_hardware()

    def apply_hold_to_all(self):
        if 0 <= self.selected_frame_idx < len(self.frames):
            target_hold = self.frames[self.selected_frame_idx].get("hold_ms", 600)
            for f in self.frames:
                f["hold_ms"] = target_hold
            self.rebuild_frame_list()
            self.live_update_hardware()

    def apply_trans_to_all(self):
        if 0 <= self.selected_frame_idx < len(self.frames):
            target_style = self.frames[self.selected_frame_idx].get("transition_style", "smooth")
            for f in self.frames:
                f["transition_style"] = target_style
            self.rebuild_frame_list()
            self.live_update_hardware()

    def add_frame_action(self):
        if self.frames and self.selected_frame_idx >= 0:
            ref = self.frames[self.selected_frame_idx]
            new_frame = {
                "zones": [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]],
                "hold_ms": ref.get("hold_ms", 600),
                "transition_style": ref.get("transition_style", "smooth"),
                "transition_ms": ref.get("transition_ms", 400),
            }
        else:
            new_frame = {
                "zones": [[0, 0, 0], [0, 0, 0], [0, 0, 0], [0, 0, 0]],
                "hold_ms": 600,
                "transition_style": "smooth",
                "transition_ms": 400,
            }
        self.frames.append(new_frame)
        self.selected_frame_idx = len(self.frames) - 1
        self.rebuild_frame_list()
        self.load_frame_into_inspector(self.selected_frame_idx)
        self.live_update_hardware()

    def duplicate_frame_action(self):
        if 0 <= self.selected_frame_idx < len(self.frames):
            copied = dict(self.frames[self.selected_frame_idx])
            copied["zones"] = [list(z) for z in copied["zones"]]
            self.frames.insert(self.selected_frame_idx + 1, copied)
            self.selected_frame_idx += 1
            self.rebuild_frame_list()
            self.load_frame_into_inspector(self.selected_frame_idx)
            self.live_update_hardware()

    def delete_frame_action(self):
        if len(self.frames) == 0:
            return
        if 0 <= self.selected_frame_idx < len(self.frames):
            self.frames.pop(self.selected_frame_idx)
            self.selected_frame_idx = max(0, self.selected_frame_idx - 1) if self.frames else -1
            self.rebuild_frame_list()
            self.load_frame_into_inspector(self.selected_frame_idx)
            self.live_update_hardware()

    def save_effect_action(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid effect name.")
            return
        if self.effect_selector_combo.findText(name) != -1:
            reply = QMessageBox.question(self, "Overwrite?", f"An effect named '{name}' already exists. Overwrite?", QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No: return
        data = {
            "name": name,
            "loop": True,
            "default_speed": self.default_speed_slider.value(),
            "default_brightness": self.default_bright_slider.value(),
            "frames": self.frames,
        }
        saved_path = self.save_custom_effect(data)
        self.refresh_saved_effects_combo()
        if self.parent_app and hasattr(self.parent_app, "reload_custom_effects"):
            self.parent_app.reload_custom_effects()
        QMessageBox.information(self, "Saved", f"Effect '{name}' saved successfully to AppData!\nSaved to: {saved_path}")

    def delete_effect_action(self):
        name = self.name_input.text().strip()
        data = self.effect_selector_combo.currentData()
        deleted = False
        if data and isinstance(data, dict):
            filepath = data.get("filepath")
            if filepath and os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    deleted = True
                except Exception as e:
                    print(f"Error deleting file {filepath}: {e}")
        if name and not deleted:
            deleted = self.delete_custom_effect(name)
            
        if deleted:
            self.refresh_saved_effects_combo()
            if self.parent_app and hasattr(self.parent_app, "reload_custom_effects"):
                self.parent_app.reload_custom_effects()
            QMessageBox.information(self, "Deleted", "The selected effect has been permanently deleted.")
        else:
            QMessageBox.warning(self, "Delete Failed", "Could not find or delete the specified effect file.")

    def on_load_effect_selected(self, index):
        data = self.effect_selector_combo.currentData()
        if data and isinstance(data, dict):
            self.name_input.setText(data.get("name", ""))
            self.default_speed_slider.setValue(data.get("default_speed", 50))
            self.default_bright_slider.setValue(data.get("default_brightness", 100))
            import copy
            self.frames = copy.deepcopy(data.get("frames", self.frames))
            self.selected_frame_idx = 0 if len(self.frames) > 0 else -1
            self.rebuild_frame_list()
            self.load_frame_into_inspector(self.selected_frame_idx)
            self.live_update_hardware()

    def import_json_action(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Custom Effect JSON", "", "JSON Files (*.json)")
        if path and os.path.exists(path):
            try:
                import json
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "frames" not in data or not isinstance(data["frames"], list):
                        raise ValueError("Missing or invalid 'frames' list.")
                    for frame in data["frames"]:
                        if "zones" not in frame or not isinstance(frame["zones"], list): raise ValueError("Invalid zones format.")
                        if "hold_ms" not in frame or not isinstance(frame["hold_ms"], (int, float)) or frame["hold_ms"] < 0: raise ValueError("Invalid hold_ms.")
                        if "transition_style" not in frame: raise ValueError("Missing transition_style.")
                    if "frames" in data:
                        import copy
                        data["frames"] = copy.deepcopy(data["frames"])
                        self.name_input.setText(data.get("name", os.path.splitext(os.path.basename(path))[0]))
                        self.default_speed_slider.setValue(data.get("default_speed", 50))
                        self.default_bright_slider.setValue(data.get("default_brightness", 100))
                        self.frames = data["frames"]
                        self.selected_frame_idx = 0 if len(self.frames) > 0 else -1
                        self.rebuild_frame_list()
                        self.load_frame_into_inspector(self.selected_frame_idx)
                        self.live_update_hardware()
                        QMessageBox.information(self, "Imported", "Custom effect JSON imported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Failed to import JSON: {e}")

    def export_json_action(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Custom Effect JSON", f"{self.name_input.text().strip()}.json", "JSON Files (*.json)")
        if path:
            try:
                import json
                data = {
                    "name": self.name_input.text().strip(),
                    "loop": True,
                    "default_speed": self.default_speed_slider.value(),
                    "default_brightness": self.default_bright_slider.value(),
                    "frames": self.frames,
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                QMessageBox.information(self, "Exported", f"Exported successfully to {path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export JSON: {e}")


if __name__ == '__main__':
    pass
