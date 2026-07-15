from typing import List, Dict, Any
from core.base import BaseEffect

class BatteryEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Battery Visualizer"

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        target_colors = [0] * 12
        
        # Read from injected state (config or external cache reference)
        percent = self.config.get("battery_percent", 100)
        charging = self.config.get("battery_charging", True)
        
        if charging:
            if percent >= 100:
                base_color = [0, 255, 0]
                active_zones_max = 4
            else:
                base_color = [0, 0, 255]
                active_zones_max = (percent // 25) + 1
        else:
            if percent <= 25:
                base_color = [255, 0, 0]
                active_zones_max = 1
            elif percent <= 50:
                base_color = [255, 128, 0]
                active_zones_max = 2
            else:
                base_color = [255, 255, 255]
                active_zones_max = 3 if percent <= 75 else 4
                
        for i in range(4):
            zone_min = i * 25
            zone_max = (i + 1) * 25
            
            if percent >= zone_max:
                brightness_mult = 1.0
            elif percent > zone_min:
                brightness_mult = (percent - zone_min) / 25.0
            else:
                brightness_mult = 0.0
                
            if i < active_zones_max:
                target_colors[i * 3] = int(base_color[0] * brightness_mult)
                target_colors[i * 3 + 1] = int(base_color[1] * brightness_mult)
                target_colors[i * 3 + 2] = int(base_color[2] * brightness_mult)
            else:
                target_colors[i * 3] = 0
                target_colors[i * 3 + 1] = 0
                target_colors[i * 3 + 2] = 0
                
        return target_colors

from effects import register_effect
register_effect("Battery Visualizer", BatteryEffect)
