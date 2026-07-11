import json
import os
import time
import threading
import sys
from pynput import keyboard

MAPPING_FILE = "keyboard_zones.json"

class ReactiveTypingEngine:
    def __init__(self, keyboard_controller, parent_app=None):
        self.kb = keyboard_controller
        self.parent_app = parent_app
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._stop_event.set() # Initially stopped
        
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

    def set_keyboard_controller(self, kb):
        self.kb = kb

    def update_settings(self, zone_colors, decay_speed, style, rainbow_mode):
        with self.lock:
            if not rainbow_mode:
                self.zone_highlight_colors = [list(c) for c in zone_colors]
            self.decay_speed = decay_speed
            self.style = style
            self.rainbow_mode = rainbow_mode

    def load_mapping(self):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, MAPPING_FILE)
        
        # In a bundled PyInstaller exe, __file__ might be inside a temp _MEIPASS folder.
        # But if we used --add-data, it will extract there perfectly.
        if getattr(sys, "frozen", False):
            json_path = os.path.join(sys._MEIPASS, MAPPING_FILE)

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
        if not self._stop_event.is_set(): 
            return
            
        # Ensure any existing thread is fully dead before starting a new one
        if self.render_thread and self.render_thread.is_alive():
            self.render_thread.join(timeout=1.0)
            
        self._stop_event.clear()
        
        # Force hardware to static mode so we can manually push colors
        if self.kb:
            try:
                self.kb.set_effect("static")
            except:
                pass
            
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        
        self.render_thread = threading.Thread(target=self.render_loop, daemon=True)
        self.render_thread.start()

    def stop(self):
        self._stop_event.set()
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.render_thread:
            self.render_thread.join(timeout=2.0)
            self.render_thread = None

    def on_press(self, key):
        try:
            if self._stop_event.is_set():
                return
                
            vk = None
            scan = None
            
            if hasattr(key, 'vk'):
                vk = key.vk
            elif hasattr(key, 'value') and hasattr(key.value, 'vk'):
                vk = key.value.vk
                
            # Attempt to extract raw scan code from pynput (undocumented but exists on Windows backend)
            scan = getattr(key, 'scan_code', getattr(key, '_scan_code', None))
                
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
                with self.lock:
                    color_to_use = self.zone_highlight_colors[found_zone_idx]
                    if getattr(self, "rainbow_mode", False):
                        import colorsys
                        r, g, b = colorsys.hsv_to_rgb(self.current_hue, 1.0, 1.0)
                        color_to_use = [int(r * 255), int(g * 255), int(b * 255)]
                        self.current_hue = (self.current_hue + 0.02) % 1.0
                        # Update the base highlight color so 'fade' style can use it without snapping back to white
                        self.zone_highlight_colors[found_zone_idx] = color_to_use

                    if self.style == "fade":
                        # Instantly light up to 1.0 for a punchy effect
                        self.zone_intensities[found_zone_idx] = 1.0
                    elif self.style == "ripple":
                        self.ripples.append({
                            "origin": found_zone_idx,
                            "age": 0.0,
                            "color": color_to_use
                        })
        except Exception as e:
            print(f"ReactiveTyping Error in on_press: {e}")

    def render_loop(self):
        while not self._stop_event.is_set():
            start_time = time.time()
            dt = 1.0 / self.fps
            
            with self.lock:
                # Process ripples
                active_ripples = []
                ripple_zone_boosts = [0.0] * 4
                ripple_colors = [None] * 4
                
                if self.style == "ripple":
                    # Map decay to wave speed (zones per second). Slower ripple for smoother effect.
                    speed = 3.0 + (self.decay_speed * 40.0) 
                    # Max distance across keyboard is 3 zones. Trailing tail is 2.0 zones wide.
                    # So the crest must travel 5.0 zones to completely clear the board in pitch black.
                    max_age = 5.5 / speed
                    
                    import math
                    for r in self.ripples:
                        r["age"] += dt
                        
                        if r["age"] < max_age:
                            active_ripples.append(r)
                            
                            for i in range(4):
                                dist = abs(i - r["origin"])
                                crest = r["age"] * speed
                                
                                # Asymmetrical "comet" wave
                                if dist >= crest:
                                    # Leading edge: Sharp dropoff so adjacent zones don't light up instantly
                                    diff = dist - crest
                                    width = 0.8 
                                else:
                                    # Trailing tail: Wide fadeout so zones blend smoothly together as it passes
                                    diff = crest - dist
                                    width = 2.0
                                    
                                if diff < width:
                                    # Perfect Cosine ease-in-out curve to seamlessly fade into pure black (base color)
                                    normalized_diff = diff / width
                                    boost = (math.cos(normalized_diff * math.pi) + 1.0) / 2.0
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
                if self.kb is None:
                    # Skip if we lost connection to keyboard, but still update _last_colors so we don't spam
                    self._last_colors = final_colors
                else:
                    try:
                        self.kb.set_colors(final_colors)
                        if self.parent_app:
                            self.parent_app.custom_colors = final_colors[:]
                    except Exception as e:
                        print(f"ReactiveTyping Error in HID write (set_colors): {e}")
                    self._last_colors = final_colors
            
            # Target FPS sleep
            elapsed = time.time() - start_time
            sleep_time = max(0.002, (1.0 / self.fps) - elapsed) # Guarantee at least 2ms yield
            time.sleep(sleep_time)
