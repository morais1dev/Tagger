"""Janela "Buscar tags online": MusicBrainz, Discogs ou Last.fm, com prévia antes/depois.

Uso (igual ao DialogoBusca antigo, o resultado é o mesmo busca.Resultado):
    dlg = DialogoBuscaOnline(faixas, parent, valor=rascunho.valor, config=config, estados=estado_servicos(config))
    if dlg.exec():
        resultado = dlg.resultado()
        rascunho.definir_por_faixa(resultado.alteracoes)
        if resultado.capa:
            rascunho.definir_capa(resultado.caminhos_capa, resultado.acao_capa)

`config` = as Configurações (lastfm_api_key, discogs_token); vazias = chave embutida ou variável de
ambiente (credenciais.py). `estados` = credenciais.estado_servicos(config): serviço indisponível fica
com o botão desabilitado e a dica que vem de lá.

Regras: a rede roda fora da thread da GUI; mensagens de erro passam por ocultar_credenciais;
capa só do Cover Art Archive (só a fonte MusicBrainz oferece capa); atribuições do Last.fm e do
Discogs ficam visíveis ao lado dos dados, com links validados por online.url_segura.
"""

import html
import logging
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QRadioButton, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from tagger.gui import busca as gui_busca
from tagger.nucleo import busca, credenciais, discogs, lastfm, online
from tagger.nucleo.busca import ErroBusca, NAO_ENCONTRADO, Resultado
from tagger.nucleo.metadata import rotulo

log = logging.getLogger(__name__)

MUSICBRAINZ, DISCOGS, LASTFM = "musicbrainz", "discogs", "lastfm"
NOMES = {MUSICBRAINZ: "MusicBrainz", DISCOGS: "Discogs", LASTFM: "Last.fm"}
DICAS = {
    MUSICBRAINZ: "Banco de dados aberto, com capas do Cover Art Archive.",
    DISCOGS: "Bom para prensagens privadas, vinis e edições raras.",
    LASTFM: "As tags como são scrobbladas: nomes canônicos e a versão do álbum mais ouvida.",
}
ATRIBUICAO_MUSICBRAINZ = "Dados do MusicBrainz · capas do Cover Art Archive."
SEM_CHAVE = {
    DISCOGS: "Busca no Discogs desativada: cole o seu token pessoal em Configurações → Serviços online.",
    LASTFM: "Busca no Last.fm desativada: cole a sua chave da API em Configurações → Serviços online.",
}


def pasta_cache_lastfm():
    """Cache do Last.fm na pasta de cache do usuário (precisa do QApplication com o nome do app)."""
    return Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation)) / "lastfm"


def cores_do_tema(widget):
    """As cores do tema da janela principal (atributo `cores` dela ou de um ancestral); {} se não houver."""
    while widget is not None:
        cores = getattr(widget, "cores", None)
        if cores:
            return cores
        widget = widget.parent()
    return {}


def colorir_links(texto_html, cores):
    """O QSS do app não pinta links de QLabel: a cor de destaque vai no próprio <a>."""
    if not cores.get("accent"):
        return texto_html
    return texto_html.replace("<a href=", f'<a style="color:{cores["accent"]}" href=')


def aplicar_cores(cores, lista):
    """A lista de resultados com o mesmo visual da tabela principal (o QSS global não estiliza QListWidget)."""
    if cores:
        lista.setStyleSheet(
            f"QListWidget {{ background: {cores['surface']}; color: {cores['text']}; border: 1px solid {cores['line']};"
            f" border-radius: 10px; outline: 0; padding: 4px; }}"
            f" QListWidget::item {{ padding: 4px 6px; border-radius: 6px; }}"
            f" QListWidget::item:hover {{ background: {cores['hover']}; }}"
            f" QListWidget::item:selected {{ background: {cores['sel']}; color: {cores['text']}; }}")


def _link(texto, url, dominios):
    """<a> só para URL https dos domínios do serviço; senão só o texto (escapado)."""
    url = online.url_segura(url, dominios)
    texto = html.escape(texto or url)
    return f'<a href="{html.escape(url, quote=True)}">{texto}</a>' if url else texto


