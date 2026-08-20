# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path


project_root = Path(SPECPATH).resolve().parent
runtime_assets_root = project_root / "assets" / "runtime"
asset_datas = [(str(runtime_assets_root), "assets/runtime")]

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
    icon=str(runtime_assets_root / "icons" / "icon-256.png"),
    manifest=str(project_root / "packaging" / "Petpet-windows.manifest"),
)
