import time
import math
import colorsys
from typing import List, Dict, Any
from core.base import BaseEffect

class SmoothWaveEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Smooth Wave"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        return True

    def stop(self) -> None:
        self._running = False

    def _get_fill_palette(self) -> List[tuple]:
        palette_name = self.config.get("smooth_wave_palette", "RGBW")
        if palette_name == "Pastel":
            return [
                (255.0, 179.0, 186.0),
                (186.0, 255.0, 201.0),
                (186.0, 225.0, 255.0),
                (255.0, 252.0, 249.0),
            ]
        if palette_name == "Custom 4-Color":
            zone_colors = self.config.get("zone_colors", [[255,0,0], [0,255,0], [0,0,255], [255,255,255]])
            return [tuple(float(c) for c in color) for color in zone_colors]
        return [
            (255.0, 0.0, 0.0),
            (0.0, 255.0, 0.0),
            (0.0, 0.0, 255.0),  # Pure Blue
            (255.0, 252.0, 249.0),
        ]

    def update(self, dt: float) -> List[int]:
        speed = self.config.get("speed", 20)
        speed_mult = speed / 50.0
        self.t += dt * speed_mult
        
        direction = self.config.get("smooth_wave_direction", "left")
        wave_fill = self.config.get("wave_fill", False)
        
        target_colors = [0] * 12
        
        if wave_fill:
            dir_mult = -0.15 if direction == "left" else 0.15
            total_cycles = int(self.t)
            phase = self.t % 1.0
            
            fill_palette = self._get_fill_palette()
            prev_idx = total_cycles % len(fill_palette)
            next_idx = (total_cycles + 1) % len(fill_palette)
            
            r_prev, g_prev, b_prev = fill_palette[prev_idx]
            r_next, g_next, b_next = fill_palette[next_idx]
            
            for i in range(4):
                x = i * 0.25 if direction == "left" else (3 - i) * 0.25
                W = 0.6 
                B = -W + phase * (0.75 + 2.0 * W)
                blend = (B - x) / W
                blend = max(0.0, min(1.0, blend))
                blend = (1.0 - math.cos(blend * math.pi)) / 2.0
                
                target_colors[i * 3] = int(r_prev * (1 - blend) + r_next * blend)
                target_colors[i * 3 + 1] = int(g_prev * (1 - blend) + g_next * blend)
                
                # Apply a slight gamma boost to blue during transitions so it doesn't fade out too quickly
                raw_b = (b_prev * (1 - blend) + b_next * blend) / 255.0
                target_colors[i * 3 + 2] = int((raw_b ** 0.7) * 255.0)
        else:
            dir_mult = -0.15 if direction == "left" else 0.15
            for i in range(4):
                hue = (self.t + i * dir_mult) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                
                # Apply a slight gamma boost to the blue channel.
                # This keeps the peak at pure 255 blue, but makes the blue "band" much wider
                # so the LEDs spend more time emitting blue light, increasing perceived brightness.
                b = b ** 0.7
                
                target_colors[i * 3] = int(r * 255)
                target_colors[i * 3 + 1] = int(g * 255)
                target_colors[i * 3 + 2] = int(b * 255)
                
        return target_colors

from effects import register_effect
register_effect("Smooth Wave", SmoothWaveEffect)
