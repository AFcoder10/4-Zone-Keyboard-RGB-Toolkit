import colorsys
import time
from typing import List, Dict, Any
from core.base import BaseEffect

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

class AmbientEffect(BaseEffect):
    # Ambient should feel responsive — low smoothing so colors track the screen closely
    preferred_smoothing = 0.4

    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.sct = None  # Created lazily on the render thread
        self._last_capture_time = 0.0
        self._cached_colors = [0] * 12
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Ambient Screen Color"

    def start(self) -> bool:
        if not HAS_MSS or not HAS_PIL:
            print("[Ambient] mss and Pillow are required for Ambient Screen Color.")
            return False
        # Don't create mss here — it uses thread-local GDI handles on Windows.
        # The instance must be created on the same thread that calls grab().
        self._running = True
        self._last_capture_time = 0.0
        self._cached_colors = [0] * 12
        return True

    def stop(self) -> None:
        self._running = False
        if self.sct:
            try:
                self.sct.close()
            except Exception:
                pass
            self.sct = None

    def _ensure_sct(self):
        """Lazily create the mss instance on the calling (render) thread."""
        if self.sct is None:
            self.sct = mss.mss()

    def update(self, dt: float) -> List[int]:
        # Read ambient_fps from config (default 30, range 5-60)
        ambient_fps = max(5, min(60, self.config.get("ambient_fps", 30)))
        capture_interval = 1.0 / ambient_fps

        now = time.monotonic()
        
        # Throttle: only capture when enough time has passed since last capture
        if now - self._last_capture_time < capture_interval:
            return self._cached_colors[:]

        self._last_capture_time = now
        target_colors = [0] * 12
        vib_mult = self.config.get("vibrance", 15) / 10.0

        if HAS_MSS and HAS_PIL:
            try:
                self._ensure_sct()
                monitor = self.sct.monitors[1]
                bbox = {
                    "top": monitor["top"] + monitor["height"] - 100,
                    "left": monitor["left"],
                    "width": monitor["width"],
                    "height": 100
                }
                sct_img = self.sct.grab(bbox)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                img = img.resize((4, 1), Image.Resampling.BOX)
                pixels = [img.getpixel((i, 0)) for i in range(4)]

                for i in range(4):
                    r, g, b = pixels[i]
                    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                    r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s * vib_mult), v)

                    target_colors[i * 3] = int(r * 255)
                    target_colors[i * 3 + 1] = int(g * 255)
                    target_colors[i * 3 + 2] = int(b * 255)
            except Exception as e:
                print(f"[Ambient] Screen capture error: {e}")

        self._cached_colors = target_colors[:]
        return target_colors

from effects import register_effect
register_effect("Ambient Screen Color", AmbientEffect)
