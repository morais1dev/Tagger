"""
Painel de edição (lado esquerdo): capa + campos de tags.

Tudo o que é digitado aqui vai para o rascunho (alterações pendentes por arquivo).
Para 1 ou vários arquivos selecionados:
- campo com o mesmo valor em todos -> mostra o valor;
- campo com valores diferentes -> fica vazio com o texto ‹vários valores›
  e só é alterado se você digitar algo nele (apagar o que digitou volta ao estado anterior).
"""

from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, QStringListModel, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCompleter, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget,
)

from tagger.nucleo.metadata import ler_capa, rotulo, validar_valor
from tagger.gui.icones import icone, pixmap
from tagger.gui.rotulo import RotuloElidido, quebravel
from tagger.gui.tema import repolir

CAMPOS_LARGOS_1 = ["title", "artist", "album", "albumartist"]
CAMPOS_PARES = ["tracknumber", "discnumber", "date", "genre"]
CAMPOS_LARGOS_2 = ["composer", "lyricist"]
CAMPOS_MULTILINHA = {"comment": 76, "lyrics": 160}     # campo -> altura
CAMPOS_MONO = {"tracknumber", "discnumber", "date"}

TEXTO_VARIOS = "‹vários valores›"
LADO_CAPA = 112
BORDA_CAPA = 2                  # a mesma espessura com e sem arrastar, para a imagem não "pular"
LIMITE_COMPARAR_CAPAS = 150     # acima disso não compara as capas uma a uma
EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png")
LIMITE_BYTES_CAPA = 500 * 1024   # acima disso a capa é recomprimida (se a otimização estiver ligada)


# ---------------------------------------------------------------------------- imagens
def _rotulo(texto, papel):
    lbl = QLabel(texto)
    lbl.setProperty("papel", papel)
    return lbl


def imagem_para_bytes(imagem):
    """QImage -> (bytes, mime). PNG se tiver transparência, senão JPEG."""
    dados = QByteArray()
    buffer = QBuffer(dados)
    buffer.open(QIODevice.WriteOnly)
    if imagem.hasAlphaChannel():
        imagem.save(buffer, "PNG")
        mime = "image/png"
    else:
        imagem.convertToFormat(QImage.Format_RGB32).save(buffer, "JPEG", 92)
        mime = "image/jpeg"
    buffer.close()
    return bytes(dados), mime


def imagem_do_mime(mime_data):
    """Lê uma imagem de um arrastar/colar: arquivo de imagem ou imagem copiada. (bytes, mime) ou None."""
    for url in mime_data.urls() if mime_data.hasUrls() else []:
        caminho = Path(url.toLocalFile())
        if caminho.suffix.lower() in EXTENSOES_IMAGEM and caminho.is_file():
            dados = caminho.read_bytes()
            if not QImage.fromData(dados).isNull():
                return dados, ("image/png" if caminho.suffix.lower() == ".png" else "image/jpeg")
    if mime_data.hasImage():
        imagem = QImage(mime_data.imageData())
        if not imagem.isNull():
            return imagem_para_bytes(imagem)
    return None


