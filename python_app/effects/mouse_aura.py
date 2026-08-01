import math
from typing import List, Dict, Any
from core.base import BaseEffect

try:
    from PySide6.QtGui import QCursor
    from PySide6.QtWidgets import QApplication
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False

class MouseAuraEffect(BaseEffect):
    preferred_smoothing = 0.15  # Near-instant for mouse tracking
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        super().__init__(keyboard_controller, parent_app, config)
        self.update_config(self.config)

    @property
    def effect_name(self) -> str:
        return "Mouse-Reactive Aura"

    def start(self) -> bool:
        if not HAS_PYQT:
            print("PySide6 is required for Mouse-Reactive Aura.")
            return False
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def update(self, dt: float) -> List[int]:
        target_colors = [0] * 12
        zone_colors = self.config.get("zone_colors", [[255, 0, 0] for _ in range(4)])
        
        try:
            cursor_pos = QCursor.pos()
            screen = QApplication.primaryScreen()
            if screen:
                screen_width = screen.size().width()
                mouse_x = max(0, min(screen_width, cursor_pos.x()))
                
                for i in range(4):
                    zone_center_ratio = (i + 0.5) / 4.0
                    mouse_ratio = mouse_x / screen_width
                    
                    dist = abs(zone_center_ratio - mouse_ratio)
                    intensity = math.exp(-(dist ** 2) * 20.0)
                    
                    target_colors[i * 3] = int(zone_colors[i][0] * intensity)
                    target_colors[i * 3 + 1] = int(zone_colors[i][1] * intensity)
                    target_colors[i * 3 + 2] = int(zone_colors[i][2] * intensity)
        except Exception as e:
            pass
            
        return target_colors

from effects import register_effect
register_effect("Mouse-Reactive Aura", MouseAuraEffect)
