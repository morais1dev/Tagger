"""
Tabela de arquivos: modelo de dados, filtro de busca, colunas configuráveis,
edição direto na célula (vira alteração pendente) e desenho das colunas especiais.
"""

from PySide6.QtCore import (
    QAbstractTableModel, QItemSelection, QItemSelectionModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt, Signal,
)
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QMenu, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableView,
)

from metadata import CAMPOS

# (chave, título, largura inicial ou None = estica, visível por padrão)
COLUNAS = [
    ("tracknumber", "Nº",               52,   True),
    ("title",       "Título",           None, True),
    ("artist",      "Artista",          170,  True),
    ("album",       "Álbum",            190,  True),
    ("albumartist", "Artista do álbum", 170,  False),
    ("discnumber",  "Disco",            60,   False),
    ("date",        "Ano",              64,   True),
    ("genre",       "Gênero",           120,  True),
    ("composer",    "Compositor",       150,  False),
    ("lyricist",    "Letrista",         150,  False),
    ("comment",     "Comentário",       200,  False),
    ("duracao",     "Duração",          76,   True),
    ("bitrate",     "Bitrate",          84,   False),
    ("arquivo",     "Arquivo",          220,  False),
    ("pasta",       "Pasta",            180,  False),
    ("capa",        "Capa",             52,   True),
    ("estado",      "",                 28,   True),
]
CHAVES = [c[0] for c in COLUNAS]
TITULOS = {c[0]: c[1] for c in COLUNAS}
COLUNAS_FIXAS = {"title", "estado"}            # não podem ser escondidas
COLUNAS_MONO = {"tracknumber", "discnumber", "date", "duracao", "bitrate"}
COLUNAS_SECUNDARIAS = {"tracknumber", "discnumber", "album", "date", "genre", "duracao", "bitrate", "pasta",
                       "composer", "lyricist", "comment"}
COLUNAS_DIREITA = {"duracao", "bitrate"}
EDITAVEIS = set(CAMPOS)                        # colunas que são tags podem ser editadas na célula

PAPEL_ORDEM = Qt.UserRole          # valor usado para ordenar a coluna
PAPEL_FAIXA = Qt.UserRole + 1      # o objeto Faixa da linha


def _numero(texto):
    parte = (texto or "").split("/")[0].strip()
    return int(parte) if parte.isdigit() else 10**9    # sem número vai para o fim


