# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import shutil

from PyInstaller.config import CONF

LV_SERVER_DIR_NAME = 'LV Inst Manager'
APP_NAME = 'CE_MainBand_Radiation'


a = Analysis(
    ['src\\app\\__main__.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('resources', 'resources'),
        ('config', 'config'),
        ('testcases', 'testcases'),
    ],
    hiddenimports=['win32timezone'],
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
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)

# LV 실행 파일은 LabVIEW 쪽 상대 경로 기준을 유지하기 위해 exe 옆에 둔다.
lv_source = Path(LV_SERVER_DIR_NAME)
if not lv_source.is_dir():
    raise SystemExit(f'LV Inst Manager directory not found: {lv_source}')
lv_target = Path(CONF['distpath']) / APP_NAME / LV_SERVER_DIR_NAME
if lv_target.exists():
    shutil.rmtree(lv_target)
shutil.copytree(lv_source, lv_target)
