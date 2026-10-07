"""
Theater Mode (Cinema Auto-Dim) Subsystem for 4-Zone-Keyboard-RGB-Toolkit
Detects fullscreen video playback across browsers and media players,
and smoothly controls RGB brightness fading and wake-up interactions.
"""

import ctypes
from ctypes import wintypes
import time
from PySide6.QtCore import QObject, Signal, QTimer

user32 = ctypes.windll.user32
powrprof = ctypes.windll.powrprof

class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG),
    ]

class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('rcMonitor', RECT),
        ('rcWork', RECT),
        ('dwFlags', wintypes.DWORD),
    ]

class POINT(ctypes.Structure):
    _fields_ = [
        ('x', wintypes.LONG),
        ('y', wintypes.LONG),
    ]

# Windows execution state flags
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

IGNORED_WINDOW_CLASSES = {
    "Progman",
    "WorkerW",
    "Shell_TrayWnd",
    "Shell_SecondaryTrayWnd",
}

def is_display_sleep_inhibited() -> bool:
    """
    Checks if any active process has requested ES_DISPLAY_REQUIRED.
    Browsers and video players issue this during active video playback,
    while audio/music players (Spotify, Apple Music) do NOT.
    """
    SystemExecutionState = 16
    exec_state = wintypes.ULONG()
    res = powrprof.CallNtPowerInformation(
        SystemExecutionState,
        None,
        0,
        ctypes.byref(exec_state),
        ctypes.sizeof(exec_state)
    )
    if res == 0:
        return bool(exec_state.value & ES_DISPLAY_REQUIRED)
    return False