class ModeloFaixas(QAbstractTableModel):
    def __init__(self, rascunho, parent=None):
        super().__init__(parent)
        self.faixas = []
        self.rascunho = rascunho
        self.ao_editar_celula = None   # função(faixa, campo, valor) -> bool  (definida pela janela)
        self.cores = {}
        self.fonte_mono = QFont()
        self.fonte_italico = QFont()
        self._linha_por_caminho = {}

    # ----- dados -----
    def _reindexar(self):
        self._linha_por_caminho = {f.caminho: i for i, f in enumerate(self.faixas)}

    def definir(self, faixas):
        self.beginResetModel()
        self.faixas = list(faixas)
        self._reindexar()
        self.endResetModel()

    def adicionar(self, faixas):
        novas = [f for f in faixas if f.caminho not in self._linha_por_caminho]
        if not novas:
            return 0
        inicio = len(self.faixas)
        self.beginInsertRows(QModelIndex(), inicio, inicio + len(novas) - 1)
        self.faixas.extend(novas)
        self._reindexar()
        self.endInsertRows()
        return len(novas)

    def remover(self, linhas):
        for linha in sorted(set(linhas), reverse=True):
            self.beginRemoveRows(QModelIndex(), linha, linha)
            del self.faixas[linha]
            self.endRemoveRows()
        self._reindexar()

    def atualizar(self, faixas):
        """Substitui faixas existentes (mesmo caminho) por versões relidas do disco."""
        for nova in faixas:
            linha = self._linha_por_caminho.get(nova.caminho)
            if linha is not None:
                self.faixas[linha] = nova
                self.dataChanged.emit(self.index(linha, 0), self.index(linha, len(COLUNAS) - 1))

    def linhas_mudaram(self, caminhos):
        """Avisa a tabela que essas linhas mudaram (ex.: rascunho alterado)."""
        for caminho in caminhos:
            linha = self._linha_por_caminho.get(caminho)
            if linha is not None:
                self.dataChanged.emit(self.index(linha, 0), self.index(linha, len(COLUNAS) - 1))

    def faixa_por_caminho(self, caminho):
        linha = self._linha_por_caminho.get(caminho)
        return None if linha is None else self.faixas[linha]

    def por_caminho(self):
        return {f.caminho: f for f in self.faixas}

    def definir_aparencia(self, cores, fonte_ui, fonte_mono):
        self.cores = cores
        self.fonte_mono = fonte_mono
        self.fonte_italico = QFont(fonte_ui)
        self.fonte_italico.setItalic(True)
        if self.faixas:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.faixas) - 1, len(COLUNAS) - 1))

    def _valor(self, faixa, chave):
        return self.rascunho.valor(faixa, chave)

    # ----- interface do Qt -----
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.faixas)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUNAS)

    def flags(self, indice):
        base = super().flags(indice)
        if indice.isValid() and CHAVES[indice.column()] in EDITAVEIS:
            base |= Qt.ItemIsEditable
        return base

    def headerData(self, secao, orientacao, papel=Qt.DisplayRole):
        if orientacao != Qt.Horizontal:
            return None
        if papel == Qt.DisplayRole:
            return COLUNAS[secao][1]
        if papel == Qt.TextAlignmentRole:
            alinhamento = Qt.AlignRight if CHAVES[secao] in COLUNAS_DIREITA else Qt.AlignLeft
            return int(alinhamento | Qt.AlignVCenter)
        return None

    def data(self, indice, papel=Qt.DisplayRole):
        if not indice.isValid():
            return None
        faixa = self.faixas[indice.row()]
        chave = CHAVES[indice.column()]

        if papel == PAPEL_FAIXA:
            return faixa

        if papel == Qt.EditRole:
            return self._valor(faixa, chave) if chave in EDITAVEIS else None

        if papel == Qt.DisplayRole:
            if chave in ("capa", "estado"):
                return None
            if chave == "duracao":
                return faixa.duracao_formatada
            if chave == "bitrate":
                return f"{faixa.bitrate} kbps" if faixa.bitrate else "—"
            if chave == "arquivo":
                return faixa.nome
            if chave == "pasta":
                return faixa.caminho.parent.name
            valor = self._valor(faixa, chave)
            if chave == "tracknumber":
                return valor.split("/")[0] or "—"
            if chave == "title":
                return valor or faixa.nome
            if chave == "comment":
                return valor.splitlines()[0] if valor else "—"
            return valor or "—"

        if papel == PAPEL_ORDEM:
            if chave == "tracknumber":
                return _numero(self._valor(faixa, chave))
            if chave == "discnumber":
                return _numero(self._valor(faixa, chave))
            if chave == "duracao":
                return faixa.duracao
            if chave == "bitrate":
                return faixa.bitrate
            if chave == "capa":
                return int(faixa.tem_capa)
            if chave == "estado":
                return int(self.rascunho.tem(faixa.caminho))
            if chave == "arquivo":
                return faixa.nome.casefold()
            if chave == "pasta":
                return str(faixa.caminho.parent).casefold()
            if chave == "title":
                return (self._valor(faixa, chave) or faixa.nome).casefold()
            return (self._valor(faixa, chave) or "￿").casefold()   # vazios no fim

        if papel == Qt.ForegroundRole and self.cores:
            if chave in EDITAVEIS and self.rascunho.tem_campo(faixa.caminho, chave):
                return QColor(self.cores["text"])           # valor alterado, não salvo
            sem_titulo = chave == "title" and not self._valor(faixa, "title")
            vazio = chave in EDITAVEIS and chave != "title" and not self._valor(faixa, chave)
            if sem_titulo or vazio or chave in COLUNAS_SECUNDARIAS:
                return QColor(self.cores["muted"])
            return QColor(self.cores["text"])

        if papel == Qt.FontRole:
            if chave in COLUNAS_MONO:
                return self.fonte_mono
            if chave == "title" and not self._valor(faixa, "title"):
                return self.fonte_italico
            return None

        if papel == Qt.TextAlignmentRole:
            alinhamento = Qt.AlignRight if chave in COLUNAS_DIREITA else Qt.AlignLeft
            return int(alinhamento | Qt.AlignVCenter)

        if papel == Qt.ToolTipRole:
            if chave in ("title", "arquivo", "pasta"):
                return str(faixa.caminho)
            if chave == "comment":
                return self._valor(faixa, chave) or None
            if chave == "capa":
                return "Tem capa" if faixa.tem_capa else "Sem capa"
            if chave == "estado" and self.rascunho.tem(faixa.caminho):
                return "Alterado, não salvo"
        return None

    def setData(self, indice, valor, papel=Qt.EditRole):
        if papel != Qt.EditRole or not indice.isValid():
            return False
        chave = CHAVES[indice.column()]
        if chave not in EDITAVEIS or self.ao_editar_celula is None:
            return False
        faixa = self.faixas[indice.row()]
        return bool(self.ao_editar_celula(faixa, chave, str(valor)))