# ---------------------------------------------------------------------------
# Uma "fonte" por serviço: busca, detalhe, análise e atribuição (sem Qt)
# ---------------------------------------------------------------------------

class FonteMusicBrainz:
    nome, tem_capa = MUSICBRAINZ, True

    def __init__(self, cliente):
        self.cliente = cliente

    def buscar(self, artista, album, titulo):
        return [(c.descricao, c) for c in self.cliente.buscar_releases(artista, album, titulo)]

    def detalhar(self, candidato):
        return self.cliente.detalhar_release(candidato.mbid)

    def capa(self, candidato):
        return self.cliente.baixar_capa(candidato.mbid)

    def analisar(self, faixas, release, valor):
        return busca.analisar(faixas, release, valor=valor)

    def atribuicao(self, release):
        return ATRIBUICAO_MUSICBRAINZ


class FonteDiscogs:
    nome, tem_capa = DISCOGS, False

    def __init__(self, cliente):
        self.cliente = cliente

    def buscar(self, artista, album, titulo):
        return [(c.descricao, c) for c in self.cliente.buscar_releases(artista, album, titulo)]

    def detalhar(self, candidato):
        return self.cliente.detalhar_release(candidato.id)

    def analisar(self, faixas, release, valor):
        return discogs.analisar(faixas, release, valor=valor)

    def atribuicao(self, release):
        texto, url = release.atribuicao
        return f"{html.escape(texto)} {_link('Ver o release no Discogs', url, discogs.DOMINIOS)}"


class FonteLastfm:
    nome, tem_capa = LASTFM, False

    def __init__(self, cliente):
        self.cliente = cliente

    def buscar(self, artista, album, titulo):
        """Com álbum: as versões dele pelo playcount; sem álbum: os mais scrobblados do artista."""
        if album.strip():
            albuns = self.cliente.versoes(artista, album)
            if not albuns:                       # fora do top do artista: pergunta direto pelo álbum
                albuns = [self.cliente.detalhar_album(artista, album)]
        else:
            albuns = self.cliente.top_albuns(artista, limite=20)
        itens = []
        for i, a in enumerate(albuns):
            marca = "  · o mais scrobblado" if i == 0 and len(albuns) > 1 else ""
            itens.append((a.descricao + marca, a))
        return itens

    def detalhar(self, album):
        if album.faixas:
            return album
        detalhe = self.cliente.detalhar_album(album.artista, album.titulo)
        detalhe.playcount = detalhe.playcount or album.playcount
        return detalhe

    def analisar(self, faixas, album, valor):
        return lastfm.analisar(faixas, album, valor=valor)

    def atribuicao(self, album):
        texto, links = album.atribuicao
        partes = [_link(nome, url, lastfm.DOMINIOS) for nome, url in links if nome]
        return f"{html.escape(texto)} · " + " · ".join(partes)


def credenciais_resolvidas(config=None):
    """{"lastfm": api_key | None, "discogs": cabeçalho Authorization | None} já resolvidos
    (Configurações > ambiente > chaves.json), como o cliente vai usar."""
    config = config or {}
    return {LASTFM: credenciais.lastfm_api_key(config.get("lastfm_api_key")),
            DISCOGS: credenciais.discogs_authorization(config.get("discogs_token"))}


def criar_fonte(nome, credencial, pasta_cache=None):
    """Fonte do Discogs ou do Last.fm com essa credencial (guardada em fonte.credencial); None sem ela."""
    if not credencial:
        return None
    if nome == DISCOGS:
        fonte = FonteDiscogs(discogs.ClienteDiscogs(credencial))
    else:
        fonte = FonteLastfm(lastfm.ClienteLastfm(credencial, pasta_cache=pasta_cache))
    fonte.credencial = credencial
    return fonte


def criar_fontes(config=None, pasta_cache=None):
    """{nome: fonte ou None (sem credencial)} a partir do dicionário das Configurações."""
    fontes = {MUSICBRAINZ: FonteMusicBrainz(busca.ClienteMusicBrainz())}
    for nome, credencial in credenciais_resolvidas(config).items():
        fontes[nome] = criar_fonte(nome, credencial, pasta_cache)
    return fontes


