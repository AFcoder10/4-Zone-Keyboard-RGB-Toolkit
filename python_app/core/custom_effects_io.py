import os
import json
import glob
from typing import List, Dict, Any, Optional

def get_custom_effects_dir() -> str:
    """
    Returns the user AppData directory for custom JSON effects.
    Guarantees cross-PC & executable (EXE) compatibility.
    """
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        target_dir = os.path.join(appdata, "4ZoneRGBToolkit", "custom_effects")
    else:
        target_dir = os.path.expanduser("~/.4zone_rgb_toolkit/custom_effects")
        
    os.makedirs(target_dir, exist_ok=True)
    return target_dir

def list_custom_effects() -> List[Dict[str, Any]]:
    """Lists all saved custom effect JSON metadata and files."""
    effects_dir = get_custom_effects_dir()
    json_files = glob.glob(os.path.join(effects_dir, "*.json"))
    result = []
    for filepath in json_files:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["filepath"] = filepath
                if "name" not in data:
                    data["name"] = os.path.splitext(os.path.basename(filepath))[0]
                result.append(data)
        except Exception as e:
            print(f"Error loading custom effect {filepath}: {e}")
    return result

def save_custom_effect(effect_data: Dict[str, Any], overwrite: bool = True) -> str:
    """Saves a custom effect JSON to AppData."""
    effects_dir = get_custom_effects_dir()
    name = effect_data.get("name", "Untitled Effect").strip() or "Untitled Effect"
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()
    
    base_filepath = os.path.join(effects_dir, f"{safe_name}.json")
    filepath = base_filepath
    
    if not overwrite:
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(effects_dir, f"{safe_name}_{counter}.json")
            counter += 1
            
        # Update the name in the data to match the new file
        if filepath != base_filepath:
            effect_data["name"] = f"{name} {counter-1}"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(effect_data, f, indent=2)
        
    return filepath

def delete_custom_effect(name: str) -> bool:
    """Deletes a custom effect file by name."""
    effects_dir = get_custom_effects_dir()
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()
    filepath = os.path.join(effects_dir, f"{safe_name}.json")
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return True
        except Exception as e:
            print(f"Failed to delete custom effect {filepath}: {e}")
    return False

def load_custom_effect_by_name(name: str) -> Optional[Dict[str, Any]]:
    """Loads a custom effect payload by name."""
    effects_dir = get_custom_effects_dir()
    safe_name = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-")).rstrip()
    filepath = os.path.join(effects_dir, f"{safe_name}.json")
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error reading custom effect {name}: {e}")
    return None
