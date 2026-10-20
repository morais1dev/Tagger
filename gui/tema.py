"""
Tema visual do Tagger: temas de cor, cor de destaque, fontes, tamanhos e a folha de estilo (QSS).

Para criar um tema novo, basta acrescentar uma entrada em TEMAS.
"""

from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFontDatabase, QPalette

from gui.icones import arquivo_svg

TEMAS = {
    "grafite": {
        "nome": "Grafite", "escuro": True,
        "bg": "#0f1012", "surface": "#16171a", "surface2": "#1c1e22", "field": "#111214",
        "line": "#25282d", "line2": "#33373d", "text": "#e8e9eb", "muted": "#9ba0a8",
        "faint": "#5d626b", "hover": "#1f2125", "erro": "#ff6b6b",
    },
    "meia-noite": {
        "nome": "Meia-noite", "escuro": True,
        "bg": "#0b1020", "surface": "#11182b", "surface2": "#172036", "field": "#0d1426",
        "line": "#1f2a44", "line2": "#2b3858", "text": "#e6eaf3", "muted": "#98a3bb",
        "faint": "#56617a", "hover": "#1a2440", "erro": "#ff6b6b",
    },
    "alto-contraste": {
        "nome": "Alto contraste", "escuro": True,
        "bg": "#000000", "surface": "#0a0a0a", "surface2": "#141414", "field": "#000000",
        "line": "#3a3a3a", "line2": "#5c5c5c", "text": "#ffffff", "muted": "#cfcfcf",
        "faint": "#8a8a8a", "hover": "#1c1c1c", "erro": "#ff5c5c",
    },
    "claro": {
        "nome": "Claro", "escuro": False,
        "bg": "#eceef1", "surface": "#ffffff", "surface2": "#f5f6f8", "field": "#ffffff",
        "line": "#e2e5e9", "line2": "#cfd4da", "text": "#14161a", "muted": "#59606a",
        "faint": "#848a93", "hover": "#f1f3f5", "erro": "#d93838",
    },
    "sepia": {
        "nome": "Sépia", "escuro": False,
        "bg": "#ece4d6", "surface": "#faf6ef", "surface2": "#f3ece0", "field": "#fffdf8",
        "line": "#e2d8c6", "line2": "#d2c5ae", "text": "#2b2419", "muted": "#685d4c",
        "faint": "#8a7e6a", "hover": "#f0e8da", "erro": "#c0392b",
    },
}

ACENTOS = [
    ("Menta", "#3ddc97"), ("Azul", "#6b9bff"), ("Laranja", "#ff9a4d"),
    ("Lilás", "#c58bff"), ("Rosa", "#ff6b9d"), ("Amarelo", "#f5c542"),
]

# Fontes preferidas, na ordem, quando a configuração está em "Automática".
# Dica: coloque Geist-*.ttf e GeistMono-*.ttf em gui/fontes/ para usar a fonte do mockup.
FONTES_UI = ["Geist", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans"]
FONTES_MONO = ["Geist Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono"]

PASTA_FONTES = Path(__file__).parent / "fontes"

ALTURA_LINHA = {"compacta": 21, "confortavel": 29, "espacosa": 37}   # somado ao tamanho da fonte


# ---------------------------------------------------------------------------- cores
def _rgba(hex_cor, alfa):
    c = QColor(hex_cor)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alfa})"


