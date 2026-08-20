import time
import threading
from typing import Dict, Type, Any, Optional

from core.keyboard import RGBKeyboard
from core.base import BaseEffect

# Importing the effects package triggers auto-registration of all effects
from effects import EFFECT_REGISTRY


class EffectManager:
    def __init__(self):
        self.kb = None
        self._initialize_keyboard()
        
        # Use the auto-populated registry from effects/__init__.py
        self.effects_registry: Dict[str, Type[BaseEffect]] = dict(EFFECT_REGISTRY)
        
        self.active_effect: Optional[BaseEffect] = None
        self.global_config: Dict[str, Any] = {
            "speed": 50,
            "brightness": 100,
            "zone_colors": [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]],
            "scanner_rainbow": False,
            "storm_intensity": 50,
            "vibrance": 100,
            "resolution": "1920x1080",
        }
        
        self.current_colors = [0] * 12
        self.target_colors = [0] * 12
        self.transition_ticks = 0
        
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def _initialize_keyboard(self):
        try:
            self.kb = RGBKeyboard()
        except Exception as e:
            print(f"Failed to initialize RGBKeyboard: {e}")
            self.kb = None

    def start(self):
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._render_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            
        with self._lock:
            if self.active_effect:
                self.active_effect.stop()
            if self.kb:
                try:
                    self.kb.set_solid_color(0, 0, 0)
                    self.kb.close()
                except Exception:
                    pass
                self.kb = None

    def release_keyboard(self):
        """Releases the hardware lock so another process (like Visualizer) can use it."""
        with self._lock:
            if self.kb:
                try:
                    self.kb.close()
                except Exception:
                    pass
                self.kb = None

    def reacquire_keyboard(self):
        """Reacquires the hardware lock after an external process is done."""
        with self._lock:
            if not self.kb:
                self._initialize_keyboard()
            if self.active_effect and self.kb:
                self.active_effect.set_keyboard_controller(self.kb)
            return self.kb

    def get_keyboard(self):
        """Used if an external process (like audio visualizer) needs to grab the hardware lock temporarily."""
        with self._lock:
            return self.kb

    def update_config(self, key: str, value: Any):
        with self._lock:
            self.global_config[key] = value
            if self.active_effect:
                # Instead of re-creating the effect, we just update its config dict
                new_config = self.active_effect.config.copy()
                new_config[key] = value
                self.active_effect.update_config(new_config)

    def turn_off(self):
        with self._lock:
            if self.active_effect:
                self.active_effect.stop()
                self.active_effect = None
            if self.kb:
                try:
                    self.kb.set_effect("static")
                    self.kb.set_solid_color(0, 0, 0)
                except Exception:
                    pass

    def set_effect(self, effect_name: str):
        with self._lock:
            if self.active_effect and self.active_effect.effect_name == effect_name:
                return

            if self.active_effect:
                self.active_effect.stop()

            if effect_name is None:
                self.active_effect = None
                return

            effect_class = self.effects_registry.get(effect_name)
            config_payload = self.global_config.copy()
            if not effect_class:
                from core.custom_effects_io import load_custom_effect_by_name
                custom_data = load_custom_effect_by_name(effect_name)
                if custom_data and "frames" in custom_data:
                    effect_class = self.effects_registry.get("Custom Sequence")
                    config_payload["frames"] = custom_data["frames"]
                    if "default_speed" in custom_data:
                        config_payload["speed"] = custom_data["default_speed"]
                    if "default_brightness" in custom_data:
                        config_payload["brightness"] = custom_data["default_brightness"]
                else:
                    self.active_effect = None
                    return

            self.active_effect = effect_class(
                keyboard_controller=self.kb,
                parent_app=None,
                config=config_payload
            )
            
            # 15 ticks of slow transition (0.5 seconds at 30fps)
            self.transition_ticks = 15
            
            # Attempt to start the effect.
            # If it returns False (e.g., Audio Visualizer subprocess handler), it means it handles itself
            if not self.active_effect.start():
                self.active_effect = None

    def _render_loop(self):
        fps = 30
        frame_time = 1.0 / fps
        
        while self._running:
            loop_start = time.monotonic()
            
            with self._lock:
                active_effect = self.active_effect
                bright_mult = self.global_config.get("brightness", 100) / 100.0

            # Allow active effect to dynamically adjust target FPS (e.g. 60 FPS for Ambient)
            current_fps = 30
            if active_effect and hasattr(active_effect, "preferred_fps"):
                try:
                    pref_fps = getattr(active_effect, "preferred_fps", 30)
                    if pref_fps and isinstance(pref_fps, (int, float)):
                        current_fps = max(5, min(60, int(pref_fps)))
                except Exception:
                    pass
            frame_time = 1.0 / current_fps
            
            target_colors = [0] * 12
            if active_effect:
                try:
                    target_colors = active_effect.update(frame_time)
                except Exception as e:
                    print(f"Effect {active_effect.effect_name} crashed: {e}")
            
            with self._lock:
                if self.active_effect is active_effect:
                    self.target_colors = target_colors

                    if getattr(self.active_effect, "ignore_global_brightness", False):
                        bright_mult = 1.0
                    
                    # Smoothing logic (Exponential Moving Average)
                    smooth_amount = 0.85
                    
                    if self.transition_ticks > 0:
                        smooth_amount = 0.9  # Slower transition when switching effects
                        self.transition_ticks -= 1
                        
                    if hasattr(self.active_effect, "preferred_smoothing"):
                        if self.transition_ticks == 0:
                            pref = getattr(self.active_effect, "preferred_smoothing", None)
                            if pref is not None:
                                smooth_amount = pref
                
                final_colors = []
                for i in range(12):
                    try:
                        target = float(self.target_colors[i])
                        if target != target:  # check for NaN
                            target = 0.0
                    except (IndexError, TypeError, ValueError):
                        target = 0.0

                    new_val = self.current_colors[i] * smooth_amount + target * (1.0 - smooth_amount)
                    
                    # Sanity check to prevent NaN propagation
                    if new_val != new_val:
                        new_val = 0.0
                        
                    self.current_colors[i] = new_val
                    
                    final_val = new_val * bright_mult
                    final_colors.append(int(max(0, min(255, final_val))))
                
                if self.kb and self.active_effect:
                    try:
                        self.kb.set_colors(final_colors)
                    except Exception as e:
                        pass
                        
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0, frame_time - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)
