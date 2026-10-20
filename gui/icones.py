"""Ícones em SVG (traço fino, estilo do mockup), recoloridos conforme o tema."""

import tempfile
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer

_CABECALHO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
              'stroke="currentColor" stroke-width="{espessura}" stroke-linecap="round" stroke-linejoin="round">')

_DESENHOS = {
    "musica":    '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "pasta":     '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "arquivo+":  '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 11v6M9 14h6"/>',
    "desfazer":  '<path d="M9 14 4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
    "refazer":   '<path d="m15 14 5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/>',
    "busca":     '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "sol":       '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "lua":       '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "salvar":    '<path d="M5 3h11l5 5v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M7 3v5h8"/><path d="M7 21v-7h10v7"/>',
    "imagem":    '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
    "upload":    '<path d="M12 15V3"/><path d="m7 8 5-5 5 5"/><path d="M20 15v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2v-4"/>',
    "seta":      '<path d="m9 6 6 6-6 6"/>',
    "seta_baixo": '<path d="m6 9 6 6 6-6"/>',
    "seta_cima": '<path d="m6 15 6-6 6 6"/>',
    "fechar":    '<path d="M18 6 6 18M6 6l12 12"/>',
    "painel":    '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/>',
    "check":     '<path d="M20 6 9 17l-5-5"/>',
    "config":    '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
    "mais":      '<circle cx="5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="19" cy="12" r="1.2"/>',
}


PASTA_SVG = Path(tempfile.gettempdir()) / "tagger-icones"


def _svg(nome, cor, espessura):
    return (_CABECALHO.format(espessura=espessura) + _DESENHOS[nome] + "</svg>").replace("currentColor", cor)


def escalas_das_telas():
    """devicePixelRatio de cada monitor conectado (ex.: {1.0, 1.5})."""
    escalas = {s.devicePixelRatio() for s in QGuiApplication.screens()} if QGuiApplication.instance() else set()
    return sorted(escalas or {1.0})


def pixmap(nome, cor, tamanho=16, espessura=1.8, dpr=None):
    """dpr=None: a maior escala entre os monitores, para ficar nítido em qualquer um deles."""
    if dpr is None:
        dpr = max(escalas_das_telas())
    svg = _svg(nome, cor, espessura)
    renderizador = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    lado = int(tamanho * dpr)
    pm = QPixmap(lado, lado)
    pm.fill(Qt.transparent)
    pintor = QPainter(pm)
    pintor.setRenderHint(QPainter.Antialiasing)
    renderizador.render(pintor, QRectF(0, 0, lado, lado))
    pintor.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def icone(nome, cor, tamanho=16, espessura=1.8):
    """Um pixmap por escala de monitor: o Qt escolhe o certo ao mudar a janela de tela."""
    resultado = QIcon()
    for dpr in set(escalas_das_telas()) | {1.0}:
        resultado.addPixmap(pixmap(nome, cor, tamanho, espessura, dpr))
    return resultado


def arquivo_svg(nome, cor, espessura=2.0):
    """Caminho de um .svg do ícone (para usar em `image: url(...)` no QSS)."""
    PASTA_SVG.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SVG / f"{nome}-{QColor(cor).name()[1:]}-{espessura:g}.svg"
    if not destino.exists():
        destino.write_text(_svg(nome, QColor(cor).name(), espessura), encoding="utf-8")
    return destino.as_posix()


def circulo(cor, tamanho=12):
    """Bolinha de cor (amostra da cor personalizada)."""
    dpr = max(escalas_das_telas())
    lado = int(tamanho * dpr)
    pm = QPixmap(lado, lado)
    pm.fill(Qt.transparent)
    pintor = QPainter(pm)
    pintor.setRenderHint(QPainter.Antialiasing)
    pintor.setPen(Qt.NoPen)
    pintor.setBrush(QColor(cor))
    pintor.drawEllipse(QRectF(0.5, 0.5, lado - 1, lado - 1))
    pintor.end()
    pm.setDevicePixelRatio(dpr)
    return QIcon(pm)


def icone_app(cor_fundo, cor_simbolo, tamanho=256):
    """Ícone da janela/barra de tarefas: nota musical num quadrado arredondado."""
    pm = QPixmap(tamanho, tamanho)
    pm.fill(Qt.transparent)
    pintor = QPainter(pm)
    pintor.setRenderHint(QPainter.Antialiasing)
    caminho = QPainterPath()
    caminho.addRoundedRect(QRectF(0, 0, tamanho, tamanho), tamanho * 0.24, tamanho * 0.24)
    pintor.fillPath(caminho, QColor(cor_fundo))
    margem = tamanho * 0.2
    simbolo = pixmap("musica", cor_simbolo, tamanho=int(tamanho - 2 * margem), espessura=2.4, dpr=1.0)
    pintor.drawPixmap(int(margem), int(margem), simbolo)
    pintor.end()
    return QIcon(pm)
