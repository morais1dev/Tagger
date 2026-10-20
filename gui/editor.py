"""
Painel de edição (lado esquerdo): capa + campos de tags.

Funciona igual para 1 ou vários arquivos selecionados:
- campo com o mesmo valor em todos -> mostra o valor;
- campo com valores diferentes -> fica vazio com o texto ‹vários valores›
  e só é alterado se você digitar algo nele.
"""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QFont, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QCompleter, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from metadata import VARIOS, ler_capa, rotulo, valores_comuns
from gui.icones import pixmap
from gui.tema import repolir

CAMPOS_LARGOS_1 = ["title", "artist", "album", "albumartist"]
CAMPOS_PARES = ["tracknumber", "discnumber", "date", "genre"]
CAMPOS_LARGOS_2 = ["composer", "lyricist"]
CAMPO_MULTILINHA = "comment"
CAMPOS_MONO = {"tracknumber", "discnumber", "date"}

TEXTO_VARIOS = "‹vários valores›"
LADO_CAPA = 112
LIMITE_COMPARAR_CAPAS = 150     # acima disso não compara as capas uma a uma

GENEROS = [
    "Alternative", "Ambient", "Axé", "Blues", "Bossa Nova", "Classical", "Country", "Dance",
    "Disco", "Drum & Bass", "Electronic", "Folk", "Forró", "Funk", "Gospel", "Hard Rock",
    "Heavy Metal", "Hip-Hop", "House", "Indie", "Indie Rock", "Jazz", "Lo-Fi", "Metal",
    "MPB", "Pagode", "Pop", "Pop Rock", "Punk", "R&B", "Rap", "Reggae", "Rock", "Samba",
    "Sertanejo", "Soul", "Soundtrack", "Synthpop", "Techno", "Trap",
]


def _rotulo(texto, papel):
    lbl = QLabel(texto)
    lbl.setProperty("papel", papel)
    return lbl


