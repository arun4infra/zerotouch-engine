# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for ZTC binary distribution"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Collect all adapter data files (YAML, templates, scripts)
datas = []
datas += collect_data_files('ztc.adapters.hetzner', include_py_files=False)
datas += collect_data_files('ztc.adapters.cilium', include_py_files=False)
datas += collect_data_files('ztc.adapters.talos', include_py_files=False)

# Collect versions.yaml
datas += [('ztc/versions.yaml', 'ztc')]

# Collect all submodules
hiddenimports = []
hiddenimports += collect_submodules('ztc')
hiddenimports += ['typer', 'rich', 'pydantic', 'jinja2', 'yaml', 'aiohttp', 'cryptography']

a = Analysis(
    ['ztc/cli.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='ztc',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
