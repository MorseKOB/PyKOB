# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

project_folder = Path("../.."")
mkob_folder = project_folder / "MKOB"
resources_folder = mkob_folder / "resources"
resources = resources_folder / "*"
pykob_folder = project_folder / "pykob"
pykob_code_tables = pykob_folder / "codetable-*"
pykob_audio = pykob_folder /

data_files = [
    ( 'resources)
]
a = Analysis(['../../MKOB/MKOB.pyw'],
             pathex=['C:\\Users\\esilk\\code\\morse\\PyKOB'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='MKOB',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='MKOB')
