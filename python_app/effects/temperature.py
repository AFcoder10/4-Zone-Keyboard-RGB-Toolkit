from typing import List, Dict, Any
import os
import json
import tempfile
import time
from core.base import BaseEffect

class TemperatureEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.last_temp_read = 0.0
        self.cpu_temp = 0.0
        self.gpu_temp = 0.0
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Temperature Mode"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        return True

    def stop(self) -> None:
        self._running = False

    def _temp_color(self, temp: float, t: float):
        if temp < 30:
            return (0, 0, 255)
        elif temp <= 40:
            return (0, int(255 * ((temp - 30) / 10.0)), 255)
        elif temp <= 50:
            b = (temp - 40) / 10.0
            return (0, 255, int(255 - b * 255))
        elif temp <= 65:
            r = (temp - 50) / 15.0
            return (int(255 * r), 255, 0)
        elif temp <= 80:
            g_ratio = 1.0 - ((temp - 65) / 15.0)
            return (255, int(165 + (255 - 165) * g_ratio), 0)
        elif temp <= 90:
            b = (temp - 80) / 10.0
            return (255, int(165 - b * 115), 0)
        elif temp <= 100:
            return (255, 0, 0)
        else:
            return (255, 0, 0) if (int(t * 4) % 2) == 0 else (0, 0, 0)

    def update(self, dt: float) -> List[int]:
        self.t += dt
        
        now = time.time()
        if now - self.last_temp_read >= 1.0:
            self.last_temp_read = now
            try:
                temp_file_path = os.path.join(tempfile.gettempdir(), "4zone_temperatures.json")
                if os.path.exists(temp_file_path):
                    with open(temp_file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.cpu_temp = float(data.get("cpu", 0.0))
                        self.gpu_temp = float(data.get("gpu", 0.0))
            except Exception:
                pass

        target_colors = [0] * 12
        
        cpu_col = self._temp_color(self.cpu_temp, self.t)
        gpu_col = self._temp_color(self.gpu_temp, self.t)
        
        target_colors[0], target_colors[1], target_colors[2] = cpu_col
        target_colors[3], target_colors[4], target_colors[5] = cpu_col
        target_colors[6], target_colors[7], target_colors[8] = gpu_col
        target_colors[9], target_colors[10], target_colors[11] = gpu_col
        
        return target_colors

from effects import register_effect
register_effect("Temperature Mode", TemperatureEffect)
