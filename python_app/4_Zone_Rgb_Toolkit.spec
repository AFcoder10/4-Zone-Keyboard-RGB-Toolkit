# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets/minus.svg', 'assets'), ('assets/plus.svg', 'assets'), ('assets/settings.svg', 'assets'), ('assets/toggle_off.svg', 'assets'), ('assets/toggle_on.svg', 'assets'), ('assets/rgb_wheel.ico', '.'), ('python_controller.py', '.'), ('audio_visualizer.py', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='4_Zone_Rgb_Toolkit',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\rgb_wheel.ico'],
)
