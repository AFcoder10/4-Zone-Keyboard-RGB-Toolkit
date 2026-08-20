"""
Chroma-Weighted Color Averaging Helper
--------------------------------------
This module contains the NumPy-based chroma-weighted saturation averaging algorithm.
Instead of simple box resizing (which can get washed out by dull gray/black backgrounds),
this calculates the color saturation/chroma of each pixel and weights vibrant pixels higher.
"""

import colorsys
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

def get_chroma_weighted_zone_colors(img, vibrance_mult=1.5):
    """
    Given a PIL Image representing a screen capture, divides it into 4 vertical zones,
    calculates the chroma-weighted average color for each zone, applies vibrance enhancement,
    and returns a flat list of 12 RGB integers: [R0, G0, B0, R1, G1, B1, ...].
    """
    target_colors = [0] * 12
    if not HAS_NUMPY:
        return target_colors

    try:
        from PIL import Image
        # Downscale to a fast, accurate resolution (64 width = exactly 16 columns per zone, 16 vertical rows)
        img_resized = img.resize((64, 16), Image.Resampling.BILINEAR)
        arr = np.array(img_resized, dtype=np.float32)
        
        # Split into 4 vertical columns matching the 4 keyboard zones
        zones = np.array_split(arr, 4, axis=1)
        
        for i in range(4):
            zone = zones[i]
            pixels = zone.reshape(-1, 3)
            r = pixels[:, 0]
            g = pixels[:, 1]
            b = pixels[:, 2]
            
            # Gentle chroma bias: vibrant pixels count ~3x more, but gray/dark pixels still contribute
            # This avoids the blocky snapping of aggressive weighting while subtly preferring color
            mx = np.maximum(np.maximum(r, g), b)
            mn = np.minimum(np.minimum(r, g), b)
            chroma = mx - mn
            weights = 1.0 + (chroma / 255.0) * 2.0
            
            avg_r = np.average(r, weights=weights)
            avg_g = np.average(g, weights=weights)
            avg_b = np.average(b, weights=weights)

            h, s, v = colorsys.rgb_to_hsv(avg_r / 255.0, avg_g / 255.0, avg_b / 255.0)
            final_r, final_g, final_b = colorsys.hsv_to_rgb(h, min(1.0, s * vibrance_mult), v)

            target_colors[i * 3] = int(max(0, min(255, final_r * 255)))
            target_colors[i * 3 + 1] = int(max(0, min(255, final_g * 255)))
            target_colors[i * 3 + 2] = int(max(0, min(255, final_b * 255)))

    except Exception as e:
        print(f"[Chroma Utils] Error calculating weighted averages: {e}")

    return target_colors
