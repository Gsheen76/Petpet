# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import re

project_root = Path(SPECPATH).resolve().parent
icon_path = project_root / "build" / "Petpet.icns"
source_text = (project_root / "version.py").read_text(encoding="utf-8")
version = re.search(r'^VERSION\s*=\s*"([^"]+)"', source_text, re.MULTILINE).group(1)
assets_root = project_root / "assets"
animation_root = assets_root / "animations"
pose_datas = [
    (str(path), "assets/poses")
    for path in (assets_root / "poses").glob("*.png")
]
asset_datas = [
    (str(assets_root / "icons"), "assets/icons"),
    (str(assets_root / "sounds"), "assets/sounds"),
    (str(assets_root / "props"), "assets/props"),
    (str(assets_root / "decorations"), "assets/decorations"),
    (str(assets_root / "knowledge"), "assets/knowledge"),
    (str(assets_root / "scenes"), "assets/scenes"),
    (str(animation_root / "manifest.json"), "assets/animations"),
]
asset_datas.extend(pose_datas)
asset_datas.extend(
    (str(path), f"assets/animations/{path.name}")
    for path in animation_root.iterdir()
    if path.is_dir() and path.name != "sources"
)

a = Analysis(
    [str(project_root / "pet.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=asset_datas + [(str(project_root / "config.json.example"), ".")],
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