def is_foreground_fullscreen() -> bool:
    """
    Checks if the currently active foreground window occupies the entire monitor area.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False

    class_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buf, 256)
    cls = class_buf.value
    if cls in IGNORED_WINDOW_CLASSES:
        return False

    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False

    h_mon = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST = 2
    if not h_mon:
        return False

    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(h_mon, ctypes.byref(mi)):
        return False

    # Check bounds against physical display monitor area
    return (
        rect.left <= mi.rcMonitor.left and
        rect.top <= mi.rcMonitor.top and
        rect.right >= mi.rcMonitor.right and
        rect.bottom >= mi.rcMonitor.bottom
    )

def get_cursor_pos():
    pt = POINT()
    if user32.GetCursorPos(ctypes.byref(pt)):
        return pt.x, pt.y
    return 0, 0


class TheaterModeManager(QObject):
    """
    Monitors theater conditions (fullscreen + video playing) and smoothly fades
    the master brightness down over 5.0 seconds.
    Wakes up on mouse movement, keyboard interaction, video pause, or exiting fullscreen.
    """
    dim_factor_changed = Signal(float)  # 0.0 (fully dimmed) to 1.0 (normal brightness)
    state_changed = Signal(bool)        # True when cinema dimmed, False when normal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = False
        self.dim_factor = 1.0
        self.is_dimmed = False

        self.last_mouse_pos = get_cursor_pos()
        self.last_user_activity = time.monotonic()
        self.last_dim_target = 1.0

        # High-level condition check timer (runs every 1000ms)
        self.check_timer = QTimer(self)
        self.check_timer.setInterval(1000)
        self.check_timer.timeout.connect(self._check_theater_condition)

        # Smooth animation timer (runs at ~30 FPS / 33ms)
        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(33)
        self.anim_timer.timeout.connect(self._animate_step)

        # 2.5s fade down (0.0132 per 33ms tick), 1.0s fade up (0.033 per tick)
        self.step_down = 33.0 / 2500.0  # ~0.0132
        self.step_up = 33.0 / 1000.0    # ~0.033

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if self.enabled:
            self.last_mouse_pos = get_cursor_pos()
            self.last_user_activity = time.monotonic()
            if not self.check_timer.isActive():
                self.check_timer.start()
        else:
            self.check_timer.stop()
            self.wake_up(force=True)

    def on_user_activity(self):
        """Called when a keypress or global hotkey is triggered."""
        self.last_user_activity = time.monotonic()
        if self.is_dimmed or self.dim_factor < 1.0:
            self.wake_up()

    def wake_up(self, force=False):
        """Wakes up lighting back to full brightness."""
        self.last_dim_target = 1.0
        if force:
            self.dim_factor = 1.0
            self.is_dimmed = False
            self.anim_timer.stop()
            self.dim_factor_changed.emit(1.0)
            self.state_changed.emit(False)
        else:
            if not self.anim_timer.isActive():
                self.anim_timer.start()

    def _check_theater_condition(self):
        if not self.enabled:
            return

        # Skip theater dimming if current mode is Ambient Screen Color
        parent = self.parent()
        if parent:
            current_mode = getattr(parent, "current_mode_name", "")
            if "ambient" in str(current_mode).lower():
                if self.is_dimmed or self.dim_factor < 1.0:
                    self.wake_up()
                return

        # 1. Check mouse movement threshold (wake up on move > 15px)
        curr_x, curr_y = get_cursor_pos()
        last_x, last_y = self.last_mouse_pos
        dx = abs(curr_x - last_x)
        dy = abs(curr_y - last_y)
        self.last_mouse_pos = (curr_x, curr_y)

        if dx > 15 or dy > 15:
            self.last_user_activity = time.monotonic()
            if self.is_dimmed or self.dim_factor < 1.0:
                self.wake_up()
                return

        # 2. Check if user recently pressed a key (within 3 seconds buffer)
        if time.monotonic() - self.last_user_activity < 3.0:
            if self.is_dimmed or self.dim_factor < 1.0:
                self.wake_up()
            return

        # 3. Check fullscreen and display video playback lock
        is_fs = is_foreground_fullscreen()
        is_video = is_display_sleep_inhibited()

        if is_fs and is_video:
            # Theater conditions met! Fade lights down to 0.0
            self.last_dim_target = 0.0
            if not self.anim_timer.isActive():
                self.anim_timer.start()
        else:
            # Video paused, closed, or user exited fullscreen -> restore lights
            if self.is_dimmed or self.dim_factor < 1.0:
                self.wake_up()

    def _animate_step(self):
        target = self.last_dim_target
        if target < self.dim_factor:
            # Dims down smoothly over 2.5 seconds
            self.dim_factor = max(0.0, self.dim_factor - self.step_down)
        elif target > self.dim_factor:
            # Fades up smoothly over 1 second
            self.dim_factor = min(1.0, self.dim_factor + self.step_up)

        self.dim_factor_changed.emit(self.dim_factor)

        if self.dim_factor <= 0.05 and not self.is_dimmed:
            self.is_dimmed = True
            self.state_changed.emit(True)
        elif self.dim_factor >= 0.95 and self.is_dimmed:
            self.is_dimmed = False
            self.state_changed.emit(False)

        # Stop animation once reached target
        if abs(self.dim_factor - target) < 0.001:
            self.dim_factor = target
            self.dim_factor_changed.emit(self.dim_factor)
            self.anim_timer.stop()


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]

# Windows GUID for Console Display State (Screen Off / Screen On / Screen Dimmed)
GUID_CONSOLE_DISPLAY_STATE = GUID(
    0x02731046,
    0x4510,
    0x4526,
    (ctypes.c_ubyte * 8)(0x99, 0xE6, 0xE5, 0xA1, 0x7E, 0xBD, 0x1A, 0xEA),
)

# Windows GUID for Session Display Status (Screen Off / Screen On / Screen Dimmed)
GUID_SESSION_DISPLAY_STATUS = GUID(
    0x2B84C10B,
    0x65DC,
    0x4693,
    (ctypes.c_ubyte * 8)(0xBE, 0x0A, 0xA2, 0x61, 0xE1, 0x21, 0xD1, 0x62),
)

def guid_equals(a, b):
    try:
        return (
            a.Data1 == b.Data1
            and a.Data2 == b.Data2
            and a.Data3 == b.Data3
            and bytes(a.Data4) == bytes(b.Data4)
        )
    except Exception:
        return False


class DisplayOffManager(QObject):
    """
    Detects when the Windows console/display turns off (monitor power-off or
    display standby), and when it turns back on.

    Uses WM_POWERBROADCAST + GUID_CONSOLE_DISPLAY_STATE / GUID_SESSION_DISPLAY_STATUS
    via the parent window's nativeEvent(). Signals are emitted on the Qt thread.

    Display state values from Windows:
        0 = Display off
        1 = Display on
        2 = Display dimmed
    """
    display_turned_off = Signal()   # emitted when display goes off
    display_turned_on  = Signal()   # emitted when display comes back on

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = False
        self._display_is_off = False

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        if not self.enabled and self._display_is_off:
            # When the feature is disabled while display is off, treat display as on
            self._display_is_off = False

    def handle_power_setting_change(self, power_guid: GUID, data_value: int):
        """
        Called by the main window's nativeEvent when a WM_POWERBROADCAST
        PBT_POWERSETTINGCHANGE arrives.
        data_value: 0 = off, 1 = on, 2 = dimmed
        """
        if not self.enabled:
            return
        is_display_guid = (
            guid_equals(power_guid, GUID_CONSOLE_DISPLAY_STATE) or
            guid_equals(power_guid, GUID_SESSION_DISPLAY_STATUS)
        )
        if not is_display_guid:
            return

        print(f"[DisplayOffSync] Display state notification: value={data_value}")
        if data_value == 0:
            if not self._display_is_off:
                self._display_is_off = True
                print("[DisplayOffSync] Display turned OFF -> emitting display_turned_off")
                self.display_turned_off.emit()
        else:
            if self._display_is_off:
                self._display_is_off = False
                print("[DisplayOffSync] Display turned ON/DIMMED -> emitting display_turned_on")
                self.display_turned_on.emit()

    def handle_sleep_state(self, is_sleep_or_off: bool):
        """
        Called when system sleep/suspend or SC_MONITORPOWER is signaled.
        """
        if not self.enabled:
            return
        if is_sleep_or_off:
            if not self._display_is_off:
                self._display_is_off = True
                print("[DisplayOffSync] System suspend or monitor power-off -> emitting display_turned_off")
                self.display_turned_off.emit()
        else:
            if self._display_is_off:
                self._display_is_off = False
                print("[DisplayOffSync] System resume or monitor power-on -> emitting display_turned_on")
                self.display_turned_on.emit()

    @property
    def is_display_off(self) -> bool:
        return self._display_is_off
