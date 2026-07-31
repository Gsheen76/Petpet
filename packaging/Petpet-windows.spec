# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH).resolve().parent
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
    icon=str(project_root / "assets" / "icons" / "icon-256.png"),
    manifest=str(project_root / "packaging" / "Petpet-windows.manifest"),
)
