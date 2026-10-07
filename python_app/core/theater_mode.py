"""
Theater Mode (Cinema Auto-Dim) Subsystem for 4-Zone-Keyboard-RGB-Toolkit
Detects fullscreen video playback across browsers and media players,
and smoothly controls RGB brightness fading and wake-up interactions.
"""

import ctypes
from ctypes import wintypes
import time
from PySide6.QtCore import QObject, Signal, QTimer, QAbstractNativeEventFilter

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

WS_CAPTION = 0x00C00000

def is_foreground_fullscreen() -> bool:
    """
    Checks if the currently active foreground window is in true fullscreen mode.
    Excludes regular maximized and windowed applications by checking for WS_CAPTION.
    """
    hwnd = user32.GetForegroundWindow()
    if not hwnd or not user32.IsWindow(hwnd):
        return False

    class_buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, class_buf, 256)
    cls = class_buf.value
    if cls in IGNORED_WINDOW_CLASSES:
        return False

    # If the window has WS_CAPTION (title bar / tabs / window control buttons),
    # it is a regular windowed or maximized window, NOT true fullscreen.
    GWL_STYLE = -16
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    if (style & WS_CAPTION) == WS_CAPTION:
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
    covers_screen = (
        rect.left <= mi.rcMonitor.left and
        rect.top <= mi.rcMonitor.top and
        rect.right >= mi.rcMonitor.right and
        rect.bottom >= mi.rcMonitor.bottom
    )
    return covers_screen

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

# Windows 8+ Console Display State (0 = Off, 1 = On, 2 = Dimmed)
# 6FE69556-704A-47A0-8F24-C28D936FDA47
GUID_CONSOLE_DISPLAY_STATE = GUID(
    0x6FE69556,
    0x704A,
    0x47A0,
    (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47),
)

# Windows Monitor Power On (0 = Off, 1 = On)
# 02731015-4510-4526-99E6-E5A17EBD1AEA
GUID_MONITOR_POWER_ON = GUID(
    0x02731015,
    0x4510,
    0x4526,
    (ctypes.c_ubyte * 8)(0x99, 0xE6, 0xE5, 0xA1, 0x7E, 0xBD, 0x1A, 0xEA),
)

# Windows Session Display Status (0 = Off, 1 = On, 2 = Dimmed)
# 2B84C20E-AD23-4DDF-93DB-05FFBD7EFCA5
GUID_SESSION_DISPLAY_STATUS = GUID(
    0x2B84C20E,
    0xAD23,
    0x4DDF,
    (ctypes.c_ubyte * 8)(0x93, 0xDB, 0x05, 0xFF, 0xBD, 0x7E, 0xFC, 0xA5),
)

class POWERBROADCAST_SETTING(ctypes.Structure):
    _fields_ = [
        ("PowerSetting", GUID),
        ("DataLength", ctypes.c_uint32),
        ("Data", ctypes.c_ubyte * 4),
    ]

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
    display standby), screen locks, or system enters sleep.

    Signals are emitted on the Qt thread.
    """
    display_turned_off = Signal()   # emitted when display goes off
    display_turned_on  = Signal()   # emitted when display comes back on

    def __init__(self, parent=None):
        super().__init__(parent)
        self.enabled = False
        self._display_is_off = False

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)
        print(f"[DisplayOffSync] Manager set_enabled: {self.enabled}")
        if not self.enabled and self._display_is_off:
            self._display_is_off = False

    def handle_power_setting_change(self, power_guid: GUID, data_value: int):
        """
        Called when a WM_POWERBROADCAST PBT_POWERSETTINGCHANGE arrives.
        data_value: 0 = off, 1 = on, 2 = dimmed
        """
        is_display_guid = (
            guid_equals(power_guid, GUID_CONSOLE_DISPLAY_STATE)
            or guid_equals(power_guid, GUID_MONITOR_POWER_ON)
            or guid_equals(power_guid, GUID_SESSION_DISPLAY_STATUS)
        )
        if not is_display_guid:
            return

        print(f"[DisplayOffSync] Display state notification: value={data_value} (enabled={self.enabled})")
        if not self.enabled:
            return

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

    def handle_session_change(self, wts_event_code: int):
        """
        Called on WM_WTSSESSION_CHANGE:
        0x7 = WTS_SESSION_LOCK (Screen locked with Win+L)
        0x8 = WTS_SESSION_UNLOCK (Screen unlocked)
        """
        if not self.enabled:
            return
        if wts_event_code == 0x7:  # WTS_SESSION_LOCK
            if not self._display_is_off:
                self._display_is_off = True
                print("[DisplayOffSync] Screen locked (Win+L) -> emitting display_turned_off")
                self.display_turned_off.emit()
        elif wts_event_code == 0x8:  # WTS_SESSION_UNLOCK
            if self._display_is_off:
                self._display_is_off = False
                print("[DisplayOffSync] Screen unlocked -> emitting display_turned_on")
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
                print("[DisplayOffSync] Sleep / Monitor-Power-Off detected -> emitting display_turned_off")
                self.display_turned_off.emit()
        else:
            if self._display_is_off:
                self._display_is_off = False
                print("[DisplayOffSync] Resume / Monitor-Power-On detected -> emitting display_turned_on")
                self.display_turned_on.emit()

    @property
    def is_display_off(self) -> bool:
        return self._display_is_off


class DisplayOffEventFilter(QAbstractNativeEventFilter):
    """
    Application-level native Windows event filter that intercepts
    WM_POWERBROADCAST and WM_WTSSESSION_CHANGE before window dispatching.
    This guarantees delivery even when the window is hidden or minimized to tray.
    """
    def __init__(self, manager: DisplayOffManager):
        super().__init__()
        self.manager = manager

    def nativeEventFilter(self, eventType, message):
        try:
            msg = wintypes.MSG.from_address(message.__int__())
            # WM_POWERBROADCAST = 0x0218
            if msg.message == 0x0218:
                if msg.wParam == 0x8013 and msg.lParam:  # PBT_POWERSETTINGCHANGE
                    ps = POWERBROADCAST_SETTING.from_address(msg.lParam)
                    data_val = int(ps.Data[0])
                    self.manager.handle_power_setting_change(ps.PowerSetting, data_val)
                elif msg.wParam == 0x0004:  # PBT_APMSUSPEND
                    self.manager.handle_sleep_state(True)
                elif msg.wParam in (0x0007, 0x0012):  # PBT_APMRESUME...
                    self.manager.handle_sleep_state(False)
            # WM_WTSSESSION_CHANGE = 0x02B1
            elif msg.message == 0x02B1:
                self.manager.handle_session_change(msg.wParam)
            # WM_SYSCOMMAND = 0x0112
            elif msg.message == 0x0112:
                cmd = msg.wParam & 0xFFF0
                if cmd == 0xF170:  # SC_MONITORPOWER
                    if msg.lParam == 2:
                        self.manager.handle_sleep_state(True)
                    elif msg.lParam == -1:
                        self.manager.handle_sleep_state(False)
        except Exception as e:
            print(f"[DisplayOffSync] Event filter error: {e}")
        return False, 0
