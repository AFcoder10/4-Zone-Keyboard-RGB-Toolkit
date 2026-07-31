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

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

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
        if not HAS_MSS or not HAS_PIL or not HAS_NUMPY:
            print("[Ambient] mss, Pillow, and numpy are required for Ambient Screen Color.")
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
                
                is_full_screen = self.config.get("ambient_full_screen", False)
                if is_full_screen:
                    bbox = {
                        "top": monitor["top"],
                        "left": monitor["left"],
                        "width": monitor["width"],
                        "height": monitor["height"]
                    }
                else:
                    bbox = {
                        "top": monitor["top"] + monitor["height"] - 100,
                        "left": monitor["left"],
                        "width": monitor["width"],
                        "height": 100
                    }
                sct_img = self.sct.grab(bbox)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                if is_full_screen:
                    # Fast downscale to a manageable size
                    img = img.resize((64, 16), Image.Resampling.BILINEAR)
                    
                    # Convert to numpy array of float32 for fast math
                    arr = np.array(img, dtype=np.float32)
                    
                    # Split into 4 vertical zones
                    zones = np.array_split(arr, 4, axis=1)
                    
                    for i in range(4):
                        zone = zones[i]
                        # Flatten spatial dimensions
                        pixels = zone.reshape(-1, 3)
                        r = pixels[:, 0]
                        g = pixels[:, 1]
                        b = pixels[:, 2]
                        
                        # Calculate chroma and brightness for weighting
                        mx = np.maximum(np.maximum(r, g), b)
                        mn = np.minimum(np.minimum(r, g), b)
                        chroma = mx - mn
                        
                        # Weight = chroma * brightness + epsilon to avoid div-by-zero
                        weights = (chroma * mx) + 0.001
                        
                        # Calculate the weighted average
                        avg_r = np.average(r, weights=weights)
                        avg_g = np.average(g, weights=weights)
                        avg_b = np.average(b, weights=weights)

                        h, s, v = colorsys.rgb_to_hsv(avg_r / 255.0, avg_g / 255.0, avg_b / 255.0)
                        final_r, final_g, final_b = colorsys.hsv_to_rgb(h, min(1.0, s * vib_mult), v)

                        target_colors[i * 3] = int(final_r * 255)
                        target_colors[i * 3 + 1] = int(final_g * 255)
                        target_colors[i * 3 + 2] = int(final_b * 255)
                else:
                    # Old BOX method for Bottom Only Ambience
                    img = img.resize((4, 1), Image.Resampling.BOX)
                    pixels = [img.getpixel((i, 0)) for i in range(4)]

                    for i in range(4):
                        r, g, b = pixels[i]
                        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                        final_r, final_g, final_b = colorsys.hsv_to_rgb(h, min(1.0, s * vib_mult), v)

                        target_colors[i * 3] = int(final_r * 255)
                        target_colors[i * 3 + 1] = int(final_g * 255)
                        target_colors[i * 3 + 2] = int(final_b * 255)
            except Exception as e:
                print(f"[Ambient] Screen capture error: {e}")

        self._cached_colors = target_colors[:]
        return target_colors

from effects import register_effect
register_effect("Ambient Screen Color", AmbientEffect)
