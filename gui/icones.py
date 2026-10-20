"""Ícones em SVG (traço fino, estilo do mockup), recoloridos conforme o tema."""

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap
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
    "check":     '<path d="M20 6 9 17l-5-5"/>',
}


def pixmap(nome, cor, tamanho=16, espessura=1.8, dpr=2.0):
    svg = (_CABECALHO.format(espessura=espessura) + _DESENHOS[nome] + "</svg>").replace("currentColor", cor)
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
    return QIcon(pixmap(nome, cor, tamanho, espessura))


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
