"""
Tagger v2.0 — interface gráfica (PySide6).

Executar:  python app.py
"""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QThread, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from metadata import (
    VERSAO_ID3, carregar, carregar_varios, definir_capa, formato, ler_capa, listar_audios,
    remover_capa, salvar, validar_alteracoes,
)
from gui import tema
from gui.editor import PainelEditor
from gui.icones import icone, icone_app, pixmap
from gui.tabela import FiltroFaixas, ModeloFaixas, TabelaFaixas
from gui.vazio import TelaVazia

VERSAO = "2.0.0-dev"
MAX_RECENTES = 6
SEM_CAPA_NO_REGISTRO = object()   # marca "a capa não fez parte desta alteração"


# ============================================================================
# Leitura dos arquivos em segundo plano (pastas grandes não travam a janela)
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
        for i, caminho in enumerate(self.caminhos, start=1):
            faixa = carregar(caminho)
            (faixas if faixa else falhas).append(faixa or Path(caminho))
            if i % 25 == 0 or i == total:
                self.progresso.emit(i, total)
        self.concluido.emit(faixas, falhas)


def expandir_caminhos(caminhos):
    """Pastas viram a lista de MP3 dentro delas (com subpastas); arquivos soltos passam direto."""
    resultado = []
    for caminho in map(Path, caminhos):
        if caminho.is_dir():
            resultado.extend(listar_audios(caminho))
        elif caminho.is_file() and formato(caminho):
            resultado.append(caminho)
    return resultado


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


# ============================================================================
# Janela principal
# ============================================================================

