import math
import colorsys
from typing import List, Dict, Any
from core.base import BaseEffect

class AuroraEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.aurora_hues = [0.45, 0.55, 0.70, 0.85]  # Green to Purple
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Aurora Borealis"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        self.t += dt
        speed = (self.config.get("speed", 50) / 100.0) * 0.5 + 0.1
        
        target_colors = [0] * 12
        for i in range(4):
            wave = math.sin(self.t * speed + (i * 1.5)) * 0.5 + 0.5
            hue_idx = (self.t * speed * 0.3 + (i * 0.2)) % len(self.aurora_hues)
            
            h1 = self.aurora_hues[int(hue_idx)]
            h2 = self.aurora_hues[(int(hue_idx) + 1) % len(self.aurora_hues)]
            blend = hue_idx - int(hue_idx)
            
            final_hue = h1 * (1 - blend) + h2 * blend
            r, g, b = colorsys.hsv_to_rgb(final_hue, 1.0, wave)
            
            target_colors[i * 3] = int(r * 255)
            target_colors[i * 3 + 1] = int(g * 255)
            target_colors[i * 3 + 2] = int(b * 255)
            
        return target_colors

from effects import register_effect
register_effect("Aurora Borealis", AuroraEffect)
