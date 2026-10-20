"""Tela inicial (nenhum arquivo aberto): área de arrastar e soltar + pastas recentes."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.icones import icone, pixmap
from gui.tema import repolir


class TelaVazia(QWidget):
    abrirPasta = Signal()
    escolherArquivos = Signal()
    abrirRecente = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cores = {}
        self._recentes = []

        externo = QVBoxLayout(self)
        externo.setContentsMargins(16, 32, 16, 32)
        externo.addStretch()

        miolo = QWidget()
        miolo.setMaximumWidth(560)
        v = QVBoxLayout(miolo)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(28)

        # área de soltar
        self.zona = QFrame(objectName="zonaDrop")
        vz = QVBoxLayout(self.zona)
        vz.setContentsMargins(32, 48, 32, 40)
        vz.setSpacing(14)
        vz.setAlignment(Qt.AlignHCenter)

        self.lbl_icone = QLabel(objectName="iconeDrop", alignment=Qt.AlignCenter)
        self.lbl_icone.setFixedSize(56, 56)
        titulo = QLabel("Arraste uma pasta ou arquivos MP3 aqui", objectName="tituloVazio", alignment=Qt.AlignCenter)
        texto = QLabel("Subpastas são incluídas. Nada é gravado nos arquivos até você clicar em Salvar.",
                       objectName="textoVazio", alignment=Qt.AlignCenter)
        texto.setWordWrap(True)

        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        botoes.addStretch()
        self.btn_pasta = QPushButton("Abrir pasta")
        self.btn_pasta.setProperty("tipo", "primario")
        self.btn_pasta.setMinimumHeight(38)
        self.btn_pasta.clicked.connect(self.abrirPasta)
        self.btn_arquivos = QPushButton("Escolher arquivos")
        self.btn_arquivos.setMinimumHeight(38)
        self.btn_arquivos.clicked.connect(self.escolherArquivos)
        botoes.addWidget(self.btn_pasta)
        botoes.addWidget(self.btn_arquivos)
        botoes.addStretch()

        dica = QHBoxLayout()
        dica.setSpacing(6)
        dica.addStretch()
        for tecla in ("Ctrl", "O"):
            lbl = QLabel(tecla)
            lbl.setProperty("papel", "tecla")
            dica.addWidget(lbl)
        dica.addWidget(QLabel("abre uma pasta", objectName="dicaVazio"))
        dica.addStretch()

        vz.addWidget(self.lbl_icone, 0, Qt.AlignHCenter)
        vz.addWidget(titulo)
        vz.addWidget(texto)
        vz.addSpacing(8)
        vz.addLayout(botoes)
        vz.addLayout(dica)
        v.addWidget(self.zona)

        # recentes
        self.caixa_recentes = QWidget()
        self.layout_recentes = QVBoxLayout(self.caixa_recentes)
        self.layout_recentes.setContentsMargins(0, 0, 0, 0)
        self.layout_recentes.setSpacing(2)
        v.addWidget(self.caixa_recentes)

        linha = QHBoxLayout()
        linha.addStretch()
        linha.addWidget(miolo, 1)
        linha.addStretch()
        externo.addLayout(linha)
        externo.addStretch()

    def definir_aparencia(self, cores):
        self.cores = cores
        self.lbl_icone.setPixmap(pixmap("upload", cores["accent"], 26, espessura=1.7))
        self.btn_pasta.setIcon(icone("pasta", cores["on_accent"], espessura=1.9))
        self.definir_recentes(self._recentes)

    def destacar(self, ativo):
        """Borda verde enquanto o usuário arrasta arquivos por cima da janela."""
        self.zona.setProperty("ativo", ativo)
        repolir(self.zona)

    def definir_recentes(self, pastas):
        self._recentes = list(pastas)
        while self.layout_recentes.count():
            item = self.layout_recentes.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        existentes = [p for p in self._recentes if Path(p).is_dir()]
        self.caixa_recentes.setVisible(bool(existentes))
        if not existentes:
            return

        titulo = QLabel("Recentes", objectName="tituloRecentes")
        titulo.setContentsMargins(12, 0, 0, 4)
        self.layout_recentes.addWidget(titulo)
        cor_icone = self.cores.get("muted", "#888888")
        for pasta in existentes:
            caminho = Path(pasta)
            linha = QWidget()
            h = QHBoxLayout(linha)
            h.setContentsMargins(0, 0, 12, 0)
            botao = QPushButton(caminho.name or str(caminho))
            botao.setProperty("tipo", "fantasma")
            botao.setIcon(icone("pasta", cor_icone))
            botao.setToolTip(str(caminho))
            botao.setCursor(Qt.PointingHandCursor)
            botao.setStyleSheet("text-align: left;")
            botao.clicked.connect(lambda _=False, p=str(caminho): self.abrirRecente.emit(p))
            local = QLabel(str(caminho.parent))
            local.setProperty("papel", "sub")
            h.addWidget(botao, 1)
            h.addWidget(local)
            self.layout_recentes.addWidget(linha)