def linhas_da_previa(alteracoes, valor):
    """[(arquivo, rótulo do campo, antes, depois)] para a tabela de prévia."""
    linhas = []
    for faixa, mudancas in alteracoes:
        for campo, depois in mudancas.items():
            linhas.append((faixa.nome, rotulo(campo), valor(faixa, campo), depois))
    return linhas


# ---------------------------------------------------------------------------
# Janela
# ---------------------------------------------------------------------------

class Trabalhador(QThread):
    """Como gui.busca.Trabalhador, mas registra o detalhe técnico (já sem credenciais) no log."""
    concluido = Signal(object, str)

    def __init__(self, funcao, conhecidas, parent=None):
        super().__init__(parent)
        self._funcao, self._conhecidas = funcao, conhecidas

    def run(self):
        try:
            self.concluido.emit(self._funcao(), "")
        except ErroBusca as erro:
            detalhe = getattr(erro, "detalhe", "")
            if detalhe:
                log.warning("Busca online: %s (%s)", erro,
                            credenciais.ocultar_credenciais(detalhe, conhecidas=self._conhecidas))
            self.concluido.emit(None, credenciais.ocultar_credenciais(str(erro), conhecidas=self._conhecidas))
        except Exception:
            log.exception("Erro na busca online")
            self.concluido.emit(None, "Erro inesperado (detalhes no tagger.log).")


