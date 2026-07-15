import math
import random
from typing import List, Dict, Any
from core.base import BaseEffect

class RealisticFireEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.fire_state = [random.random() for _ in range(4)]
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Realistic Fire"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        self.fire_state = [random.random() for _ in range(4)]
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        speed_mult = self.config.get("speed", 50) / 50.0
        
        self.t += dt * speed_mult * 3.0
        
        target_colors = [0] * 12
        for i in range(4):
            heat_wave = math.sin(self.t + i * 1.5) * 0.3
            jitter = (random.random() - 0.5) * 0.9 * speed_mult
            
            self.fire_state[i] = max(0.1, min(1.0, self.fire_state[i] + jitter + heat_wave * 0.2))
            intensity = self.fire_state[i]
            
            if random.random() < 0.12 * speed_mult:
                intensity = min(1.0, intensity + 0.6)
                self.fire_state[i] = intensity
                
            r = int(255 * min(1.0, intensity * 2.0))
            r = max(40, r)
            g = int(60 * intensity * (0.3 + 0.6 * random.random()))
            b = int(5 * intensity * random.random())
            
            target_colors[i * 3] = r
            target_colors[i * 3 + 1] = g
            target_colors[i * 3 + 2] = b
            
        return target_colors

from effects import register_effect
register_effect("Realistic Fire", RealisticFireEffect)
