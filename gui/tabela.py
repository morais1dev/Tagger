"""Tabela de arquivos: modelo de dados, filtro de busca e desenho das colunas especiais."""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableView,
)

# (chave, título da coluna, largura inicial)  — largura None = estica
COLUNAS = [
    ("tracknumber", "Nº",       52),
    ("title",       "Título",   None),
    ("artist",      "Artista",  170),
    ("album",       "Álbum",    190),
    ("date",        "Ano",      64),
    ("genre",       "Gênero",   120),
    ("duracao",     "Duração",  76),
    ("capa",        "Capa",     52),
    ("estado",      "",         28),
]
CHAVES = [c[0] for c in COLUNAS]
COLUNAS_MONO = {"tracknumber", "date", "duracao"}
COLUNAS_SECUNDARIAS = {"tracknumber", "album", "date", "genre", "duracao"}

PAPEL_ORDEM = Qt.UserRole          # valor usado para ordenar a coluna
PAPEL_FAIXA = Qt.UserRole + 1      # o objeto Faixa da linha


def _numero(texto):
    parte = (texto or "").split("/")[0].strip()
    return int(parte) if parte.isdigit() else 10**9    # sem número vai para o fim


class ModeloFaixas(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.faixas = []
        self._pendentes = set()      # caminhos com alterações ainda não salvas
        self.cores = {}
        self.fonte_mono = QFont()
        self.fonte_italico = QFont()

    # ----- dados -----
    def definir(self, faixas):
        self.beginResetModel()
        self.faixas = list(faixas)
        self._pendentes.clear()
        self.endResetModel()

    def adicionar(self, faixas):
        existentes = {f.caminho for f in self.faixas}
        novas = [f for f in faixas if f.caminho not in existentes]
        if not novas:
            return 0
        inicio = len(self.faixas)
        self.beginInsertRows(QModelIndex(), inicio, inicio + len(novas) - 1)
        self.faixas.extend(novas)
        self.endInsertRows()
        return len(novas)

    def atualizar(self, faixas):
        """Substitui faixas já existentes (mesmo caminho) por versões relidas do disco."""
        por_caminho = {f.caminho: f for f in faixas}
        for linha, atual in enumerate(self.faixas):
            nova = por_caminho.get(atual.caminho)
            if nova is not None:
                self.faixas[linha] = nova
                self.dataChanged.emit(self.index(linha, 0), self.index(linha, len(COLUNAS) - 1))

    def marcar_pendentes(self, caminhos):
        caminhos = set(caminhos)
        if caminhos == self._pendentes:
            return
        self._pendentes = caminhos
        if self.faixas:
            coluna = CHAVES.index("estado")
            self.dataChanged.emit(self.index(0, coluna), self.index(len(self.faixas) - 1, coluna))

    def pendente(self, faixa):
        return faixa.caminho in self._pendentes

    def definir_aparencia(self, cores, fonte_ui, fonte_mono):
        self.cores = cores
        self.fonte_mono = fonte_mono
        self.fonte_italico = QFont(fonte_ui)
        self.fonte_italico.setItalic(True)
        if self.faixas:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.faixas) - 1, len(COLUNAS) - 1))

    # ----- interface do Qt -----
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.faixas)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUNAS)

    def headerData(self, secao, orientacao, papel=Qt.DisplayRole):
        if orientacao != Qt.Horizontal:
            return None
        if papel == Qt.DisplayRole:
            return COLUNAS[secao][1]
        if papel == Qt.TextAlignmentRole:
            alinhamento = Qt.AlignRight if CHAVES[secao] == "duracao" else Qt.AlignLeft
            return int(alinhamento | Qt.AlignVCenter)
        return None

    def data(self, indice, papel=Qt.DisplayRole):
        if not indice.isValid():
            return None
        faixa = self.faixas[indice.row()]
        chave = CHAVES[indice.column()]

        if papel == PAPEL_FAIXA:
            return faixa

        if papel == Qt.DisplayRole:
            if chave in ("capa", "estado"):
                return None
            if chave == "duracao":
                return faixa.duracao_formatada
            if chave == "tracknumber":
                return faixa.tags["tracknumber"].split("/")[0] or "—"
            if chave == "title":
                return faixa.tags["title"] or faixa.nome
            return faixa.tags.get(chave) or "—"

        if papel == PAPEL_ORDEM:
            if chave == "tracknumber":
                return _numero(faixa.tags["tracknumber"])
            if chave == "duracao":
                return faixa.duracao
            if chave == "capa":
                return int(faixa.tem_capa)
            if chave == "estado":
                return int(self.pendente(faixa))
            if chave == "title":
                return (faixa.tags["title"] or faixa.nome).casefold()
            return (faixa.tags.get(chave) or "￿").casefold()   # vazios no fim

        if papel == Qt.ForegroundRole and self.cores:
            sem_titulo = chave == "title" and not faixa.tags["title"]
            vazio = chave not in ("title", "duracao", "capa", "estado") and not faixa.tags.get(chave)
            if sem_titulo or vazio or chave in COLUNAS_SECUNDARIAS:
                return QColor(self.cores["muted"])
            return QColor(self.cores["text"])

        if papel == Qt.FontRole:
            if chave in COLUNAS_MONO:
                return self.fonte_mono
            if chave == "title" and not faixa.tags["title"]:
                return self.fonte_italico
            return None

        if papel == Qt.TextAlignmentRole:
            alinhamento = Qt.AlignRight if chave == "duracao" else Qt.AlignLeft
            return int(alinhamento | Qt.AlignVCenter)

        if papel == Qt.ToolTipRole:
            if chave == "title":
                return str(faixa.caminho)
            if chave == "capa":
                return "Tem capa" if faixa.tem_capa else "Sem capa"
            if chave == "estado" and self.pendente(faixa):
                return "Alterado, não salvo"
        return None


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
        faixa = self.sourceModel().faixas[linha]
        alvo = " ".join((faixa.tags["title"], faixa.tags["artist"], faixa.tags["album"], faixa.nome))
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
        if chave == "capa":
            lado = 16
            quadro = QRectF(r.x() + 8.5, r.center().y() - lado / 2 + 0.5, lado, lado)
            if faixa.tem_capa:
                pintor.setPen(QPen(QColor(cores["line2"]), 1))
                preenchimento = QColor(cores["accent"])
                preenchimento.setAlpha(150)
                pintor.setBrush(preenchimento)
            else:
                caneta = QPen(QColor(cores["line2"]), 1, Qt.DashLine)
                pintor.setPen(caneta)
                pintor.setBrush(Qt.NoBrush)
            pintor.drawRoundedRect(quadro, 4, 4)
        elif self.modelo.pendente(faixa):
            pintor.setPen(Qt.NoPen)
            pintor.setBrush(QColor(cores["accent"]))
            pintor.drawEllipse(QRectF(r.center().x() - 3.5, r.center().y() - 3.5, 7, 7))
        pintor.restore()