def otimizar_imagem(dados, mime, lado_max):
    """
    Capa grande (lado > lado_max ou > 500 KB) vira JPEG de no máximo lado_max px.
    Devolve (dados, mime), os originais se a imagem já é pequena ou não dá para melhorar.
    """
    imagem = QImage.fromData(dados)
    if not lado_max or imagem.isNull():
        return dados, mime
    grande = max(imagem.width(), imagem.height()) > lado_max
    if not grande and len(dados) <= LIMITE_BYTES_CAPA:
        return dados, mime
    if grande:
        imagem = imagem.scaled(lado_max, lado_max, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if imagem.hasAlphaChannel():           # JPEG não tem transparência: fundo branco
        fundo = QImage(imagem.size(), QImage.Format_RGB32)
        fundo.fill(Qt.white)
        pintor = QPainter(fundo)
        pintor.drawImage(0, 0, imagem)
        pintor.end()
        imagem = fundo
    novos, novo_mime = imagem_para_bytes(imagem.convertToFormat(QImage.Format_RGB32))
    if not grande and len(novos) >= len(dados):
        return dados, mime
    return novos, novo_mime


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


class QuadroCapa(QLabel):
    """Quadro da capa: aceita imagem arrastada e tem menu de clique direito."""
    imagemSolta = Signal(object, str)
    menuPedido = Signal(object)

    def __init__(self):
        super().__init__(objectName="capa", alignment=Qt.AlignCenter)
        self.setFixedSize(LADO_CAPA, LADO_CAPA)
        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.menuPedido.emit(self.mapToGlobal(pos)))
        self.setToolTip("Arraste uma imagem aqui ou clique com o botão direito")

    def _arrastando(self, ativo):
        self.setProperty("arrastando", ativo)
        repolir(self)

    def dragEnterEvent(self, evento):
        dados = evento.mimeData()
        tem_imagem = dados.hasImage() or any(
            Path(u.toLocalFile()).suffix.lower() in EXTENSOES_IMAGEM for u in dados.urls())
        if tem_imagem and self.isEnabled():
            evento.acceptProposedAction()
            self._arrastando(True)
        else:
            evento.ignore()

    def dragLeaveEvent(self, evento):
        self._arrastando(False)

    def dropEvent(self, evento):
        self._arrastando(False)
        imagem = imagem_do_mime(evento.mimeData())
        if imagem:
            evento.acceptProposedAction()
            self.imagemSolta.emit(imagem[0], imagem[1])


