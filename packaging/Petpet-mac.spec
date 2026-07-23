# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import re

project_root = Path(SPECPATH).resolve().parent
icon_path = project_root / "build" / "Petpet.icns"
source_text = (project_root / "pet.py").read_text(encoding="utf-8")
version = re.search(r'^VERSION\s*=\s*"([^"]+)"', source_text, re.MULTILINE).group(1)

a = Analysis(
    [str(project_root / "pet.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "poses"), "poses"),
        (str(project_root / "icons"), "icons"),
        (str(project_root / "buddy_ai.py"), "."),
        (str(project_root / "config.json.example"), "."),
    ],
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
    name="Petpet",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name="Petpet.app",
    icon=str(icon_path),
    bundle_identifier="com.gsheen.petpet",
    info_plist={
        "CFBundleDisplayName": "Pet陪它",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
    },
)
