# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

project_folder = Path('.').resolve()
mkob_folder = project_folder / 'MKOB'
mkob_app = mkob_folder / 'MKOB.pyw'
mkob_resources_folder = mkob_folder / 'resources'
mkob_resources = mkob_resources_folder / '*'
pykob_folder = project_folder / 'pykob'
pykob_data_folder = pykob_folder / 'data'
pykob_data = pykob_data_folder / '*'
pykob_resources_folder = pykob_folder / 'resources'
pykob_resources = pykob_resources_folder / '*'

print('Project:', project_folder)
print('MKOB4:', mkob_app)
print('MKOB4 Resources:', mkob_resources)
print('PyKOB:', pykob_folder)
print('PyKOB Data:', pykob_data)
print('PyKOB Resources:', pykob_resources)

data_files = [
    (mkob_resources, 'resources'), 
    (pykob_data, 'pykob/data'), 
    (pykob_resources, 'pykob/resources')
]
print('Data Files:', data_files)

a = Analysis([str(mkob_app)],
             pathex=[project_folder],
             binaries=[],
             datas=data_files,
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
          name='MKOB4',
          debug=True,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='MKOB4')