# ---------------------------------------------------------------------------- painel
class PainelEditor(QWidget):
    alterado = Signal()            # algo no painel mudou o rascunho
    salvarPedido = Signal()
    descartarPedido = Signal()
    aviso = Signal(str)            # mensagem curta para a barra de status

    def __init__(self, rascunho, parent=None):
        super().__init__(parent)
        self.setObjectName("painel")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.rascunho = rascunho
        self.cores = {}
        self._faixas = []
        self._varios = {}          # campo -> True se os valores eram diferentes ao carregar
        self._fotos = {}           # campo -> fotografia do rascunho ao carregar
        self._carregando = False
        self._editando = False     # True enquanto o próprio painel mexe no rascunho
        self._capas_disco = {}     # cache: caminho -> (dados, mime) | None
        self._capa_mostrada = None # (dados, mime) da capa em exibição, se houver
        self.lado_max_capa = 0     # 0 = não reduz capas grandes ao inserir
        self.campos = {}           # campo -> (widget, rótulo)
        self._erros = {}           # campo -> rótulo da mensagem de erro (abaixo do campo)
        self._modelo_generos = QStringListModel(self)

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
        v.addStretch()
        self.icone_vazio = QLabel(alignment=Qt.AlignCenter)
        titulo = QLabel("Nenhum arquivo selecionado", objectName="painelVazioTitulo", alignment=Qt.AlignCenter)
        texto = QLabel("Clique em uma música para editar.\nUse Ctrl, Shift ou arraste o mouse para editar várias.",
                       objectName="painelVazioTexto", alignment=Qt.AlignCenter)
        texto.setWordWrap(True)
        texto.setContentsMargins(32, 0, 32, 0)
        for item in (self.icone_vazio, titulo, texto):
            v.addWidget(item)
        v.setSpacing(10)
        v.addStretch()
        self.rodape_vazio = self._criar_rodape()
        v.addWidget(self.rodape_vazio[0])
        v.setContentsMargins(0, 32, 0, 0)
        return w

    def _criar_conteudo(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        topo = QWidget(objectName="painelTopo")
        topo.setAttribute(Qt.WA_StyledBackground, True)
        vt = QVBoxLayout(topo)
        vt.setContentsMargins(20, 16, 20, 12)
        vt.setSpacing(3)
        self.lbl_titulo = RotuloElidido(objectName="tituloPainel")
        self.lbl_sub = _rotulo("", "sub")
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setMinimumWidth(0)
        vt.addWidget(self.lbl_titulo)
        vt.addWidget(self.lbl_sub)
        v.addWidget(topo)

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
        for campo in CAMPOS_MULTILINHA:
            vc.addWidget(self._criar_campo(campo, multilinha=True))
        vc.addStretch()

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rolagem.viewport().setObjectName("viewportPainel")
        rolagem.setWidget(corpo)
        v.addWidget(rolagem, 1)

        self.rodape = self._criar_rodape()
        v.addWidget(self.rodape[0])
        return w

    def _criar_rodape(self):
        rodape = QWidget(objectName="painelRodape")
        rodape.setAttribute(Qt.WA_StyledBackground, True)
        hr = QHBoxLayout(rodape)
        hr.setContentsMargins(20, 12, 20, 12)
        hr.setSpacing(8)
        hr.addStretch()
        descartar = QPushButton("Descartar")
        descartar.setProperty("tipo", "fantasma")
        descartar.setToolTip("Descartar todas as alterações não salvas")
        descartar.clicked.connect(self.descartarPedido)
        salvar = QPushButton("Salvar")
        salvar.setProperty("tipo", "primario")
        salvar.setToolTip("Salvar todas as alterações pendentes (Ctrl+S)")
        salvar.clicked.connect(self.salvarPedido)
        hr.addWidget(descartar)
        hr.addWidget(salvar)
        return rodape, descartar, salvar

    def _criar_bloco_capa(self):
        h = QHBoxLayout()
        h.setSpacing(14)
        self.quadro_capa = QuadroCapa()
        self.quadro_capa.imagemSolta.connect(lambda dados, mime: self._definir_capa(("definir", dados, mime)))
        self.quadro_capa.menuPedido.connect(self._menu_capa)
        h.addWidget(self.quadro_capa)

        lado = QVBoxLayout()
        lado.setSpacing(6)
        lado.addStretch()
        self.lbl_info_capa = _rotulo("", "info")
        self.lbl_info_capa.setTextFormat(Qt.RichText)
        self.lbl_info_capa.setProperty("mono", True)
        self.lbl_info_capa.setWordWrap(True)
        lado.addWidget(self.lbl_info_capa)
        botoes = QHBoxLayout()
        botoes.setSpacing(6)
        self.btn_trocar_capa = QPushButton("Trocar capa")
        self.btn_trocar_capa.clicked.connect(self._escolher_capa)
        self.btn_mais_capa = QPushButton()
        self.btn_mais_capa.setProperty("tipo", "fantasma")
        self.btn_mais_capa.setFixedSize(32, 32)
        self.btn_mais_capa.setToolTip("Mais opções da capa")
        self.btn_mais_capa.setAccessibleName("Mais opções da capa")
        self.btn_mais_capa.clicked.connect(
            lambda: self._menu_capa(self.btn_mais_capa.mapToGlobal(self.btn_mais_capa.rect().bottomLeft())))
        botoes.addWidget(self.btn_trocar_capa)
        botoes.addWidget(self.btn_mais_capa)
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
            widget.setFixedHeight(CAMPOS_MULTILINHA[campo])
            widget.setTabChangesFocus(True)
            widget.textChanged.connect(lambda c=campo: self._ao_editar(c))
        else:
            widget = QLineEdit()
            widget.textEdited.connect(lambda _texto, c=campo: self._ao_editar(c))
            widget.returnPressed.connect(self._enter_no_campo)
            if campo in CAMPOS_MONO:
                widget.setProperty("mono", True)
            if campo == "genre":
                completar = QCompleter(self._modelo_generos, widget)
                completar.setCaseSensitivity(Qt.CaseInsensitive)
                completar.setFilterMode(Qt.MatchContains)
                completar.popup().setObjectName("popupCompletar")
                widget.setCompleter(completar)
        lbl.setBuddy(widget)
        erro = _rotulo("", "erroCampo")
        erro.setWordWrap(True)
        erro.setVisible(False)
        v.addWidget(lbl)
        v.addWidget(widget)
        v.addWidget(erro)
        self.campos[campo] = (widget, lbl)
        self._erros[campo] = erro
        return caixa

    # ------------------------------------------------------------------ aparência
    def definir_aparencia(self, cores, altura_botao=32):
        """Também chamado quando a janela muda para um monitor com outra escala (refaz ícones e capa)."""
        self.cores = cores
        self.icone_vazio.setPixmap(pixmap("musica", cores["muted"], 28, espessura=1.5))
        self.btn_mais_capa.setIcon(icone("mais", cores["muted"]))
        self.btn_mais_capa.setFixedSize(altura_botao, altura_botao)
        for campo in self.campos:
            self._atualizar_rotulo(campo)
        self._mostrar_capa()

    def definir_generos(self, generos):
        self._modelo_generos.setStringList(sorted(set(generos), key=str.casefold))

    # ------------------------------------------------------------------ carregar
    def carregar(self, faixas):
        """Mostra a seleção atual (valores do rascunho por cima dos do arquivo)."""
        self._faixas = list(faixas)
        if not self._faixas:
            self.pilha.setCurrentIndex(0)
            self.atualizar_rodape()
            return
        self.pilha.setCurrentIndex(1)

        caminhos = [f.caminho for f in self._faixas]
        self._carregando = True
        for campo, (widget, _lbl) in self.campos.items():
            valores = {self.rascunho.valor(f, campo) for f in self._faixas}
            varios = len(valores) > 1
            texto = "" if varios else valores.pop()
            self._varios[campo] = varios
            self._fotos[campo] = self.rascunho.fotografar(caminhos, campo)
            if isinstance(widget, QPlainTextEdit):
                if widget.toPlainText() != texto:
                    widget.setPlainText(texto)
            elif widget.text() != texto:
                widget.setText(texto)
                widget.setCursorPosition(0)
            widget.setPlaceholderText(TEXTO_VARIOS if varios else "")
            self._validar_campo(campo, texto)
            self._atualizar_rotulo(campo)
        self._carregando = False

        n = len(self._faixas)
        if n == 1:
            f = self._faixas[0]
            self.lbl_titulo.definir(self.rascunho.valor(f, "title") or f.nome)
            bitrate = f"{f.bitrate} kbps" if f.bitrate else "—"
            self.lbl_sub.setText(f"{quebravel(f.nome)} · {f.duracao_formatada} · {bitrate}")
            self.lbl_sub.setToolTip(str(f.caminho))
        else:
            self.lbl_titulo.definir(f"{n} arquivos selecionados")
            self.lbl_sub.setText("Campos diferentes aparecem como ‹vários valores› e só mudam se você editar.")
            self.lbl_sub.setToolTip("")

        self._mostrar_capa()
        self.atualizar_rodape()

    def ao_mudar_rascunho(self):
        """O rascunho mudou por fora (desfazer, colar, tabela...): mostra os novos valores."""
        if not self._editando:
            self.carregar(self._faixas)
        else:
            self.atualizar_rodape()

    def invalidar_capas(self, caminhos=None):
        if caminhos is None:
            self._capas_disco.clear()
        else:
            for caminho in caminhos:
                self._capas_disco.pop(caminho, None)

    # ------------------------------------------------------------------ capa
    def _capa_efetiva(self, faixa):
        """(dados, mime) ou None, já considerando o rascunho."""
        pendente = self.rascunho.capa(faixa.caminho)
        if pendente is not None:
            return (pendente[1], pendente[2]) if pendente[0] == "definir" else None
        if not faixa.tem_capa:
            return None
        if faixa.caminho not in self._capas_disco:
            self._capas_disco[faixa.caminho] = ler_capa(faixa.caminho)
        return self._capas_disco[faixa.caminho]

    def _mostrar_capa(self):
        if not hasattr(self, "quadro_capa"):
            return
        faixas = self._faixas
        pendentes = [self.rascunho.capa(f.caminho) for f in faixas]
        tem_pendente = any(p is not None for p in pendentes)

        capa, texto = None, "Sem capa"
        if faixas:
            if len(faixas) > LIMITE_COMPARAR_CAPAS and not tem_pendente:
                todas_sem = not any(f.tem_capa for f in faixas)
                texto = "Sem capa" if todas_sem else "‹várias capas›"
            else:
                efetivas = [self._capa_efetiva(f) for f in faixas]
                primeira = efetivas[0]
                if all(e == primeira for e in efetivas[1:]):
                    capa = primeira
                else:
                    texto = "‹várias capas›"

        self._capa_mostrada = capa
        lado = LADO_CAPA - 2 * BORDA_CAPA
        imagem = _capa_arredondada(capa[0], lado, self.devicePixelRatioF(), raio=8) if capa else None
        if imagem is not None:
            self.quadro_capa.setText("")
            self.quadro_capa.setPixmap(imagem)
            info = _descrever_capa(capa[0], capa[1])
        else:
            self.quadro_capa.setPixmap(QPixmap())
            self.quadro_capa.setText(texto)
            info = "Capas diferentes" if texto.startswith("‹") else "Nenhuma imagem"

        if tem_pendente and self.cores:
            todas_remover = all(p is not None and p[0] == "remover" for p in pendentes)
            acao = "Capa será removida" if todas_remover else "Nova capa"
            info = (f'<span style="color:{self.cores["text"]}">{acao}</span> '
                    f'<span style="color:{self.cores["accent"]}">●</span><br>{info}')
        self.lbl_info_capa.setText(info)

    def _definir_capa(self, acao):
        if not self._faixas:
            return
        if acao and acao[0] == "definir":
            dados, mime = otimizar_imagem(acao[1], acao[2], self.lado_max_capa)
            if len(dados) != len(acao[1]):
                antes, depois = QImage.fromData(acao[1]), QImage.fromData(dados)
                self.aviso.emit(f"Capa reduzida: {antes.width()}×{antes.height()}, {round(len(acao[1]) / 1024)} KB "
                                f"→ {depois.width()}×{depois.height()}, {round(len(dados) / 1024)} KB")
            acao = ("definir", dados, mime)
        self._editando = True
        try:
            self.rascunho.definir_capa([f.caminho for f in self._faixas], acao)
        finally:
            self._editando = False
        self._mostrar_capa()
        self.atualizar_rodape()
        self.alterado.emit()

    def _escolher_capa(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Escolher capa", "", "Imagens (*.jpg *.jpeg *.png)")
        if not caminho:
            return
        dados = Path(caminho).read_bytes()
        if QImage.fromData(dados).isNull():
            self.aviso.emit("Não consegui abrir essa imagem.")
            return
        mime = "image/png" if caminho.lower().endswith(".png") else "image/jpeg"
        self._definir_capa(("definir", dados, mime))

    def colar_capa(self):
        imagem = imagem_do_mime(QApplication.clipboard().mimeData())
        if imagem is None:
            self.aviso.emit("Não há imagem na área de transferência.")
            return
        self._definir_capa(("definir", imagem[0], imagem[1]))

    def _exportar_capa(self):
        if not self._capa_mostrada:
            return
        dados, mime = self._capa_mostrada
        extensao = ".png" if mime == "image/png" else ".jpg"
        sugestao = (self.rascunho.valor(self._faixas[0], "album") or "capa") + extensao
        sugestao = "".join(c for c in sugestao if c not in '\\/:*?"<>|')
        pasta = self._faixas[0].caminho.parent
        destino, _ = QFileDialog.getSaveFileName(self, "Exportar capa", str(pasta / sugestao),
                                                 f"Imagem (*{extensao})")
        if destino:
            Path(destino).write_bytes(dados)
            self.aviso.emit(f"Capa exportada para {Path(destino).name}")

    def _salvar_cover_na_pasta(self):
        """Grava a capa mostrada como cover.jpg (ou .png) na pasta de cada arquivo selecionado."""
        if not self._capa_mostrada:
            return
        dados, mime = self._capa_mostrada
        nome = "cover.png" if mime == "image/png" else "cover.jpg"
        pastas = sorted({f.caminho.parent for f in self._faixas})
        existentes = [p for p in pastas if (p / nome).exists()]
        if existentes:
            resposta = QMessageBox.question(
                self, "Substituir capa da pasta?",
                f"Já existe um {nome} em {len(existentes)} pasta(s). Substituir?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if resposta != QMessageBox.Yes:
                return
        falhas = []
        for pasta in pastas:
            try:
                (pasta / nome).write_bytes(dados)
            except OSError:
                falhas.append(pasta)
        if falhas:
            self.aviso.emit(f"Não consegui gravar {nome} em {len(falhas)} pasta(s).")
        else:
            onde = pastas[0].name if len(pastas) == 1 else f"{len(pastas)} pastas"
            self.aviso.emit(f"{nome} salvo em {onde}")

    def _menu_capa(self, posicao_global):
        if not self._faixas:
            return
        menu = QMenu(self)
        menu.addAction("Escolher imagem…", self._escolher_capa)
        acao_colar = menu.addAction("Colar imagem", self.colar_capa)
        dados_area = QApplication.clipboard().mimeData()
        acao_colar.setEnabled(imagem_do_mime(dados_area) is not None)
        acao_exportar = menu.addAction("Exportar capa…", self._exportar_capa)
        acao_exportar.setEnabled(self._capa_mostrada is not None)
        acao_cover = menu.addAction("Salvar como cover.jpg na pasta", self._salvar_cover_na_pasta)
        acao_cover.setEnabled(self._capa_mostrada is not None)
        menu.addSeparator()
        tem_alguma = any(self._capa_efetiva(f) is not None for f in self._faixas[:LIMITE_COMPARAR_CAPAS]) \
            or any(f.tem_capa for f in self._faixas)
        acao_remover = menu.addAction("Remover capa", lambda: self._definir_capa(("remover",)))
        acao_remover.setEnabled(tem_alguma)
        pendente = any(self.rascunho.capa(f.caminho) is not None for f in self._faixas)
        acao_manter = menu.addAction("Manter capa original", lambda: self._definir_capa(None))
        acao_manter.setEnabled(pendente)
        menu.exec(posicao_global)

    # ------------------------------------------------------------------ edição
    def _texto(self, campo):
        widget = self.campos[campo][0]
        return widget.toPlainText() if isinstance(widget, QPlainTextEdit) else widget.text()

    def _ao_editar(self, campo):
        if self._carregando or not self._faixas:
            return
        texto = self._texto(campo)
        self._editando = True
        try:
            if self._varios.get(campo) and texto == "":
                self.rascunho.restaurar(self._fotos[campo], campo)   # apagou o que digitou: volta como estava
            else:
                self.rascunho.definir(self._faixas, campo, texto)
        finally:
            self._editando = False
        self._validar_campo(campo, texto)
        self._atualizar_rotulo(campo)
        if campo == "title" and len(self._faixas) == 1:
            self.lbl_titulo.definir(texto or self._faixas[0].nome)
        self.atualizar_rodape()
        self.alterado.emit()

    def _validar_campo(self, campo, texto):
        """Borda vermelha + mensagem abaixo do campo na hora em que o valor fica inválido (ex.: ano com 2 dígitos)."""
        ok, mensagem = validar_valor(campo, texto)
        self._mostrar_erro(campo, None if ok else mensagem)

    def _mostrar_erro(self, campo, mensagem):
        widget = self.campos[campo][0]
        erro = bool(mensagem)
        widget.setToolTip(mensagem or "")
        self._erros[campo].setText(mensagem or "")
        self._erros[campo].setVisible(erro)
        if bool(widget.property("erro")) != erro:
            widget.setProperty("erro", erro)
            repolir(widget)

    def _atualizar_rotulo(self, campo):
        _widget, lbl = self.campos[campo]
        sujo = any(self.rascunho.tem_campo(f.caminho, campo) for f in self._faixas)
        texto = rotulo(campo)
        if sujo and self.cores:
            texto += f'&nbsp;&nbsp;<span style="color:{self.cores["accent"]}">●</span>'
        lbl.setText(texto)
        if lbl.property("alterado") != sujo:
            lbl.setProperty("alterado", sujo)
            repolir(lbl)

    def atualizar_rodape(self):
        n = len(self.rascunho)
        pendente = n > 0
        texto = "Salvar" if not pendente else ("Salvar 1 arquivo" if n == 1 else f"Salvar {n} arquivos")
        for _rodape, descartar, salvar in (self.rodape, self.rodape_vazio):
            salvar.setText(texto)
            salvar.setEnabled(pendente)
            descartar.setEnabled(pendente)
        self.rodape_vazio[0].setVisible(pendente)

    def _enter_no_campo(self):
        if not self.rascunho.vazio:
            self.salvarPedido.emit()

    # ------------------------------------------------------------------ API pública
    @property
    def faixas(self):
        return self._faixas

    @property
    def capa_mostrada(self):
        return self._capa_mostrada

    def marcar_erros(self, campos):
        primeiro = None
        for campo in campos:
            if campo in self.campos:
                ok, mensagem = validar_valor(campo, self._texto(campo))
                self._mostrar_erro(campo, "Valor inválido" if ok else mensagem)
                primeiro = primeiro or campo
        if primeiro:
            self.campos[primeiro][0].setFocus()

    def focar_primeiro_campo(self):
        widget = self.campos["title"][0]
        widget.setFocus()
        widget.selectAll()
