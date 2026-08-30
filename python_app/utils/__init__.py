# Utilities package for 4-Zone Keyboard RGB Toolkit
from .chroma_utils import get_chroma_weighted_zone_colors, HAS_NUMPY
from .system_info import get_laptop_model

__all__ = [
    "get_chroma_weighted_zone_colors",
    "HAS_NUMPY",
    "get_laptop_model",
]
