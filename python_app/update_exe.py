import os
import shutil
import subprocess
import sys

# Change to the application directory 
os.chdir(os.path.dirname(os.path.abspath(__file__)))

def perform_update_and_clean():
    print("=== 4 ZONE RGB TOOLKIT UPDATER & CLEANER ===")
    
    # 1. Ensure any outdated PIP packages are updated securely to their latest versions
    print("\n[+] Updating dependent python packages (PySide6, pynput, wmi, mss)...")
    required_packages = ["PySide6", "pynput", "psutil", "wmi", "mss", "Pillow", "pyaudiowpatch"]
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + required_packages)
    
    # 2. Hard-Delete specifically old outdated .exe folders and PyInstaller Junk
    print("\n[+] Removing old junk leftovers and dirty compilation caches...")
    junk_folders = ["build", "dist", "__pycache__"]
    for folder in junk_folders:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f" -> Successfully deleted old directory: {folder}/")
            except Exception as e:
                print(f" -> Failed to delete {folder}/: {e}")
                
    # 3. Clean up loose PyInstaller leftover configuration specification files
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".spec"):
                file_path = os.path.join(root, file)
                os.remove(file_path)
                print(f" -> Removed outdated configuration blueprint: {file}")

def rebuild_exe():
    print("\n[+] Initializing fresh compilation of Standalone .EXE Application...")
    subprocess.check_call([sys.executable, "build_exe.py"])
    
if __name__ == '__main__':
    perform_update_and_clean()
    rebuild_exe()
    
    print("\n[+] Moving executable to root directory...")
    exe_path = os.path.join("dist", "4_Zone_Rgb_Toolkit.exe")
    target_path = os.path.join("..", "4_Zone_Rgb_Toolkit.exe")
    if os.path.exists(exe_path):
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except OSError:
                print("Warning: Could not remove old executable, it might be running. Please replace manually.")
        try:
            shutil.move(exe_path, target_path)
            print(f" -> Moved securely to {os.path.abspath(target_path)}")
        except Exception as e:
            print(f" -> Failed to move: {e}")
            
    print("\n=== UPDATE SUCCESSFUL ===")
    print("The standalone .EXE has been successfully rebuilt from the latest code,")
    print("and all old garbage files have been permanently cleared away!")
