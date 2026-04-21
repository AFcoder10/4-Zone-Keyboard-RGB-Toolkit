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
        "--icon=assets/rgb_wheel.ico",
        "--name=4_Zone_Rgb_Toolkit",
        "--version-file=version_info.txt",
        "--add-data=assets/minus.svg;assets",
        "--add-data=assets/plus.svg;assets",
        "--add-data=assets/settings.svg;assets",
        "--add-data=assets/toggle_off.svg;assets",
        "--add-data=assets/toggle_on.svg;assets",
        "--add-data=assets/rgb_wheel.ico;assets",
        "--add-data=python_controller.py;.",
        "--add-data=audio_visualizer.py;.",
        "--add-data=temperature_worker.py;.",
        "--add-data=../wintemp.py;.",
        "--add-data=../LibreHardwareMonitor;LibreHardwareMonitor",
        "--hidden-import=clr",
        "--hidden-import=System",
        "--hidden-import=psutil",
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
    build_standalone_exe()