def _texto_sobre(hex_cor):
    """Preto ou branco, o que tiver mais contraste com a cor de destaque."""
    c = QColor(hex_cor)

    def canal(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    luminancia = 0.2126 * canal(c.red()) + 0.7152 * canal(c.green()) + 0.0722 * canal(c.blue())
    return "#0b0d0c" if luminancia > 0.28 else "#ffffff"


def paleta(tema_id, acento):
    """Dicionário com todas as cores do tema + cor de destaque."""
    base = TEMAS.get(tema_id) or TEMAS["grafite"]
    cores = {k: v for k, v in base.items() if k != "nome"}
    acento = QColor(acento).name() if QColor(acento).isValid() else ACENTOS[0][1]
    cores.update(
        accent=acento,
        on_accent=_texto_sobre(acento),
        accent_hover=QColor(acento).lighter(110).name(),
        sel=_rgba(acento, 40 if base["escuro"] else 46),
        sel_line=_rgba(acento, 115),
        veu=_rgba(base["surface"], 225),     # fundo do aviso "Solte para adicionar"
        tema=tema_id,
    )
    return cores


def temas_escuros():
    return {k: v["nome"] for k, v in TEMAS.items() if v["escuro"]}


def temas_claros():
    return {k: v["nome"] for k, v in TEMAS.items() if not v["escuro"]}


# ---------------------------------------------------------------------------- fontes
def registrar_fontes():
    """Registra fontes da pasta gui/fontes (se existir)."""
    if PASTA_FONTES.is_dir():
        for arquivo in PASTA_FONTES.iterdir():
            if arquivo.suffix.lower() in (".ttf", ".otf"):
                QFontDatabase.addApplicationFont(str(arquivo))


def familias_instaladas():
    return sorted(set(QFontDatabase.families()), key=str.casefold)


def escolher_fontes(preferida_ui="", preferida_mono=""):
    """Família da interface e dos números. Vazio = automática (primeira instalada da lista)."""
    instaladas = set(QFontDatabase.families())
    ui = preferida_ui if preferida_ui in instaladas else next((f for f in FONTES_UI if f in instaladas), "")
    mono = preferida_mono if preferida_mono in instaladas else next(
        (f for f in FONTES_MONO if f in instaladas), "monospace")
    return ui, mono


def altura_linha(tamanho_fonte, densidade):
    return tamanho_fonte + ALTURA_LINHA.get(densidade, ALTURA_LINHA["compacta"])


def altura_cabecalho(tamanho_fonte):
    """O cabeçalho da tabela não acompanha a densidade das linhas."""
    return tamanho_fonte + 19


def altura_botao(tamanho_fonte):
    """Altura de todos os botões (os de ícone são quadrados com esse lado)."""
    return max(32, tamanho_fonte + 17)


# ---------------------------------------------------------------------------- Qt
def aplicar_paleta_qt(app, cores):
    """Cores que o QSS não alcança (placeholder, caixas de seleção, menus nativos)."""
    p = app.palette()
    p.setColor(QPalette.Window, QColor(cores["bg"]))
    p.setColor(QPalette.WindowText, QColor(cores["text"]))
    p.setColor(QPalette.Base, QColor(cores["field"]))
    p.setColor(QPalette.AlternateBase, QColor(cores["surface2"]))
    p.setColor(QPalette.Text, QColor(cores["text"]))
    p.setColor(QPalette.Button, QColor(cores["surface2"]))
    p.setColor(QPalette.ButtonText, QColor(cores["text"]))
    p.setColor(QPalette.Highlight, QColor(cores["accent"]))
    p.setColor(QPalette.HighlightedText, QColor(cores["on_accent"]))
    p.setColor(QPalette.PlaceholderText, QColor(cores["muted"]))
    p.setColor(QPalette.ToolTipBase, QColor(cores["surface2"]))
    p.setColor(QPalette.ToolTipText, QColor(cores["text"]))
    app.setPalette(p)


_QSS = Template("""
* { font-family: "$fonte"; font-size: ${fs}px; color: $text; }
*[mono="true"] { font-family: "$mono"; }
QMainWindow, #raiz, QDialog { background: $bg; }
/* menus e dicas têm fundo translúcido (ver FiltroJanelas em app.py), então o radius não deixa cantos quadrados */
QToolTip { background: $surface2; color: $text; border: 1px solid $line2; padding: 4px 8px; border-radius: 6px; }

/* ---------- Barra superior ---------- */
#barraTopo { background: $surface; border-bottom: 1px solid $line; }
#logo { background: $accent; border-radius: 7px; }
#nomeApp { font-size: ${fs_xl}px; font-weight: 600; }
#sep { background: $line; }

/* ---------- Botões ---------- */
QPushButton {
    background: $surface2; border: 1px solid $line; border-radius: 8px;
    padding: 0 12px; min-height: ${h_botao}px; font-weight: 500;
}
QPushButton:hover { border-color: $line2; background: $hover; }
QPushButton:focus { border-color: $accent; }
QPushButton:pressed { background: $surface2; }
QPushButton:disabled { color: $faint; }
QPushButton[tipo="primario"] { background: $accent; color: $on_accent; border: 1px solid $accent; }
QPushButton[tipo="primario"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[tipo="primario"]:focus { border-color: $text; }
QPushButton[tipo="primario"]:disabled { background: $surface2; color: $faint; border-color: $line; }
QPushButton[tipo="fantasma"] { background: transparent; border-color: transparent; color: $muted; }
QPushButton[tipo="fantasma"]:hover { background: $hover; color: $text; }
QPushButton[tipo="fantasma"]:focus { border-color: $accent; }
QPushButton[tipo="fantasma"]:disabled { color: $faint; }
QPushButton[tipo="amostra"] { border-radius: 13px; padding: 0; min-height: 26px; min-width: 26px; max-width: 26px; max-height: 26px; }
QPushButton::menu-indicator { image: none; width: 0; }

/* ---------- Campos ---------- */
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: $field; border: 1px solid $line; border-radius: 8px;
    padding: 0 10px; min-height: ${h_campo}px; selection-background-color: $sel_line; selection-color: $text;
}
QPlainTextEdit { padding: 6px 6px; }
QLineEdit:hover, QPlainTextEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: $line2; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: $accent; }
QLineEdit[erro="true"], QPlainTextEdit[erro="true"] { border-color: $erro; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: url("$svg_baixo"); width: 12px; height: 12px; }
QComboBox::down-arrow:disabled, QSpinBox::up-arrow:disabled, QSpinBox::down-arrow:disabled { image: url("$svg_baixo_faint"); }
QComboBox QAbstractItemView { background: $surface2; border: 1px solid $line2; selection-background-color: $sel; selection-color: $text; outline: 0; }
QSpinBox { padding-right: 22px; }
QSpinBox::up-button, QSpinBox::down-button { border: none; width: 20px; subcontrol-origin: border; }
QSpinBox::up-button { subcontrol-position: top right; }
QSpinBox::down-button { subcontrol-position: bottom right; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: $hover; border-radius: 4px; }
QSpinBox::up-arrow { image: url("$svg_cima"); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url("$svg_baixo"); width: 10px; height: 10px; }
#busca { max-width: 300px; }
#busca:focus { border-color: $sel_line; }

/* ---------- Caixas de seleção ---------- */
QCheckBox, QRadioButton { spacing: 8px; }
QCheckBox::indicator, QRadioButton::indicator {
    width: 14px; height: 14px; border: 1px solid $line2; background: $field;
}
QCheckBox::indicator { border-radius: 4px; }
QRadioButton::indicator { border-radius: 8px; }
QCheckBox::indicator:hover, QRadioButton::indicator:hover { border-color: $accent; }
QCheckBox::indicator:focus, QRadioButton::indicator:focus { border: 2px solid $accent; width: 12px; height: 12px; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent; image: url("$svg_check"); }
QRadioButton::indicator:checked {
    border-color: $accent;
    background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.5, fx: 0.5, fy: 0.5,
                                stop: 0 $on_accent, stop: 0.38 $on_accent, stop: 0.48 $accent, stop: 1 $accent);
}
QCheckBox::indicator:checked:focus, QRadioButton::indicator:checked:focus { border-color: $text; }
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled { background: $surface2; border-color: $line; }

/* ---------- Tabela ---------- */
QTableView {
    background: $surface; border: 1px solid $line; border-radius: 10px;
    gridline-color: transparent; outline: 0;
    selection-background-color: $sel; selection-color: $text;
}
QTableView::item { border-bottom: 1px solid $line; padding: 0 6px; }
/* o hover é pintado na linha inteira pelo DelegadoTabela */
QTableView::item:selected { background: $sel; color: $text; }
QTableView QLineEdit { border-radius: 0; min-height: 0; padding: 0 5px; border: 1px solid $accent; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: $surface2; color: $muted; border: none; border-bottom: 1px solid $line;
    padding: 0 6px; font-size: ${fs_s}px; font-weight: 500;
}
/* o Qt não recorta os filhos da tabela: arredonda o cabeçalho para não sair pelos cantos */
QHeaderView::section:first { border-top-left-radius: 9px; }
QHeaderView::section:last { border-top-right-radius: 9px; }
QHeaderView::section:only-one { border-top-left-radius: 9px; border-top-right-radius: 9px; }
QHeaderView::section:hover { color: $text; }
/* seta da coluna ordenada: crescente aponta para cima */
QHeaderView::up-arrow { image: url("$svg_cima_accent"); width: 10px; height: 10px; subcontrol-position: center right; right: 6px; }
QHeaderView::down-arrow { image: url("$svg_baixo_accent"); width: 10px; height: 10px; subcontrol-position: center right; right: 6px; }
QTableCornerButton::section { background: $surface2; border: none; }
#migalha, #contagem { color: $muted; font-size: ${fs_s}px; }

/* ---------- Painel editor ---------- */
#painel, #corpoPainel, #viewportPainel { background: $surface; }
#painelTopo { background: $surface; border-bottom: 1px solid $line; }
#painelRodape { background: $surface; border-top: 1px solid $line; }
#tituloPainel { font-size: ${fs_l}px; font-weight: 600; }
QLabel[papel="sub"] { color: $muted; font-size: ${fs_s}px; }
QLabel[papel="rotulo"] { color: $muted; font-size: ${fs_s}px; font-weight: 500; }
QLabel[papel="rotulo"][alterado="true"] { color: $text; }
QLabel[papel="info"] { color: $muted; font-size: ${fs_xs}px; }
#capa { background: $surface2; border: 2px solid $line; border-radius: 10px; color: $muted; font-size: ${fs_s}px; }
#capa[arrastando="true"] { border: 2px dashed $accent; }
QLabel[papel="erroCampo"] { color: $erro; font-size: ${fs_xs}px; }
#painelVazioTitulo { font-weight: 500; }
#painelVazioTexto { color: $muted; font-size: ${fs_s}px; }

/* ---------- Tela vazia ---------- */
#zonaDrop { background: $surface; border: 2px dashed $line2; border-radius: 16px; }
#zonaDrop[ativo="true"] { border-color: $accent; }
#iconeDrop { background: $surface2; border: 1px solid $line; border-radius: 14px; }
#tituloVazio { font-size: ${fs_xxl}px; font-weight: 600; }
#textoVazio, #dicaVazio, #tituloRecentes { color: $muted; }
#tituloRecentes { font-size: ${fs_s}px; font-weight: 500; }
#linhaRecente { background: transparent; border: 1px solid transparent; border-radius: 8px; }
#linhaRecente:hover { background: $hover; }
#linhaRecente:focus { border-color: $accent; }
#nomeRecente { font-weight: 500; }
#overlayDrop { background: $veu; border: 2px dashed $accent; border-radius: 10px; font-size: ${fs_l}px; font-weight: 600; }
QLabel[papel="tecla"] { color: $muted; font-size: ${fs_xs}px; border: 1px solid $line2; border-radius: 5px; padding: 1px 6px; }

/* ---------- Configurações ---------- */
QTabWidget::pane { border: 1px solid $line; border-radius: 10px; background: $surface; top: -1px; }
QTabBar::tab { background: transparent; color: $muted; padding: 8px 14px; border: none; border-bottom: 2px solid transparent; font-weight: 500; }
QTabBar::tab:selected { color: $text; border-bottom: 2px solid $accent; }
QTabBar::tab:hover { color: $text; }
QTabBar::tab:selected:focus { background: $hover; }
QLabel[papel="secao"] { font-weight: 600; font-size: ${fs}px; }
QLabel[papel="ajuda"] { color: $muted; font-size: ${fs_s}px; }

/* ---------- Barra de status ---------- */
QStatusBar { background: $surface; border-top: 1px solid $line; min-height: 28px; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $muted; font-size: ${fs_s}px; padding: 0 8px; }
QStatusBar QLabel#destaqueStatus { color: $text; }
QProgressBar { background: $surface2; border: none; border-radius: 3px; max-height: 6px; min-width: 140px; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }

/* ---------- Splitter, rolagem, menus, diálogos ---------- */
/* alça larga (fácil de pegar) com só a linha de 1px no meio */
QSplitter::handle:horizontal {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 transparent, stop: 0.42 transparent,
                                stop: 0.43 $line, stop: 0.57 $line, stop: 0.58 transparent, stop: 1 transparent);
}
QSplitter::handle:horizontal:hover {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0, stop: 0 transparent, stop: 0.28 transparent,
                                stop: 0.29 $accent, stop: 0.71 $accent, stop: 0.72 transparent, stop: 1 transparent);
}
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $line2; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:horizontal { background: $line2; border-radius: 3px; min-width: 30px; }
QScrollBar::handle:hover { background: $faint; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: none; }
QAbstractItemView#popupCompletar { background: $surface2; border: 1px solid $line2; selection-background-color: $sel; selection-color: $text; }
QMessageBox { background: $surface; }
QMenu { background: $surface2; border: 1px solid $line2; padding: 4px; border-radius: 8px; }
QMenu::item { padding: 6px 28px 6px 28px; border-radius: 6px; }
QMenu::item:selected { background: $sel; }
QMenu::item:disabled { color: $faint; }
QMenu::indicator { width: 14px; height: 14px; left: 8px; }
QMenu::indicator:checked { image: url("$svg_check_texto"); }
QMenu::separator { height: 1px; background: $line; margin: 4px 8px; }
""")


def folha_de_estilo(cores, fonte_ui, fonte_mono, tamanho_fonte=13):
    valores = {k: v for k, v in cores.items() if isinstance(v, str)}
    fs = int(tamanho_fonte)
    svgs = dict(
        svg_baixo=arquivo_svg("seta_baixo", cores["muted"]),
        svg_baixo_faint=arquivo_svg("seta_baixo", cores["faint"]),
        svg_cima=arquivo_svg("seta_cima", cores["muted"]),
        svg_baixo_accent=arquivo_svg("seta_baixo", cores["accent"], 2.4),
        svg_cima_accent=arquivo_svg("seta_cima", cores["accent"], 2.4),
        svg_check=arquivo_svg("check", cores["on_accent"], 3.0),
        svg_check_texto=arquivo_svg("check", cores["text"], 2.4),
    )
    return _QSS.substitute(
        valores, **svgs,
        fonte=fonte_ui or "sans-serif", mono=fonte_mono or "monospace",
        fs=fs, fs_s=fs - 1, fs_xs=max(9, fs - 2), fs_l=fs + 1, fs_xl=fs + 2, fs_xxl=fs + 7,
        h_botao=altura_botao(fs), h_campo=fs + 19,
    )


def repolir(widget):
    """Reaplica o QSS depois de mudar uma propriedade dinâmica (ex.: erro=true)."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
