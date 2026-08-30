import json
import os
import math
from typing import List, Dict, Any
try:
    from pynput import keyboard
    HAS_PYNPUT = True
except ImportError:
    keyboard = None
    HAS_PYNPUT = False
from core.base import BaseEffect

MAPPING_FILE = "keyboard_zones.json"

class ReactiveTypingEffect(BaseEffect):
    preferred_smoothing = 0.2  # Instant response for keystrokes
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        
        # Load mapping
        self.mapping = {"Zone 1": [], "Zone 2": [], "Zone 3": [], "Zone 4": []}
        self.load_mapping()
        
        # Default State
        self.ripples = []
        self.zone_intensities = [0.0, 0.0, 0.0, 0.0]
        self.base_color = [0, 0, 0]
        self.current_hue = 0.0
        self.zone_highlight_colors = [[255, 252, 248] for _ in range(4)]
        self.listener = None
        
        # Apply initial config
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Reactive Typing"
        
    def update_config(self, config: Dict[str, Any]) -> None:
        super().update_config(config)
        with self._lock:
            # We don't overwrite if rainbow mode is on, to preserve the rainbow
            if not self.config.get("reactive_rainbow", False):
                zc = config.get("zone_colors", [[255, 252, 248] for _ in range(4)])
                self.zone_highlight_colors = [list(c) for c in zc]
                
            val = config.get("speed", 20)
            self.decay_speed = max(0.005, (val / 100.0) * 0.05)
            self.style = config.get("reactive_style", "Fade").lower()
            self.rainbow_mode = config.get("reactive_rainbow", False)

    def load_mapping(self):
        import sys
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(os.path.dirname(script_dir), MAPPING_FILE)
        
        if getattr(sys, "frozen", False):
            json_path = os.path.join(sys._MEIPASS, MAPPING_FILE)

        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    self.mapping = json.load(f)
            except Exception as e:
                pass

    def start(self) -> bool:
        if not HAS_PYNPUT or not keyboard:
            print("Reactive Typing unavailable: pynput is not installed.")
            return False
        try:
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()
            self._running = True
            return True
        except Exception as e:
            print(f"Failed to start reactive typing listener: {e}")
            return False

    def stop(self) -> None:
        self._running = False
        if getattr(self, 'listener', None):
            try:
                if self.listener.is_alive():
                    self.listener.stop()
            except Exception:
                pass
            self.listener = None

    def on_press(self, key):
        try:
            if not self._running: return
                
            vk = None
            scan = getattr(key, 'scan_code', getattr(key, '_scan_code', None))
            
            if hasattr(key, 'vk'):
                vk = key.vk
            elif hasattr(key, 'value') and hasattr(key.value, 'vk'):
                vk = key.value.vk
                
            if vk == 160: scan, vk = 42, 16
            elif vk == 161: scan, vk = 54, 16
            elif vk == 162: scan, vk = 29, 17
            elif vk == 163: scan, vk = 57373, 17
            elif vk == 164: scan, vk = 56, 18
            elif vk == 165: scan, vk = 57400, 18
                
            found_zone_idx = None
            if scan is not None:
                for i in range(1, 5):
                    for kd in self.mapping.get(f"Zone {i}", []):
                        if kd.get('vk') == vk and kd.get('scan') == scan:
                            found_zone_idx = i - 1
                            break
                    if found_zone_idx is not None: break
                        
            if found_zone_idx is None:
                for i in range(1, 5):
                    for kd in self.mapping.get(f"Zone {i}", []):
                        if kd.get('vk') == vk:
                            found_zone_idx = i - 1
                            break
                    if found_zone_idx is not None: break
                    
            if found_zone_idx is not None:
                with self._lock:
                    color_to_use = self.zone_highlight_colors[found_zone_idx]
                    if self.rainbow_mode:
                        import colorsys
                        r, g, b = colorsys.hsv_to_rgb(self.current_hue, 1.0, 1.0)
                        color_to_use = [int(r * 255), int(g * 255), int(b * 255)]
                        self.current_hue = (self.current_hue + 0.02) % 1.0
                        self.zone_highlight_colors[found_zone_idx] = color_to_use

                    if self.style == "fade":
                        self.zone_intensities[found_zone_idx] = 1.0
                    elif self.style == "ripple":
                        self.ripples.append({
                            "origin": found_zone_idx,
                            "age": 0.0,
                            "color": color_to_use
                        })
        except Exception as e:
            pass

    def update(self, dt: float) -> List[int]:
        with self._lock:
            active_ripples = []
            ripple_zone_boosts = [0.0] * 4
            ripple_colors = [None] * 4
            
            if self.style == "ripple":
                speed = 3.0 + (self.decay_speed * 40.0) 
                max_age = 5.5 / speed
                
                for r in self.ripples:
                    r["age"] += dt
                    if r["age"] < max_age:
                        active_ripples.append(r)
                        for i in range(4):
                            dist = abs(i - r["origin"])
                            crest = r["age"] * speed
                            if dist >= crest:
                                diff = dist - crest
                                width = 0.8 
                            else:
                                diff = crest - dist
                                width = 2.0
                                
                            if diff < width:
                                boost = (math.cos((diff / width) * math.pi) + 1.0) / 2.0
                                if boost > ripple_zone_boosts[i]:
                                    ripple_zone_boosts[i] = boost
                                    ripple_colors[i] = r["color"]
            
            self.ripples = active_ripples
            final_colors = []
            
            for i in range(4):
                if self.zone_intensities[i] > 0.0:
                    self.zone_intensities[i] = max(0.0, self.zone_intensities[i] - self.decay_speed)
                    
                total_intensity = min(1.0, self.zone_intensities[i] + ripple_zone_boosts[i])
                bc = self.base_color
                
                hc = ripple_colors[i] if (ripple_zone_boosts[i] > 0 and ripple_colors[i]) else self.zone_highlight_colors[i]
                
                final_colors.extend([
                    int(bc[0] + (hc[0] - bc[0]) * total_intensity),
                    int(bc[1] + (hc[1] - bc[1]) * total_intensity),
                    int(bc[2] + (hc[2] - bc[2]) * total_intensity)
                ])
                
            return final_colors

from effects import register_effect
register_effect("Reactive Typing", ReactiveTypingEffect)
