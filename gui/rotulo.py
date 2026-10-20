"""Rótulos que não empurram o tamanho mínimo da janela: cortam o texto com reticências e mostram tudo na dica."""

import html
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

_TAGS = re.compile(r"<[^>]+>")


def texto_puro(rico):
    """Texto visível de um trecho HTML simples (para medir a largura)."""
    return html.unescape(_TAGS.sub("", rico))


def quebravel(texto, minimo=16):
    """Permite quebrar palavras longas (ex.: nome de arquivo sem espaços) em rótulos com quebra de linha."""
    return " ".join("​".join(p) if len(p) > minimo else p for p in texto.split(" "))


class RotuloElidido(QLabel):
    """Uma linha só; corta com '…' quando não cabe e então mostra o texto completo na dica.

    `prefixo_html` (ex.: um ● colorido) fica sempre visível antes do texto.
    """

    def __init__(self, texto="", modo=Qt.ElideRight, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._texto = ""
        self._prefixo = ""
        self._dica = ""
        self._modo = modo
        self.setTextFormat(Qt.RichText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.definir(texto)

    def definir(self, texto, prefixo_html="", dica=""):
        self._texto = texto or ""
        self._prefixo = prefixo_html or ""
        self._dica = dica
        self._ajustar()

    def texto_completo(self):
        return self._texto

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar()

    def changeEvent(self, evento):
        super().changeEvent(evento)
        if evento.type() in (evento.Type.FontChange, evento.Type.StyleChange):
            self._ajustar()

    def _ajustar(self):
        fm = self.fontMetrics()
        margens = self.contentsMargins()
        livre = self.width() - margens.left() - margens.right() - fm.horizontalAdvance(texto_puro(self._prefixo))
        cortado = fm.elidedText(self._texto, self._modo, max(0, livre))
        super().setText(self._prefixo + html.escape(cortado))
        self.setToolTip(self._dica or (self._texto if cortado != self._texto else ""))


class Migalha(QLabel):
    """Caminho da pasta: mostra as últimas pastas que couberem (até 3) e '…' quando há mais antes."""

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._partes = []
        self._cores = {}
        self.setTextFormat(Qt.RichText)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)

    def definir(self, partes, cores, dica=""):
        self._partes = list(partes)
        self._cores = cores
        self.setToolTip(dica)
        self._ajustar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar()

    def _ajustar(self):
        if not self._partes or not self._cores:
            super().setText("")
            return
        fm = self.fontMetrics()
        sep = " › "
        livre = self.width() - 2
        partes = self._partes
        n = min(3, len(partes))
        while n > 1 and fm.horizontalAdvance(("…" + sep) * (n < len(partes)) + sep.join(partes[-n:])) > livre:
            n -= 1
        visiveis = list(partes[-n:])
        corta_inicio = n < len(partes)
        if n == 1:   # nem a última pasta cabe inteira
            reservado = fm.horizontalAdvance("…" + sep) if corta_inicio else 0
            visiveis[0] = fm.elidedText(visiveis[0], Qt.ElideMiddle, max(0, livre - reservado))

        seta = f'<span style="color:{self._cores["faint"]}">{sep}</span>'
        pedacos = [html.escape(p) for p in visiveis]
        pedacos[-1] = f'<span style="color:{self._cores["text"]}">{pedacos[-1]}</span>'
        if corta_inicio:
            pedacos.insert(0, "…")
        super().setText(seta.join(pedacos))
