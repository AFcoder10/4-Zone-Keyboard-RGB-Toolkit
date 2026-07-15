import random
from typing import List, Dict, Any
from core.base import BaseEffect

class MeteorEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.meteor_pos = -1.0
        self.meteor_dir = 1.0
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Meteor Shower"

    def start(self) -> bool:
        self._running = True
        self.meteor_pos = -1.0
        self.meteor_dir = 1.0
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        strike_freq = (self.config.get("speed", 50) / 100.0) * 2.0 + 0.5
        
        if self.meteor_pos < -2.0 or self.meteor_pos > 5.0:
            if random.random() < strike_freq * dt:
                self.meteor_dir = random.choice([-1.0, 1.0])
                self.meteor_pos = -1.0 if self.meteor_dir == 1.0 else 4.0
        else:
            meteor_speed = 15.0
            self.meteor_pos += self.meteor_dir * meteor_speed * dt
            
        target_colors = [0] * 12
        for i in range(4):
            dist = self.meteor_dir * (self.meteor_pos - i)
            r, g, b = 0, 0, 0
            
            if dist > 0 and dist < 3.0:
                intensity = max(0.0, 1.0 - (dist / 2.0) ** 2)
                if dist < 1.0:
                    r, g, b = 255, int(200 * (1.0 - dist * 0.5)), 0
                else:
                    r, g, b = 255, int(100 * max(0.0, 1.0 - (dist - 1.0) / 2.0)), 0
                    
                r = int(r * intensity)
                g = int(g * intensity)
                b = int(b * intensity)
            elif dist > -0.5 and dist <= 0:
                r, g, b = 255, 255, 200
                
            target_colors[i * 3] = r
            target_colors[i * 3 + 1] = g
            target_colors[i * 3 + 2] = b
            
        return target_colors

from effects import register_effect
register_effect("Meteor Shower", MeteorEffect)
