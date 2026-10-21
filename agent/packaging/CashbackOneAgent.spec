# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs
import os
import sys

block_cipher = None

datas = []
datas += collect_data_files('certifi')
datas += collect_data_files('tzdata')

binaries = []
try:
    binaries += collect_dynamic_libs('pywin32')
except Exception:
    pass

hiddenimports = [
    'win32timezone',
    'servicemanager',
    'win32service',
    'win32serviceutil',
    'win32event',
    'pythoncom',
    'pywintypes',
    'tzdata',
    'zoneinfo',
    'pydantic',
    'pydantic_settings',
    'httpx',
    'httpcore',
    'anyio',
    'poscenter_loyalty_agent',
    'poscenter_loyalty_agent.config',
    'poscenter_loyalty_agent.logging',
    'poscenter_loyalty_agent.main',
    'poscenter_loyalty_agent.models',
    'poscenter_loyalty_agent.runtime',
    'poscenter_loyalty_agent.state_store',
    'poscenter_loyalty_agent.windows_service',
    'poscenter_loyalty_agent.process_lock',
    'poscenter_loyalty_agent.source',
    'poscenter_loyalty_agent.one_com_source',
    'poscenter_loyalty_agent.one_cursor',
    'poscenter_loyalty_agent.one_mapping',
    'poscenter_loyalty_agent.one_time',
    'poscenter_loyalty_agent.phone_norm',
    'poscenter_loyalty_agent.dry_run',
    'poscenter_loyalty_agent.stage0',
    'poscenter_loyalty_agent.stage0.cli',
    'poscenter_loyalty_agent.stage0.environment',
    'poscenter_loyalty_agent.stage0.metadata_probe',
    'poscenter_loyalty_agent.stage0.data_profile',
    'poscenter_loyalty_agent.stage0.report',
]

a = Analysis(
    ['entrypoint.py'],
    pathex=['../src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CashbackOneAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='CashbackOneAgent',
)
