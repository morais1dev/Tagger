"""
Log em arquivo e erros inesperados.

Qualquer exceção não tratada (na janela ou numa thread de leitura/gravação) vai para o
tagger.log e aparece num diálogo, em vez de o programa fechar ou travar sem aviso.
O log fica na pasta de dados do usuário (no Windows: %LOCALAPPDATA%\\Tagger).
"""

import logging
import platform
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

log = logging.getLogger("tagger")


def pasta_de_dados():
    """Pasta de dados do usuário (precisa do QApplication já criado, com o nome do app)."""
    pasta = Path(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation))
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def configurar_log(versao):
    """Liga o log em tagger.log (até ~1 MB, mais 2 arquivos antigos). Devolve o caminho."""
    caminho = pasta_de_dados() / "tagger.log"
    arquivo = RotatingFileHandler(caminho, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    arquivo.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(arquivo)
    log.setLevel(logging.INFO)

    import mutagen
    from PySide6 import __version__ as versao_pyside
    log.info("Tagger %s · Python %s · PySide6 %s · mutagen %s · %s", versao, platform.python_version(),
             versao_pyside, mutagen.version_string, platform.platform())
    return caminho


class _Ponte(QObject):
    """Leva o erro de qualquer thread para a thread da interface (só ela pode abrir janelas)."""
    erro = Signal(str)


def instalar_tratamento_de_erros(caminho_log):
    ponte = _Ponte(QApplication.instance())
    mostrando = []

    def mostrar(detalhes):
        if mostrando:                 # um erro em cascata não empilha dezenas de janelas
            return
        mostrando.append(True)
        try:
            caixa = QMessageBox(QApplication.activeWindow())
            caixa.setIcon(QMessageBox.Critical)
            caixa.setWindowTitle("Erro inesperado")
            caixa.setText("O Tagger encontrou um erro inesperado, mas continua aberto.")
            caixa.setInformativeText("Suas alterações não salvas foram mantidas. Se algo parecer errado, "
                                     f"salve o que puder e reabra o programa.\n\nDetalhes em: {caminho_log}")
            caixa.setDetailedText(detalhes)
            abrir = caixa.addButton("Abrir pasta do log", QMessageBox.ActionRole)
            caixa.addButton(QMessageBox.Ok)
            caixa.exec()
            if caixa.clickedButton() is abrir:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(caminho_log).parent)))
        finally:
            mostrando.clear()

    ponte.erro.connect(mostrar, Qt.QueuedConnection)

    def gancho(tipo, valor, rastro):
        if issubclass(tipo, KeyboardInterrupt):
            sys.__excepthook__(tipo, valor, rastro)
            return
        detalhes = "".join(traceback.format_exception(tipo, valor, rastro))
        log.error("Erro não tratado:\n%s", detalhes)
        try:
            ponte.erro.emit(detalhes)
        except RuntimeError:          # app já fechando
            sys.__excepthook__(tipo, valor, rastro)

    sys.excepthook = gancho
    threading.excepthook = lambda args: gancho(args.exc_type, args.exc_value, args.exc_traceback)
