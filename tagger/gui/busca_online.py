"""Janela "Buscar tags online": MusicBrainz, Discogs ou Last.fm, com prévia antes/depois.

Uso (igual ao DialogoBusca antigo, o resultado é o mesmo busca.Resultado):
    dlg = DialogoBuscaOnline(faixas, parent, valor=rascunho.valor, credenciais=(lastfm, discogs))
    if dlg.exec():
        resultado = dlg.resultado()
        rascunho.definir_por_faixa(resultado.alteracoes)
        if resultado.capa:
            rascunho.definir_capa(resultado.caminhos_capa, resultado.acao_capa)

`credenciais` = (config/lastfm_api_key, config/discogs_token) das Configurações; vazias = chave
embutida ou variável de ambiente (credenciais.py). Sem nenhuma, o botão daquele serviço fica
desabilitado com uma dica.

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


def criar_fontes(credenciais_config=("", ""), pasta_cache=None):
    """{nome: fonte ou None (sem credencial)} a partir do que está nas Configurações."""
    chave_lastfm, token_discogs = credenciais_config
    api_key = credenciais.lastfm_api_key(chave_lastfm)
    authorization = credenciais.discogs_authorization(token_discogs)
    return {
        MUSICBRAINZ: FonteMusicBrainz(busca.ClienteMusicBrainz()),
        DISCOGS: FonteDiscogs(discogs.ClienteDiscogs(authorization)) if authorization else None,
        LASTFM: FonteLastfm(lastfm.ClienteLastfm(api_key, pasta_cache=pasta_cache)) if api_key else None,
    }


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
    def __init__(self, faixas, parent=None, valor=None, credenciais=("", ""), fontes=None, fonte_inicial=MUSICBRAINZ,
                 estados=None):
        """`estados`: {"lastfm"|"discogs": objeto com .disponivel e .dica} (credenciais.estado_servicos),
        quando a janela principal já souber; senão vale ter ou não credencial (fontes[nome] is None)."""
        super().__init__(parent)
        self.faixas = list(faixas)
        self._valor = valor or (lambda faixa, campo: faixa.tags.get(campo, ""))
        self._conhecidas = tuple(c for c in credenciais if c)
        self._fontes = dict(fontes if fontes is not None else criar_fontes(credenciais, pasta_cache_lastfm()))
        self._dicas_sem_chave = dict(SEM_CHAVE)
        for nome, estado in (estados or {}).items():
            if nome in self._fontes and not estado.disponivel:
                self._fontes[nome] = None
                self._dicas_sem_chave[nome] = estado.dica or SEM_CHAVE[nome]
        self._fechado = False
        self._resultado = None
        self._trabalho = None
        self._fonte_resultados = None          # fonte dos itens na lista (pode ser o Discogs como alternativa)
        self._detalhes = {}                    # id(candidato) -> (release, alteracoes, casadas, sem_par)
        self.setWindowTitle("Buscar tags online")
        self.setMinimumSize(420, 360)
        self.resize(720, 600)

        # fonte: um botão por serviço, desabilitado com dica quando falta credencial
        self.grupo_fonte = QButtonGroup(self)
        self.botoes_fonte = {}
        linha_fonte = QHBoxLayout()
        linha_fonte.addWidget(QLabel("Fonte"))
        for nome in (MUSICBRAINZ, DISCOGS, LASTFM):
            botao = QRadioButton(NOMES[nome])
            disponivel = self._fontes.get(nome) is not None
            botao.setEnabled(disponivel)
            botao.setToolTip(DICAS[nome] if disponivel else self._dicas_sem_chave[nome])
            self.grupo_fonte.addButton(botao)
            self.botoes_fonte[nome] = botao
            botao.toggled.connect(lambda ligado, n=nome: ligado and self._ao_trocar_fonte(n))
            linha_fonte.addWidget(botao)
        linha_fonte.addStretch()
        self.ck_alternativa = QCheckBox("Se o MusicBrainz não achar, buscar no Discogs")
        self.ck_alternativa.setEnabled(self._fontes.get(DISCOGS) is not None)
        self.ck_alternativa.setChecked(self.ck_alternativa.isEnabled())
        if not self.ck_alternativa.isEnabled():
            self.ck_alternativa.setToolTip(self._dicas_sem_chave[DISCOGS])

        valor_de = lambda campo: gui_busca._primeiro_valor(self.faixas, campo, self._valor)
        self.ed_artista = QLineEdit(valor_de("albumartist") or valor_de("artist"))
        self.ed_album = QLineEdit(valor_de("album"))
        self.ed_titulo = QLineEdit(valor_de("title") if len(self.faixas) == 1 else "")
        for ed in (self.ed_artista, self.ed_album, self.ed_titulo):
            ed.returnPressed.connect(self.buscar)
        form = QFormLayout()
        form.addRow("Artista", self.ed_artista)
        form.addRow("Álbum", self.ed_album)
        form.addRow("Título (se não houver álbum)", self.ed_titulo)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar)

        self.lista = QListWidget()
        self.lista.itemSelectionChanged.connect(self._ao_selecionar)
        self.lista.itemDoubleClicked.connect(lambda _item: self.aplicar())
        self.previa = QTableWidget(0, 4)
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

        self.ck_capa = QCheckBox("Baixar a capa também (Cover Art Archive)")
        self.ck_capa.setChecked(True)
        btn_sobre = QPushButton("Sobre")
        btn_sobre.setProperty("tipo", "fantasma")
        btn_sobre.clicked.connect(self._sobre)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        self.btn_aplicar = QPushButton("Aplicar ao rascunho")
        self.btn_aplicar.setProperty("tipo", "primario")
        self.btn_aplicar.clicked.connect(self.aplicar)
        rodape = QHBoxLayout()
        rodape.addWidget(self.ck_capa)
        rodape.addStretch()
        rodape.addWidget(btn_sobre)
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
        v.addWidget(self.atribuicao)
        v.addWidget(self.estado)
        v.addLayout(rodape)

        self._cores = cores_do_tema(parent)
        aplicar_cores(self._cores, self.lista)
        inicial = fonte_inicial if self._fontes.get(fonte_inicial) else MUSICBRAINZ
        self.botoes_fonte[inicial].setChecked(True)
        self._ao_trocar_fonte(inicial)

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
        candidato = self._candidato()
        self.btn_aplicar.setEnabled(livre and candidato is not None and id(candidato) in self._detalhes
                                    and bool(self._detalhes[id(candidato)][2]))
        fonte = self._fontes.get(self._fonte_resultados or self.fonte)
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
        if candidato is not None and id(candidato) not in self._detalhes:
            self._ao_selecionar()            # a seleção mudou enquanto outra consulta rodava

    def _ao_trocar_fonte(self, nome):
        if self._ocupado():
            return
        self.lista.clear()
        self._limpar_previa("Prévia: escolha um resultado.")
        self._fonte_resultados = None
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
                return principal.nome, itens
            return alternativa.nome, alternativa.buscar(*termos)

        self._executar(trabalho, self._buscou, f"Buscando no {NOMES[self.fonte]}...")

    def _buscou(self, dados, erro):
        if self._fechado:
            return
        self.lista.clear()
        self._limpar_previa("Prévia: escolha um resultado.")
        if erro:
            self._mensagem(erro)
            return
        nome, itens = dados
        self._fonte_resultados = nome
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

    def _ao_selecionar(self):
        candidato = self._candidato()
        self._atualizar()
        if candidato is None:
            return
        if id(candidato) in self._detalhes:
            self._mostrar_previa(candidato)
            return
        if self._ocupado():
            return                            # _ao_terminar busca este depois
        fonte = self._fontes[self._fonte_resultados]
        faixas, valor = self.faixas, self._valor

        def trabalho():
            release = fonte.detalhar(candidato)
            return candidato, release, fonte.analisar(faixas, release, valor)

        self._limpar_previa("Carregando a prévia...")
        self._executar(trabalho, self._detalhou, "Baixando dados do álbum...")

    def _detalhou(self, dados, erro):
        if self._fechado:
            return
        if erro:
            self._limpar_previa("Prévia indisponível.")
            self._mensagem(erro)
            return
        candidato, release, (alteracoes, casadas, sem_par) = dados
        self._detalhes[id(candidato)] = (release, alteracoes, casadas, sem_par)
        if candidato is self._candidato():
            self._mostrar_previa(candidato)

    def _limpar_previa(self, texto):
        self.previa.setRowCount(0)
        self.lbl_previa.setText(texto)

    def _mostrar_previa(self, candidato):
        release, alteracoes, casadas, sem_par = self._detalhes[id(candidato)]
        fonte = self._fontes[self._fonte_resultados]
        self._definir_atribuicao(fonte.atribuicao(release))
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
        if self._ocupado() or candidato is None or id(candidato) not in self._detalhes:
            return
        _release, alteracoes, casadas, sem_par = self._detalhes[id(candidato)]
        if not casadas:
            return
        fonte = self._fontes[self._fonte_resultados]
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
            # não espera (travaria a janela): solta a thread, que termina sozinha
            trabalho.concluido.disconnect()
            trabalho.finished.disconnect()
            trabalho.setParent(None)
            gui_busca._ORFAOS.add(trabalho)
            trabalho.finished.connect(lambda: (gui_busca._ORFAOS.discard(trabalho), trabalho.deleteLater()))
        super().done(codigo)
