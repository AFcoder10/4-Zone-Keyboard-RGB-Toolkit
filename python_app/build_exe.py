import os
import subprocess
import sys

# Make sure all working directories are set to python_app
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def install_pyinstaller():
    print("Verifying PyInstaller is installed...")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Installing via Pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def compile_csharp_wrapper():
    print("Compiling secure UAC wrapper (thermal_sensor_access_v3)...")
    csc_path = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Microsoft.NET", "Framework64", "v4.0.30319", "csc.exe")
    if not os.path.exists(csc_path):
        print(f"Warning: {csc_path} not found. Cannot compile wrapper.")
        return
    
    out_exe = "assets/thermal_sensor_access_v3.exe"
    cs_file = "thermal_sensor_wrapper.cs"
    if not os.path.exists("assets"):
        os.makedirs("assets", exist_ok=True)
        
    subprocess.check_call([
        csc_path,
        "/t:winexe",
        "/nologo",
        f"/out:{out_exe}",
        cs_file
    ])
    print("Wrapper compiled successfully.")


def build_standalone_exe():
    print("\n--- COMPILING 4 ZONE RGB TOOLKIT ---")

    # We use PyInstaller directly via a module call or CLI hook
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--noupx",
        "--icon=assets/rgb_wheel.ico",
        "--name=4_Zone_Rgb_Toolkit",
        "--version-file=version_info.txt",
        # --- Assets ---
        "--add-data=assets/minus.svg;assets",
        "--add-data=assets/plus.svg;assets",
        "--add-data=assets/settings.svg;assets",
        "--add-data=assets/toggle_off.svg;assets",
        "--add-data=assets/toggle_on.svg;assets",
        "--add-data=assets/rgb_wheel.ico;assets",
        "--add-data=assets/boot.gif;assets",
        "--add-data=assets/github.svg;assets",
        "--add-data=assets/discord.svg;assets",
        "--add-data=assets/thermal_sensor_access_v3.exe;assets",
        # --- Data files ---
        "--add-data=keyboard_zones.json;.",
        "--add-data=temperature_worker.py;.",
        "--add-data=wintemp.py;.",
        "--add-data=LibreHardwareMonitor;LibreHardwareMonitor",
        # --- New packages (core/, effects/, and utils/) ---
        "--add-data=core;core",
        "--add-data=effects;effects",
        "--add-data=utils;utils",
        # --- Hidden imports (stdlib + third-party) ---
        "--hidden-import=clr",
        "--hidden-import=System",
        "--hidden-import=psutil",
        "--hidden-import=hid",
        "--hidden-import=pynput",
        "--hidden-import=pynput.keyboard",
        "--hidden-import=pynput.keyboard._win32",
        "--hidden-import=colorsys",
        "--hidden-import=urllib.request",
        "--hidden-import=urllib.error",
        "--hidden-import=json",
        "--hidden-import=base64",
        "--hidden-import=fastapi",
        "--hidden-import=uvicorn",
        "--hidden-import=numpy",
        "--hidden-import=mss",
        "--hidden-import=PIL",
        # --- Hidden imports (app top-level modules) ---
        "--hidden-import=custom_builder_gui",
        "--hidden-import=cloud_hub",
        "--hidden-import=mobile_server",
        "--hidden-import=fastapi_server",
        "--hidden-import=temperature_worker",
        "--hidden-import=wintemp",
        # --- Hidden imports (core package) ---
        "--hidden-import=core",
        "--hidden-import=core.base",
        "--hidden-import=core.keyboard",
        "--hidden-import=core.manager",
        "--hidden-import=core.config",
        "--hidden-import=core.custom_effects_io",
        # --- Hidden imports (utils package) ---
        "--hidden-import=utils",
        "--hidden-import=utils.chroma_utils",
        "--hidden-import=utils.system_info",
        "--hidden-import=winreg",
        # --- Hidden imports (effects package) ---
        "--hidden-import=effects",
        "--hidden-import=effects.reactive_typing",
        "--hidden-import=effects.smooth_wave",
        "--hidden-import=effects.lightning",
        "--hidden-import=effects.scanner",
        "--hidden-import=effects.party",
        "--hidden-import=effects.realistic_fire",
        "--hidden-import=effects.aurora",
        "--hidden-import=effects.meteor",
        "--hidden-import=effects.mouse_aura",
        "--hidden-import=effects.valorant_spike",
        "--hidden-import=effects.battery",
        "--hidden-import=effects.temperature",
        "--hidden-import=effects.ambient",
        "--hidden-import=effects.audio_visualizer",
        "--hidden-import=effects.custom_sequence",
        "main.py",
    ]

    # Actually run the compile command
    subprocess.check_call(command)

    print("\n[SUCCESS] Custom Executable has been successfully compiled!")
    print(f"Location: {os.path.abspath('dist/4_Zone_Rgb_Toolkit.exe')}")
    print(
        "You can double-click this executable to run the standalone app without needing python!\n"
    )


if __name__ == "__main__":
    install_pyinstaller()
    compile_csharp_wrapper()
    build_standalone_exe()
