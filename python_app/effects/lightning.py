import math
import random
from typing import List, Dict, Any
from core.base import BaseEffect

class LightningEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.lightning_strikes = []
        self.next_lightning_time = 0.0
        self.preferred_smoothing = 0.2  # Faster interpolation for sharp flashes
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Lightning"

    def start(self) -> bool:
        self._running = True
        self.t = 0.0
        self.lightning_strikes = []
        self.next_lightning_time = 0.0
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        self.t += dt
        
        speed_factor = max(0.2, self.config.get("speed", 50) / 100.0)
        storm_factor = max(0.05, self.config.get("storm_intensity", 50) / 100.0)
        
        target_colors = [0] * 12
        
        # Base storm clouds — dark with a subtle cool tint
        storm_wave = 0.35 + 0.15 * math.sin(self.t * 0.6)
        base_r = 3 + int(5 * storm_wave)
        base_g = 4 + int(6 * storm_wave)
        base_b = 7 + int(10 * storm_wave)
        
        for i in range(4):
            target_colors[i * 3] = base_r
            target_colors[i * 3 + 1] = base_g
            target_colors[i * 3 + 2] = base_b

        if self.t >= self.next_lightning_time:
            spawn_chance = (0.35 + 0.55 * speed_factor) * (0.5 + 1.5 * storm_factor)
            spawn_chance = min(0.98, spawn_chance)
            
            if random.random() < spawn_chance:
                primary_zone = random.randrange(4)
                strike_type = "small"
                r = random.random()
                if r > 0.85: strike_type = "huge"
                elif r > 0.45: strike_type = "medium"

                if strike_type == "small":
                    branch_count = random.choice([1, 1, 2])
                    pre_ticks = random.randint(1, 2)
                    flash_ticks = random.randint(1, 2)
                    flicker_ticks = random.randint(1, 3)
                    after_ticks = random.randint(4, 10)
                    bleed_mult = 0.14
                    colors = {"main": [240, 240, 255], "pre": [120, 115, 140], "after": [90, 85, 120]}
                elif strike_type == "medium":
                    branch_count = random.choice([1, 2, 2, 3])
                    pre_ticks = random.randint(2, 3)
                    flash_ticks = random.randint(2, 4)
                    flicker_ticks = random.randint(3, 6)
                    after_ticks = random.randint(8, 18)
                    bleed_mult = 0.2
                    colors = {"main": [255, 255, 255], "pre": [140, 130, 170], "after": [100, 95, 145]}
                else:
                    branch_count = random.choice([2, 3, 3, 4])
                    pre_ticks = random.randint(3, 5)
                    flash_ticks = random.randint(3, 8)
                    flicker_ticks = random.randint(6, 14)
                    after_ticks = random.randint(15, 40)
                    linger_boost = 1.0 + 1.8 * storm_factor
                    flash_ticks = max(1, int(round(flash_ticks * linger_boost)))
                    flicker_ticks = max(1, int(round(flicker_ticks * linger_boost)))
                    after_ticks = max(1, int(round(after_ticks * linger_boost)))
                    if random.random() < (0.35 + 0.45 * storm_factor):
                        flash_ticks += random.randint(8, 50)
                        flicker_ticks += random.randint(10, 60)
                        after_ticks += random.randint(10, 50)
                    bleed_mult = 0.28
                    colors = {"main": [255, 255, 255], "pre": [160, 150, 190], "after": [120, 110, 165]}

                zones = {primary_zone}
                while len(zones) < branch_count:
                    zones.add((primary_zone + random.choice([-1, 1, 2, -2])) % 4)

                strike = {
                    "zones": list(zones), "type": strike_type, "stage": "pre",
                    "ticks_left": pre_ticks, "flash_ticks": flash_ticks, 
                    "flicker_ticks": flicker_ticks, "after_ticks": after_ticks,
                    "after_total": after_ticks, "main_color": colors["main"],
                    "pre_color": colors["pre"], "after_color": colors["after"], "bleed": bleed_mult
                }
                self.lightning_strikes.append(strike)

                base_gap = max(0.35, (2.1 - 1.5 * speed_factor) * (1.2 - 0.7 * storm_factor))
                self.next_lightning_time = self.t + random.uniform(base_gap * 0.6, base_gap * 1.3)

        active_strikes = []
        for strike in self.lightning_strikes:
            stage = strike["stage"]
            color = strike["pre_color"]
            intensity = 0.3

            if stage == "pre":
                intensity = 0.35 + random.random() * 0.25
                strike["ticks_left"] -= 1
                if strike["ticks_left"] <= 0:
                    strike["stage"], strike["ticks_left"] = "flash", strike["flash_ticks"]
            elif stage == "flash":
                color, intensity = strike["main_color"], 1.0
                strike["ticks_left"] -= 1
                if strike["ticks_left"] <= 0:
                    strike["stage"], strike["ticks_left"] = "flicker", strike["flicker_ticks"]
            elif stage == "flicker":
                color = [230, 225, 245]
                intensity = 0.775 + 0.225 * math.sin(self.t * 25.0)
                strike["ticks_left"] -= 1
                if strike["ticks_left"] <= 0:
                    strike["stage"], strike["ticks_left"] = "after", strike["after_ticks"]
            else:
                color = strike["after_color"]
                decay = strike["ticks_left"] / float(strike["after_total"])
                intensity = 0.25 + 0.5 * decay
                strike["ticks_left"] -= 1

            for z in strike["zones"]:
                idx = z * 3
                target_colors[idx] = max(target_colors[idx], int(color[0] * intensity))
                target_colors[idx+1] = max(target_colors[idx+1], int(color[1] * intensity))
                target_colors[idx+2] = max(target_colors[idx+2], int(color[2] * intensity))

            if stage in ("flash", "flicker"):
                bleed = strike["bleed"] if stage == "flash" else strike["bleed"] * 0.55
                for i in range(4):
                    idx = i * 3
                    target_colors[idx] = max(target_colors[idx], int(200 * bleed))
                    target_colors[idx+1] = max(target_colors[idx+1], int(195 * bleed))
                    target_colors[idx+2] = max(target_colors[idx+2], int(220 * bleed))

            if strike["ticks_left"] > 0:
                active_strikes.append(strike)

        self.lightning_strikes = active_strikes
        return target_colors

from effects import register_effect
register_effect("Lightning", LightningEffect)
