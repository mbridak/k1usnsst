# -*- mode: python ; coding: utf-8 -*-


block_cipher = None


a = Analysis(['k1usnsst.py'],
             pathex=['.'],
             binaries=[('icon/*.png','icon'),
             ('font/*.ttf','font')],
             datas=[('cwinterface.py','.'),
             ('main.ui','.'),
             ('dialog.ui','.'),
             ('settings.ui','.'),
             ('cwmacros_sst.txt','.')
             ],
             hiddenimports=[],
             hookspath=[],
             hooksconfig={},
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
          a.binaries,
          a.zipfiles,
          a.datas,  
          [],
          name='k1usnsst.exe',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=False,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          disable_windowed_traceback=False,
          target_arch=None,
          codesign_identity=None,
          entitlements_file=None )
