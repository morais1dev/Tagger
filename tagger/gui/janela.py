"""
Tagger — interface gráfica (PySide6).

Executar:  python -m tagger
"""

import logging
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QSettings, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QMessageBox, QProgressBar, QPushButton, QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from tagger.nucleo import metadata
from tagger.nucleo.credenciais import estado_servicos
from tagger.nucleo.metadata import (
    CAMPOS, analisar_extras, carregar, carregar_varios, curingas_audio, foi_modificado, formato, limpar_extras,
    listar_audios, mtime_atual, nomes_formatos, rotulo, validar_valor,
)
from tagger.nucleo.organizar import (
    executar_movimentos, executar_organizacao, pasta_apos_mover, remover_pastas_vazias,
)
from tagger.nucleo.padroes import ItemRenomear, executar_renomeacao
from tagger import __version__
from tagger.gui import tema
from tagger.gui.config import carregar_config, salvar_config
from tagger.gui.configuracoes import DialogoConfiguracoes
from tagger.gui.busca_online import DialogoBuscaOnline
from tagger.gui.editor import PainelEditor, garantir_jpeg_ou_png
from tagger.gui.erros import configurar_log, instalar_tratamento_de_erros
from tagger.gui.icones import icone, icone_app, pixmap
from tagger.gui.limpeza import DialogoLimpeza
from tagger.gui.organizar import DialogoOrganizar, DialogoResumoOrganizar
from tagger.gui.padrao import DialogoRenomear, DialogoTagsDoNome, lembrar_padrao
from tagger.nucleo.rascunho import Rascunho, Renomeacao, executar_salvamento, migrar_historico
from tagger.gui.rotulo import Migalha, RotuloElidido
from tagger.gui.tabela import FiltroFaixas, ModeloFaixas, TabelaFaixas
from tagger.gui.vazio import TelaVazia

VERSAO = __version__
log = logging.getLogger("tagger")
MAX_RECENTES = 6
CHAVES_APARENCIA = ("usar_escuro", "tema_escuro", "tema_claro", "acento", "fonte", "fonte_mono",
                    "tamanho_fonte", "densidade")
LARGURA_BARRA_COMPACTA = 1100    # abaixo disso os botões da barra superior ficam só com ícone


# ============================================================================
# Trabalho em segundo plano (pastas grandes e lotes grandes não travam a janela)
# ============================================================================

class Carregador(QThread):
    progresso = Signal(int, int)
    concluido = Signal(list, list)     # faixas, falhas

    def __init__(self, caminhos, parent=None):
        super().__init__(parent)
        self.caminhos = caminhos

    def run(self):
        faixas, falhas = [], []
        total = len(self.caminhos)
        try:
            for i, caminho in enumerate(self.caminhos, start=1):
                try:
                    faixa = carregar(caminho)
                except Exception:          # nunca deixa a pasta "carregando para sempre"
                    log.exception("Erro ao ler %s", caminho)
                    faixa = None
                (faixas if faixa else falhas).append(faixa or Path(caminho))
                if i % 25 == 0 or i == total:
                    self.progresso.emit(i, total)
        finally:
            self.concluido.emit(faixas, falhas)


class Salvador(QThread):
    progresso = Signal(int, int)
    concluido = Signal(object)         # (registros, falhas, faixas)

    def __init__(self, trabalhos, mtimes, parent=None):
        super().__init__(parent)
        self.trabalhos = trabalhos
        self.mtimes = mtimes

    def run(self):
        try:
            resultado = executar_salvamento(self.trabalhos, lambda i, total: self.progresso.emit(i, total),
                                            self.mtimes)
        except Exception:
            log.exception("Erro ao salvar")
            resultado = ([], {t[0]: "erro inesperado (detalhes no tagger.log)" for t in self.trabalhos}, [])
        self.concluido.emit(resultado)


class Movedor(QThread):
    """Roda uma função de mover arquivos fora da thread da interface (cópia entre unidades pode demorar)."""
    concluido = Signal(object)         # o que a função devolveu (ou o erro, se ela quebrou)

    def __init__(self, funcao, parent=None):
        super().__init__(parent)
        self.funcao = funcao

    def run(self):
        try:
            resultado = self.funcao()
        except Exception as erro:
            log.exception("Erro ao mover arquivos")
            resultado = erro
        self.concluido.emit(resultado)


class Limpador(QThread):
    progresso = Signal(int, int)
    concluido = Signal(object)         # (limpos, falhas, faixas relidas)

    def __init__(self, caminhos, opcoes, parent=None):
        super().__init__(parent)
        self.caminhos = caminhos
        self.opcoes = opcoes

    def run(self):
        limpos, falhas, relidas = 0, {}, []
        total = len(self.caminhos)
        try:
            for i, caminho in enumerate(self.caminhos, start=1):
                try:
                    limpos += bool(limpar_extras(caminho, **self.opcoes))
                except Exception as erro:
                    log.warning("Não limpou %s: %s", caminho, erro)
                    falhas[caminho] = str(erro)
                self.progresso.emit(i, total)
            relidas, _ = carregar_varios(self.caminhos)
        except Exception:
            log.exception("Erro ao limpar")
        finally:
            self.concluido.emit((limpos, falhas, relidas))


ROTULO_TAGS = {"mp3": lambda v: f"ID3v2.{v}", "flac": "Vorbis", "ogg": "Vorbis", "m4a": "iTunes", "mp4": "iTunes"}


def expandir_caminhos(caminhos, recursivo=True):
    """Pastas viram a lista de áudios dentro delas; arquivos soltos passam direto."""
    resultado = []
    for caminho in map(Path, caminhos):
        if caminho.is_dir():
            resultado.extend(listar_audios(caminho, recursivo=recursivo))
        elif caminho.is_file() and formato(caminho):
            resultado.append(caminho)
    return resultado


def mostrar_no_explorador(caminho):
    """Abre a pasta do arquivo com ele selecionado (Windows/macOS) ou só a pasta (Linux)."""
    caminho = Path(caminho)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(caminho)])
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(caminho)])
            return
    except OSError:
        pass
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(caminho.parent)))


