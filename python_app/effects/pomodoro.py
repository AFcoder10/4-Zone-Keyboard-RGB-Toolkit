import math
import time
from typing import List, Dict, Any
from core.base import BaseEffect

class PomodoroEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Pomodoro Timer"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        self.t += dt
        target_colors = [0] * 12
        
        # In the new architecture, the Pomodoro UI/State should pass remaining seconds via config
        pomo_remaining_seconds = self.config.get("pomo_remaining_seconds", 0)
        pomo_total_seconds = self.config.get("pomo_total_seconds", 1)
        pomo_is_finished = self.config.get("pomo_is_finished", False)
        
        now = time.monotonic()
        
        if pomo_is_finished:
            pomo_flash_on = int(now * 2) % 2 == 0
            f = 1 if pomo_flash_on else 0
            for i in range(4):
                target_colors[i * 3] = 255 * f
                target_colors[i * 3 + 1] = 252 * f
                target_colors[i * 3 + 2] = 248 * f
        elif pomo_remaining_seconds <= 5:
            pulse = 0.5 + 0.5 * math.sin(now * math.pi)
            for i in range(4):
                target_colors[i * 3] = int(255 * pulse)
                target_colors[i * 3 + 1] = int(252 * pulse)
                target_colors[i * 3 + 2] = int(248 * pulse)
        else:
            effective_total = max(1, pomo_total_seconds - 5)
            progress = 1.0 - ((pomo_remaining_seconds - 5) / effective_total)
            
            for i in range(4):
                zone_start = i * 0.25
                zone_end = (i + 1) * 0.25
                
                if progress <= zone_start:
                    intensity = 1.0
                elif progress >= zone_end:
                    intensity = 0.0
                else:
                    intensity = 1.0 - ((progress - zone_start) / 0.25)
                    
                target_colors[i * 3] = int(255 * intensity)
                target_colors[i * 3 + 1] = int(252 * intensity)
                target_colors[i * 3 + 2] = int(248 * intensity)
                
        return target_colors

from effects import register_effect
register_effect("Pomodoro Timer", PomodoroEffect)
