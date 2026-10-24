"""
Tabela de arquivos: modelo de dados, filtro de busca, colunas configuráveis,
edição direto na célula (vira alteração pendente) e desenho das colunas especiais.
"""

from PySide6.QtCore import (
    QAbstractTableModel, QItemSelection, QItemSelectionModel, QModelIndex, QRectF, QSortFilterProxyModel, Qt, QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QMenu, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTableView,
)

from tagger.nucleo.agrupar import chave_grupo, mais_de_um_album, ordem_faixa, titulo_cabecalho
from tagger.nucleo.metadata import CAMPOS

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
    ("gravadora",   "Gravadora",        150,  False),
    ("comment",     "Comentário",       200,  False),
    ("lyrics",      "Letra",            200,  False),
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
                       "composer", "lyricist", "gravadora", "comment", "lyrics"}
COLUNAS_DIREITA = {"duracao", "bitrate"}
EDITAVEIS = set(CAMPOS)                        # colunas que são tags podem ser editadas na célula
CAMPOS_TEXTO_LONGO = {"comment", "lyrics"}     # a célula mostra só a 1ª linha
LARGURA_MIN_TITULO = 160
# quando a tabela fica estreita, essas colunas somem sozinhas (na ordem) até o Título caber
ORDEM_ESCONDER = ["lyrics", "comment", "gravadora", "lyricist", "composer", "pasta", "arquivo", "bitrate", "discnumber",
                  "albumartist", "genre", "date", "capa", "duracao", "album", "tracknumber"]

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

    def renomear(self, mapa):
        """Arquivos renomeados no disco ({antigo: novo}): a mesma Faixa passa a apontar para o caminho novo."""
        for linha, faixa in enumerate(self.faixas):
            novo = mapa.get(faixa.caminho)
            if novo is not None:
                faixa.caminho = novo
                self.dataChanged.emit(self.index(linha, 0), self.index(linha, len(COLUNAS) - 1))
        self._reindexar()

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
        chave = CHAVES[indice.column()] if indice.isValid() else None
        if chave in EDITAVEIS and chave != "lyrics":      # letra: várias linhas, só no painel
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
            if chave in CAMPOS_TEXTO_LONGO:
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
            if chave in CAMPOS_TEXTO_LONGO:
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


CAMPOS_GRUPO = ("album", "albumartist", "artist", "date", "discnumber", "tracknumber")