class DialogoBuscaOnline(QDialog):
    def __init__(self, faixas, parent=None, valor=None, config=None, fontes=None, fonte_inicial=MUSICBRAINZ,
                 estados=None):
        """`estados`: {"lastfm"|"discogs": EstadoServico(disponivel, dica)} (JanelaPrincipal.estado_servicos());
        sem ele vale ter ou não credencial (fontes[nome] is None)."""
        super().__init__(parent)
        self.faixas = list(faixas)
        self._valor = valor or (lambda faixa, campo: faixa.tags.get(campo, ""))
        self._conhecidas = credenciais.credenciais_da_config(config)      # ocultadas em toda mensagem de erro
        self._fontes = dict(fontes if fontes is not None else criar_fontes(config, pasta_cache_lastfm()))
        self._dicas_sem_chave = dict(SEM_CHAVE)
        self._aplicar_estados(estados)
        self._fechado = False
        self._resultado = None
        self._trabalho = None
        # fonte (o objeto) que trouxe os itens da lista: pode ser o Discogs como alternativa, e pode deixar de
        # ser a de self._fontes se as credenciais mudarem com a janela aberta (aí os itens são descartados)
        self._fonte_lista = None
        # id(candidato) -> (candidato, release, alteracoes, casadas, sem_par). O id só vale enquanto o objeto
        # vive (o CPython reaproveita): por isso a entrada guarda o candidato, conferido com `is` em _detalhe,
        # e o dicionário é limpo a cada busca nova e troca de fonte.
        self._detalhes = {}
        self.setWindowTitle("Buscar tags online")
        self.resize(720, 600)

        # fonte: um botão por serviço, desabilitado com dica quando falta credencial
        self.grupo_fonte = QButtonGroup(self)
        self.botoes_fonte = {}
        linha_fonte = QHBoxLayout()
        linha_fonte.addWidget(QLabel("Fonte"))
        for nome in (MUSICBRAINZ, DISCOGS, LASTFM):
            botao = QRadioButton(NOMES[nome])
            self.grupo_fonte.addButton(botao)
            self.botoes_fonte[nome] = botao
            botao.toggled.connect(lambda ligado, n=nome: ligado and self._ao_trocar_fonte(n))
            linha_fonte.addWidget(botao)
        linha_fonte.addStretch()
        self.ck_alternativa = QCheckBox("Se o MusicBrainz não achar, buscar no Discogs")
        self.ck_alternativa.setChecked(self._fontes.get(DISCOGS) is not None)

        valor_de = lambda campo: gui_busca._primeiro_valor(self.faixas, campo, self._valor)
        self.ed_artista = QLineEdit(valor_de("albumartist") or valor_de("artist"))
        self.ed_album = QLineEdit(valor_de("album"))
        self.ed_titulo = QLineEdit(valor_de("title") if len(self.faixas) == 1 else "")
        for ed in (self.ed_artista, self.ed_album, self.ed_titulo):
            ed.returnPressed.connect(self.buscar)
        form = QFormLayout()
        form.addRow("Artista", self.ed_artista)
        form.addRow("Álbum", self.ed_album)
        self.ed_titulo.setPlaceholderText("só se não houver álbum")
        form.addRow("Título", self.ed_titulo)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar)

        self.lista = QListWidget()
        self.lista.setMinimumHeight(56)       # o divisor pode encolher as duas partes em janelas baixas
        self.lista.itemSelectionChanged.connect(self._ao_selecionar)
        self.lista.itemDoubleClicked.connect(lambda _item: self.aplicar())
        self.previa = QTableWidget(0, 4)
        self.previa.setMinimumHeight(56)
        self.previa.setHorizontalHeaderLabels(["Arquivo", "Campo", "Antes", "Depois"])
        self.previa.verticalHeader().setVisible(False)
        self.previa.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.previa.setSelectionMode(QAbstractItemView.NoSelection)
        self.previa.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.previa.horizontalHeader().setStretchLastSection(True)
        divisor = QSplitter(Qt.Vertical)
        divisor.addWidget(self.lista)
        caixa_previa = QWidget()
        vp = QVBoxLayout(caixa_previa)
        vp.setContentsMargins(0, 0, 0, 0)
        self.lbl_previa = gui_busca._rotulo("Prévia: escolha um resultado.", "ajuda")
        self.lbl_previa.setTextFormat(Qt.PlainText)          # nomes vindos do serviço não viram HTML
        vp.addWidget(self.lbl_previa)
        vp.addWidget(self.previa, 1)
        divisor.addWidget(caixa_previa)
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 1)
        divisor.setChildrenCollapsible(False)

        self.atribuicao = QLabel()
        self.atribuicao.setProperty("papel", "ajuda")
        self.atribuicao.setWordWrap(True)
        self.atribuicao.setTextFormat(Qt.RichText)
        self.atribuicao.setOpenExternalLinks(True)
        self.atribuicao.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.estado = gui_busca._rotulo("", "ajuda")
        self.estado.setTextFormat(Qt.PlainText)

        self.ck_capa = QCheckBox("Baixar a capa")
        self.ck_capa.setToolTip("Capa do Cover Art Archive (só com o MusicBrainz)")
        self.ck_capa.setChecked(True)
        self.lnk_sobre = QLabel('<a href="#sobre">Sobre</a>')
        self.lnk_sobre.setProperty("papel", "ajuda")
        self.lnk_sobre.setTextFormat(Qt.RichText)
        self.lnk_sobre.setToolTip("Sobre o Tagger e os serviços online (F1)")
        self.lnk_sobre.linkActivated.connect(lambda _link: self._sobre())
        linha_atribuicao = QHBoxLayout()
        linha_atribuicao.addWidget(self.atribuicao, 1)
        linha_atribuicao.addWidget(self.lnk_sobre, 0, Qt.AlignTop)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        self.btn_aplicar = QPushButton("Aplicar ao rascunho")
        self.btn_aplicar.setProperty("tipo", "primario")
        self.btn_aplicar.clicked.connect(self.aplicar)
        rodape = QHBoxLayout()
        rodape.addWidget(self.ck_capa)
        rodape.addStretch()
        rodape.addWidget(btn_cancelar)
        rodape.addWidget(self.btn_aplicar)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 16)
        v.setSpacing(10)
        v.addLayout(linha_fonte)
        v.addWidget(self.ck_alternativa)
        v.addLayout(form)
        v.addWidget(self.btn_buscar, alignment=Qt.AlignRight)
        v.addWidget(divisor, 1)
        v.addLayout(linha_atribuicao)
        v.addWidget(self.estado)
        v.addLayout(rodape)

        self._cores = cores_do_tema(parent)
        aplicar_cores(self._cores, self.lista)
        self.lnk_sobre.setText(colorir_links(self.lnk_sobre.text(), self._cores))
        self._atualizar_dicas()
        inicial = fonte_inicial if self._fontes.get(fonte_inicial) else MUSICBRAINZ
        self.botoes_fonte[inicial].setChecked(True)
        self._ao_trocar_fonte(inicial)

    # ------------------------------------------------------------ serviços
    def _aplicar_estados(self, estados, config=None):
        """Com `config`: a fonte cuja credencial resolvida mudou (token trocado, apagado e caindo na chave
        embutida...) é recriada, para nenhum pedido seguir com a credencial antiga. Serviço indisponível
        em `estados` fica sem fonte (botão desabilitado com a dica)."""
        if config is not None:
            for nome, credencial in credenciais_resolvidas(config).items():
                if getattr(self._fontes.get(nome), "credencial", None) != credencial:
                    self._fontes[nome] = criar_fonte(nome, credencial, pasta_cache_lastfm())
        for nome, estado in (estados or {}).items():
            if nome in SEM_CHAVE and not estado.disponivel:
                self._fontes[nome] = None
                self._dicas_sem_chave[nome] = estado.dica or SEM_CHAVE[nome]

    def atualizar_servicos(self, estados, config):
        """Ligado ao sinal JanelaPrincipal.servicos_mudaram enquanto a janela está aberta."""
        self._conhecidas = tuple(dict.fromkeys(self._conhecidas + credenciais.credenciais_da_config(config)))
        self._aplicar_estados(estados, config)
        self._atualizar_dicas()
        if self._fonte_lista is not None and not self._fonte_valida(self._fonte_lista):
            nome = NOMES[self._fonte_lista.nome]
            self.lista.clear()
            self._detalhes.clear()
            self._fonte_lista = None
            self._limpar_previa("Prévia: escolha um resultado.")
            self._mensagem(f"As credenciais do {nome} mudaram: busque de novo.")
        if self._fontes.get(self.fonte) is None:
            self.botoes_fonte[MUSICBRAINZ].setChecked(True)
        self._atualizar()

    def _atualizar_dicas(self):
        for nome, botao in self.botoes_fonte.items():
            disponivel = self._fontes.get(nome) is not None
            botao.setToolTip(DICAS[nome] if disponivel else self._dicas_sem_chave[nome])
        tem_discogs = self._fontes.get(DISCOGS) is not None
        self.ck_alternativa.setEnabled(tem_discogs)
        if not tem_discogs:
            self.ck_alternativa.setChecked(False)
        self.ck_alternativa.setToolTip("" if tem_discogs else self._dicas_sem_chave[DISCOGS])

    def _fonte_valida(self, fonte):
        """A fonte ainda é a atual daquele serviço (não foi trocada nem desligada)?"""
        return fonte is not None and self._fontes.get(fonte.nome) is fonte

    @property
    def _fonte_resultados(self):
        return self._fonte_lista.nome if self._fonte_lista is not None else None

    # ------------------------------------------------------------ estado
    @property
    def fonte(self):
        """Fonte escolhida nos botões."""
        return next(n for n, b in self.botoes_fonte.items() if b.isChecked())

    def _ocupado(self):
        return self._trabalho is not None and self._trabalho.isRunning()

    def _atualizar(self):
        livre = not self._ocupado()
        self.btn_buscar.setEnabled(livre)
        for nome, botao in self.botoes_fonte.items():
            botao.setEnabled(livre and self._fontes.get(nome) is not None)
        detalhe = self._detalhe(self._candidato())
        self.btn_aplicar.setEnabled(livre and detalhe is not None and bool(detalhe[2]))
        fonte = self._fonte_lista or self._fontes.get(self.fonte)
        self.ck_capa.setVisible(bool(fonte and fonte.tem_capa))
        self.ck_alternativa.setVisible(self.fonte == MUSICBRAINZ)

    def _mensagem(self, texto):
        self.estado.setText(texto)

    def _executar(self, funcao, ao_concluir, texto):
        self._mensagem(texto)
        self._trabalho = Trabalhador(funcao, self._conhecidas, self)
        self._trabalho.concluido.connect(ao_concluir)
        self._trabalho.finished.connect(self._ao_terminar)
        self._trabalho.start()
        self._atualizar()

    def _ao_terminar(self):
        if self._fechado:
            return
        self._atualizar()
        candidato = self._candidato()
        if candidato is not None and self._detalhe(candidato) is None:
            self._ao_selecionar()            # a seleção mudou enquanto outra consulta rodava

    def _ao_trocar_fonte(self, nome):
        if self._ocupado():
            return
        self.lista.clear()
        self._detalhes.clear()
        self._limpar_previa("Prévia: escolha um resultado.")
        self._fonte_lista = None
        self._definir_atribuicao(self._atribuicao_da_fonte(nome))
        self._mensagem(DICAS[nome])
        self._atualizar()

    def _definir_atribuicao(self, texto_html):
        self.atribuicao.setText(colorir_links(texto_html, self._cores))

    def _atribuicao_da_fonte(self, nome):
        if nome == LASTFM:
            return f'{html.escape(lastfm.ATRIBUICAO)} · {_link("Last.fm", lastfm.URL_SITE, lastfm.DOMINIOS)}'
        if nome == DISCOGS:
            return f'{html.escape(discogs.ATRIBUICAO)} {_link("discogs.com", discogs.URL_SITE, discogs.DOMINIOS)}'
        return ATRIBUICAO_MUSICBRAINZ

    # ------------------------------------------------------------ busca
    def buscar(self):
        if self._ocupado():
            return
        termos = tuple(e.text() for e in (self.ed_artista, self.ed_album, self.ed_titulo))
        principal = self._fontes[self.fonte]
        alternativa = (self._fontes.get(DISCOGS) if self.fonte == MUSICBRAINZ and self.ck_alternativa.isChecked()
                       else None)

        def trabalho():
            try:
                itens = principal.buscar(*termos)
            except ErroBusca as erro:
                if alternativa is None or str(erro) != NAO_ENCONTRADO:
                    raise
                itens = []
            if itens or alternativa is None:
                return principal, itens
            return alternativa, alternativa.buscar(*termos)

        self._executar(trabalho, self._buscou, f"Buscando no {NOMES[self.fonte]}...")

    def _buscou(self, dados, erro):
        if self._fechado:
            return
        self.lista.clear()
        self._detalhes.clear()
        self._limpar_previa("Prévia: escolha um resultado.")
        if erro:
            self._mensagem(erro)
            return
        fonte, itens = dados
        if not self._fonte_valida(fonte):
            self._mensagem(f"As credenciais do {NOMES[fonte.nome]} mudaram durante a busca: busque de novo.")
            return
        self._fonte_lista = fonte
        nome = fonte.nome
        for descricao, candidato in itens:
            item = QListWidgetItem(descricao)
            item.setData(Qt.UserRole, candidato)
            self.lista.addItem(item)
        aviso = self._aviso_alternativa()
        self._definir_atribuicao(self._atribuicao_da_fonte(nome))
        if itens:
            self._mensagem(f"{aviso}{len(itens)} resultado(s). Escolha o álbum certo e confira a prévia.")
            self.lista.setCurrentRow(0)
        else:
            self._mensagem("Nenhum resultado. Tente outro nome.")
        self._atualizar()

    def _aviso_alternativa(self):
        if self._fonte_resultados and self._fonte_resultados != self.fonte:
            return f"O {NOMES[self.fonte]} não achou nada; resultados do {NOMES[self._fonte_resultados]}. "
        return ""

    # ------------------------------------------------------------ prévia
    def _candidato(self):
        itens = self.lista.selectedItems()
        return itens[0].data(Qt.UserRole) if itens else None

    def _detalhe(self, candidato):
        """(release, alteracoes, casadas, sem_par) já baixados para ESTE candidato, ou None."""
        guardado = self._detalhes.get(id(candidato)) if candidato is not None else None
        if guardado is None or guardado[0] is not candidato:
            return None
        return guardado[1:]

    def _na_lista(self, candidato):
        return any(self.lista.item(i).data(Qt.UserRole) is candidato for i in range(self.lista.count()))

    def _ao_selecionar(self):
        candidato = self._candidato()
        self._atualizar()
        if candidato is None:
            return
        if self._detalhe(candidato) is not None:
            self._mostrar_previa(candidato)
            return
        if self._ocupado():
            return                            # _ao_terminar busca este depois
        fonte = self._fonte_lista
        if fonte is None:
            return
        faixas, valor = self.faixas, self._valor

        def trabalho():
            release = fonte.detalhar(candidato)
            return fonte, candidato, release, fonte.analisar(faixas, release, valor)

        self._limpar_previa("Carregando a prévia...")
        self._executar(trabalho, self._detalhou, "Baixando dados do álbum...")

    def _detalhou(self, dados, erro):
        if self._fechado:
            return
        if erro:
            self._limpar_previa("Prévia indisponível.")
            self._mensagem(erro)
            return
        fonte, candidato, release, (alteracoes, casadas, sem_par) = dados
        if fonte is not self._fonte_lista or not self._na_lista(candidato):
            return                            # resposta de uma busca anterior ou de credencial velha: descarta
        self._detalhes[id(candidato)] = (candidato, release, alteracoes, casadas, sem_par)
        if candidato is self._candidato():
            self._mostrar_previa(candidato)

    def _limpar_previa(self, texto):
        self.previa.setRowCount(0)
        self.lbl_previa.setText(texto)

    def _mostrar_previa(self, candidato):
        release, alteracoes, casadas, sem_par = self._detalhe(candidato)
        self._definir_atribuicao(self._fonte_lista.atribuicao(release))
        linhas = linhas_da_previa(alteracoes, self._valor)
        self.previa.setRowCount(len(linhas))
        for i, linha in enumerate(linhas):
            for j, texto in enumerate(linha):
                self.previa.setItem(i, j, QTableWidgetItem(texto))
        self.previa.resizeColumnsToContents()
        if not casadas:
            texto = "Nenhuma das faixas casa com esse álbum (confira título e número da faixa)."
        elif not alteracoes:
            texto = "Nada a alterar nas tags: as faixas já têm esses dados."
        else:
            texto = f"Prévia: {len(alteracoes)} arquivo(s), {len(linhas)} alteração(ões)."
        if sem_par:
            texto += f" {len(sem_par)} faixa(s) sem par não mudam: " + ", ".join(f.nome for f in sem_par[:3])
        self.lbl_previa.setText(texto)
        aviso = self._aviso_alternativa()
        self._mensagem(f"{aviso}Confira a prévia e clique em Aplicar ao rascunho. Nada é gravado até você salvar.")
        self._atualizar()

    # ------------------------------------------------------------ aplicar
    def aplicar(self):
        candidato = self._candidato()
        detalhe = self._detalhe(candidato)
        if self._ocupado() or detalhe is None:
            return
        _release, alteracoes, casadas, sem_par = detalhe
        fonte = self._fonte_lista
        if not casadas or fonte is None:
            return
        if fonte.tem_capa and self.ck_capa.isChecked():
            self._executar(lambda: fonte.capa(candidato),
                           lambda capa, erro: self._concluir(alteracoes, capa, casadas, sem_par, erro),
                           "Baixando a capa do Cover Art Archive...")
        else:
            self._concluir(alteracoes, None, casadas, sem_par, "")

    def _concluir(self, alteracoes, capa, casadas, sem_par, erro):
        if self._fechado:
            return
        if erro:
            self._mensagem(f"Capa não baixada: {erro}")
            capa = None
        if not alteracoes and not capa:
            self._mensagem("Nada a alterar: as faixas já têm esses dados.")
            return
        self._resultado = Resultado(alteracoes, capa, casadas, sem_par)
        self.accept()

    def resultado(self):
        """busca.Resultado após exec() aceito; None se cancelado."""
        return self._resultado

    def _sobre(self):
        from tagger.gui.sobre import DialogoSobre
        DialogoSobre(self).exec()

    def done(self, codigo):
        self._fechado = True
        trabalho = self._trabalho
        if trabalho is not None and trabalho.isRunning():
            # não espera (travaria a janela): solta a thread, que termina sozinha. Não há como cancelar
            # uma requisição do urllib em andamento: ela vai até o fim (no máximo o TIMEOUT de cada
            # tentativa) e o resultado é descartado. Aceito: só custa a requisição.
            trabalho.concluido.disconnect()
            trabalho.finished.disconnect()
            trabalho.setParent(None)
            gui_busca._ORFAOS.add(trabalho)
            trabalho.finished.connect(lambda: (gui_busca._ORFAOS.discard(trabalho), trabalho.deleteLater()))
        super().done(codigo)