class JanelaPrincipal(QMainWindow):
    def __init__(self, fonte_ui, fonte_mono):
        super().__init__()
        self.config = QSettings("Tagger", "Tagger")
        self.escuro = self.config.value("tema_escuro", True, type=bool)
        self.fonte_ui_nome = fonte_ui
        self.fonte_mono = QFont(fonte_mono)
        self.fonte_mono.setPixelSize(13)
        self.fonte_mono.setStyleHint(QFont.Monospace)

        self.pasta_atual = None
        self.cores = tema.paleta(self.escuro)
        self.pilha_desfazer = []      # cada item: lista de registros (caminho, tags, capa)
        self.pilha_refazer = []
        self._carregador = None
        self._substituir_ao_carregar = False
        self._ignorar_selecao = False

        self.setWindowTitle("Tagger")
        self.resize(1440, 900)
        self.setMinimumSize(960, 600)
        self.setAcceptDrops(True)

        self.modelo = ModeloFaixas(self)
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
        self.telas.addWidget(self.tela_vazia)
        self.telas.addWidget(self._criar_tela_principal())
        layout.addWidget(self.telas, 1)
        self.setCentralWidget(raiz)

        self._criar_barra_status()
        self._criar_atalhos()

        self.tela_vazia.definir_recentes(self._recentes())
        self.aplicar_tema()
        self._atualizar_estado()

        geometria = self.config.value("geometria")
        if geometria:
            self.restoreGeometry(geometria)

    # ------------------------------------------------------------------ montagem
    def _criar_barra_topo(self):
        barra = QWidget(objectName="barraTopo")
        barra.setAttribute(Qt.WA_StyledBackground, True)
        h = QHBoxLayout(barra)
        h.setContentsMargins(16, 10, 16, 10)
        h.setSpacing(8)

        self.logo = QLabel(objectName="logo", alignment=Qt.AlignCenter)
        self.logo.setFixedSize(26, 26)
        h.addWidget(self.logo)
        nome = QLabel("Tagger", objectName="nomeApp")
        h.addWidget(nome)
        h.addSpacing(12)

        self.btn_abrir = QPushButton("Abrir pasta")
        self.btn_abrir.setToolTip("Abrir pasta (Ctrl+O)")
        self.btn_abrir.clicked.connect(lambda: self.abrir_pasta())
        self.btn_adicionar = QPushButton("Adicionar arquivos")
        self.btn_adicionar.clicked.connect(lambda: self.adicionar_arquivos())
        h.addWidget(self.btn_abrir)
        h.addWidget(self.btn_adicionar)

        separador = QFrame(objectName="sep")
        separador.setFixedSize(1, 20)
        h.addSpacing(4)
        h.addWidget(separador)
        h.addSpacing(4)

        self.btn_desfazer = self._botao_icone("Desfazer (Ctrl+Z)", self.desfazer)
        self.btn_refazer = self._botao_icone("Refazer (Ctrl+Y)", self.refazer)
        h.addWidget(self.btn_desfazer)
        h.addWidget(self.btn_refazer)
        h.addStretch()

        self.busca = QLineEdit(objectName="busca")
        self.busca.setPlaceholderText("Filtrar por título, artista, álbum…")
        self.busca.setClearButtonEnabled(True)
        self.acao_busca = self.busca.addAction(icone("busca", "#888888"), QLineEdit.LeadingPosition)
        self.busca.textChanged.connect(self._ao_buscar)
        h.addWidget(self.busca)

        self.btn_tema = self._botao_icone("Alternar tema claro/escuro", self.alternar_tema)
        h.addWidget(self.btn_tema)

        self.btn_salvar_topo = QPushButton("Salvar")
        self.btn_salvar_topo.setProperty("tipo", "primario")
        self.btn_salvar_topo.setToolTip("Salvar (Ctrl+S)")
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

    def _criar_tela_principal(self):
        self.painel = PainelEditor()
        self.painel.alterado.connect(self._ao_alterar_painel)
        self.painel.salvarPedido.connect(lambda: self.salvar())
        self.painel.descartarPedido.connect(self.descartar)
        self.painel.setMinimumWidth(330)
        self.painel.setMaximumWidth(560)

        direita = QWidget()
        v = QVBoxLayout(direita)
        v.setContentsMargins(16, 0, 16, 16)
        v.setSpacing(0)

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(0, 12, 0, 12)
        self.lbl_migalha = QLabel(objectName="migalha")
        self.lbl_migalha.setTextFormat(Qt.RichText)
        self.lbl_contagem = QLabel(objectName="contagem")
        cabecalho.addWidget(self.lbl_migalha, 1)
        cabecalho.addWidget(self.lbl_contagem)
        v.addLayout(cabecalho)

        self.tabela = TabelaFaixas(self.modelo, self.filtro)
        self.tabela.selectionModel().selectionChanged.connect(self._ao_mudar_selecao)
        self.filtro.layoutChanged.connect(self._atualizar_contagem)
        self.filtro.rowsInserted.connect(self._atualizar_contagem)
        self.filtro.modelReset.connect(self._atualizar_contagem)
        v.addWidget(self.tabela, 1)

        divisor = QSplitter(Qt.Horizontal)
        divisor.setHandleWidth(1)
        divisor.setChildrenCollapsible(False)
        divisor.addWidget(self.painel)
        divisor.addWidget(direita)
        divisor.setStretchFactor(0, 0)
        divisor.setStretchFactor(1, 1)
        divisor.setSizes([380, 1060])
        self.divisor = divisor
        estado = self.config.value("divisor")
        if estado:
            divisor.restoreState(estado)
        return divisor

    def _criar_barra_status(self):
        barra = self.statusBar()
        barra.setSizeGripEnabled(False)
        self.lbl_status = QLabel()
        self.lbl_pendente = QLabel(objectName="destaqueStatus")
        self.lbl_pendente.setTextFormat(Qt.RichText)
        self.lbl_aviso = QLabel(objectName="destaqueStatus")
        self.lbl_aviso.setTextFormat(Qt.RichText)
        barra.addWidget(self.lbl_status)
        barra.addWidget(self.lbl_pendente)
        barra.addWidget(self.lbl_aviso, 1)
        formato_lbl = QLabel(f"MP3 · ID3v2.{VERSAO_ID3}")
        formato_lbl.setProperty("mono", True)
        barra.addPermanentWidget(formato_lbl)
        self._timer_aviso = QTimer(self, singleShot=True, interval=5000)
        self._timer_aviso.timeout.connect(lambda: self.lbl_aviso.setText(""))

    def _criar_atalhos(self):
        atalhos = [
            (["Ctrl+O"], self.abrir_pasta),
            (["Ctrl+S"], self.salvar),
            (["Ctrl+Z"], self.desfazer),
            (["Ctrl+Y", "Ctrl+Shift+Z"], self.refazer),
            (["Ctrl+F"], self._focar_busca),
            (["Escape"], self._ao_escape),
        ]
        for teclas, funcao in atalhos:
            acao = QAction(self)
            acao.setShortcuts([QKeySequence(t) for t in teclas])
            acao.setShortcutContext(Qt.WindowShortcut)
            acao.triggered.connect(lambda _=False, f=funcao: f())
            self.addAction(acao)

    # ------------------------------------------------------------------ tema
    def aplicar_tema(self):
        cores = tema.paleta(self.escuro)
        self.cores = cores
        app = QApplication.instance()
        tema.aplicar_paleta_qt(app, cores)
        app.setStyleSheet(tema.folha_de_estilo(cores, self.fonte_ui_nome, self.fonte_mono.family()))

        self.logo.setPixmap(pixmap("musica", cores["on_accent"], 15, espessura=2.4))
        self.btn_abrir.setIcon(icone("pasta", cores["text"]))
        self.btn_adicionar.setIcon(icone("arquivo+", cores["text"]))
        self.btn_desfazer.setIcon(icone("desfazer", cores["muted"]))
        self.btn_refazer.setIcon(icone("refazer", cores["muted"]))
        self.btn_tema.setIcon(icone("sol" if self.escuro else "lua", cores["muted"]))
        self.btn_salvar_topo.setIcon(icone("salvar", cores["on_accent"], espessura=2))
        self.acao_busca.setIcon(icone("busca", cores["muted"]))

        fonte_ui = QFont(self.fonte_ui_nome) if self.fonte_ui_nome else QFont()
        fonte_ui.setPixelSize(13)
        self.modelo.definir_aparencia(cores, fonte_ui, self.fonte_mono)
        self.painel.definir_aparencia(cores, self.fonte_mono)
        self.tela_vazia.definir_aparencia(cores)
        self.setWindowIcon(icone_app(cores["accent"], cores["on_accent"]))
        barra_de_titulo_escura(self, self.escuro)
        self._atualizar_migalha()
        self._atualizar_estado()

    def alternar_tema(self):
        self.escuro = not self.escuro
        self.config.setValue("tema_escuro", self.escuro)
        self.aplicar_tema()

    # ------------------------------------------------------------------ abrir arquivos
    def abrir_pasta(self):
        if not self._confirmar_pendencias():
            return
        inicial = self.config.value("ultima_pasta", str(Path.home()))
        pasta = QFileDialog.getExistingDirectory(self, "Abrir pasta de músicas", inicial)
        if pasta:
            self.carregar_caminhos([pasta], substituir=True)

    def adicionar_arquivos(self):
        inicial = self.config.value("ultima_pasta", str(Path.home()))
        arquivos, _ = QFileDialog.getOpenFileNames(self, "Adicionar arquivos", inicial, "Arquivos MP3 (*.mp3)")
        if arquivos:
            self.carregar_caminhos(arquivos, substituir=not self.modelo.faixas)

    def carregar_caminhos(self, caminhos, substituir):
        if self._carregador is not None:
            self.avisar("Aguarde: ainda estou lendo os arquivos anteriores.")
            return
        if substituir and not self._confirmar_pendencias():
            return

        pastas = [Path(c) for c in caminhos if Path(c).is_dir()]
        arquivos = expandir_caminhos(caminhos)
        if not arquivos:
            self.avisar("Nenhum arquivo MP3 encontrado.")
            return

        if pastas:
            self.config.setValue("ultima_pasta", str(pastas[0]))
            if substituir and len(pastas) == 1:
                self.pasta_atual = pastas[0]
                self._lembrar_recente(pastas[0])
        elif substituir:
            self.pasta_atual = None
            self.config.setValue("ultima_pasta", str(arquivos[0].parent))

        self._substituir_ao_carregar = substituir
        self.lbl_status.setText(f"Lendo {len(arquivos)} arquivos…")
        self._carregador = Carregador(arquivos, self)
        self._carregador.progresso.connect(
            lambda i, total: self.lbl_status.setText(f"Lendo arquivos… {i}/{total}"))
        self._carregador.concluido.connect(self._ao_carregar)
        self._carregador.finished.connect(self._carregador.deleteLater)
        self._carregador.start()

    def _ao_carregar(self, faixas, falhas):
        self._carregador = None
        if self._substituir_ao_carregar:
            self._ignorar_selecao = True
            self.modelo.definir(faixas)
            self.pilha_desfazer.clear()
            self.pilha_refazer.clear()
            self._ignorar_selecao = False
            self.painel.carregar([])
            novos = len(faixas)
        else:
            novos = self.modelo.adicionar(faixas)

        self.telas.setCurrentIndex(1 if self.modelo.faixas else 0)
        self._atualizar_migalha()
        self._atualizar_estado()
        if falhas:
            self.avisar(f"{len(falhas)} arquivo(s) não puderam ser lidos (corrompidos ou não são MP3).")
        elif not self._substituir_ao_carregar:
            self.avisar(f"{novos} arquivo(s) adicionado(s).", ok=True)

    # ------------------------------------------------------------------ seleção
    def _faixas_selecionadas(self):
        return [self.modelo.faixas[linha] for linha in self.tabela.linhas_selecionadas()]

    def _ao_mudar_selecao(self, *_):
        if self._ignorar_selecao:
            return
        if self.painel.tem_pendencias():
            if self._perguntar_salvar(len(self.painel.faixas)):
                self.salvar(recarregar_painel=False)
        self.painel.carregar(self._faixas_selecionadas())
        self._atualizar_estado()

    # ------------------------------------------------------------------ salvar / descartar
    def salvar(self, faixas=None, recarregar_painel=True):
        if not self.painel.tem_pendencias():
            return
        faixas = faixas if faixas is not None else self.painel.faixas
        if not faixas:
            return

        alteracoes, erros = validar_alteracoes(self.painel.alteracoes())
        if erros:
            self.painel.marcar_erros(erros)
            self.avisar(next(iter(erros.values())), erro=True)
            return

        capa = self.painel.capa_pendente
        caminhos = [f.caminho for f in faixas]

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            antes = self._registrar(caminhos, alteracoes.keys(), capa is not None)
            falhas = self._gravar(caminhos, alteracoes, capa)
        finally:
            QApplication.restoreOverrideCursor()

        self.pilha_desfazer.append(antes)
        self.pilha_refazer.clear()
        self._reler(caminhos, recarregar_painel)

        if falhas:
            nomes = ", ".join(Path(c).name for c in list(falhas)[:3])
            self.avisar(f"{len(falhas)} arquivo(s) não foram salvos: {nomes}…", erro=True)
        else:
            n = len(caminhos)
            self.avisar("1 arquivo salvo" if n == 1 else f"{n} arquivos salvos", ok=True)

    def _gravar(self, caminhos, alteracoes, capa):
        """Grava tags e capa. Devolve {caminho: erro} dos que falharam."""
        falhas = {}
        for caminho in caminhos:
            try:
                if alteracoes:
                    salvar(caminho, alteracoes)
                if capa and capa[0] == "definir":
                    definir_capa(caminho, capa[1], capa[2])
                elif capa and capa[0] == "remover":
                    remover_capa(caminho)
            except Exception as erro:
                falhas[caminho] = str(erro)
        return falhas

    def descartar(self):
        self.painel.carregar(self._faixas_selecionadas())

    def _reler(self, caminhos, recarregar_painel=True):
        """Relê os arquivos do disco e atualiza a tabela (e o painel)."""
        faixas, _ = carregar_varios(caminhos)
        # a tabela pode reordenar/filtrar linhas aqui; isso não deve disparar a pergunta de "salvar?"
        self._ignorar_selecao = True
        try:
            self.modelo.atualizar(faixas)
        finally:
            self._ignorar_selecao = False
        if recarregar_painel:
            self.painel.carregar(self._faixas_selecionadas())
        self._atualizar_estado()

    # ------------------------------------------------------------------ desfazer / refazer
    def _registrar(self, caminhos, campos, com_capa):
        """Fotografa o estado atual (só dos campos envolvidos) para poder desfazer."""
        campos = list(campos)
        registros = []
        for caminho in caminhos:
            faixa = carregar(caminho)
            if faixa is None:
                continue
            tags = {campo: faixa.tags[campo] for campo in campos}
            capa = ler_capa(caminho) if com_capa else SEM_CAPA_NO_REGISTRO
            registros.append((caminho, tags, capa))
        return registros

    def _restaurar(self, registros):
        for caminho, tags, capa in registros:
            try:
                if tags:
                    salvar(caminho, tags)
                if capa is not SEM_CAPA_NO_REGISTRO:
                    if capa is None:
                        remover_capa(caminho)
                    else:
                        definir_capa(caminho, capa[0], capa[1])
            except Exception:
                pass

    def _trocar_estado(self, origem, destino, mensagem):
        if not origem:
            return
        if self.painel.tem_pendencias():
            self.painel.carregar(self.painel.faixas)   # descarta edições em andamento
        registros = origem.pop()
        caminhos = [r[0] for r in registros]
        campos = registros[0][1].keys() if registros else []
        com_capa = bool(registros) and registros[0][2] is not SEM_CAPA_NO_REGISTRO
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            destino.append(self._registrar(caminhos, campos, com_capa))
            self._restaurar(registros)
        finally:
            QApplication.restoreOverrideCursor()
        self._reler(caminhos)
        self.avisar(mensagem, ok=True)

    def desfazer(self):
        self._trocar_estado(self.pilha_desfazer, self.pilha_refazer, "Alteração desfeita")

    def refazer(self):
        self._trocar_estado(self.pilha_refazer, self.pilha_desfazer, "Alteração refeita")

    # ------------------------------------------------------------------ busca e estado
    def _ao_buscar(self, texto):
        self.filtro.definir_texto(texto)
        self._atualizar_contagem()

    def _focar_busca(self):
        self.busca.setFocus()
        self.busca.selectAll()

    def _ao_escape(self):
        if self.busca.hasFocus() and self.busca.text():
            self.busca.clear()
        elif self.painel.tem_pendencias():
            self.descartar()

    def _ao_alterar_painel(self):
        pendente = self.painel.tem_pendencias()
        self.modelo.marcar_pendentes(f.caminho for f in self.painel.faixas if pendente)
        self._atualizar_estado()

    def _atualizar_contagem(self, *_):
        self.lbl_contagem.setText(f"Mostrando {self.filtro.rowCount()} de {self.modelo.rowCount()}")

    def _atualizar_migalha(self):
        seta = f'<span style="color:{self.cores["faint"]}">&nbsp;›&nbsp;</span>'
        if self.pasta_atual:
            partes = self.pasta_atual.parts[-3:]
            texto = seta.join(partes[:-1] + (f'<span style="color:{self.cores["text"]}">{partes[-1]}</span>',))
        else:
            texto = "Arquivos avulsos"
        self.lbl_migalha.setText(texto)
        self.lbl_migalha.setToolTip(str(self.pasta_atual or ""))

    def _atualizar_estado(self):
        if not hasattr(self, "lbl_status") or self._carregador is not None:
            return
        total = len(self.modelo.faixas)
        n_sel = len(self.painel.faixas)
        self.lbl_status.setText(
            f"{total} {'arquivo' if total == 1 else 'arquivos'} · "
            f"{n_sel} {'selecionado' if n_sel == 1 else 'selecionados'}")

        pendente = self.painel.tem_pendencias()
        if pendente:
            q = self.painel.quantidade_pendente()
            ponto = f'<span style="color:{self.cores["accent"]}">●</span>'
            self.lbl_pendente.setText(f"{ponto} {q} {'campo alterado' if q == 1 else 'campos alterados'} · não salvo")
            self.lbl_aviso.setText("")
        else:
            self.lbl_pendente.setText("")
        self.lbl_pendente.setVisible(pendente)

        self.btn_salvar_topo.setEnabled(pendente)
        self.btn_salvar_topo.setText(f"Salvar · {n_sel}" if pendente and n_sel > 1 else "Salvar")
        self.btn_desfazer.setEnabled(bool(self.pilha_desfazer))
        self.btn_refazer.setEnabled(bool(self.pilha_refazer))
        self._atualizar_contagem()

    def avisar(self, texto, ok=False, erro=False):
        if ok:
            simbolo = f'<span style="color:{self.cores["accent"]}">✓</span> '
        elif erro:
            simbolo = f'<span style="color:{self.cores["erro"]}">!</span> '
        else:
            simbolo = ""
        self.lbl_aviso.setText(simbolo + texto)
        self._timer_aviso.start()

    # ------------------------------------------------------------------ confirmações
    def _perguntar_salvar(self, quantidade):
        """True = salvar, False = descartar."""
        caixa = QMessageBox(self)
        caixa.setIcon(QMessageBox.Question)
        caixa.setWindowTitle("Alterações não salvas")
        alvo = "1 arquivo" if quantidade == 1 else f"{quantidade} arquivos"
        caixa.setText(f"Você tem alterações não salvas em {alvo}.")
        caixa.setInformativeText("Deseja salvar antes de continuar?")
        caixa.setStandardButtons(QMessageBox.Save | QMessageBox.Discard)
        caixa.button(QMessageBox.Save).setText("Salvar")
        caixa.button(QMessageBox.Discard).setText("Descartar")
        caixa.setDefaultButton(QMessageBox.Save)
        caixa.exec()
        return caixa.clickedButton() == caixa.button(QMessageBox.Save)

    def _confirmar_pendencias(self):
        """Pergunta se deve salvar antes de trocar de pasta/fechar. Sempre deixa continuar."""
        if self.painel.tem_pendencias():
            if self._perguntar_salvar(len(self.painel.faixas)):
                self.salvar()
            else:
                self.painel.carregar(self.painel.faixas)
        return True

    # ------------------------------------------------------------------ recentes
    def _recentes(self):
        valor = self.config.value("recentes", [])
        if isinstance(valor, str):
            valor = [valor]
        return list(valor or [])

    def _lembrar_recente(self, pasta):
        lista = [str(pasta)] + [p for p in self._recentes() if p != str(pasta)]
        lista = lista[:MAX_RECENTES]
        self.config.setValue("recentes", lista)
        self.tela_vazia.definir_recentes(lista)

    # ------------------------------------------------------------------ arrastar e soltar
    def dragEnterEvent(self, evento):
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()
            self.tela_vazia.destacar(True)

    def dragLeaveEvent(self, evento):
        self.tela_vazia.destacar(False)

    def dropEvent(self, evento):
        self.tela_vazia.destacar(False)
        caminhos = [url.toLocalFile() for url in evento.mimeData().urls() if url.isLocalFile()]
        if caminhos:
            evento.acceptProposedAction()
            self.carregar_caminhos(caminhos, substituir=not self.modelo.faixas)

    # ------------------------------------------------------------------ fechar
    def closeEvent(self, evento):
        self._confirmar_pendencias()
        self.config.setValue("geometria", self.saveGeometry())
        self.config.setValue("divisor", self.divisor.saveState())
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
    fonte_ui, fonte_mono = tema.carregar_fontes()
    if fonte_ui:
        fonte = QFont(fonte_ui)
        fonte.setPixelSize(13)
        app.setFont(fonte)

    janela = JanelaPrincipal(fonte_ui, fonte_mono)
    janela.show()

    # arquivos/pastas passados na linha de comando (ou arrastados sobre o .exe)
    if len(sys.argv) > 1:
        janela.carregar_caminhos(sys.argv[1:], substituir=True)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
