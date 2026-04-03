# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + collect_submodules("starlette")
    + [
        "email.mime.multipart",
        "email.mime.text",
        "sklearn.ensemble",
        "sklearn.linear_model",
        "sklearn.feature_extraction",
        "sklearn.model_selection",
        "sklearn.metrics",
    ]
)

a = Analysis(
    ["app/cli.py"],
    pathex=[],
    binaries=[],
    datas=[("app/static", "app/static")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="mental-math-trainer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)
