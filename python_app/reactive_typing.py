import json
import os
import time
import threading
from pynput import keyboard

MAPPING_FILE = "keyboard_zones.json"

class ReactiveTypingEngine:
    def __init__(self, keyboard_controller, parent_app=None):
        self.kb = keyboard_controller
        self.parent_app = parent_app
        self.running = False
        
        # Load mapping
        self.mapping = {"Zone 1": [], "Zone 2": [], "Zone 3": [], "Zone 4": []}
        self.load_mapping()
        
        # Settings
        self.fps = 30
        self.decay_speed = 0.01 # Higher = faster fade. Tunable from UI.
        self.style = "fade" # "fade" or "ripple"
        self.rainbow_mode = False
        self.current_hue = 0.0
        self.ripples = []
        
        # Colors: [R, G, B] for 4 zones
        self.base_color = [0, 0, 0] # Always dark/off for base
        # Default highlight color for each zone (can be overridden by UI)
        self.zone_highlight_colors = [
            [255, 252, 248],
            [255, 252, 248],
            [255, 252, 248],
            [255, 252, 248]
        ]
        
        # State: 1.0 = fully lit, 0.0 = fully dark
        self.zone_intensities = [0.0, 0.0, 0.0, 0.0]
        
        self.listener = None
        self.render_thread = None

    def load_mapping(self):
        # We need the absolute path relative to this script just in case
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(os.path.dirname(script_dir), MAPPING_FILE)
        
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    self.mapping = json.load(f)
            except Exception as e:
                print(f"Error loading mapping: {e}")
        elif os.path.exists(MAPPING_FILE):
             try:
                with open(MAPPING_FILE, 'r') as f:
                    self.mapping = json.load(f)
             except:
                 pass

    def start(self):
        if self.running: return
        self.running = True
        
        # Force hardware to static mode so we can manually push colors
        try:
            self.kb.set_effect("static")
        except:
            pass
            
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        
        self.render_thread = threading.Thread(target=self.render_loop, daemon=True)
        self.render_thread.start()

    def stop(self):
        self.running = False
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.render_thread:
            self.render_thread.join(timeout=1.0)
            self.render_thread = None

    def on_press(self, key):
        try:
            if not self.running:
                return
                
            vk = None
            scan = None
            
            if hasattr(key, 'vk'):
                vk = key.vk
            elif hasattr(key, 'value') and hasattr(key.value, 'vk'):
                vk = key.value.vk
                
            # Synthesize scan codes for modifiers where pynput gives specific L/R VKs
            # but PyQt recorded generic VK + specific scan
            if vk == 160: # LSHIFT
                vk = 16
                scan = 42
            elif vk == 161: # RSHIFT
                vk = 16
                scan = 54
            elif vk == 162: # LCTRL
                vk = 17
                scan = 29
            elif vk == 163: # RCTRL
                vk = 17
                scan = 57373
            elif vk == 164: # LALT
                vk = 18
                scan = 56
            elif vk == 165: # RALT
                vk = 18
                scan = 57400
                
            found_zone_idx = None
            
            # Pass 1: Try to find an EXACT match (both VK and Scan code) if scan is known
            if scan is not None:
                for i in range(1, 5):
                    zone_name = f"Zone {i}"
                    keys = self.mapping.get(zone_name, [])
                    for key_data in keys:
                        if key_data.get('vk') == vk and key_data.get('scan') == scan:
                            found_zone_idx = i - 1
                            break
                    if found_zone_idx is not None:
                        break
                        
            # Pass 2: If no exact match, fallback to just VK matching
            if found_zone_idx is None:
                for i in range(1, 5):
                    zone_name = f"Zone {i}"
                    keys = self.mapping.get(zone_name, [])
                    for key_data in keys:
                        if key_data.get('vk') == vk:
                            found_zone_idx = i - 1
                            break
                    if found_zone_idx is not None:
                        break
                    
            if found_zone_idx is not None:
                color_to_use = self.zone_highlight_colors[found_zone_idx]
                if getattr(self, "rainbow_mode", False):
                    import colorsys
                    r, g, b = colorsys.hsv_to_rgb(self.current_hue, 1.0, 1.0)
                    color_to_use = [int(r * 255), int(g * 255), int(b * 255)]
                    self.current_hue = (self.current_hue + 0.02) % 1.0

                if self.style == "fade":
                    # Instantly light up to 1.0 for a punchy effect
                    self.zone_intensities[found_zone_idx] = 1.0
                    if getattr(self, "rainbow_mode", False):
                        self.zone_highlight_colors[found_zone_idx] = color_to_use
                elif self.style == "ripple":
                    self.ripples.append({
                        "origin": found_zone_idx,
                        "age": 0.0,
                        "color": color_to_use
                    })
        except Exception as e:
            pass

    def render_loop(self):
        while self.running:
            start_time = time.time()
            dt = 1.0 / self.fps
            
            # Process ripples
            active_ripples = []
            ripple_zone_boosts = [0.0] * 4
            ripple_colors = [None] * 4
            
            if self.style == "ripple":
                # Map decay_speed (0.005 -> 0.05) to prop time (0.15s -> 0.05s)
                prop_time_per_zone = max(0.02, 0.16 - (self.decay_speed * 2.0))
                
                for r in self.ripples:
                    r["age"] += dt
                    
                    # Ripple must live long enough to reach distance 3 and fully decay
                    max_age = (3 * prop_time_per_zone) + (1.0 / (self.decay_speed * 100))
                    
                    if r["age"] < max_age:
                        active_ripples.append(r)
                        
                        for i in range(4):
                            dist = abs(i - r["origin"])
                            
                            hit_time = dist * prop_time_per_zone
                            if r["age"] >= hit_time:
                                local_age = r["age"] - hit_time
                                # Decay factor proportional to global decay
                                local_decay = local_age * (self.decay_speed * 100)
                                if local_decay < 1.0:
                                    boost = 1.0 - local_decay
                                    if boost > ripple_zone_boosts[i]:
                                        ripple_zone_boosts[i] = boost
                                        ripple_colors[i] = r["color"]
            
            self.ripples = active_ripples

            final_colors = []
            
            for i in range(4):
                # Calculate base intensity and decay it
                if self.zone_intensities[i] > 0.0:
                    self.zone_intensities[i] = max(0.0, self.zone_intensities[i] - self.decay_speed)
                    
                base_intensity = self.zone_intensities[i]
                ripple_boost = ripple_zone_boosts[i]
                
                total_intensity = min(1.0, base_intensity + ripple_boost)
                
                bc = self.base_color
                # Prioritize ripple color if ripple is active here
                if ripple_boost > 0 and ripple_colors[i]:
                    hc = ripple_colors[i]
                else:
                    hc = self.zone_highlight_colors[i]
                
                # Lerp
                r = int(bc[0] + (hc[0] - bc[0]) * total_intensity)
                g = int(bc[1] + (hc[1] - bc[1]) * total_intensity)
                b = int(bc[2] + (hc[2] - bc[2]) * total_intensity)
                
                final_colors.extend([r, g, b])
                
            # If colors changed since last frame, we MUST update
            if getattr(self, "_last_colors", None) != final_colors:
                try:
                    self.kb.set_colors(final_colors)
                    if self.parent_app:
                        self.parent_app.custom_colors = final_colors[:]
                except:
                    pass
                self._last_colors = final_colors
            
            # Target FPS sleep
            elapsed = time.time() - start_time
            sleep_time = max(0, (1.0 / self.fps) - elapsed)
            time.sleep(sleep_time)
