"""Diálogo "Sobre o Tagger": versão, fontes dos dados online e os avisos que os serviços exigem."""

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from tagger import __version__
from tagger.nucleo import discogs, lastfm


def texto_sobre():
    """HTML do diálogo (separado para testar sem abrir janela)."""
    return (
        f"<p><b>Tagger {html.escape(__version__)}</b><br>Editor de tags de música.</p>"
        "<p>Busca online: tags do <a href=\"https://musicbrainz.org\">MusicBrainz</a>, capas do "
        "<a href=\"https://coverartarchive.org\">Cover Art Archive</a>, dados do "
        f"<a href=\"{discogs.URL_SITE}\">Discogs</a> e do <a href=\"https://www.last.fm\">Last.fm</a> "
        f"({html.escape(lastfm.ATRIBUICAO)}; uso não comercial).</p>"
        f"<p>{html.escape(discogs.AVISO_SOBRE)}</p>"
    )


class DialogoSobre(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sobre o Tagger")
        from tagger.gui.busca_online import colorir_links, cores_do_tema
        texto = QLabel(colorir_links(texto_sobre(), cores_do_tema(parent)))
        texto.setTextFormat(Qt.RichText)
        texto.setWordWrap(True)
        texto.setOpenExternalLinks(True)
        texto.setTextInteractionFlags(Qt.TextBrowserInteraction)
        fechar = QPushButton("Fechar")
        fechar.setProperty("tipo", "primario")
        fechar.clicked.connect(self.accept)
        rodape = QHBoxLayout()
        rodape.addStretch()
        rodape.addWidget(fechar)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 16)
        v.addWidget(texto)
        v.addLayout(rodape)
        self.resize(460, 0)
