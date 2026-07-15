import math
import colorsys
from typing import List, Dict, Any
from core.base import BaseEffect

class ScannerEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.scanner_pos = 0.0
        self.scanner_dir = 1.0  # 1 for right, -1 for left
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Scanner (Cylon)"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        self.scanner_pos = 0.0
        self.scanner_dir = 1.0
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        self.t += dt
        
        speed = self.config.get("speed", 50)
        rainbow_mode = self.config.get("scanner_rainbow", False)
        zone_colors = self.config.get("zone_colors", [[255, 0, 0]] * 4)

        # Move scanner position
        # Multiplying dt by 30 to match original fixed 30fps step sizes (sweep_speed was added per frame)
        sweep_speed = (0.05 + (speed / 100.0) * 0.15) * (dt * 30.0)
        self.scanner_pos += self.scanner_dir * sweep_speed

        # Bounce logic (index 0 to 3)
        if self.scanner_pos > 3.0:
            self.scanner_pos = 3.0
            self.scanner_dir = -1.0
        elif self.scanner_pos < 0.0:
            self.scanner_pos = 0.0
            self.scanner_dir = 1.0

        target_colors = [0] * 12

        for i in range(4):
            dist = abs(self.scanner_pos - i)
            # Exponential falloff for a glowing laser tail
            intensity = math.exp(-(dist ** 2) * 1.5)

            if rainbow_mode:
                hue = (self.t * 0.5) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                target_colors[i * 3] = int(r * 255 * intensity)
                target_colors[i * 3 + 1] = int(g * 255 * intensity)
                target_colors[i * 3 + 2] = int(b * 255 * intensity)
            else:
                target_colors[i * 3] = int(zone_colors[i][0] * intensity)
                target_colors[i * 3 + 1] = int(zone_colors[i][1] * intensity)
                target_colors[i * 3 + 2] = int(zone_colors[i][2] * intensity)

        return target_colors

from effects import register_effect
register_effect("Scanner (Cylon)", ScannerEffect)