class FiltroFaixas(QSortFilterProxyModel):
    """Filtra por título, artista, álbum ou nome do arquivo e ordena pelas chaves certas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._texto = ""
        self.setSortRole(PAPEL_ORDEM)

    def definir_texto(self, texto):
        self._texto = texto.strip().casefold()
        self.invalidateFilter()

    def filterAcceptsRow(self, linha, pai):
        if not self._texto:
            return True
        modelo = self.sourceModel()
        faixa = modelo.faixas[linha]
        valor = modelo.rascunho.valor
        alvo = " ".join((valor(faixa, "title"), valor(faixa, "artist"), valor(faixa, "album"), faixa.nome))
        return self._texto in alvo.casefold()


class DelegadoTabela(QStyledItemDelegate):
    """Tira o retângulo de foco e desenha as colunas Capa (quadradinho) e estado (ponto)."""

    def __init__(self, modelo, parent=None):
        super().__init__(parent)
        self.modelo = modelo

    def initStyleOption(self, opcao, indice):
        super().initStyleOption(opcao, indice)
        opcao.state &= ~QStyle.State_HasFocus

    def paint(self, pintor, opcao, indice):
        chave = CHAVES[indice.column()]
        if chave not in ("capa", "estado"):
            super().paint(pintor, opcao, indice)
            return

        # fundo (seleção/hover) igual às outras células
        fundo = QStyleOptionViewItem(opcao)
        self.initStyleOption(fundo, indice)
        estilo = fundo.widget.style() if fundo.widget else None
        if estilo:
            estilo.drawPrimitive(QStyle.PE_PanelItemViewItem, fundo, pintor, fundo.widget)

        faixa = indice.data(PAPEL_FAIXA)
        cores = self.modelo.cores
        if faixa is None or not cores:
            return

        pintor.save()
        pintor.setRenderHint(QPainter.Antialiasing)
        r = opcao.rect
        rascunho = self.modelo.rascunho
        if chave == "capa":
            pendente = rascunho.capa(faixa.caminho)
            tem = faixa.tem_capa if pendente is None else pendente[0] == "definir"
            lado = 16
            quadro = QRectF(r.x() + 8.5, r.center().y() - lado / 2 + 0.5, lado, lado)
            if tem:
                pintor.setPen(QPen(QColor(cores["line2"]), 1))
                preenchimento = QColor(cores["accent"])
                preenchimento.setAlpha(150)
                pintor.setBrush(preenchimento)
            else:
                pintor.setPen(QPen(QColor(cores["line2"]), 1, Qt.DashLine))
                pintor.setBrush(Qt.NoBrush)
            pintor.drawRoundedRect(quadro, 4, 4)
        elif rascunho.tem(faixa.caminho):
            pintor.setPen(Qt.NoPen)
            pintor.setBrush(QColor(cores["accent"]))
            pintor.drawEllipse(QRectF(r.center().x() - 3.5, r.center().y() - 3.5, 7, 7))
        pintor.restore()


class TabelaFaixas(QTableView):
    menuPedido = Signal(object)          # posição global do clique direito nas linhas

    def __init__(self, modelo, filtro, parent=None):
        super().__init__(parent)
        filtro.setSourceModel(modelo)
        self.setModel(filtro)
        self.setItemDelegate(DelegadoTabela(modelo, self))

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)
        self.setMouseTracking(True)
        self.setCornerButtonEnabled(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(lambda pos: self.menuPedido.emit(self.viewport().mapToGlobal(pos)))

        vertical = self.verticalHeader()
        vertical.setVisible(False)
        vertical.setSectionResizeMode(QHeaderView.Fixed)

        cabecalho = self.horizontalHeader()
        cabecalho.setHighlightSections(False)
        cabecalho.setStretchLastSection(False)
        cabecalho.setMinimumSectionSize(28)
        cabecalho.setSectionsMovable(True)
        cabecalho.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        cabecalho.setContextMenuPolicy(Qt.CustomContextMenu)
        cabecalho.customContextMenuRequested.connect(self._menu_colunas)
        self.colunas_padrao()
        self.definir_altura(34)

        # começa na ordem em que os arquivos foram carregados (sem coluna ordenada)
        cabecalho.setSortIndicator(-1, Qt.AscendingOrder)
        self.setSortingEnabled(True)

    # ----- colunas -----
    def colunas_padrao(self):
        cabecalho = self.horizontalHeader()
        for coluna, (chave, _titulo, largura, visivel) in enumerate(COLUNAS):
            visual = cabecalho.visualIndex(coluna)
            if visual != coluna:
                cabecalho.moveSection(visual, coluna)
            if largura is None:
                cabecalho.setSectionResizeMode(coluna, QHeaderView.Stretch)
            else:
                cabecalho.setSectionResizeMode(
                    coluna, QHeaderView.Fixed if chave in ("capa", "estado") else QHeaderView.Interactive)
                self.setColumnWidth(coluna, largura)
            cabecalho.setSectionHidden(coluna, not visivel)

    def _menu_colunas(self, pos):
        cabecalho = self.horizontalHeader()
        menu = QMenu(self)
        for coluna, (chave, titulo, _largura, _visivel) in enumerate(COLUNAS):
            if chave in COLUNAS_FIXAS:
                continue
            acao = QAction(titulo, menu, checkable=True, checked=not cabecalho.isSectionHidden(coluna))
            acao.toggled.connect(lambda on, c=coluna: cabecalho.setSectionHidden(c, not on))
            menu.addAction(acao)
        menu.addSeparator()
        menu.addAction("Restaurar colunas padrão", self.colunas_padrao)
        menu.exec(cabecalho.mapToGlobal(pos))

    def definir_altura(self, altura):
        self.verticalHeader().setDefaultSectionSize(altura)
        self.horizontalHeader().setFixedHeight(altura)

    # ----- seleção -----
    def linhas_selecionadas(self):
        """Índices (no modelo de origem) das linhas selecionadas, na ordem da tela."""
        filtro = self.model()
        indices = sorted(self.selectionModel().selectedRows(), key=lambda i: i.row())
        return [filtro.mapToSource(i).row() for i in indices]

    def selecionar_linhas(self, linhas_origem):
        filtro = self.model()
        selecao = QItemSelection()
        primeira = None
        for linha in linhas_origem:
            indice = filtro.mapFromSource(self.model().sourceModel().index(linha, 0))
            if indice.isValid():
                selecao.select(indice, indice)
                primeira = primeira or indice
        self.selectionModel().select(
            selecao, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows)
        if primeira is not None:
            self.scrollTo(primeira)