class TabelaFaixas(QTableView):
    def __init__(self, modelo, filtro, parent=None):
        super().__init__(parent)
        filtro.setSourceModel(modelo)
        self.setModel(filtro)
        self.setItemDelegate(DelegadoTabela(modelo, self))

        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.ElideRight)
        self.setMouseTracking(True)
        self.setCornerButtonEnabled(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        vertical = self.verticalHeader()
        vertical.setVisible(False)
        vertical.setDefaultSectionSize(34)
        vertical.setSectionResizeMode(QHeaderView.Fixed)

        cabecalho = self.horizontalHeader()
        cabecalho.setHighlightSections(False)
        cabecalho.setStretchLastSection(False)
        cabecalho.setMinimumSectionSize(28)
        cabecalho.setFixedHeight(34)
        cabecalho.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for coluna, (chave, _titulo, largura) in enumerate(COLUNAS):
            if largura is None:
                cabecalho.setSectionResizeMode(coluna, QHeaderView.Stretch)
            else:
                cabecalho.setSectionResizeMode(
                    coluna, QHeaderView.Fixed if chave in ("capa", "estado") else QHeaderView.Interactive)
                self.setColumnWidth(coluna, largura)

        # começa na ordem em que os arquivos foram carregados (sem coluna ordenada)
        cabecalho.setSortIndicator(-1, Qt.AscendingOrder)
        self.setSortingEnabled(True)

    def linhas_selecionadas(self):
        """Índices (no modelo de origem) das linhas selecionadas, na ordem da tela."""
        filtro = self.model()
        indices = sorted(self.selectionModel().selectedRows(), key=lambda i: i.row())
        return [filtro.mapToSource(i).row() for i in indices]
