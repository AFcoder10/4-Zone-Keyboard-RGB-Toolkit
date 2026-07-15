from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import threading

class BaseEffect(ABC):
    """Abstract base class for all keyboard effects."""
    
    # Override in subclasses to control EMA smoothing in EffectManager.
    # Lower = more responsive (0.0 = instant), higher = smoother (0.85 = default).
    # Reactive effects (typing, mouse) should use ~0.2 for snappy response.
    preferred_smoothing: Optional[float] = None
    
    def __init__(self, keyboard_controller, parent_app=None, config: Dict = None):
        self.kb = keyboard_controller
        self.parent_app = parent_app
        self.config = config or {}
        self._running = False
        self._lock = threading.Lock()
        self._last_colors = None
        
    @property
    @abstractmethod
    def effect_name(self) -> str:
        """Unique identifier for this effect."""
        pass
    
    @property
    def effect_type(self) -> str:
        """software, hardware, or external"""
        return "software"
    
    @abstractmethod
    def start(self) -> bool:
        """Initialize and start the effect. Return True on success."""
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Clean shutdown of the effect."""
        pass
    
    @abstractmethod
    def update(self, dt: float) -> List[int]:
        """
        Compute next frame colors.
        Returns: List of 12 ints [R,G,B * 4] or None to skip frame.
        """
        pass
    
    def set_colors(self, colors: List[int]) -> bool:
        """Send colors to keyboard. Returns True on success."""
        if not self.kb:
            return False
        try:
            self.kb.set_colors(colors)
            if self.parent_app:
                self.parent_app.custom_colors = colors[:]
            self._last_colors = colors[:]
            return True
        except Exception as e:
            print(f"[{self.effect_name}] HID write error: {e}")
            return False
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update runtime configuration (speed, brightness, etc.)."""
        with self._lock:
            self.config.update(config)
    
    def set_keyboard_controller(self, kb) -> None:
        """Update the keyboard controller reference (e.g. after HID reacquire)."""
        self.kb = kb
    
    def is_running(self) -> bool:
        return self._running