def barra_de_titulo_escura(janela, escura):
    """No Windows 10/11, deixa a barra de título da janela no tema escuro/claro."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        valor = ctypes.c_int(1 if escura else 0)
        hwnd = int(janela.winId())
        for atributo in (20, 19):   # 20 = Windows 11 / 10 20H1+, 19 = versões anteriores
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, atributo, ctypes.byref(valor), ctypes.sizeof(valor)) == 0:
                break
    except Exception:
        pass


class FiltroJanelas(QObject):
    """Filtro de eventos do app inteiro.

    - QMenu e dicas (QToolTip) ganham fundo translúcido e sem sombra nativa, senão o border-radius
      do QSS deixa cantos quadrados aparecendo no Windows;
    - toda janela que abre (Configurações, QMessageBox, QColorDialog...) recebe a barra de título
      escura/clara conforme o tema.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.escuro = True

    def eventFilter(self, obj, evento):
        tipo = evento.type()
        if tipo == QEvent.Polish and obj.isWidgetType():
            if (isinstance(obj, QMenu) or obj.metaObject().className() == "QTipLabel") \
                    and not obj.testAttribute(Qt.WA_WState_Created):
                obj.setAttribute(Qt.WA_TranslucentBackground, True)
                obj.setWindowFlags(obj.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        elif tipo == QEvent.Show and obj.isWidgetType() and obj.isWindow() \
                and not isinstance(obj, QMenu) and obj.metaObject().className() != "QTipLabel" \
                and not obj.windowFlags() & Qt.FramelessWindowHint:
            barra_de_titulo_escura(obj, self.escuro)
        return False

    def aplicar_em_todas(self, escuro):
        self.escuro = escuro
        for janela in QApplication.topLevelWidgets():
            if janela.isVisible() and janela.isWindow() and not isinstance(janela, QMenu):
                barra_de_titulo_escura(janela, escuro)


# ============================================================================
# Janela principal
# ============================================================================

class JanelaPrincipal(QMainWindow):
    # {"lastfm"/"discogs": EstadoServico} sempre que as Configurações são salvas (botões da busca online)
    servicos_mudaram = Signal(dict)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("Tagger", "Tagger")
        self.config = carregar_config(self.settings)

        self.rascunho = Rascunho()
        self.rascunho.ao_mudar = self._ao_mudar_rascunho
        self.historico_pendente = None   # (registros, "desfazer" | "refazer") aguardando Salvar
        self.pilha_desfazer = []         # cada item: lista de registros (caminho, tags, capa) ou Renomeacao
        self.pilha_refazer = []
        self.area_tags = None            # tags copiadas: {"tags": {...}, "capa": (dados, mime) | None}

        self.pasta_atual = None
        self.cores = {}
        self.fonte_mono = QFont()
        self._carregador = None
        self._salvador = None
        self._limpador = None
        self._movedor = None
        self._mtimes_antes, self._itens_movendo, self._pilha_movendo, self._desfazendo = {}, [], None, None
        self._pastas_do_movimento = ()   # (pasta aberta antes de organizar, destino): a migalha segue ao desfazer
        self._pastas_criadas = set()     # pastas de destino que o Tagger criou (para limpar ao desfazer)
        self._modo_carregar = "substituir"   # "substituir" | "adicionar" | "recarregar"
        self._config_pendente = None
        self.filtro_janelas = None       # FiltroJanelas, instalado pelo main()

        self.setWindowTitle("Tagger")
        self.setMinimumSize(600, 320)
        self.setAcceptDrops(True)

        self.modelo = ModeloFaixas(self.rascunho, self)
        self.modelo.ao_editar_celula = self._editar_celula
        self.filtro = FiltroFaixas(self)

        raiz = QWidget(objectName="raiz")
        raiz.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(raiz)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._criar_barra_topo())

        self.telas = QStackedWidget()
        self.tela_vazia = TelaVazia()
        self.tela_vazia.abrirPasta.connect(self.abrir_pasta)
        self.tela_vazia.escolherArquivos.connect(self.adicionar_arquivos)
        self.tela_vazia.abrirRecente.connect(lambda p: self.carregar_caminhos([p], substituir=True))
        self.tela_vazia.removerRecente.connect(self._esquecer_recente)
        rolagem = QScrollArea()           # em janelas baixas a tela vazia rola em vez de impor altura mínima
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rolagem.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        rolagem.setWidget(self.tela_vazia)
        self.telas.addWidget(rolagem)
        self.telas.addWidget(self._criar_tela_principal())
        layout.addWidget(self.telas, 1)
        self.setCentralWidget(raiz)

        self._timer_selecao = QTimer(self, singleShot=True, interval=60)
        self._timer_selecao.timeout.connect(self._carregar_selecao)
        # a prévia das Configurações reaplica o tema só quando o usuário para de mexer
        self._timer_config = QTimer(self, singleShot=True, interval=150)
        self._timer_config.timeout.connect(self._aplicar_config_pendente)

        self._criar_barra_status()
        self._criar_acoes()
        self._aplicar_config_metadata()

        self.tela_vazia.definir_recentes(self._recentes())
        self.tela_vazia.definir_subpastas(self.config["subpastas"])
        self.tabela.definir_agrupar(self.config["agrupar_por_album"])
        self.aplicar_tema()
        self._atualizar_generos()
        self._atualizar_estado()

        geometria = self.settings.value("geometria")
        if not geometria or not self.restoreGeometry(geometria):
            self._geometria_inicial()
        self._encaixar_na_tela()
        self.settings.remove("cabecalho_v3")      # layout antigo: a coluna Gravadora mudou os índices
        cabecalho = self.settings.value("cabecalho_v4")
        if cabecalho:
            self.tabela.restaurar_cabecalho(cabecalho)
        if str(self.settings.value("painel_visivel", True)).lower() in ("false", "0"):
            self.alternar_painel()

        ultima = self.settings.value("ultima_pasta_aberta", "")
        if self.config["reabrir_ultima"] and ultima and Path(ultima).is_dir():
            QTimer.singleShot(0, lambda: self.carregar_caminhos([ultima], substituir=True))

    # ------------------------------------------------------------------ montagem
    def _geometria_inicial(self):
        """1ª execução: ~85% da tela (no máximo 1440×900), centralizada."""
        area = self.screen().availableGeometry()
        largura = max(self.minimumWidth(), min(1440, int(area.width() * 0.85)))
        altura = max(self.minimumHeight(), min(900, int(area.height() * 0.85)))
        self.resize(min(largura, area.width()), min(altura, area.height()))
        self.move(area.center() - self.rect().center())

    def _encaixar_na_tela(self):
        """A geometria salva pode ser de um monitor maior ou que não está mais conectado."""
        if self.isMaximized() or self.isFullScreen():
            return
        area = self.screen().availableGeometry()
        moldura = self.frameGeometry()
        if moldura.width() > area.width() or moldura.height() > area.height():
            self.resize(min(self.width(), area.width()), min(self.height(), area.height()))
            moldura = self.frameGeometry()
        if not area.contains(moldura.topLeft()) or not area.intersects(moldura):
            self.move(area.center() - self.rect().center())

    def _criar_barra_topo(self):
        barra = QWidget(objectName="barraTopo")
        barra.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(barra)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(8)

        self.logo = QLabel(objectName="logo", alignment=Qt.AlignCenter)
        self.logo.setFixedSize(26, 26)
        h.addWidget(self.logo)
        self.lbl_nome_app = QLabel("Tagger", objectName="nomeApp")
        h.addWidget(self.lbl_nome_app)
        h.addSpacing(12)

        self.btn_abrir = QPushButton("Abrir pasta")
        self.btn_abrir.setToolTip("Abrir pasta (Ctrl+O)")
        self.btn_abrir.setAccessibleName("Abrir pasta")
        self.btn_abrir.clicked.connect(lambda: self.abrir_pasta())
        self.btn_adicionar = QPushButton("Adicionar arquivos")
        self.btn_adicionar.setToolTip("Adicionar arquivos")
        self.btn_adicionar.setAccessibleName("Adicionar arquivos")
        self.btn_adicionar.clicked.connect(lambda: self.adicionar_arquivos())
        self.btn_online = QPushButton("Buscar online")
        self.btn_online.setToolTip("Buscar tags online das faixas selecionadas: MusicBrainz, Discogs ou Last.fm (Ctrl+Shift+M)")
        self.btn_online.setAccessibleName("Buscar online")
        self.btn_online.clicked.connect(lambda: self.buscar_tags_online())
        h.addWidget(self.btn_abrir)
        h.addWidget(self.btn_adicionar)
        h.addWidget(self.btn_online)

        separador = QFrame(objectName="sep")
        separador.setFixedSize(1, 20)
        h.addSpacing(4)
        h.addWidget(separador)
        h.addSpacing(4)

        self.btn_painel = self._botao_icone("Mostrar/esconder o editor (Ctrl+E)", self.alternar_painel)
        self.btn_desfazer = self._botao_icone("Desfazer (Ctrl+Z)", self.desfazer)
        self.btn_refazer = self._botao_icone("Refazer (Ctrl+Y)", self.refazer)
        h.addWidget(self.btn_painel)
        h.addWidget(self.btn_desfazer)
        h.addWidget(self.btn_refazer)
        h.addStretch()

        self.busca = QLineEdit(objectName="busca")
        self.busca.setPlaceholderText("Filtrar por título, artista, álbum…")
        self.busca.setClearButtonEnabled(True)
        self.acao_busca = self.busca.addAction(icone("busca", "#888888"), QLineEdit.LeadingPosition)
        self.busca.textChanged.connect(self._ao_buscar)
        self.busca.setMinimumWidth(220)
        h.addWidget(self.busca, 1)

        self.btn_config = self._botao_icone("Configurações (Ctrl+,)", self.abrir_configuracoes)
        self.btn_tema = self._botao_icone("Alternar tema claro/escuro", self.alternar_tema)
        h.addWidget(self.btn_config)
        h.addWidget(self.btn_tema)

        self.btn_salvar_topo = QPushButton("Salvar")
        self.btn_salvar_topo.setProperty("tipo", "primario")
        self.btn_salvar_topo.setToolTip("Salvar todas as alterações pendentes (Ctrl+S)")
        self.btn_salvar_topo.clicked.connect(lambda: self.salvar())
        h.addWidget(self.btn_salvar_topo)
        return barra

    def _botao_icone(self, dica, acao):
        botao = QPushButton()
        botao.setProperty("tipo", "fantasma")
        botao.setFixedSize(32, 32)
        botao.setToolTip(dica)
        botao.setAccessibleName(dica)
        botao.clicked.connect(lambda: acao())
        return botao

    def _botoes_icone(self):
        return (self.btn_painel, self.btn_desfazer, self.btn_refazer, self.btn_config, self.btn_tema)

    def _ajustar_barra_topo(self):
        """Em janelas estreitas, "Abrir pasta"/"Adicionar arquivos" ficam só com ícone e a busca encolhe."""
        compacta = self.width() < LARGURA_BARRA_COMPACTA
        lado = tema.altura_botao(int(self.config["tamanho_fonte"]))
        if (compacta, lado) == getattr(self, "_estado_barra", None):
            return
        self._estado_barra = (compacta, lado)
        for botao, texto in ((self.btn_abrir, "Abrir pasta"), (self.btn_adicionar, "Adicionar arquivos"),
                             (self.btn_online, "Buscar online")):
            if compacta:
                botao.setText("")
                botao.setFixedSize(lado, lado)
            else:
                botao.setText(texto)
                botao.setMinimumSize(0, 0)
                botao.setMaximumSize(16777215, 16777215)
            botao.setProperty("tipo", "fantasma" if compacta else None)
            tema.repolir(botao)
        self.busca.setMinimumWidth(60 if compacta else 220)
        self.btn_online.parentWidget().layout().setSpacing(6 if compacta else 8)   # cabe em 600 px com "Buscar online"
        self.lbl_nome_app.setVisible(not compacta)
        self._fixar_largura_salvar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar_barra_topo()

    def _criar_tela_principal(self):
        self.painel = PainelEditor(self.rascunho)
        self.painel.alterado.connect(self._atualizar_estado)
        self.painel.salvarPedido.connect(lambda: self.salvar())
        self.painel.descartarPedido.connect(self.descartar)
        self.painel.aviso.connect(lambda texto: self.avisar(texto))
        self.painel.setMinimumWidth(240)
        self.painel.setMaximumWidth(560)

        direita = QWidget()
        v = QVBoxLayout(direita)
        v.setContentsMargins(16, 0, 16, 16)
        v.setSpacing(0)

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(0, 12, 0, 12)
        self.lbl_migalha = Migalha(objectName="migalha")
        self.lbl_contagem = QLabel(objectName="contagem")
        cabecalho.addWidget(self.lbl_migalha, 1)
        cabecalho.addWidget(self.lbl_contagem)
        v.addLayout(cabecalho)

        self.tabela = TabelaFaixas(self.modelo, self.filtro)
        self.tabela.selectionModel().selectionChanged.connect(lambda *_: self._timer_selecao.start())
        self.tabela.menuPedido.connect(self._menu_linhas)
        self.filtro.layoutChanged.connect(self._atualizar_contagem)
        self.filtro.rowsInserted.connect(self._atualizar_contagem)
        self.filtro.rowsRemoved.connect(self._atualizar_contagem)
        self.filtro.modelReset.connect(self._atualizar_contagem)
        v.addWidget(self.tabela, 1)

        # aviso que aparece por cima da tabela ao arrastar arquivos para a janela
        self.overlay_drop = QLabel("Solte para adicionar à lista", self.tabela, objectName="overlayDrop",
                                   alignment=Qt.AlignCenter)
        self.overlay_drop.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.overlay_drop.setAttribute(Qt.WA_StyledBackground, True)
        self.overlay_drop.hide()

        divisor = QSplitter(Qt.Horizontal)
        divisor.setHandleWidth(7)      # fácil de pegar; o QSS desenha só a linha de 1px no meio
        divisor.setChildrenCollapsible(False)
        divisor.addWidget(self.painel)
        divisor.addWidget(direita)
        divisor.setStretchFactor(0, 0)
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([380, 1060])
        self.divisor = divisor
        estado = self.settings.value("divisor")
        if estado:
            divisor.restoreState(estado)
        return divisor

    def _criar_barra_status(self):
        barra = self.statusBar()
        barra.setSizeGripEnabled(False)
        self.lbl_status = QLabel()
        self.lbl_pendente = RotuloElidido(objectName="destaqueStatus")
        self.lbl_aviso = RotuloElidido(objectName="destaqueStatus")
        self.progresso = QProgressBar()
        self.progresso.setTextVisible(False)
        politica = self.progresso.sizePolicy()
        politica.setRetainSizeWhenHidden(True)      # o espaço fica reservado: nada se mexe ao aparecer/sumir
        self.progresso.setSizePolicy(politica)
        self.progresso.setVisible(False)
        barra.addWidget(self.lbl_status)
        barra.addWidget(self.lbl_pendente, 1)
        barra.addWidget(self.lbl_aviso, 2)
        self.lbl_formato = QLabel()
        self.lbl_formato.setProperty("mono", True)
        barra.addPermanentWidget(self.progresso)
        barra.addPermanentWidget(self.lbl_formato)
        self._timer_aviso = QTimer(self, singleShot=True, interval=6000)
        self._timer_aviso.timeout.connect(lambda: self.lbl_aviso.definir(""))

    def _nova_acao(self, texto, teclas, funcao, contexto=Qt.WindowShortcut, alvo=None):
        acao = QAction(texto, self)
        if teclas:
            acao.setShortcuts([QKeySequence(t) for t in teclas])
        acao.setShortcutContext(contexto)
        acao.triggered.connect(lambda _=False, f=funcao: f())
        (alvo or self).addAction(acao)
        return acao

    def _criar_acoes(self):
        self._nova_acao("Abrir pasta", ["Ctrl+O"], self.abrir_pasta)
        self._nova_acao("Salvar", ["Ctrl+S"], self.salvar)
        self._nova_acao("Desfazer", ["Ctrl+Z"], self.desfazer)
        self._nova_acao("Refazer", ["Ctrl+Y", "Ctrl+Shift+Z"], self.refazer)
        self._nova_acao("Buscar", ["Ctrl+F"], self._focar_busca)
        self._nova_acao("Configurações", ["Ctrl+,"], self.abrir_configuracoes)
        self._nova_acao("Mostrar/esconder o editor", ["Ctrl+E"], self.alternar_painel)
        self._nova_acao("Esc", ["Escape"], self._ao_escape)
        self._nova_acao("Sobre o Tagger", ["F1"], self.mostrar_sobre)
        # ações das linhas (também aparecem no menu de clique direito)
        self.acao_recarregar = self._nova_acao("Recarregar do disco", ["F5"], self.recarregar)
        self.acao_numerar = self._nova_acao("Numerar faixas", ["Ctrl+Shift+N"], self.numerar_faixas)
        self.acao_renomear = self._nova_acao("Renomear pelas tags…", ["Ctrl+Shift+R"], self.renomear_pelas_tags)
        self.acao_tags_nome = self._nova_acao("Preencher tags pelo nome…", ["Ctrl+Shift+T"], self.tags_pelo_nome)
        self.acao_organizar = self._nova_acao("Organizar em pastas…", ["Ctrl+Shift+O"], self.organizar_em_pastas)
        self.acao_busca_online = self._nova_acao("Buscar tags online…", ["Ctrl+Shift+M"], self.buscar_tags_online)
        self.acao_limpar = self._nova_acao("Limpar tags extras…", [], self.limpar_tags_extras)
        self.acao_copiar = self._nova_acao("Copiar tags", ["Ctrl+Shift+C"], self.copiar_tags)
        self.acao_colar = self._nova_acao("Colar tags", ["Ctrl+Shift+V"], self.colar_tags)
        self.acao_pasta = self._nova_acao("Mostrar na pasta", [], self.mostrar_na_pasta)
        self.acao_remover = self._nova_acao("Remover da lista", ["Delete"], self.remover_da_lista,
                                            Qt.WidgetShortcut, self.tabela)
        self.acao_editar = self._nova_acao("Editar célula", ["F2"], self._editar_celula_atual,
                                           Qt.WidgetShortcut, self.tabela)
        self.acao_tudo = self._nova_acao("Selecionar tudo", ["Ctrl+A"], self.tabela.selectAll,
                                         Qt.WidgetShortcut, self.tabela)

    # ------------------------------------------------------------------ tema e configurações
    def _tema_atual(self):
        return self.config["tema_escuro"] if self.config["usar_escuro"] else self.config["tema_claro"]

    def aplicar_tema(self):
        c = self.config
        cores = tema.paleta(self._tema_atual(), c["acento"])
        self.cores = cores
        tamanho = int(c["tamanho_fonte"])
        fonte_ui_nome, fonte_mono_nome = tema.escolher_fontes(c["fonte"], c["fonte_mono"])

        app = QApplication.instance()
        fonte_app = QFont(fonte_ui_nome) if fonte_ui_nome else QFont()
        fonte_app.setPixelSize(tamanho)
        app.setFont(fonte_app)
        self.fonte_mono = QFont(fonte_mono_nome)
        self.fonte_mono.setPixelSize(tamanho)
        self.fonte_mono.setStyleHint(QFont.Monospace)
        tema.aplicar_paleta_qt(app, cores)
        app.setStyleSheet(tema.folha_de_estilo(cores, fonte_ui_nome, fonte_mono_nome, tamanho))

        escuro = tema.TEMAS.get(self._tema_atual(), {}).get("escuro", True)
        lado = tema.altura_botao(tamanho)
        for botao in self._botoes_icone():
            botao.setFixedSize(lado, lado)

        fonte_italico_base = QFont(fonte_ui_nome) if fonte_ui_nome else QFont()
        fonte_italico_base.setPixelSize(tamanho)
        self.modelo.definir_aparencia(cores, fonte_italico_base, self.fonte_mono)
        self.tabela.definir_altura(tema.altura_linha(tamanho, c["densidade"]), tema.altura_cabecalho(tamanho))
        self._atualizar_icones()
        self.setWindowIcon(icone_app(cores["accent"], cores["on_accent"]))
        if self.filtro_janelas is not None:
            self.filtro_janelas.aplicar_em_todas(escuro)
        else:
            barra_de_titulo_escura(self, escuro)
        self._atualizar_formato()
        self._ajustar_barra_topo()
        self._fixar_largura_salvar()
        self._atualizar_migalha()
        self._atualizar_estado()

    def _atualizar_icones(self):
        """Ícones e capa na escala do monitor atual (também ao arrastar a janela para outro monitor)."""
        cores = self.cores
        escuro = tema.TEMAS.get(self._tema_atual(), {}).get("escuro", True)
        self.logo.setPixmap(pixmap("musica", cores["on_accent"], 15, espessura=2.4))
        self.btn_abrir.setIcon(icone("pasta", cores["text"]))
        self.btn_adicionar.setIcon(icone("arquivo+", cores["text"]))
        self.btn_online.setIcon(icone("globo", cores["text"]))
        self.btn_painel.setIcon(icone("painel", cores["muted"]))
        self.btn_desfazer.setIcon(icone("desfazer", cores["muted"]))
        self.btn_refazer.setIcon(icone("refazer", cores["muted"]))
        self.btn_config.setIcon(icone("config", cores["muted"]))
        self.btn_tema.setIcon(icone("sol" if escuro else "lua", cores["muted"]))
        self.btn_salvar_topo.setIcon(icone("salvar", cores["on_accent"], espessura=2))
        self.acao_busca.setIcon(icone("busca", cores["muted"]))
        self.painel.definir_aparencia(cores, tema.altura_botao(int(self.config["tamanho_fonte"])))
        self.tela_vazia.definir_aparencia(cores)

    def _fixar_largura_salvar(self):
        """Largura mínima de "Salvar · 999": a barra não pula toda vez que o número muda."""
        botao = self.btn_salvar_topo
        texto = botao.text()
        botao.setMinimumWidth(0)
        if not getattr(self, "_estado_barra", (False,))[0]:       # na barra compacta o botão pode encolher
            botao.setText("Salvar · 999")
            botao.ensurePolished()
            botao.setMinimumWidth(botao.sizeHint().width())
            botao.setText(texto)

    def changeEvent(self, evento):
        super().changeEvent(evento)
        mudou_escala = getattr(QEvent, "DevicePixelRatioChange", None)
        if mudou_escala is not None and evento.type() == mudou_escala and self.cores:
            self._atualizar_icones()

    def showEvent(self, evento):
        super().showEvent(evento)
        janela = self.windowHandle()
        if janela is not None and not getattr(self, "_tela_conectada", False):
            janela.screenChanged.connect(lambda _tela: self.cores and self._atualizar_icones())
            self._tela_conectada = True
            # sem isso o 1º botão da barra ganha o foco (e o anel de foco) ao abrir o programa
            QTimer.singleShot(0, lambda: self.tabela.setFocus() if self.tabela.isVisible() else self.setFocus())

    def aplicar_config(self, config):
        """Chamado ao vivo pela janela de configurações (e no Cancelar, com os valores antigos).
        Espera ~150 ms sem mudanças antes de aplicar, para não reaplicar o tema a cada clique no spin."""
        self._config_pendente = dict(config)
        self._timer_config.start()

    def _aplicar_config_pendente(self):
        self._timer_config.stop()
        if self._config_pendente is None:
            return
        anterior = self.config
        self.config = self._config_pendente
        self._config_pendente = None
        self._aplicar_config_metadata()
        self._atualizar_formato()
        if any(anterior.get(k) != self.config.get(k) for k in CHAVES_APARENCIA):
            self.aplicar_tema()
        if anterior.get("generos") != self.config.get("generos"):
            self._atualizar_generos()
        self.tela_vazia.definir_subpastas(self.config["subpastas"])
        self.tabela.definir_agrupar(self.config["agrupar_por_album"])

    def _aplicar_config_metadata(self):
        """Opções de gravação ficam no módulo metadata (a CLI usa os padrões de lá)."""
        c = self.config
        metadata.VERSAO_ID3 = int(c["versao_id3"])
        metadata.MULTIVALOR = bool(c["multivalor"])
        metadata.REMOVER_ID3V1 = bool(c["remover_id3v1"])
        self.painel.lado_max_capa = int(c["lado_max_capa"]) if c["otimizar_capa"] else 0

    def abrir_configuracoes(self):
        dialogo = DialogoConfiguracoes(self.config, self)
        dialogo.mudou.connect(self.aplicar_config)
        aceito = []
        dialogo.accepted.connect(lambda: aceito.append(True))
        dialogo.exec()
        self._aplicar_config_pendente()
        if aceito:
            # as credenciais não passam pela prévia ao vivo: entram só aqui, já indo para o QSettings
            # (de onde o log as lê para ocultar). No Cancelar a sessão nunca as vê.
            self.config.update(dialogo.credenciais_aceitas())
            salvar_config(self.settings, self.config)
            self.servicos_mudaram.emit(self.estado_servicos())

    def estado_servicos(self):
        """Last.fm/Discogs disponíveis com as Configurações atuais, e a dica para quando não estão."""
        return estado_servicos(self.config)

    def alternar_tema(self):
        self.config["usar_escuro"] = not self.config["usar_escuro"]
        salvar_config(self.settings, self.config)
        self.aplicar_tema()

    def alternar_painel(self):
        visivel = self.painel.isHidden()
        self.painel.setVisible(visivel)
        self.btn_painel.setToolTip(("Esconder" if visivel else "Mostrar") + " o editor (Ctrl+E)")
        self.settings.setValue("painel_visivel", visivel)

    def _atualizar_generos(self):
        dos_arquivos = {f.tags["genre"] for f in self.modelo.faixas if f.tags["genre"]}
        self.painel.definir_generos(list(self.config["generos"]) + list(dos_arquivos))

    # ------------------------------------------------------------------ abrir arquivos
    def abrir_pasta(self):
        if not self._confirmar_pendencias():
            return
        inicial = self.settings.value("ultima_pasta", str(Path.home()))
        pasta = QFileDialog.getExistingDirectory(self, "Abrir pasta de músicas", inicial)
        if pasta:
            self.carregar_caminhos([pasta], substituir=True, ja_confirmado=True)

    def adicionar_arquivos(self):
        inicial = self.settings.value("ultima_pasta", str(Path.home()))
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Adicionar arquivos", inicial, f"Arquivos de áudio ({' '.join(curingas_audio())})")
        if arquivos:
            self.carregar_caminhos(arquivos, substituir=not self.modelo.faixas)

    def carregar_caminhos(self, caminhos, substituir, ja_confirmado=False):
        if self._carregador is not None or self._gravando():
            self.avisar("Aguarde: ainda estou trabalhando nos arquivos anteriores.")
            return
        if substituir and not ja_confirmado and not self._confirmar_pendencias():
            return

        pastas = [Path(c) for c in caminhos if Path(c).is_dir()]
        arquivos = expandir_caminhos(caminhos, recursivo=self.config["subpastas"])
        if not arquivos:
            self.avisar(f"Nenhum arquivo de áudio encontrado ({nomes_formatos()}).")
            return

        if pastas:
            self.settings.setValue("ultima_pasta", str(pastas[0]))
            if substituir and len(pastas) == 1:
                self.pasta_atual = pastas[0]
                self.settings.setValue("ultima_pasta_aberta", str(pastas[0]))
                self._lembrar_recente(pastas[0])
        elif substituir:
            self.pasta_atual = None
            self.settings.setValue("ultima_pasta", str(arquivos[0].parent))

        self._iniciar_carregador(arquivos, "substituir" if substituir else "adicionar")

    def _iniciar_carregador(self, arquivos, modo):
        self._modo_carregar = modo
        self.lbl_status.setText(f"Lendo {len(arquivos)} arquivos…")
        self._mostrar_progresso(0, len(arquivos))
        self._carregador = Carregador(arquivos, self)
        self._carregador.progresso.connect(self._ao_progresso_leitura)
        self._carregador.concluido.connect(self._ao_carregar)
        self._carregador.finished.connect(self._carregador.deleteLater)
        self._carregador.start()

    def _ao_progresso_leitura(self, i, total):
        self.lbl_status.setText(f"Lendo arquivos… {i}/{total}")
        self._mostrar_progresso(i, total)

    def recarregar(self):
        """F5: relê do disco os arquivos da lista (e acha arquivos novos na pasta aberta)."""
        if not self.modelo.faixas or self._ocupado() or not self._confirmar_pendencias():
            return
        caminhos = [f.caminho for f in self.modelo.faixas]
        if self.pasta_atual and self.pasta_atual.is_dir():
            conhecidos = set(caminhos)
            caminhos += [c for c in listar_audios(self.pasta_atual, recursivo=self.config["subpastas"])
                         if c not in conhecidos]
        self._iniciar_carregador(caminhos, "recarregar")

    def _ao_recarregar(self, faixas, falhas):
        existentes = self.modelo.por_caminho()
        self.modelo.atualizar([f for f in faixas if f.caminho in existentes])
        novos = self.modelo.adicionar([f for f in faixas if f.caminho not in existentes])
        sumiram = set(falhas)
        linhas = [i for i, f in enumerate(self.modelo.faixas) if f.caminho in sumiram]
        if linhas:
            self.modelo.remover(linhas)
        self.painel.invalidar_capas()
        self._carregar_selecao()
        partes = [f"{len(faixas)} arquivo(s) relidos do disco"]
        if novos:
            partes.append(f"{novos} novo(s)")
        if linhas:
            partes.append(f"{len(linhas)} não existem mais ou não abrem e saíram da lista")
        self.avisar(" · ".join(partes), ok=not linhas, erro=bool(linhas))

    def _ao_carregar(self, faixas, falhas):
        self._carregador = None
        self.progresso.setVisible(False)
        if self._modo_carregar == "recarregar":
            self._ao_recarregar(faixas, falhas)
        elif self._modo_carregar == "substituir":
            self.rascunho.descartar()
            self.historico_pendente = None
            self.pilha_desfazer.clear()
            self.pilha_refazer.clear()
            self.modelo.definir(faixas)
            self.painel.invalidar_capas()
            self.painel.carregar([])
            novos = len(faixas)
        else:
            novos = self.modelo.adicionar(faixas)

        self.telas.setCurrentIndex(1 if self.modelo.faixas else 0)
        self._atualizar_generos()
        self._atualizar_migalha()
        self._atualizar_estado()
        if self._modo_carregar == "recarregar":
            return
        if falhas:
            self.avisar(f"{len(falhas)} arquivo(s) não puderam ser lidos (corrompidos ou não são {nomes_formatos()}).", erro=True)
        elif self._modo_carregar == "adicionar":
            self.avisar(f"{novos} arquivo(s) adicionado(s).", ok=True)

    # ------------------------------------------------------------------ seleção e rascunho
    def _faixas_selecionadas(self):
        return [self.modelo.faixas[linha] for linha in self.tabela.linhas_selecionadas()]

    def _carregar_selecao(self):
        self.painel.carregar(self._faixas_selecionadas())
        self._atualizar_estado()

    def _ao_mudar_rascunho(self, caminhos):
        self.modelo.linhas_mudaram(caminhos)
        self.painel.ao_mudar_rascunho()
        self._atualizar_estado()

    def _editar_celula(self, faixa, campo, valor):
        """Edição direto na tabela: valida e vira alteração pendente."""
        ok, mensagem = validar_valor(campo, valor)
        if not ok:
            self.avisar(f"{rotulo(campo)}: {mensagem}", erro=True)
            return False
        self.rascunho.definir([faixa], campo, valor)
        return True

    def _editar_celula_atual(self):
        indice = self.tabela.currentIndex()
        if indice.isValid():
            self.tabela.edit(indice)

    # ------------------------------------------------------------------ salvar / descartar
    def salvar(self, sincrono=False):
        """
        Grava TODAS as alterações pendentes. Devolve False se não salvou (ex.: valor inválido).
        sincrono=True é o "salvar antes de continuar" (fechar, abrir outra pasta...): só devolve True se
        tudo foi gravado, ou se o usuário aceitou descartar as alterações dos arquivos que falharam.
        """
        if self.rascunho.vazio or self._gravando():
            return self.rascunho.vazio

        erros = self.rascunho.validar()
        if erros:
            caminho, campo, mensagem = erros[0]
            self.avisar(f"{Path(caminho).name} — {rotulo(campo)}: {mensagem}", erro=True)
            faixa = self.modelo.faixa_por_caminho(caminho)
            if faixa is not None:
                self.tabela.selecionar_linhas([self.modelo.faixas.index(faixa)])
                self._carregar_selecao()
                self.painel.marcar_erros([campo])
            return False

        trabalhos, mtimes = self._trabalhos_conferidos()
        if trabalhos is None:
            return False
        if not trabalhos:
            return True
        if sincrono:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                resultado = executar_salvamento(trabalhos, mtimes=mtimes)
            finally:
                QApplication.restoreOverrideCursor()
            self._ao_salvar(resultado)
            falhas = resultado[1]
            if falhas and self._perguntar_falhas(falhas):
                self.rascunho.descartar(falhas)
                return True
            return not falhas

        self._bloquear(True)
        self.lbl_status.setText(f"Salvando {len(trabalhos)} arquivos…")
        self._mostrar_progresso(0, len(trabalhos))
        self._salvador = Salvador(trabalhos, mtimes, self)
        self._salvador.progresso.connect(self._ao_progresso_salvar)
        self._salvador.concluido.connect(self._ao_salvar)
        self._salvador.finished.connect(self._salvador.deleteLater)
        self._salvador.start()
        return True

    def _trabalhos_conferidos(self):
        """
        Trabalhos do rascunho + {caminho: mtime esperado}. Se algum arquivo mudou no disco depois de lido
        (outro player/tagger), pergunta: sobrescrever, recarregar esses (descarta as alterações deles)
        ou cancelar. Devolve (None, None) se cancelou.
        """
        por_caminho = self.modelo.por_caminho()
        faixas = [por_caminho[c] for c in self.rascunho.caminhos() if c in por_caminho]
        mtimes = {f.caminho: f.mtime for f in faixas}
        modificadas = [f for f in faixas if foi_modificado(f)]
        if modificadas:
            resposta = self._perguntar_modificados(modificadas)
            if resposta == "cancelar":
                return None, None
            caminhos = [f.caminho for f in modificadas]
            if resposta == "sobrescrever":
                mtimes.update({c: mtime_atual(c) for c in caminhos})
            else:
                self.rascunho.descartar(caminhos)
                relidas, _ = carregar_varios(caminhos)
                self.modelo.atualizar(relidas)
                self.painel.invalidar_capas(caminhos)
                self._carregar_selecao()
                self.avisar(f"{len(relidas)} arquivo(s) recarregados do disco; as alterações deles foram descartadas.")
        return self.rascunho.trabalhos(), mtimes

    def _perguntar_modificados(self, faixas):
        """'sobrescrever', 'recarregar' ou 'cancelar'."""
        n = len(faixas)
        nomes = "\n".join(f"•  {f.nome}" for f in faixas[:6]) + (f"\n…e mais {n - 6}" if n > 6 else "")
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Warning)
        caixa.setWindowTitle("Arquivos alterados por outro programa")
        caixa.setText(f"{'1 arquivo foi alterado' if n == 1 else f'{n} arquivos foram alterados'} "
                      "no disco depois que o Tagger leu.")
        caixa.setInformativeText(f"{nomes}\n\nSobrescrever grava as suas alterações por cima. Recarregar descarta "
                                 "as suas alterações nesses arquivos e mostra o que está no disco.")
        sobrescrever = caixa.addButton("Sobrescrever", QMessageBox.AcceptRole)
        recarregar = caixa.addButton("Recarregar esses", QMessageBox.DestructiveRole)
        caixa.addButton("Cancelar", QMessageBox.RejectRole)
        caixa.setDefaultButton(sobrescrever)
        caixa.exec()
        if caixa.clickedButton() is sobrescrever:
            return "sobrescrever"
        if caixa.clickedButton() is recarregar:
            return "recarregar"
        return "cancelar"

    def _perguntar_falhas(self, falhas):
        """Salvar antes de continuar falhou em alguns arquivos. True = descartar as alterações deles e continuar."""
        n = len(falhas)
        nomes = "\n".join(f"•  {Path(c).name}: {erro}" for c, erro in list(falhas.items())[:6])
        if n > 6:
            nomes += f"\n…e mais {n - 6}"
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Warning)
        caixa.setWindowTitle("Alterações não salvas")
        caixa.setText(f"{'1 arquivo não pôde ser salvo' if n == 1 else f'{n} arquivos não puderam ser salvos'} "
                      "(em uso ou somente leitura?).")
        caixa.setInformativeText(f"{nomes}\n\nVoltar mantém as alterações pendentes para você tentar de novo. "
                                 "Descartar perde as alterações desses arquivos.")
        descartar = caixa.addButton("Descartar e continuar", QMessageBox.DestructiveRole)
        voltar = caixa.addButton("Voltar", QMessageBox.RejectRole)
        caixa.setDefaultButton(voltar)
        caixa.exec()
        return caixa.clickedButton() is descartar

    def _ao_progresso_salvar(self, i, total):
        self.lbl_status.setText(f"Salvando… {i}/{total}")
        self._mostrar_progresso(i, total)

    def _ao_salvar(self, resultado):
        registros, falhas, faixas = resultado
        self._salvador = None
        self._bloquear(False)
        self.progresso.setVisible(False)

        self.modelo.atualizar(faixas)
        caminhos = [f.caminho for f in faixas]
        self.painel.invalidar_capas(caminhos)
        salvos = [c for c in caminhos if c not in falhas]
        self.rascunho.descartar(salvos)

        registros_ok = [r for r in registros if r[0] not in falhas]
        if registros_ok:
            tipo = self.historico_pendente[1] if self.historico_pendente else None
            if tipo == "desfazer":
                self.pilha_refazer.append(registros_ok)
            elif tipo == "refazer":
                self.pilha_desfazer.append(registros_ok)
            else:
                self.pilha_desfazer.append(registros_ok)
                self.pilha_refazer.clear()
        self.historico_pendente = None

        self._carregar_selecao()
        self._atualizar_generos()
        if falhas:
            for caminho, erro in falhas.items():
                log.warning("Não salvou %s: %s", caminho, erro)
            nomes = ", ".join(Path(c).name for c in list(falhas)[:3])
            motivo = next(iter(falhas.values()))
            self.avisar(f"{len(falhas)} arquivo(s) não foram salvos ({motivo}): {nomes}", erro=True)
        else:
            n = len(salvos)
            self.avisar("1 arquivo salvo" if n == 1 else f"{n} arquivos salvos", ok=True)

    def descartar(self):
        """Descarta todas as alterações pendentes (e devolve um desfazer/refazer não confirmado)."""
        if self.historico_pendente:
            registros, tipo = self.historico_pendente
            (self.pilha_desfazer if tipo == "desfazer" else self.pilha_refazer).append(registros)
            self.historico_pendente = None
        if not self.rascunho.vazio:
            self.rascunho.descartar()
            self.avisar("Alterações descartadas")
        self._atualizar_estado()

    def _bloquear(self, sim):
        self.centralWidget().setEnabled(not sim)

    def _mostrar_progresso(self, i, total):
        self.progresso.setVisible(True)
        self.progresso.setMaximum(max(1, total))
        self.progresso.setValue(i)

    # ------------------------------------------------------------------ desfazer / refazer
    def desfazer(self):
        """Com alterações pendentes: descarta. Senão: coloca os valores anteriores como pendentes."""
        if self._gravando():
            return
        if not self.rascunho.vazio or self.historico_pendente:
            self.descartar()
            return
        if self.pilha_desfazer:
            item = self.pilha_desfazer.pop()
            if isinstance(item, Renomeacao):
                self._reverter_renomeacao(item, self.pilha_refazer, "Desfeito")
            else:
                self._preparar_historico(item, "desfazer")

    def refazer(self):
        if self._gravando() or not self.rascunho.vazio or not self.pilha_refazer:
            return
        item = self.pilha_refazer.pop()
        if isinstance(item, Renomeacao):
            self._reverter_renomeacao(item, self.pilha_desfazer, "Refeito")
        else:
            self._preparar_historico(item, "refazer")

    def _reverter_renomeacao(self, item, pilha_oposta, verbo):
        """Renomear/mover não passa pelo rascunho: desfazer/refazer move de volta na hora (em segundo plano)."""
        plano = [ItemRenomear(origem, destino) for origem, destino in item.inversa().pares]
        liberadas, criadas = set(self._pastas_criadas), []

        def tarefa():
            feitos, falhas = executar_movimentos(plano, criadas)
            # pastas que o Tagger criou ao organizar e que ficaram vazias saem junto
            remover_pastas_vazias({o.parent for o, _d in feitos}, permitidas=liberadas)
            return feitos, falhas

        pilha_origem = self.pilha_refazer if pilha_oposta is self.pilha_desfazer else self.pilha_desfazer

        def concluir(resultado):
            feitos, falhas = resultado
            self._pastas_criadas.update(criadas)
            self._aplicar_renomeacao(dict(feitos), self._mtimes_antes)
            self._seguir_arquivos_movidos(*self._pastas_do_movimento)
            if feitos:
                pilha_oposta.append(Renomeacao(feitos))
            if falhas:        # o que não voltou continua no histórico para tentar de novo
                pilha_origem.append(Renomeacao([(a, n) for a, n in item.pares if n in falhas]))
                nomes = ", ".join(Path(c).name for c in list(falhas)[:3])
                self.avisar(f"{verbo}: {len(feitos)} movido(s), {len(falhas)} falharam: {nomes}", erro=True)
            else:
                self.avisar(f"{verbo}: {len(feitos)} arquivo(s) no lugar anterior", ok=True)

        self._mover_em_segundo_plano(tarefa, concluir, "Movendo arquivos…", plano, pilha_oposta, (item, pilha_origem))

    def _mover_em_segundo_plano(self, tarefa, concluir, texto, itens=(), pilha=None, desfazendo=None):
        """Bloqueia a janela (cursor de espera) enquanto `tarefa` roda; `concluir(resultado)` roda na interface.
        itens: [ItemRenomear] previstos; se a tarefa quebrar, o que já foi movido é registrado em `pilha`.
        desfazendo: (Renomeacao, pilha de onde saiu) quando é desfazer/refazer; None = organizar novo."""
        self._mtimes_antes = {i.origem: mtime_atual(i.origem) for i in itens}
        self._itens_movendo, self._pilha_movendo, self._desfazendo = list(itens), pilha, desfazendo
        self._bloquear(True)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.lbl_status.setText(texto)
        self.progresso.setVisible(True)
        self.progresso.setRange(0, 0)            # indeterminado
        self._movedor = Movedor(tarefa, self)
        self._movedor.concluido.connect(lambda r: self._ao_mover(r, concluir))
        self._movedor.finished.connect(self._movedor.deleteLater)
        self._movedor.start()
        self._atualizar_estado()

    def _ao_mover(self, resultado, concluir):
        self._movedor = None
        QApplication.restoreOverrideCursor()
        self._bloquear(False)
        self.progresso.setRange(0, 1)
        self.progresso.setVisible(False)
        if isinstance(resultado, Exception):
            # a tarefa quebrou no meio: registra o que já saiu do lugar (origem some, destino aparece)
            feitos = [(i.origem, i.destino) for i in self._itens_movendo
                      if not i.origem.exists() and i.destino.exists()]
            self._aplicar_renomeacao(dict(feitos), self._mtimes_antes)
            self._seguir_arquivos_movidos(*self._pastas_do_movimento)
            if feitos and self._pilha_movendo is not None:
                self._pilha_movendo.append(Renomeacao(feitos))
            if self._desfazendo is None:
                self.pilha_refazer.clear()          # organizar novo invalida o refazer
            else:                                   # o que não voltou continua na pilha de onde saiu
                item, pilha_origem = self._desfazendo
                feitos_inversos = {(d, o) for o, d in feitos}
                faltam = [(a, n) for a, n in item.pares if (a, n) not in feitos_inversos]
                if faltam:
                    pilha_origem.append(Renomeacao(faltam))
            self.avisar(f"Erro ao mover os arquivos ({resultado}); {len(feitos)} já foram movidos.", erro=True)
        else:
            concluir(resultado)
        self._atualizar_estado()

    def _preparar_historico(self, registros, tipo):
        mudou = self.rascunho.aplicar_registros(registros, self.modelo.por_caminho())
        if not mudou:
            self.avisar("Os arquivos já estão nesse estado.")
            self._atualizar_estado()
            return
        self.historico_pendente = (registros, tipo)
        linhas = [i for i, f in enumerate(self.modelo.faixas) if f.caminho in mudou]
        self.tabela.selecionar_linhas(linhas)
        self._carregar_selecao()
        acao = "Desfazer" if tipo == "desfazer" else "Refazer"
        self.avisar(f"{acao}: revise e clique em Salvar para confirmar (Esc cancela)")

    # ------------------------------------------------------------------ menu das linhas
    def _menu_linhas(self, posicao):
        selecionadas = self._faixas_selecionadas()
        n = len(selecionadas)
        self.acao_numerar.setText(f"Numerar faixas (1 a {n})" if n > 1 else "Numerar faixas")
        self.acao_numerar.setEnabled(n > 0)
        for acao in (self.acao_renomear, self.acao_tags_nome, self.acao_organizar, self.acao_busca_online,
                     self.acao_limpar):
            acao.setEnabled(n > 0)
        self.acao_copiar.setEnabled(n > 0)
        self.acao_colar.setEnabled(n > 0 and self.area_tags is not None)
        self.acao_pasta.setEnabled(n > 0)
        self.acao_remover.setText("Remover da lista" if n <= 1 else f"Remover {n} da lista")
        self.acao_remover.setEnabled(n > 0)

        menu = QMenu(self)
        menu.addAction(self.acao_editar)
        menu.addAction(self.acao_numerar)
        menu.addAction(self.acao_renomear)
        menu.addAction(self.acao_tags_nome)
        menu.addAction(self.acao_organizar)
        menu.addAction(self.acao_busca_online)
        menu.addSeparator()
        menu.addAction(self.acao_copiar)
        menu.addAction(self.acao_colar)
        menu.addSeparator()
        menu.addAction(self.acao_limpar)
        menu.addSeparator()
        menu.addAction(self.acao_pasta)
        menu.addAction(self.acao_recarregar)
        menu.addAction(self.acao_remover)
        menu.addSeparator()
        menu.addAction(self.acao_tudo)
        menu.exec(posicao)

    def numerar_faixas(self):
        selecionadas = self._faixas_selecionadas()   # na ordem em que aparecem na tela
        total = len(selecionadas)
        if not total:
            return
        com_total = self.config["numerar_com_total"]
        itens = [(f, {"tracknumber": f"{i}/{total}" if com_total else str(i)})
                 for i, f in enumerate(selecionadas, start=1)]
        self.rascunho.definir_por_faixa(itens)
        self.avisar(f"{total} faixas numeradas na ordem da tabela — clique em Salvar para gravar")

    def copiar_tags(self):
        selecionadas = self._faixas_selecionadas()
        if not selecionadas:
            return
        tags = {}
        for campo in CAMPOS:
            valores = {self.rascunho.valor(f, campo) for f in selecionadas}
            if len(valores) == 1:
                valor = valores.pop()
                if valor:
                    tags[campo] = valor
        capa = None
        if self.painel.faixas == selecionadas:
            capa = self.painel.capa_mostrada
        self.area_tags = {"tags": tags, "capa": capa}
        extra = " + capa" if capa else ""
        self.avisar(f"{len(tags)} tags copiadas{extra}", ok=True)

    def colar_tags(self):
        selecionadas = self._faixas_selecionadas()
        if not selecionadas or not self.area_tags:
            return
        tags = dict(self.area_tags["tags"])
        if len(selecionadas) > 1:            # título, faixa e letra são únicos de cada música
            for campo in ("title", "tracknumber", "lyrics"):
                tags.pop(campo, None)
        self.rascunho.definir_por_faixa([(f, tags) for f in selecionadas])
        capa = self.area_tags.get("capa")
        if capa:
            self.rascunho.definir_capa([f.caminho for f in selecionadas], ("definir", capa[0], capa[1]))
        self.avisar(f"Tags coladas em {len(selecionadas)} arquivo(s) — clique em Salvar para gravar")

    def _gravando(self):
        """Uma thread está gravando nos arquivos (salvar ou limpar tags)."""
        return self._salvador is not None or self._limpador is not None or self._movedor is not None

    def _ocupado(self):
        if self._carregador is not None or self._gravando():
            self.avisar("Aguarde: ainda estou trabalhando nos arquivos anteriores.")
            return True
        return False

    def _lembrar_padrao(self, tipo, padrao):
        self.config[f"padrao_{tipo}"] = padrao
        self.config[f"recentes_{tipo}"] = lembrar_padrao(self.config[f"recentes_{tipo}"], padrao)
        salvar_config(self.settings, self.config)

    def renomear_pelas_tags(self):
        selecionadas = self._faixas_selecionadas()
        if not selecionadas or self._ocupado():
            return
        pendentes = any(self.rascunho.tem(f.caminho) for f in selecionadas)
        dialogo = DialogoRenomear(selecionadas, self.rascunho.valor, self.config["padrao_renomear"],
                                  self.config["recentes_renomear"], self.cores, pendentes, self)
        if dialogo.exec() != QDialog.Accepted:
            return
        self._lembrar_padrao("renomear", dialogo.padrao)
        feitos, falhas = executar_renomeacao([item for item in dialogo.plano if item.valido])
        self._aplicar_renomeacao(dict(feitos))
        if feitos:
            self.pilha_desfazer.append(Renomeacao(feitos))
            self.pilha_refazer.clear()
        if falhas:
            for caminho, erro in falhas.items():
                log.warning("Não renomeou %s: %s", caminho, erro)
            nomes = ", ".join(Path(c).name for c in list(falhas)[:3])
            self.avisar(f"{len(feitos)} renomeado(s), {len(falhas)} falharam (em uso?): {nomes}", erro=True)
        else:
            self.avisar(f"{len(feitos)} arquivo(s) renomeado(s) — Ctrl+Z desfaz", ok=True)
        self._atualizar_estado()

    def organizar_em_pastas(self):
        selecionadas = self._faixas_selecionadas()
        if not selecionadas or self._ocupado():
            return
        destino = self.pasta_atual or selecionadas[0].caminho.parent
        pendentes = any(self.rascunho.tem(f.caminho) for f in selecionadas)
        dialogo = DialogoOrganizar(selecionadas, self.rascunho.valor, self.config["padrao_organizar"],
                                   self.config["recentes_organizar"], self.cores, str(destino), pendentes, self)
        if dialogo.exec() != QDialog.Accepted:
            return
        self._lembrar_padrao("organizar", dialogo.padrao)
        plano, remover, raiz, criadas = dialogo.plano, dialogo.remover_vazias, self.pasta_atual, []
        self._pastas_do_movimento = (raiz, plano.pasta)       # onde as faixas estavam e para onde vão (desfazer/refazer)

        def concluir(resultado):
            feitos, falhas, removidas = resultado
            self._pastas_criadas.update(criadas)
            self._aplicar_renomeacao(dict(feitos), self._mtimes_antes)
            if feitos:
                self.pilha_desfazer.append(Renomeacao(feitos))
                self.pilha_refazer.clear()
            extra = f" · {len(removidas)} pasta(s) vazia(s) removida(s)" if removidas else ""
            if falhas:
                for caminho, erro in falhas.items():
                    log.warning("Não moveu %s: %s", caminho, erro)
                nomes = ", ".join(Path(c).name for c in list(falhas)[:3])
                self.avisar(f"{len(feitos)} movido(s), {len(falhas)} falharam (em uso?): {nomes}{extra}", erro=True)
            else:
                self.avisar(f"{len(feitos)} arquivo(s) movido(s){extra} — Ctrl+Z desfaz", ok=True)
            self._seguir_arquivos_movidos(plano.pasta)
            if feitos or falhas:
                DialogoResumoOrganizar(feitos, falhas, plano.pasta, self).exec()

        self._mover_em_segundo_plano(lambda: executar_organizacao(plano, remover, raiz, criadas), concluir,
                                     f"Movendo {len(plano.validos())} arquivos…", plano.validos(), self.pilha_desfazer)

    def _seguir_arquivos_movidos(self, *preferidas):
        """Migalha (e F5) acompanham os arquivos quando saem da pasta aberta (ver nucleo.pasta_apos_mover)."""
        nova = pasta_apos_mover(self.pasta_atual, [f.caminho for f in self.modelo.faixas], preferidas)
        if nova != self.pasta_atual:
            self.pasta_atual = nova
            self._atualizar_migalha()

    def buscar_tags_online(self):
        selecionadas = self._faixas_selecionadas()
        if not selecionadas:
            self.avisar("Selecione as faixas que quer buscar online.")
            return
        if self._ocupado():
            return
        dialogo = DialogoBuscaOnline(selecionadas, self, valor=self.rascunho.valor, config=self.config,
                                     estados=self.estado_servicos())
        if dialogo.exec() != QDialog.Accepted:
            return
        resultado = dialogo.resultado()
        self.rascunho.definir_por_faixa(resultado.alteracoes)
        if resultado.capa:
            _, dados, mime = resultado.acao_capa
            self.rascunho.definir_capa(resultado.caminhos_capa, ("definir", *garantir_jpeg_ou_png(dados, mime)))
        mensagem = f"Tags online aplicadas em {resultado.alteradas} arquivo(s) — clique em Salvar para gravar"
        if resultado.sem_par:
            nomes = ", ".join(f.nome for f in resultado.sem_par[:3])
            mensagem += f" · {len(resultado.sem_par)} sem correspondência (não alterados): {nomes}"
        self.avisar(mensagem)

    def mostrar_sobre(self):
        from tagger.gui.sobre import DialogoSobre
        DialogoSobre(self).exec()

    def _aplicar_renomeacao(self, mapa, mtimes_antes=None):
        """Arquivos renomeados ({antigo: novo}): lista, rascunho e histórico passam a usar o caminho novo.
        mtimes_antes: {antigo: mtime antes de mover}; se batia com o lido, o mtime novo (FAT32/exFAT muda)
        passa a valer, senão uma alteração externa anterior continua sendo detectada no Salvar."""
        if not mapa:
            return
        self.modelo.renomear(mapa)
        if mtimes_antes:
            antigos = {novo: antigo for antigo, novo in mapa.items()}
            for faixa in self.modelo.faixas:
                antigo = antigos.get(faixa.caminho)
                if antigo is not None and mtimes_antes.get(antigo) == faixa.mtime:
                    faixa.mtime = mtime_atual(faixa.caminho) or faixa.mtime
        self.rascunho.renomear(mapa)
        migrar_historico(self.pilha_desfazer, mapa)
        migrar_historico(self.pilha_refazer, mapa)
        if self.historico_pendente:
            registros, tipo = self.historico_pendente
            pilha = [registros]
            migrar_historico(pilha, mapa)
            self.historico_pendente = (pilha[0], tipo)
        self.painel.invalidar_capas([*mapa, *mapa.values()])
        self._carregar_selecao()

    def tags_pelo_nome(self):
        selecionadas = self._faixas_selecionadas()
        if not selecionadas or self._ocupado():
            return
        dialogo = DialogoTagsDoNome(selecionadas, self.rascunho.valor, self.config["padrao_tags"],
                                    self.config["recentes_tags"], self.cores, self)
        if dialogo.exec() != QDialog.Accepted:
            return
        self._lembrar_padrao("tags", dialogo.padrao)
        self.rascunho.definir_por_faixa(dialogo.resultado)
        n = len(dialogo.resultado)
        self.avisar(f"Tags lidas do nome em {n} arquivo(s) — clique em Salvar para gravar")

    def limpar_tags_extras(self):
        if not self._faixas_selecionadas() or self._ocupado():
            return
        pendentes = [f.caminho for f in self._faixas_selecionadas() if self.rascunho.tem(f.caminho)]
        if pendentes:
            if not self._confirmar_pendencias(pendentes):   # a limpeza grava na hora: salva (ou descarta) antes
                return
        selecionadas = self._faixas_selecionadas()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            analises = [analisar_extras(f.caminho) for f in selecionadas]
        finally:
            QApplication.restoreOverrideCursor()
        dialogo = DialogoLimpeza(analises, self)
        if dialogo.exec() != QDialog.Accepted:
            return

        caminhos = [f.caminho for f in selecionadas]
        self._bloquear(True)
        self.lbl_status.setText(f"Limpando {len(caminhos)} arquivos…")
        self._mostrar_progresso(0, len(caminhos))
        self._limpador = Limpador(caminhos, dialogo.opcoes(), self)
        self._limpador.progresso.connect(self._ao_progresso_limpar)
        self._limpador.concluido.connect(self._ao_limpar)
        self._limpador.finished.connect(self._limpador.deleteLater)
        self._limpador.start()
        self._atualizar_estado()

    def _ao_progresso_limpar(self, i, total):
        self.lbl_status.setText(f"Limpando… {i}/{total}")
        self._mostrar_progresso(i, total)

    def _ao_limpar(self, resultado):
        limpos, falhas, relidas = resultado
        self._limpador = None
        self._bloquear(False)
        self.progresso.setVisible(False)
        self.modelo.atualizar(relidas)
        self.painel.invalidar_capas([f.caminho for f in relidas])
        self._carregar_selecao()
        if falhas:
            self.avisar(f"{limpos} arquivo(s) limpos, {len(falhas)} falharam (em uso ou somente leitura?)", erro=True)
        else:
            self.avisar(f"{limpos} arquivo(s) limpos" if limpos else "Nada para limpar", ok=True)

    def mostrar_na_pasta(self):
        selecionadas = self._faixas_selecionadas()
        if selecionadas:
            mostrar_no_explorador(selecionadas[0].caminho)

    def remover_da_lista(self):
        linhas = self.tabela.linhas_selecionadas()
        if not linhas:
            return
        caminhos = [self.modelo.faixas[l].caminho for l in linhas]
        com_rascunho = [c for c in caminhos if self.rascunho.tem(c)]
        if com_rascunho:
            self.rascunho.descartar(com_rascunho)
        self.modelo.remover(linhas)
        self.painel.carregar([])
        if not self.modelo.faixas:
            self.telas.setCurrentIndex(0)
        extra = f" ({len(com_rascunho)} com alterações descartadas)" if com_rascunho else ""
        self.avisar(f"{len(linhas)} arquivo(s) removido(s) da lista{extra}. Nada foi apagado do disco.")
        self._atualizar_estado()

    # ------------------------------------------------------------------ busca e estado
    def _ao_buscar(self, texto):
        self.filtro.definir_texto(texto)
        self._atualizar_contagem()

    def _focar_busca(self):
        self.busca.setFocus()
        self.busca.selectAll()

    def _ao_escape(self):
        """Esc: limpa a busca, sai do campo em edição ou cancela um desfazer/refazer não confirmado.
        (Não descarta edições normais — para isso existe o botão Descartar.)"""
        foco = QApplication.focusWidget()
        if foco is self.busca and self.busca.text():
            self.busca.clear()
        elif foco is not None and self.painel.isAncestorOf(foco):
            self.tabela.setFocus()
        elif self.historico_pendente:
            self.descartar()

    def _atualizar_contagem(self, *_):
        self.lbl_contagem.setText(f"Mostrando {self.filtro.rowCount()} de {self.modelo.rowCount()}")

    def _atualizar_migalha(self):
        if not self.cores:
            return
        partes = self.pasta_atual.parts if self.pasta_atual else ["Arquivos avulsos"]
        self.lbl_migalha.definir(partes, self.cores, str(self.pasta_atual or ""))

    def _atualizar_formato(self):
        """Rodapé: formato (e tipo de tag) das faixas selecionadas, ou de todas se nada está selecionado."""
        faixas = self._faixas_selecionadas() or self.modelo.faixas
        formatos = {f.formato for f in faixas if f.formato}
        if len(formatos) > 1:
            texto = "Vários formatos"
        elif formatos:
            fmt = formatos.pop()
            texto = f"{fmt.upper()} · {ROTULO_TAGS[fmt](metadata.VERSAO_ID3) if fmt == 'mp3' else ROTULO_TAGS[fmt]}"
        else:
            texto = f"MP3 · ID3v2.{metadata.VERSAO_ID3}"
        self.lbl_formato.setText(texto)

    def _atualizar_estado(self):
        if not hasattr(self, "lbl_status") or not self.cores:
            return
        self._atualizar_formato()
        trabalhando = self._carregador is not None or self._gravando()
        total = len(self.modelo.faixas)
        n_sel = len(self.painel.faixas)
        if not trabalhando:
            self.lbl_status.setText(
                f"{total} {'arquivo' if total == 1 else 'arquivos'} · "
                f"{n_sel} {'selecionado' if n_sel == 1 else 'selecionados'}")

        n_arquivos = len(self.rascunho)
        pendente = n_arquivos > 0
        if pendente:
            q = self.rascunho.quantidade_campos()
            ponto = f'<span style="color:{self.cores["accent"]}">●</span> '
            self.lbl_pendente.definir(
                f"{q} {'alteração' if q == 1 else 'alterações'} em "
                f"{n_arquivos} {'arquivo' if n_arquivos == 1 else 'arquivos'} · não salvo", ponto)
        self.lbl_pendente.setVisible(pendente)

        self.btn_salvar_topo.setEnabled(pendente and not trabalhando)
        self.btn_salvar_topo.setText(f"Salvar · {n_arquivos}" if n_arquivos > 1 else "Salvar")
        pode_desfazer = pendente or bool(self.pilha_desfazer) or bool(self.historico_pendente)
        self.btn_desfazer.setEnabled(pode_desfazer and not trabalhando)
        self.btn_desfazer.setToolTip("Descartar alterações não salvas (Ctrl+Z)" if pendente else "Desfazer (Ctrl+Z)")
        self.btn_refazer.setEnabled(not pendente and bool(self.pilha_refazer) and not trabalhando)
        self.painel.atualizar_rodape()
        self._atualizar_contagem()

    def avisar(self, texto, ok=False, erro=False):
        simbolo = ""
        if ok:
            simbolo = f'<span style="color:{self.cores.get("accent", "")}">✓</span> '
        elif erro:
            simbolo = f'<span style="color:{self.cores.get("erro", "")}">!</span> '
        self.lbl_aviso.definir(texto, simbolo)
        self._timer_aviso.start()

    # ------------------------------------------------------------------ confirmações
    def _perguntar_salvar(self, n=None):
        """'salvar', 'descartar' ou 'cancelar'. n: quantos arquivos têm alterações (padrão: todos)."""
        n = len(self.rascunho) if n is None else n
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Question)
        caixa.setWindowTitle("Alterações não salvas")
        caixa.setText(f"Você tem alterações não salvas em {'1 arquivo' if n == 1 else f'{n} arquivos'}.")
        caixa.setInformativeText("Deseja salvar antes de continuar?")
        caixa.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        caixa.button(QMessageBox.Save).setText("Salvar")
        caixa.button(QMessageBox.Discard).setText("Descartar")
        caixa.button(QMessageBox.Cancel).setText("Cancelar")
        caixa.setDefaultButton(QMessageBox.Save)
        caixa.exec()
        clicado = caixa.clickedButton()
        if clicado == caixa.button(QMessageBox.Save):
            return "salvar"
        if clicado == caixa.button(QMessageBox.Discard):
            return "descartar"
        return "cancelar"

    def _confirmar_pendencias(self, caminhos=None):
        """True = pode continuar (salvou, descartou ou não havia nada).
        Com `caminhos`, "Descartar" descarta só as alterações desses arquivos."""
        if self.rascunho.vazio:
            return True
        resposta = self._perguntar_salvar(len(caminhos) if caminhos is not None else None)
        if resposta == "salvar":
            return self.salvar(sincrono=True)
        if resposta == "descartar":
            if caminhos is None:
                self.descartar()
            else:
                self.rascunho.descartar(caminhos)
                self.avisar("Alterações descartadas")
                self._atualizar_estado()
            return True
        return False

    # ------------------------------------------------------------------ recentes
    def _recentes(self):
        valor = self.settings.value("recentes", [])
        if isinstance(valor, str):
            valor = [valor]
        return list(valor or [])

    def _esquecer_recente(self, pasta):
        lista = [p for p in self._recentes() if p != str(pasta)]
        self.settings.setValue("recentes", lista)
        self.tela_vazia.definir_recentes(lista)

    def _lembrar_recente(self, pasta):
        lista = [str(pasta)] + [p for p in self._recentes() if p != str(pasta)]
        lista = lista[:MAX_RECENTES]
        self.settings.setValue("recentes", lista)
        self.tela_vazia.definir_recentes(lista)

    # ------------------------------------------------------------------ arrastar e soltar
    @staticmethod
    def _aceita_soltar(mime_data):
        """Só pastas ou arquivos de áudio suportados (imagens, textos etc. não acendem nada)."""
        if not mime_data.hasUrls():
            return False
        caminhos = [Path(u.toLocalFile()) for u in mime_data.urls() if u.isLocalFile()]
        return any(c.is_dir() or formato(c) for c in caminhos)

    def _destacar_soltar(self, ativo):
        na_tela_vazia = self.telas.currentIndex() == 0
        self.tela_vazia.destacar(ativo and na_tela_vazia)
        if ativo and not na_tela_vazia:
            self.overlay_drop.setGeometry(self.tabela.rect())
            self.overlay_drop.raise_()
            self.overlay_drop.show()
        else:
            self.overlay_drop.hide()

    def dragEnterEvent(self, evento):
        if self._aceita_soltar(evento.mimeData()):
            evento.acceptProposedAction()
            self._destacar_soltar(True)
        else:
            evento.ignore()

    def dragMoveEvent(self, evento):
        if self.overlay_drop.isVisible():
            self.overlay_drop.setGeometry(self.tabela.rect())
        super().dragMoveEvent(evento)

    def dragLeaveEvent(self, evento):
        self._destacar_soltar(False)

    def dropEvent(self, evento):
        self._destacar_soltar(False)
        caminhos = [url.toLocalFile() for url in evento.mimeData().urls() if url.isLocalFile()]
        if caminhos:
            evento.acceptProposedAction()
            self.carregar_caminhos(caminhos, substituir=not self.modelo.faixas)

    # ------------------------------------------------------------------ fechar
    def closeEvent(self, evento):
        if self._gravando():
            self.avisar("Aguarde terminar de gravar os arquivos antes de fechar.")
            evento.ignore()
            return
        if not self._confirmar_pendencias():
            evento.ignore()
            return
        self.settings.setValue("geometria", self.saveGeometry())
        self.settings.setValue("divisor", self.divisor.saveState())
        self.settings.setValue("cabecalho_v4", self.tabela.estado_cabecalho())
        if self._carregador is not None:
            self._carregador.wait(3000)
        super().closeEvent(evento)


def main():
    if sys.platform == "win32":
        try:   # ícone próprio na barra de tarefas do Windows
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("tagger.app")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName("Tagger")
    app.setApplicationVersion(VERSAO)
    app.setStyle("Fusion")
    instalar_tratamento_de_erros(configurar_log(VERSAO))
    tema.registrar_fontes()
    filtro_janelas = FiltroJanelas(app)
    app.installEventFilter(filtro_janelas)

    janela = JanelaPrincipal()
    janela.filtro_janelas = filtro_janelas
    filtro_janelas.aplicar_em_todas(tema.TEMAS.get(janela._tema_atual(), {}).get("escuro", True))
    janela.show()

    # arquivos/pastas passados na linha de comando (ou arrastados sobre o .exe)
    if len(sys.argv) > 1:
        janela.carregar_caminhos(sys.argv[1:], substituir=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
