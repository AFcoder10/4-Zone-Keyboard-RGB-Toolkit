import math
import random
import colorsys
from typing import List, Dict, Any
from core.base import BaseEffect

class PartyEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.party_state = {
            "last_t": 0.0,
            "acc": 0.0,
            "palette": [255, 0, 0] * 4,
            "strobe": 0,
            "zone_pops": [1.0] * 4,
        }
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Party"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        self.party_state["last_t"] = 0.0
        self.party_state["acc"] = 0.0
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        self.t += dt
        speed_factor = max(0.2, self.config.get("speed", 50) / 100.0)
        
        bpm = 90 + 120 * speed_factor
        beat_len = 60.0 / bpm
        
        self.party_state["acc"] += dt
        
        while self.party_state["acc"] >= beat_len:
            self.party_state["acc"] -= beat_len
            palette = []
            for _ in range(4):
                hue = random.random()
                sat = 0.8 + 0.2 * random.random()
                val = 0.9 + 0.1 * random.random()
                r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
                palette.extend([r * 255, g * 255, b * 255])
            self.party_state["palette"] = palette
            
            if random.random() < 0.18 * speed_factor:
                self.party_state["strobe"] = random.randint(2, 4)
                
        beat_phase = self.party_state["acc"] / max(beat_len, 1e-6)
        pulse = 0.4 + 0.6 * (1.0 - beat_phase)
        
        is_strobing = False
        if self.party_state["strobe"] > 0:
            pulse = 1.0
            is_strobing = True
            self.party_state["strobe"] -= 1
            
        zone_pops = self.party_state["zone_pops"]
        decay = 0.82 + 0.12 * speed_factor
        max_pop = 1.32
        
        target_colors = [0] * 12
        for i in range(4):
            if is_strobing:
                base_r, base_g, base_b = 255, 255, 255
            else:
                base_r = self.party_state["palette"][i * 3]
                base_g = self.party_state["palette"][i * 3 + 1]
                base_b = self.party_state["palette"][i * 3 + 2]
                
            zone_pops[i] = 1.0 + (zone_pops[i] - 1.0) * decay
            if random.random() < 0.06 * speed_factor:
                zone_pops[i] = max(zone_pops[i], 1.18 + 0.18 * random.random())
                
            pop = min(zone_pops[i], max_pop)
            
            target_colors[i * 3] = int(min(255, base_r * pulse * pop))
            target_colors[i * 3 + 1] = int(min(255, base_g * pulse * pop))
            target_colors[i * 3 + 2] = int(min(255, base_b * pulse * pop))
            
        self.party_state["zone_pops"] = zone_pops
        return target_colors

from effects import register_effect
register_effect("Party", PartyEffect)
