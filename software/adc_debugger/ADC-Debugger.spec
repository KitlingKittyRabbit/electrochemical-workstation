import os
from pathlib import Path

os.environ["QT_API"] = "pyside6"
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "firmware"), "firmware"),
        (str(ROOT / "runtime"), "runtime"),
        (str(ROOT / "run_linux.sh"), "."),
    ],
    hiddenimports=["firmware_installer"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "matplotlib",
        "IPython",
        "sphinx",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ADC-Debugger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="ADC-Debugger",
)
