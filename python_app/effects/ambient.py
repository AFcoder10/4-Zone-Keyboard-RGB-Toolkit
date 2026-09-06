import colorsys
import time
from typing import List, Dict, Any
from core.base import BaseEffect
from utils.chroma_utils import get_chroma_weighted_zone_colors, HAS_NUMPY

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import mss
    HAS_MSS = True
    try:
        import mss.windows
        # Disable CAPTUREBLT to prevent mouse cursor flickering during rapid screen captures (fixes Issue #12)
        mss.windows.CAPTUREBLT = 0
    except (ImportError, AttributeError):
        pass
except ImportError:
    HAS_MSS = False

class AmbientEffect(BaseEffect):
    # Dynamic smoothing: overridden per-frame in update() based on FPS
    # This matches the original v2.9 formula: smooth_amount = 15.0 / fps
    # At 30 FPS → 0.5 (smooth, organic transitions between frames)
    # At 60 FPS → 0.25 (faster response but still buttery)
    preferred_smoothing = 0.5

    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.sct = None  # Created lazily on the render thread
        self._last_capture_time = 0.0
        self._cached_colors = [0] * 12
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Ambient Screen Color"

    @property
    def preferred_fps(self) -> int:
        return max(5, min(60, self.config.get("ambient_fps", 30)))

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
        
        # Jitter tolerance (0.85x) prevents frame-skipping when manager runs at exact requested FPS
        if now - self._last_capture_time < capture_interval * 0.85:
            return self._cached_colors[:]

        self._last_capture_time = now

        # Dynamic smoothing: matches the original v2.9 formula exactly
        # smooth_amount = 15.0 / fps → at 30fps=0.5, at 60fps=0.25
        # Higher = more of the OLD color retained = smoother, more organic transitions
        self.preferred_smoothing = max(0.01, min(1.0, 15.0 / ambient_fps))

        target_colors = [0] * 12
        vib_mult = self.config.get("vibrance", 15) / 10.0

        if HAS_MSS and HAS_PIL:
            try:
                self._ensure_sct()
                monitor = self.sct.monitors[1]
                # Capture full screen
                bbox = {
                    "top": monitor["top"],
                    "left": monitor["left"],
                    "width": monitor["width"],
                    "height": monitor["height"]
                }
                sct_img = self.sct.grab(bbox)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                # Use chroma-weighted averaging if numpy is available for richer colors
                if HAS_NUMPY:
                    target_colors = get_chroma_weighted_zone_colors(img, vib_mult)
                else:
                    # Fallback: simple BOX resize to 4x1 (original v2.9 method)
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