class FiltroFaixas(QSortFilterProxyModel):
    """Filtra por título, artista, álbum ou nome do arquivo e ordena pelas chaves certas.
    Com o agrupamento ligado, os álbuns ficam juntos (em ordem) e a coluna ordenada vale dentro de cada um."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._texto = ""
        self.agrupar = False
        self._cache_tags = {}
        self.setSortRole(PAPEL_ORDEM)
        # editar álbum/disco/faixa muda o grupo da linha: reordena depois que o Qt terminar a edição
        self._timer_regrupar = QTimer(self, singleShot=True, interval=0)
        self._timer_regrupar.timeout.connect(self.invalidate)

    def setSourceModel(self, modelo):
        # o cache é limpo antes de o proxy reagir às mudanças da origem (a conexão do proxy vem depois)
        for sinal in (modelo.dataChanged, modelo.rowsInserted, modelo.rowsRemoved, modelo.modelReset,
                      modelo.layoutChanged):
            sinal.connect(self._cache_tags.clear)
        super().setSourceModel(modelo)
        modelo.dataChanged.connect(lambda *_: self.agrupar and self._timer_regrupar.start())

    def definir_texto(self, texto):
        self._texto = texto.strip().casefold()
        self.invalidateFilter()

    def definir_agrupar(self, ligado):
        if ligado != self.agrupar:
            self.agrupar = ligado
            self.invalidate()

    def tags_da_linha(self, linha):
        """Tags (com o rascunho aplicado) da linha de origem, só os campos usados no agrupamento."""
        tags = self._cache_tags.get(linha)
        if tags is None:
            modelo = self.sourceModel()
            faixa = modelo.faixas[linha]
            tags = self._cache_tags[linha] = {campo: modelo.rascunho.valor(faixa, campo) for campo in CAMPOS_GRUPO}
        return tags

    def lessThan(self, esquerda, direita):
        if not self.agrupar:
            return super().lessThan(esquerda, direita)
        a, b = self.tags_da_linha(esquerda.row()), self.tags_da_linha(direita.row())
        ga, gb = chave_grupo(a), chave_grupo(b)
        if ga != gb:
            # sem álbum vai para o fim; a ordem dos álbuns não inverte com a coluna em ordem decrescente
            menor = (ga == ("", ""), ga) < (gb == ("", ""), gb)
            return menor if self.sortOrder() == Qt.AscendingOrder else not menor
        if CHAVES[self.sortColumn()] == "tracknumber":
            return ordem_faixa(a) < ordem_faixa(b)
        if super().lessThan(esquerda, direita):
            return True
        if super().lessThan(direita, esquerda):
            return False
        return ordem_faixa(a) < ordem_faixa(b)

    def filterAcceptsRow(self, linha, pai):
        if not self._texto:
            return True
        modelo = self.sourceModel()
        faixa = modelo.faixas[linha]
        valor = modelo.rascunho.valor
        alvo = " ".join((valor(faixa, "title"), valor(faixa, "artist"), valor(faixa, "album"), faixa.nome))
        return self._texto in alvo.casefold()


class DelegadoTabela(QStyledItemDelegate):
    """Tira o retângulo de foco, pinta o hover da linha inteira e o fundo das células alteradas,
    e desenha as colunas Capa (quadradinho) e estado (ponto)."""

    def __init__(self, modelo, parent=None):
        super().__init__(parent)
        self.modelo = modelo
        self.linha_hover = -1          # linha (da tela) sob o mouse
        self.cabecalhos = {}           # linha (da tela) -> (título, nº de faixas) do álbum que começa nela
        self.altura_cabecalho = 0      # faixa extra no topo dessas linhas, onde o cabeçalho é desenhado

    def initStyleOption(self, opcao, indice):
        super().initStyleOption(opcao, indice)
        opcao.state &= ~(QStyle.State_HasFocus | QStyle.State_MouseOver)

    def _pintar_fundo(self, pintor, opcao, indice, chave):
        cores = self.modelo.cores
        if not cores or opcao.state & QStyle.State_Selected:
            return
        if indice.row() == self.linha_hover:
            pintor.fillRect(opcao.rect, QColor(cores["hover"]))
        faixa = indice.data(PAPEL_FAIXA)
        if chave in EDITAVEIS and faixa is not None and self.modelo.rascunho.tem_campo(faixa.caminho, chave):
            tinta = QColor(cores["accent"])
            tinta.setAlpha(26)
            pintor.fillRect(opcao.rect, tinta)

    def _sem_cabecalho(self, opcao, indice):
        """Cópia da opção sem a faixa do topo reservada ao cabeçalho do álbum (se a linha tiver um)."""
        if indice.row() in self.cabecalhos:
            opcao = QStyleOptionViewItem(opcao)
            opcao.rect.setTop(opcao.rect.top() + self.altura_cabecalho)
        return opcao

    def updateEditorGeometry(self, editor, opcao, indice):
        super().updateEditorGeometry(editor, self._sem_cabecalho(opcao, indice), indice)

    def paint(self, pintor, opcao, indice):
        opcao = self._sem_cabecalho(opcao, indice)
        chave = CHAVES[indice.column()]
        self._pintar_fundo(pintor, opcao, indice, chave)
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
        self.delegado = DelegadoTabela(modelo, self)
        self.setItemDelegate(self.delegado)
        self._auto_escondidas = set()      # colunas escondidas só por falta de espaço
        self._altura_linha = 34
        self._ordem_automatica = False     # a ordenação por Nº foi posta pelo agrupamento, não pelo usuário
        self._timer_grupos = QTimer(self, singleShot=True, interval=0)
        self._timer_grupos.timeout.connect(self._atualizar_grupos)
        self._ordem_anterior = (-1, Qt.AscendingOrder)   # ordenação do usuário, guardada enquanto agrupa
        self._mudando_ordem = False
        for sinal in (filtro.rowsInserted, filtro.rowsRemoved, filtro.modelReset, filtro.dataChanged):
            sinal.connect(lambda *_: self._timer_grupos.start())
        filtro.layoutChanged.connect(lambda *_: self._atualizar_grupos())     # síncrono: sem piscar ao reordenar

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
        self.definir_altura(34, 32)

        # começa na ordem em que os arquivos foram carregados (sem coluna ordenada)
        cabecalho.setSortIndicator(-1, Qt.AscendingOrder)
        self.setSortingEnabled(True)
        cabecalho.sortIndicatorChanged.connect(self._ordem_mudou)

    # ----- colunas -----
    def colunas_padrao(self):
        self._auto_escondidas.clear()
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
        self._ajustar_colunas()

    def _menu_colunas(self, pos):
        cabecalho = self.horizontalHeader()
        menu = QMenu(self)
        for coluna, (chave, titulo, _largura, _visivel) in enumerate(COLUNAS):
            if chave in COLUNAS_FIXAS:
                continue
            visivel = not cabecalho.isSectionHidden(coluna) or coluna in self._auto_escondidas
            acao = QAction(titulo, menu, checkable=True, checked=visivel)
            acao.toggled.connect(lambda on, c=coluna: self._mostrar_coluna(c, on))
            menu.addAction(acao)
        if self._auto_escondidas:
            menu.addSeparator()
            nomes = ", ".join(TITULOS[CHAVES[c]] for c in sorted(self._auto_escondidas))
            aviso = menu.addAction(f"Sem espaço agora: {nomes}")
            aviso.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Restaurar colunas padrão", self.colunas_padrao)
        menu.exec(cabecalho.mapToGlobal(pos))

    def _mostrar_coluna(self, coluna, visivel):
        self._auto_escondidas.discard(coluna)
        self.horizontalHeader().setSectionHidden(coluna, not visivel)
        self._ajustar_colunas()

    def _ajustar_colunas(self):
        """Esconde colunas secundárias enquanto o Título ficaria estreito demais (e as mostra de volta)."""
        cabecalho = self.horizontalHeader()
        for coluna in self._auto_escondidas:
            cabecalho.setSectionHidden(coluna, False)
        self._auto_escondidas.clear()
        titulo = CHAVES.index("title")

        def ocupado():
            return sum(cabecalho.sectionSize(c) for c in range(len(COLUNAS))
                       if c != titulo and not cabecalho.isSectionHidden(c))

        disponivel = self.viewport().width()
        for chave in ORDEM_ESCONDER:
            if disponivel - ocupado() >= LARGURA_MIN_TITULO:
                break
            coluna = CHAVES.index(chave)
            if not cabecalho.isSectionHidden(coluna):
                cabecalho.setSectionHidden(coluna, True)
                self._auto_escondidas.add(coluna)

    def estado_cabecalho(self):
        """Estado para salvar, sem as colunas que só estão escondidas por falta de espaço."""
        cabecalho = self.horizontalHeader()
        for coluna in self._auto_escondidas:
            cabecalho.setSectionHidden(coluna, False)
        estado = cabecalho.saveState()
        for coluna in self._auto_escondidas:
            cabecalho.setSectionHidden(coluna, True)
        return estado

    def restaurar_cabecalho(self, estado):
        self._auto_escondidas.clear()
        self.horizontalHeader().restoreState(estado)
        self._ajustar_colunas()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar_colunas()

    def definir_altura(self, altura_linha, altura_cabecalho):
        self._altura_linha = altura_linha
        self.delegado.altura_cabecalho = max(24, altura_linha - 2)
        self.verticalHeader().setDefaultSectionSize(altura_linha)
        self.horizontalHeader().setFixedHeight(altura_cabecalho)
        self._atualizar_grupos()

    # ----- agrupar por álbum -----
    def definir_agrupar(self, ligado):
        """Liga/desliga os cabeçalhos de álbum. Ligado, a lista fica ordenada por álbum, disco e faixa."""
        ligado = bool(ligado)
        filtro = self.model()
        if ligado == filtro.agrupar:
            return
        cabecalho = self.horizontalHeader()
        if ligado:
            # dentro de cada álbum a ordem é disco > faixa: a ordenação do usuário volta ao desligar
            self._ordem_anterior = (cabecalho.sortIndicatorSection(), cabecalho.sortIndicatorOrder())
            self._ordem_automatica = True
            self._definir_ordem(CHAVES.index("tracknumber"), Qt.AscendingOrder)
        elif self._ordem_automatica:
            self._definir_ordem(*self._ordem_anterior)
        if not ligado:
            self._ordem_automatica = False
        filtro.definir_agrupar(ligado)
        self._atualizar_grupos()

    def _definir_ordem(self, coluna, ordem):
        self._mudando_ordem = True
        try:
            self.horizontalHeader().setSortIndicator(coluna, ordem)
        finally:
            self._mudando_ordem = False

    def _ordem_mudou(self, *_):
        if not self._mudando_ordem:
            self._ordem_automatica = False      # o usuário escolheu a ordem: não desfazer ao desligar

    def _limites_grupo(self, linha):
        """Primeira e última linha (da tela) do álbum que contém `linha`."""
        inicios = sorted(self.delegado.cabecalhos)
        inicio = max((i for i in inicios if i <= linha), default=0)
        fim = min((i for i in inicios if i > linha), default=self.model().rowCount()) - 1
        return inicio, fim

    def _no_cabecalho(self, evento):
        y = evento.position().toPoint().y()
        linha = self.rowAt(y)
        return linha if linha in self.delegado.cabecalhos and             y - self.rowViewportPosition(linha) < self.delegado.altura_cabecalho else -1

    def mousePressEvent(self, evento):
        linha = self._no_cabecalho(evento)
        if linha < 0:
            return super().mousePressEvent(evento)
        if evento.button() == Qt.LeftButton:            # clicar no cabeçalho seleciona o álbum inteiro
            inicio, fim = self._limites_grupo(linha)
            filtro = self.model()
            self.selecionar_linhas([filtro.mapToSource(filtro.index(i, 0)).row() for i in range(inicio, fim + 1)])

    def mouseDoubleClickEvent(self, evento):
        if self._no_cabecalho(evento) < 0:
            super().mouseDoubleClickEvent(evento)

    def _atualizar_grupos(self):
        """Recalcula onde começa cada álbum (só com mais de um álbum carregado) e a altura dessas linhas."""
        filtro = self.model()
        modelo = filtro.sourceModel()
        cabecalhos = {}
        if filtro.agrupar and mais_de_um_album(filtro.tags_da_linha(i) for i in range(len(modelo.faixas))):
            grupo, tags = None, []
            for linha in range(filtro.rowCount()):
                dados = filtro.tags_da_linha(filtro.mapToSource(filtro.index(linha, 0)).row())
                if chave_grupo(dados) != grupo:
                    grupo, tags = chave_grupo(dados), []
                    cabecalhos[linha] = tags
                tags.append(dados)
            cabecalhos = {linha: (titulo_cabecalho(t), len(t)) for linha, t in cabecalhos.items()}
        self.delegado.cabecalhos = cabecalhos
        extra = self.delegado.altura_cabecalho
        for linha in range(filtro.rowCount()):
            altura = self._altura_linha + (extra if linha in cabecalhos else 0)
            if self.rowHeight(linha) != altura:
                self.setRowHeight(linha, altura)
        self.viewport().update()

    def paintEvent(self, evento):
        super().paintEvent(evento)
        cabecalhos, cores = self.delegado.cabecalhos, self.delegado.modelo.cores
        if not cabecalhos or not cores:
            return
        pintor = QPainter(self.viewport())
        altura = self.delegado.altura_cabecalho
        largura = self.viewport().width()
        negrito = QFont(self.font())
        negrito.setBold(True)
        for linha, (titulo, total) in cabecalhos.items():
            y = self.rowViewportPosition(linha)
            if y + altura < evento.rect().top() or y > evento.rect().bottom():
                continue
            pintor.fillRect(0, y, largura, altura, QColor(cores["surface2"]))
            pintor.fillRect(0, y, 3, altura, QColor(cores["accent"]))
            contagem = f"{total} faixa" + ("" if total == 1 else "s")
            pintor.setFont(self.font())
            pintor.setPen(QColor(cores["muted"]))
            caixa = pintor.boundingRect(0, y, largura - 10, altura, Qt.AlignRight | Qt.AlignVCenter, contagem)
            pintor.drawText(caixa, Qt.AlignRight | Qt.AlignVCenter, contagem)
            disponivel = max(0, caixa.left() - 24)
            pintor.setFont(negrito)
            pintor.setPen(QColor(cores["text"]))
            elidido = pintor.fontMetrics().elidedText(titulo, Qt.ElideRight, disponivel)
            pintor.drawText(14, y, disponivel, altura, Qt.AlignLeft | Qt.AlignVCenter, elidido)
            pintor.setPen(QColor(cores["line"]))
            pintor.drawLine(0, y + altura - 1, largura, y + altura - 1)
        pintor.end()

    # ----- hover da linha inteira -----
    def _definir_hover(self, linha):
        anterior = self.delegado.linha_hover
        if linha == anterior:
            return
        self.delegado.linha_hover = linha
        largura = self.viewport().width()
        for l in (anterior, linha):
            if l >= 0:
                self.viewport().update(0, self.rowViewportPosition(l), largura, self.rowHeight(l))

    def _hover_pelo_cursor(self):
        pos = self.viewport().mapFromGlobal(QCursor.pos())
        dentro = self.viewport().rect().contains(pos)
        self._definir_hover(self.rowAt(pos.y()) if dentro else -1)

    def mouseMoveEvent(self, evento):
        super().mouseMoveEvent(evento)
        self._definir_hover(self.rowAt(evento.position().toPoint().y()))

    def leaveEvent(self, evento):
        super().leaveEvent(evento)
        self._definir_hover(-1)

    def scrollContentsBy(self, dx, dy):
        super().scrollContentsBy(dx, dy)
        if dy:
            self._hover_pelo_cursor()

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
