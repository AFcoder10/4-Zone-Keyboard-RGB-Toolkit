import os
import sys
import subprocess


class PythonInnoSetupGenerator:
    def __init__(
        self, app_name, app_version, app_publisher, app_exe, source_dir, output_dir
    ):
        self.app_name = app_name
        self.app_version = app_version
        self.app_publisher = app_publisher
        self.app_exe = app_exe
        self.source_dir = os.path.abspath(source_dir)
        self.output_dir = os.path.abspath(output_dir)

    def generate_script(self, script_path="setup.iss"):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        value_data = '""{app}\\' + self.app_exe + '"" --hidden'
        script = f"""
[Setup]
AppName={self.app_name}
AppVersion={self.app_version}
AppPublisher={self.app_publisher}
DefaultDirName={{autopf}}\\{self.app_name}
DefaultGroupName={self.app_name}
SolidCompression=yes
Compression=lzma2/ultra64

OutputDir={self.output_dir}
OutputBaseFilename={self.app_name.replace(" ", "_")}_Setup
SetupIconFile={os.path.abspath("assets/rgb_wheel.ico")}

PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked
Name: "startupicon"; Description: "Launch {self.app_name} when Windows starts (Hidden in tray)"; GroupDescription: "{{cm:AdditionalIcons}}"; Flags: unchecked

[Files]
Source: "{self.source_dir}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{self.app_name}"; Filename: "{{app}}\\{self.app_exe}"
Name: "{{autodesktop}}\\{self.app_name}"; Filename: "{{app}}\\{self.app_exe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\\Microsoft\\Windows\\CurrentVersion\\Run"; ValueType: string; ValueName: "4ZoneRgbToolkit"; ValueData: "{value_data}"; Tasks: startupicon

[Run]
Filename: "{{app}}\\{self.app_exe}"; Description: "Launch {self.app_name}"; Flags: nowait postinstall skipifsilent
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        print(f"Generated Inno Setup Script: {script_path}")
        return script_path


def compile_inno_setup(script_path):
    # Standard installation paths for Inno Script Compiler
    possible_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"D:\Program Files\Inno Setup 6\ISCC.exe",
    ]

    iscc_path = None
    for p in possible_paths:
        if os.path.exists(p):
            iscc_path = p
            break

    if not iscc_path:
        print("[ERROR] Inno Setup Compiler (ISCC.exe) not found.")
        return False

    print(f"\nFound Inno Compiler at: {iscc_path}")
    print("Building Setup installer executable... This may take a minute...\n")
    try:
        subprocess.check_call([iscc_path, script_path])
        return True
    except subprocess.CalledProcessError as e:
        print(f"Compilation failed: {e}")
        return False


if __name__ == "__main__":
    APP_NAME = "4 Zone Rgb Toolkit"
    APP_VERSION = "1.0.0"
    APP_PUBLISHER = "Custom Hardware Integration"
    APP_EXE = "4_Zone_Rgb_Toolkit.exe"

    # With --onefile, the raw executable is dropped directly into the dist root
    SOURCE_DIST_DIR = os.path.abspath("dist")
    FINAL_OUTPUT_DIR = os.path.abspath("dist/Installer")

    print("=== SETUP WIZARD COMPILER ===")

    if not os.path.exists(os.path.join(SOURCE_DIST_DIR, APP_EXE)):
        print(f"[ERROR] Executable {APP_EXE} not found at: {SOURCE_DIST_DIR}")
        print(
            "You must run `build_exe.py` and `update_exe.py` normally first to create the standalone application bundle before it can be wrapped into an installer."
        )
        sys.exit(1)

    generator = PythonInnoSetupGenerator(
        APP_NAME, APP_VERSION, APP_PUBLISHER, APP_EXE, SOURCE_DIST_DIR, FINAL_OUTPUT_DIR
    )

    script_file = generator.generate_script("setup_wizard.iss")
    success = compile_inno_setup(script_file)

    if success:
        print(
            f"Your final setup installer is waiting at: {os.path.join(FINAL_OUTPUT_DIR, '4_Zone_Rgb_Toolkit_Setup.exe')}"
        )
