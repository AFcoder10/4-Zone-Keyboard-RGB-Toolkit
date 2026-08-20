import colorsys
import time
from typing import List, Dict, Any
from core.base import BaseEffect

try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

class ValorantSpikeEffect(BaseEffect):
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.t = 0.0
        self.spike_active = False
        self.spike_start_time = 0.0
        self.spike_cooldown_until = 0.0
        self.last_spike_scan = 0.0
        self.sct = None
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Valorant Spike Timer"

    def start(self) -> bool:
        if not HAS_MSS:
            print("mss is required for Valorant Spike Timer.")
            return False
        if self.sct is None:
            self.sct = mss.mss()
        self._running = True
        self.t = 0.0
        self.spike_active = False
        self.spike_start_time = 0.0
        self.spike_cooldown_until = 0.0
        self.last_spike_scan = 0.0
        return True

    def stop(self) -> None:
        self._running = False
        if self.sct:
            self.sct.close()
            self.sct = None

    def _get_spike_bbox(self, monitor):
        res_text = self.config.get("resolution", "1920x1080")
        w_center = monitor["left"] + monitor["width"] // 2
        
        if "2560x1440" in res_text:
            return {"top": monitor["top"] + 40, "left": w_center - 13, "width": 26, "height": 33}
        elif "3840x2160" in res_text:
            return {"top": monitor["top"] + 60, "left": w_center - 20, "width": 40, "height": 50}
        else: # 1920x1080 default
            return {"top": monitor["top"] + 30, "left": w_center - 10, "width": 20, "height": 25}

    def update(self, dt: float) -> List[int]:
        self.t += dt
        if self.config.pop("spike_test_active", False):
            self.spike_active = True
            self.spike_start_time = self.t - 35.0  # Fast forward to intense part
        target_colors = [0] * 12
        
        if self.spike_active:
            elapsed = self.t - self.spike_start_time
            if elapsed >= 48.0:
                self.spike_active = False
                self.spike_cooldown_until = self.t + 15.0
            elif elapsed >= 45.0:
                fade = max(0.0, 1.0 - ((elapsed - 45.0) / 3.0))
                val = int(255 * fade)
                for i in range(12): target_colors[i] = val
            elif elapsed >= 42.5:
                if int(elapsed * 20) % 2 == 0:
                    for i in range(12): target_colors[i] = 255
                else:
                    for i in range(4):
                        target_colors[i*3], target_colors[i*3+1], target_colors[i*3+2] = 255, 0, 0
            else:
                bps = 1.0
                if elapsed >= 35.0: bps = 4.0
                elif elapsed >= 25.0: bps = 2.0
                
                beat_phase = (elapsed * bps) % 1.0
                if beat_phase < 0.15: intensity = 1.0
                else: intensity = max(0.0, 1.0 - ((beat_phase - 0.15) * 2.0))
                
                val = int(255 * intensity)
                dim_red = 20
                for i in range(4):
                    target_colors[i*3] = max(dim_red, val)
                    target_colors[i*3+1] = 0
                    target_colors[i*3+2] = 0
        else:
            if HAS_MSS and self.sct and self.t > self.spike_cooldown_until:
                if (self.t - self.last_spike_scan) > 0.1:
                    self.last_spike_scan = self.t
                    try:
                        monitor = self.sct.monitors[1]
                        bbox = self._get_spike_bbox(monitor)
                        sct_img = self.sct.grab(bbox)
                        raw = sct_img.bgra
                        total_pixels = bbox["width"] * bbox["height"]
                        red_match = 0
                        white_match = 0
                        
                        target_red = self.config.get("spike_target_red", (255, 60, 60))
                        th, ts, tv = colorsys.rgb_to_hsv(target_red[0]/255.0, target_red[1]/255.0, target_red[2]/255.0)
                        
                        for i in range(0, len(raw), 4):
                            b, g, r = raw[i], raw[i+1], raw[i+2]
                            h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)
                            
                            if v > 0.8 and s < 0.35:
                                white_match += 1
                            else:
                                hd = abs(h - th)
                                if hd > 0.5: hd = 1.0 - hd
                                if hd < 0.1 and s > 0.4 and v > 0.4: 
                                    red_match += 1
                                    
                        if red_match > (total_pixels * 0.4) and white_match > 2:
                            self.spike_active = True
                            self.spike_start_time = self.t
                    except Exception:
                        pass
                        
        return target_colors

from effects import register_effect
register_effect("Valorant Spike Timer", ValorantSpikeEffect)
