"""Janela de configurações. Cada mudança aparece na hora (prévia); Cancelar desfaz."""

from copy import deepcopy

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QRadioButton, QSizePolicy, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from tagger.gui.config import DENSIDADES, PADROES
from tagger.gui.tema import ACENTO_DO_TEMA, ACENTOS, acento_efetivo, familias_instaladas, temas_claros, temas_escuros

AUTOMATICA = "Automática"


def _rotulo(texto, papel):
    lbl = QLabel(texto)
    lbl.setProperty("papel", papel)
    lbl.setWordWrap(True)
    return lbl


def _bolinha(cor, lado=12):
    pm = QPixmap(lado * 2, lado * 2)
    pm.fill(Qt.transparent)
    pintor = QPainter(pm)
    pintor.setRenderHint(QPainter.Antialiasing)
    pintor.setPen(Qt.NoPen)
    pintor.setBrush(QColor(cor))
    pintor.drawEllipse(0, 0, lado * 2, lado * 2)
    pintor.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


def _formulario():
    form = QFormLayout()
    form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    form.setHorizontalSpacing(24)
    form.setVerticalSpacing(12)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
    return form


class DialogoConfiguracoes(QDialog):
    mudou = Signal(dict)      # prévia ao vivo: a janela principal aplica na hora

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurações")
        self.setMinimumSize(620, 700)
        self.original = deepcopy(config)
        self.config = deepcopy(config)
        self._preenchendo = False

        abas = QTabWidget()
        abas.addTab(self._aba_aparencia(), "Aparência")
        abas.addTab(self._aba_comportamento(), "Comportamento")
        abas.addTab(self._aba_tags(), "Tags")

        btn_padroes = QPushButton("Restaurar padrões")
        btn_padroes.setProperty("tipo", "fantasma")
        btn_padroes.clicked.connect(self._restaurar_padroes)
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        btn_ok = QPushButton("OK")
        btn_ok.setProperty("tipo", "primario")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)

        rodape = QHBoxLayout()
        rodape.addWidget(btn_padroes)
        rodape.addStretch()
        rodape.addWidget(btn_cancelar)
        rodape.addWidget(btn_ok)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)
        layout.addWidget(abas, 1)
        layout.addLayout(rodape)

        self._preencher()

    # ------------------------------------------------------------------ abas
    def _aba_aparencia(self):
        w = QWidget()
        form = _formulario()
        form.setContentsMargins(20, 20, 20, 20)

        self.grupo_modo = QButtonGroup(self)
        self.rb_escuro = QRadioButton("Escuro")
        self.rb_claro = QRadioButton("Claro")
        self.grupo_modo.addButton(self.rb_escuro)
        self.grupo_modo.addButton(self.rb_claro)
        self.rb_escuro.toggled.connect(lambda on: self._definir("usar_escuro", on))
        modo = QHBoxLayout()
        modo.addWidget(self.rb_escuro)
        modo.addWidget(self.rb_claro)
        modo.addStretch()
        form.addRow("Modo", modo)

        self.cb_tema_escuro = QComboBox()
        for chave, nome in temas_escuros().items():
            self.cb_tema_escuro.addItem(nome, chave)
        self.cb_tema_escuro.currentIndexChanged.connect(
            lambda: self._definir("tema_escuro", self.cb_tema_escuro.currentData()))
        form.addRow("Tema escuro", self.cb_tema_escuro)

        self.cb_tema_claro = QComboBox()
        for chave, nome in temas_claros().items():
            self.cb_tema_claro.addItem(nome, chave)
        self.cb_tema_claro.currentIndexChanged.connect(
            lambda: self._definir("tema_claro", self.cb_tema_claro.currentData()))
        form.addRow("Tema claro", self.cb_tema_claro)

        # linha 1: bolinhas de cor | linha 2: "Do tema" e "Personalizada…"
        linha_cores = QHBoxLayout()
        linha_cores.setSpacing(8)
        self.amostras = {}
        for nome, cor in ACENTOS:
            botao = QPushButton()
            botao.setProperty("tipo", "amostra")
            botao.setToolTip(nome)
            botao.setAccessibleName(f"Cor de destaque {nome}")
            botao.setCursor(Qt.PointingHandCursor)
            botao.clicked.connect(lambda _=False, c=cor: self._definir("acento", c))
            self.amostras[cor] = botao
            linha_cores.addWidget(botao)
        linha_cores.addStretch()

        linha_botoes = QHBoxLayout()
        linha_botoes.setSpacing(8)
        self.btn_do_tema = QPushButton("Do tema")
        self.btn_do_tema.setToolTip("Usa a cor de destaque de cada tema (ex.: roxo no Dracula)")
        self.btn_do_tema.clicked.connect(lambda: self._definir("acento", ACENTO_DO_TEMA))
        self.btn_cor_livre = QPushButton("Personalizada…")
        self.btn_cor_livre.setToolTip("Escolher qualquer cor")
        self.btn_cor_livre.clicked.connect(self._escolher_cor)
        for botao in (self.btn_do_tema, self.btn_cor_livre):
            botao.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)   # nunca espreme o texto
            linha_botoes.addWidget(botao)
        linha_botoes.addStretch()

        acentos = QVBoxLayout()
        acentos.setSpacing(10)
        acentos.addLayout(linha_cores)
        acentos.addLayout(linha_botoes)
        form.addRow("Cor de destaque", acentos)

        familias = familias_instaladas()
        self.cb_fonte = QComboBox()
        self.cb_fonte_mono = QComboBox()
        for combo, chave in ((self.cb_fonte, "fonte"), (self.cb_fonte_mono, "fonte_mono")):
            combo.addItem(AUTOMATICA, "")
            for familia in familias:
                combo.addItem(familia, familia)
            combo.setMaxVisibleItems(16)
            combo.currentIndexChanged.connect(lambda _i, c=combo, k=chave: self._definir(k, c.currentData()))
        form.addRow("Fonte da interface", self.cb_fonte)
        form.addRow("Fonte dos números", self.cb_fonte_mono)

        self.sp_tamanho = QSpinBox()
        self.sp_tamanho.setRange(11, 18)
        self.sp_tamanho.setSuffix(" px")
        self.sp_tamanho.valueChanged.connect(lambda v: self._definir("tamanho_fonte", v))
        form.addRow("Tamanho da fonte", self.sp_tamanho)

        self.cb_densidade = QComboBox()
        for chave, nome in DENSIDADES.items():
            self.cb_densidade.addItem(nome, chave)
        self.cb_densidade.currentIndexChanged.connect(
            lambda: self._definir("densidade", self.cb_densidade.currentData()))
        form.addRow("Altura das linhas", self.cb_densidade)

        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addLayout(form)
        v.addStretch()
        return w

    def _aba_comportamento(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        self.ck_subpastas = QCheckBox("Incluir subpastas ao abrir uma pasta")
        self.ck_subpastas.toggled.connect(lambda on: self._definir("subpastas", on))
        self.ck_reabrir = QCheckBox("Reabrir a última pasta ao iniciar o Tagger")
        self.ck_reabrir.toggled.connect(lambda on: self._definir("reabrir_ultima", on))
        self.ck_total = QCheckBox("Incluir o total ao numerar faixas (ex.: 3/12 em vez de 3)")
        self.ck_total.toggled.connect(lambda on: self._definir("numerar_com_total", on))

        for item in (self.ck_subpastas, self.ck_reabrir, self.ck_total):
            v.addWidget(item)
        v.addSpacing(8)
        v.addWidget(_rotulo(
            "Alterações ficam pendentes (com o ponto verde) até você clicar em Salvar, inclusive "
            "as feitas por Desfazer, Numerar faixas, Colar tags e edição direto na tabela.", "ajuda"))
        v.addStretch()
        return w

    def _aba_tags(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(10)

        v.addWidget(_rotulo("Versão do ID3 ao salvar (só MP3)", "secao"))
        v.addWidget(_rotulo("FLAC, Ogg e M4A usam o formato de tags próprio deles; as opções de ID3 "
                            "não mudam nada nesses arquivos.", "ajuda"))
        self.grupo_id3 = QButtonGroup(self)
        self.rb_v23 = QRadioButton("ID3v2.3 — mais compatível (Windows Explorer, carros, players antigos)")
        self.rb_v24 = QRadioButton("ID3v2.4 — mais recente")
        self.grupo_id3.addButton(self.rb_v23)
        self.grupo_id3.addButton(self.rb_v24)
        self.rb_v23.toggled.connect(lambda on: self._definir("versao_id3", 3 if on else 4))
        v.addWidget(self.rb_v23)
        v.addWidget(self.rb_v24)

        v.addSpacing(12)
        v.addWidget(_rotulo("Ao salvar", "secao"))
        self.ck_multivalor = QCheckBox("Gravar \"A; B\" como vários valores (artista, gênero, compositor…)")
        self.ck_multivalor.setToolTip("Players modernos mostram cada artista/gênero separado. "
                                      "Desligado, \"A; B\" é gravado como um texto só. Vale para todos os formatos.")
        self.ck_multivalor.toggled.connect(lambda on: self._definir("multivalor", on))
        self.ck_id3v1 = QCheckBox("Remover a tag ID3v1 antiga (dos anos 90) dos MP3 salvos")
        self.ck_id3v1.setToolTip("Só existe em MP3. FLAC, Ogg e M4A não são afetados.")
        self.ck_id3v1.toggled.connect(lambda on: self._definir("remover_id3v1", on))
        v.addWidget(self.ck_multivalor)
        v.addWidget(self.ck_id3v1)

        v.addSpacing(12)
        v.addWidget(_rotulo("Capa", "secao"))
        linha_capa = QHBoxLayout()
        self.ck_otimizar = QCheckBox("Reduzir capas grandes ao inserir, para no máximo")
        self.ck_otimizar.toggled.connect(lambda on: self._definir("otimizar_capa", on))
        self.ck_otimizar.toggled.connect(lambda on: self.sp_lado_capa.setEnabled(on))
        self.sp_lado_capa = QSpinBox()
        self.sp_lado_capa.setRange(300, 3000)
        self.sp_lado_capa.setSingleStep(100)
        self.sp_lado_capa.setSuffix(" px")
        self.sp_lado_capa.valueChanged.connect(lambda n: self._definir("lado_max_capa", n))
        linha_capa.addWidget(self.ck_otimizar)
        linha_capa.addWidget(self.sp_lado_capa)
        linha_capa.addStretch()
        v.addLayout(linha_capa)
        v.addWidget(_rotulo("Imagens maiores que isso (ou com mais de 500 KB) viram JPEG. "
                            "Uma capa de 5 MB em cada faixa pesa no álbum inteiro.", "ajuda"))

        v.addSpacing(12)
        v.addWidget(_rotulo("Gêneros sugeridos no autocompletar", "secao"))
        v.addWidget(_rotulo("Um por linha. Os gêneros que já estão nos seus arquivos também aparecem.", "ajuda"))
        self.tx_generos = QPlainTextEdit()
        self.tx_generos.textChanged.connect(self._ao_mudar_generos)
        v.addWidget(self.tx_generos, 1)
        return w

    # ------------------------------------------------------------------ estado
    def _preencher(self):
        self._preenchendo = True
        c = self.config
        (self.rb_escuro if c["usar_escuro"] else self.rb_claro).setChecked(True)
        self._selecionar(self.cb_tema_escuro, c["tema_escuro"])
        self._selecionar(self.cb_tema_claro, c["tema_claro"])
        self._selecionar(self.cb_fonte, c["fonte"])
        self._selecionar(self.cb_fonte_mono, c["fonte_mono"])
        self.sp_tamanho.setValue(int(c["tamanho_fonte"]))
        self._selecionar(self.cb_densidade, c["densidade"])
        self.ck_subpastas.setChecked(c["subpastas"])
        self.ck_reabrir.setChecked(c["reabrir_ultima"])
        self.ck_total.setChecked(c["numerar_com_total"])
        (self.rb_v23 if int(c["versao_id3"]) == 3 else self.rb_v24).setChecked(True)
        self.ck_multivalor.setChecked(c["multivalor"])
        self.ck_id3v1.setChecked(c["remover_id3v1"])
        self.ck_otimizar.setChecked(c["otimizar_capa"])
        self.sp_lado_capa.setValue(int(c["lado_max_capa"]))
        self.sp_lado_capa.setEnabled(c["otimizar_capa"])
        self.tx_generos.setPlainText("\n".join(c["generos"]))
        self._atualizar_amostras()
        self._preenchendo = False

    @staticmethod
    def _selecionar(combo, dado):
        indice = combo.findData(dado)
        combo.setCurrentIndex(max(0, indice))

    def _tema_atual(self):
        return self.config["tema_escuro"] if self.config["usar_escuro"] else self.config["tema_claro"]

    def _atualizar_amostras(self):
        do_tema = self.config["acento"] == ACENTO_DO_TEMA
        self.btn_do_tema.setIcon(_bolinha(acento_efetivo(self._tema_atual(), ACENTO_DO_TEMA)))
        self.btn_do_tema.setStyleSheet("border: 2px solid palette(window-text);" if do_tema else "")
        atual = "" if do_tema else QColor(self.config["acento"]).name()
        for cor, botao in self.amostras.items():
            borda = "palette(window-text)" if cor == atual else "transparent"
            botao.setStyleSheet(f"background: {cor}; border: 2px solid {borda};")
        personalizada = bool(atual) and atual not in self.amostras
        self.btn_cor_livre.setIcon(_bolinha(atual) if personalizada else QIcon())
        self.btn_cor_livre.setStyleSheet("border: 2px solid palette(window-text);" if personalizada else "")

    def _definir(self, chave, valor):
        if self._preenchendo or self.config.get(chave) == valor:
            return
        self.config[chave] = valor
        if chave in ("acento", "usar_escuro", "tema_escuro", "tema_claro"):
            self._atualizar_amostras()
        self.mudou.emit(deepcopy(self.config))

    def _ao_mudar_generos(self):
        linhas = [l.strip() for l in self.tx_generos.toPlainText().splitlines()]
        self._definir("generos", [l for l in linhas if l])

    def _escolher_cor(self):
        inicial = acento_efetivo(self._tema_atual(), self.config["acento"])
        cor = QColorDialog.getColor(QColor(inicial), self, "Cor de destaque")
        if cor.isValid():
            self._definir("acento", cor.name())

    def _restaurar_padroes(self):
        padroes_do_usuario = {k: v for k, v in self.config.items() if k.startswith(("padrao_", "recentes_"))}   # não aparecem aqui
        self.config = deepcopy(PADROES) | padroes_do_usuario
        self._preencher()
        self.mudou.emit(deepcopy(self.config))

    def reject(self):
        self.mudou.emit(deepcopy(self.original))    # volta tudo como estava
        super().reject()