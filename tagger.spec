# -*- mode: python ; coding: utf-8 -*-
"""
Build do executável do Tagger (PyInstaller).

    pip install -r requirements-dev.txt
    pyinstaller tagger.spec            ->  dist/Tagger.exe

Um arquivo só, sem console, com ícone, as fontes de tagger/gui/recursos/fontes/ e a versão de tagger/__init__.py
no recurso do .exe (Propriedades > Detalhes, no Windows Explorer).
"""

import re
import sys
from pathlib import Path

RAIZ = Path(SPECPATH)
sys.path.insert(0, str(RAIZ))
from tagger import __version__

numeros = [int(n) for n in re.findall(r"\d+", __version__)[:4]]
numeros += [0] * (4 - len(numeros))

versao_exe = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )
    versao_exe = VSVersionInfo(
        ffi=FixedFileInfo(filevers=tuple(numeros), prodvers=tuple(numeros)),
        kids=[
            StringFileInfo([StringTable("041604B0", [
                StringStruct("CompanyName", "Tagger"),
                StringStruct("FileDescription", "Tagger — editor de tags de MP3"),
                StringStruct("FileVersion", __version__),
                StringStruct("InternalName", "Tagger"),
                StringStruct("LegalCopyright", "MIT License"),
                StringStruct("OriginalFilename", "Tagger.exe"),
                StringStruct("ProductName", "Tagger"),
                StringStruct("ProductVersion", __version__),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0416, 1200])]),
        ],
    )

datas = [("tagger/gui/recursos/fontes", "tagger/gui/recursos/fontes")]
# chaves das APIs (gerado no Actions por scripts/gerar_chaves.py); build local sem ele continua funcionando
if (RAIZ / "tagger" / "nucleo" / "chaves.json").exists():
    datas.append(("tagger/nucleo/chaves.json", "tagger/nucleo"))

a = Analysis(
    ["tagger/__main__.py"],
    pathex=[str(RAIZ)],
    datas=datas,
    excludes=["tkinter", "customtkinter", "tagger.cli", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Tagger",
    icon=str(RAIZ / "tagger" / "gui" / "recursos" / "tagger.ico"),
    version=versao_exe,
    console=False,               # --windowed
    upx=False,
    runtime_tmpdir=None,
)