def _capa_arredondada(dados, lado, dpr, raio=10):
    """Recorta a imagem num quadrado com cantos arredondados. None se inválida."""
    imagem = QImage.fromData(dados)
    if imagem.isNull():
        return None
    px = int(lado * dpr)
    escalada = QPixmap.fromImage(imagem).scaled(px, px, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    final = QPixmap(px, px)
    final.fill(Qt.transparent)
    pintor = QPainter(final)
    pintor.setRenderHint(QPainter.Antialiasing)
    caminho = QPainterPath()
    caminho.addRoundedRect(QRectF(0, 0, px, px), raio * dpr, raio * dpr)
    pintor.setClipPath(caminho)
    pintor.drawPixmap((px - escalada.width()) // 2, (px - escalada.height()) // 2, escalada)
    pintor.end()
    final.setDevicePixelRatio(dpr)
    return final


def _descrever_capa(dados, mime):
    imagem = QImage.fromData(dados)
    formato = (mime or "").split("/")[-1].upper().replace("JPG", "JPEG") or "IMAGEM"
    tamanho = f"{max(1, round(len(dados) / 1024))} KB"
    if imagem.isNull():
        return f"{formato} · {tamanho}"
    return f"{formato} · {imagem.width()}×{imagem.height()} · {tamanho}"


class PainelEditor(QWidget):
    alterado = Signal()            # mudou o estado de "tem alterações pendentes"
    salvarPedido = Signal()
    descartarPedido = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("painel")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.cores = {}
        self.fonte_mono = QFont()
        self._faixas = []
        self._originais = {}       # campo -> texto mostrado ao carregar
        self._sujos = set()        # campos editados pelo usuário
        self._carregando = False
        self._capa_pendente = None # None | ("definir", dados, mime) | ("remover",)
        self._capa_atual = None    # (dados, mime) da capa mostrada, se houver
        self._capa_texto = ""      # texto quando não há imagem ("Sem capa", "‹várias capas›")
        self.campos = {}           # campo -> (widget, rótulo)

        self.pilha = QStackedWidget()
        self.pilha.addWidget(self._criar_vazio())
        self.pilha.addWidget(self._criar_conteudo())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.pilha)

    # ------------------------------------------------------------------ montagem
    def _criar_vazio(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(32, 32, 32, 32)
        v.addStretch()
        self.icone_vazio = QLabel(alignment=Qt.AlignCenter)
        titulo = QLabel("Nenhum arquivo selecionado", objectName="painelVazioTitulo", alignment=Qt.AlignCenter)
        texto = QLabel("Clique em uma música para editar.\nUse Ctrl ou Shift para editar várias de uma vez.",
                       objectName="painelVazioTexto", alignment=Qt.AlignCenter)
        texto.setWordWrap(True)
        for item in (self.icone_vazio, titulo, texto):
            v.addWidget(item)
        v.setSpacing(10)
        v.addStretch()
        return w

    def _criar_conteudo(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        # topo: título e subtítulo
        topo = QWidget(objectName="painelTopo")
        topo.setAttribute(Qt.WA_StyledBackground, True)
        vt = QVBoxLayout(topo)
        vt.setContentsMargins(20, 16, 20, 12)
        vt.setSpacing(3)
        self.lbl_titulo = QLabel(objectName="tituloPainel")
        self.lbl_sub = _rotulo("", "sub")
        self.lbl_sub.setWordWrap(True)
        vt.addWidget(self.lbl_titulo)
        vt.addWidget(self.lbl_sub)
        v.addWidget(topo)

        # corpo rolável
        corpo = QWidget(objectName="corpoPainel")
        corpo.setAttribute(Qt.WA_StyledBackground, True)
        vc = QVBoxLayout(corpo)
        vc.setContentsMargins(20, 16, 20, 20)
        vc.setSpacing(14)
        vc.addLayout(self._criar_bloco_capa())
        for campo in CAMPOS_LARGOS_1:
            vc.addWidget(self._criar_campo(campo))
        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(14)
        for i, campo in enumerate(CAMPOS_PARES):
            grade.addWidget(self._criar_campo(campo), i // 2, i % 2)
        grade.setColumnStretch(0, 1)
        grade.setColumnStretch(1, 1)
        vc.addLayout(grade)
        for campo in CAMPOS_LARGOS_2:
            vc.addWidget(self._criar_campo(campo))
        vc.addWidget(self._criar_campo(CAMPO_MULTILINHA, multilinha=True))
        vc.addStretch()

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rolagem.viewport().setObjectName("viewportPainel")
        rolagem.setWidget(corpo)
        v.addWidget(rolagem, 1)

        # rodapé fixo
        rodape = QWidget(objectName="painelRodape")
        rodape.setAttribute(Qt.WA_StyledBackground, True)
        hr = QHBoxLayout(rodape)
        hr.setContentsMargins(20, 12, 20, 12)
        hr.setSpacing(8)
        hr.addStretch()
        self.btn_descartar = QPushButton("Descartar")
        self.btn_descartar.setProperty("tipo", "fantasma")
        self.btn_descartar.clicked.connect(self.descartarPedido)
        self.btn_salvar = QPushButton("Salvar")
        self.btn_salvar.setProperty("tipo", "primario")
        self.btn_salvar.clicked.connect(self.salvarPedido)
        hr.addWidget(self.btn_descartar)
        hr.addWidget(self.btn_salvar)
        v.addWidget(rodape)
        return w

    def _criar_bloco_capa(self):
        h = QHBoxLayout()
        h.setSpacing(14)
        self.lbl_capa = QLabel(objectName="capa", alignment=Qt.AlignCenter)
        self.lbl_capa.setFixedSize(LADO_CAPA, LADO_CAPA)
        self.lbl_capa.setWordWrap(True)
        h.addWidget(self.lbl_capa)

        lado = QVBoxLayout()
        lado.setSpacing(6)
        lado.addStretch()
        self.lbl_info_capa = _rotulo("", "info")
        self.lbl_info_capa.setProperty("mono", True)
        self.lbl_info_capa.setTextFormat(Qt.RichText)
        lado.addWidget(self.lbl_info_capa)
        botoes = QHBoxLayout()
        botoes.setSpacing(6)
        self.btn_trocar_capa = QPushButton("Trocar capa")
        self.btn_trocar_capa.clicked.connect(self._escolher_capa)
        self.btn_remover_capa = QPushButton("Remover")
        self.btn_remover_capa.setProperty("tipo", "fantasma")
        self.btn_remover_capa.clicked.connect(self._remover_capa)
        botoes.addWidget(self.btn_trocar_capa)
        botoes.addWidget(self.btn_remover_capa)
        botoes.addStretch()
        lado.addLayout(botoes)
        h.addLayout(lado, 1)
        return h

    def _criar_campo(self, campo, multilinha=False):
        caixa = QWidget()
        v = QVBoxLayout(caixa)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        lbl = _rotulo(rotulo(campo), "rotulo")
        lbl.setTextFormat(Qt.RichText)

        if multilinha:
            widget = QPlainTextEdit()
            widget.setFixedHeight(76)
            widget.setTabChangesFocus(True)
            widget.textChanged.connect(lambda c=campo: self._ao_editar(c))
        else:
            widget = QLineEdit()
            widget.textEdited.connect(lambda _texto, c=campo: self._ao_editar(c))
            widget.returnPressed.connect(self._enter_no_campo)
            if campo in CAMPOS_MONO:
                widget.setProperty("mono", True)
            if campo == "genre":
                completar = QCompleter(GENEROS, widget)
                completar.setCaseSensitivity(Qt.CaseInsensitive)
                completar.setFilterMode(Qt.MatchContains)
                completar.popup().setObjectName("popupCompletar")
                widget.setCompleter(completar)
        lbl.setBuddy(widget)
        v.addWidget(lbl)
        v.addWidget(widget)
        self.campos[campo] = (widget, lbl)
        return caixa

    # ------------------------------------------------------------------ aparência
    def definir_aparencia(self, cores, fonte_mono):
        self.cores = cores
        self.fonte_mono = fonte_mono
        self.icone_vazio.setPixmap(pixmap("musica", cores["muted"], 28, espessura=1.5))
        for campo in self.campos:
            self._atualizar_rotulo(campo)
        self._mostrar_capa()

    # ------------------------------------------------------------------ carregar
    def carregar(self, faixas):
        """Mostra no painel os valores da seleção atual (descarta edições não salvas)."""
        self._faixas = list(faixas)
        self._sujos.clear()
        self._capa_pendente = None

        if not self._faixas:
            self.pilha.setCurrentIndex(0)
            self.alterado.emit()
            return
        self.pilha.setCurrentIndex(1)

        self._carregando = True
        comuns = valores_comuns(self._faixas)
        for campo, (widget, _lbl) in self.campos.items():
            varios = comuns[campo] == VARIOS
            texto = "" if varios else comuns[campo]
            self._originais[campo] = texto
            if isinstance(widget, QPlainTextEdit):
                widget.setPlainText(texto)
            else:
                widget.setText(texto)
                widget.setCursorPosition(0)
            widget.setPlaceholderText(TEXTO_VARIOS if varios else "")
            self._definir_erro(campo, False)
            self._atualizar_rotulo(campo)
        self._carregando = False

        n = len(self._faixas)
        if n == 1:
            f = self._faixas[0]
            self.lbl_titulo.setText(f.tags["title"] or f.nome)
            self.lbl_sub.setText(f"{f.nome} · {f.duracao_formatada} · {f.bitrate} kbps")
            self.lbl_sub.setToolTip(str(f.caminho))
        else:
            self.lbl_titulo.setText(f"{n} arquivos selecionados")
            self.lbl_sub.setText("Campos diferentes aparecem como ‹vários valores› e só mudam se você editar.")
            self.lbl_sub.setToolTip("")

        self._carregar_capa()
        self._atualizar_rodape()
        self.alterado.emit()

    def _carregar_capa(self):
        self._capa_atual = None
        com_capa = {f.tem_capa for f in self._faixas}

        if com_capa == {False}:
            self._capa_texto = "Sem capa"
        elif len(com_capa) > 1 or len(self._faixas) > LIMITE_COMPARAR_CAPAS:
            self._capa_texto = "‹várias capas›"
        else:
            primeira = ler_capa(self._faixas[0].caminho)
            iguais = primeira is not None and all(
                ler_capa(f.caminho) == primeira for f in self._faixas[1:])
            if iguais:
                self._capa_atual = primeira
            else:
                self._capa_texto = "‹várias capas›" if len(self._faixas) > 1 else "Sem capa"

        self.btn_remover_capa.setEnabled(True in com_capa)
        self._mostrar_capa()

    def _mostrar_capa(self):
        if not hasattr(self, "lbl_capa"):
            return
        pendente = self._capa_pendente
        dados = None
        if pendente and pendente[0] == "definir":
            dados, mime = pendente[1], pendente[2]
        elif pendente is None and self._capa_atual:
            dados, mime = self._capa_atual

        imagem = _capa_arredondada(dados, LADO_CAPA, self.devicePixelRatioF()) if dados else None
        if imagem is not None:
            self.lbl_capa.setPixmap(imagem)
            info = _descrever_capa(dados, mime)
        else:
            self.lbl_capa.setPixmap(QPixmap())
            self.lbl_capa.setText("Sem capa" if pendente else self._capa_texto)
            info = "Nenhuma imagem" if (pendente or self._capa_texto == "Sem capa") else "Capas diferentes"

        if pendente and self.cores:
            acao = "Nova capa" if pendente[0] == "definir" else "Capa será removida"
            info = (f'<span style="color:{self.cores["text"]}">{acao}</span> '
                    f'<span style="color:{self.cores["accent"]}">●</span><br>{info}')
        self.lbl_info_capa.setText(info)

    # ------------------------------------------------------------------ edição
    def _texto(self, campo):
        widget = self.campos[campo][0]
        return widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text()

    def _ao_editar(self, campo):
        if self._carregando:
            return
        if self._texto(campo) == self._originais.get(campo, ""):
            self._sujos.discard(campo)      # voltou ao valor original
        else:
            self._sujos.add(campo)
        self._definir_erro(campo, False)
        self._atualizar_rotulo(campo)
        self._atualizar_rodape()
        self.alterado.emit()

    def _atualizar_rotulo(self, campo):
        _widget, lbl = self.campos[campo]
        sujo = campo in self._sujos
        texto = rotulo(campo)
        if sujo and self.cores:
            texto += f'&nbsp;&nbsp;<span style="color:{self.cores["accent"]}">●</span>'
        lbl.setText(texto)
        if lbl.property("alterado") != sujo:
            lbl.setProperty("alterado", sujo)
            repolir(lbl)

    def _definir_erro(self, campo, erro):
        widget = self.campos[campo][0]
        if bool(widget.property("erro")) != erro:
            widget.setProperty("erro", erro)
            repolir(widget)

    def _atualizar_rodape(self):
        n = len(self._faixas)
        pendente = self.tem_pendencias()
        self.btn_salvar.setText("Salvar" if not pendente else
                                ("Salvar 1 arquivo" if n == 1 else f"Salvar {n} arquivos"))
        self.btn_salvar.setEnabled(pendente)
        self.btn_descartar.setEnabled(pendente)

    def _enter_no_campo(self):
        if self.tem_pendencias():
            self.salvarPedido.emit()

    def _escolher_capa(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Escolher capa", "", "Imagens (*.jpg *.jpeg *.png)")
        if not caminho:
            return
        dados = Path(caminho).read_bytes()
        if QImage.fromData(dados).isNull():
            return
        mime = "image/png" if caminho.lower().endswith(".png") else "image/jpeg"
        self._capa_pendente = ("definir", dados, mime)
        self.btn_remover_capa.setEnabled(True)
        self._mostrar_capa()
        self._atualizar_rodape()
        self.alterado.emit()

    def _remover_capa(self):
        self._capa_pendente = ("remover",)
        self._mostrar_capa()
        self._atualizar_rodape()
        self.alterado.emit()

    # ------------------------------------------------------------------ API pública
    @property
    def faixas(self):
        return self._faixas

    @property
    def capa_pendente(self):
        return self._capa_pendente

    def tem_pendencias(self):
        return bool(self._sujos) or self._capa_pendente is not None

    def quantidade_pendente(self):
        return len(self._sujos) + (1 if self._capa_pendente is not None else 0)

    def alteracoes(self):
        """Somente os campos que o usuário mexeu: {campo: texto}."""
        return {campo: self._texto(campo).strip() for campo in self._sujos}

    def marcar_erros(self, erros):
        primeiro = None
        for campo in erros:
            self._definir_erro(campo, True)
            primeiro = primeiro or campo
        if primeiro:
            self.campos[primeiro][0].setFocus()

    def focar_primeiro_campo(self):
        widget = self.campos["title"][0]
        widget.setFocus()
        widget.selectAll()
