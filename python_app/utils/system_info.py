"""
System & Hardware Information utilities for 4-Zone Keyboard RGB Toolkit.
Strictly read-only access to Windows SMBIOS / Registry.
"""

import winreg

def get_laptop_model() -> str:
    """
    Safely retrieves the laptop model name (e.g. 'LOQ 15IRX9') using
    strict read-only Windows SMBIOS registry query.
    Guaranteed zero-elevation, read-only memory lookup.
    """
    try:
        # Strictly KEY_READ (read-only access)
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\BIOS",
            0,
            winreg.KEY_READ
        ) as key:
            for field in ("SystemFamily", "SystemVersion", "SystemProductName"):
                try:
                    val, _ = winreg.QueryValueEx(key, field)
                    val = str(val).strip()
                    if val and val.lower() not in ("none", "to be filled by o.e.m.", "default string", "unknown"):
                        return val
                except FileNotFoundError:
                    continue
    except Exception:
        pass
    return "Unknown Model"
