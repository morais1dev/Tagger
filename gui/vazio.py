"""Tela inicial (nenhum arquivo aberto): área de arrastar e soltar + pastas recentes."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gui.icones import icone, pixmap
from gui.rotulo import RotuloElidido
from gui.tema import repolir


class LinhaRecente(QFrame):
    """Uma pasta recente: a linha inteira é clicável (e focável pelo teclado), com botão para tirar da lista."""
    abrir = Signal(str)
    remover = Signal(str)

    def __init__(self, caminho, cores, parent=None):
        super().__init__(parent, objectName="linhaRecente")
        self.caminho = str(caminho)
        caminho = Path(caminho)
        nome = caminho.name or str(caminho)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(f"Abrir pasta recente {nome}")
        self.setToolTip(str(caminho))

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 6, 6, 6)
        h.setSpacing(10)
        icone_pasta = QLabel()
        icone_pasta.setPixmap(pixmap("pasta", cores.get("muted", "#888888"), 16))
        self.lbl_nome = RotuloElidido(nome, objectName="nomeRecente")
        self.lbl_local = RotuloElidido(str(caminho.parent), Qt.ElideMiddle)
        self.lbl_local.setProperty("papel", "sub")
        self.lbl_local.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        for rotulo in (self.lbl_nome, self.lbl_local):
            rotulo.setAttribute(Qt.WA_TransparentForMouseEvents)
            rotulo.setToolTip("")
        botao = QPushButton()
        botao.setProperty("tipo", "fantasma")
        botao.setIcon(icone("fechar", cores.get("muted", "#888888"), 14))
        botao.setFixedSize(26, 26)
        botao.setToolTip("Tirar da lista de recentes")
        botao.setAccessibleName(f"Tirar {nome} da lista de recentes")
        botao.setCursor(Qt.ArrowCursor)
        botao.clicked.connect(lambda: self.remover.emit(self.caminho))
        h.addWidget(icone_pasta)
        h.addWidget(self.lbl_nome, 2)
        h.addWidget(self.lbl_local, 3)
        h.addWidget(botao)

    def mouseReleaseEvent(self, evento):
        if evento.button() == Qt.LeftButton and self.rect().contains(evento.position().toPoint()):
            self.abrir.emit(self.caminho)
        super().mouseReleaseEvent(evento)

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.abrir.emit(self.caminho)
        elif evento.key() == Qt.Key_Delete:
            self.remover.emit(self.caminho)
        else:
            super().keyPressEvent(evento)


class TelaVazia(QWidget):
    abrirPasta = Signal()
    escolherArquivos = Signal()
    abrirRecente = Signal(str)
    removerRecente = Signal(str)

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
        self.lbl_texto = QLabel(objectName="textoVazio", alignment=Qt.AlignCenter)
        self.lbl_texto.setWordWrap(True)
        self.definir_subpastas(True)

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
        vz.addWidget(self.lbl_texto)
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

    def definir_subpastas(self, incluir):
        inicio = "Subpastas são incluídas." if incluir else "Só os arquivos da própria pasta (sem subpastas)."
        self.lbl_texto.setText(f"{inicio} Nada é gravado nos arquivos até você clicar em Salvar.")

    def destacar(self, ativo):
        """Borda na cor de destaque enquanto o usuário arrasta arquivos por cima da janela."""
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
        for pasta in existentes:
            linha = LinhaRecente(pasta, self.cores)
            linha.abrir.connect(self.abrirRecente)
            linha.remover.connect(self.removerRecente)
            self.layout_recentes.addWidget(linha)
