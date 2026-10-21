"""
Tema visual do Tagger: temas de cor, cor de destaque, fontes, tamanhos e a folha de estilo (QSS).

Para criar um tema novo, basta acrescentar uma entrada em TEMAS (todas as chaves são
obrigatórias). "acento" é a cor de destaque usada quando a configuração está em "Do tema".
"""

from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFontDatabase, QPalette

TEMAS = {
    # ---------------------------------------------------------------- escuros
    "grafite": {
        "nome": "Grafite", "escuro": True, "acento": "#3ddc97",
        "bg": "#0f1012", "surface": "#16171a", "surface2": "#1c1e22", "field": "#111214",
        "line": "#25282d", "line2": "#33373d", "text": "#e8e9eb", "muted": "#9ba0a8",
        "faint": "#5d626b", "hover": "#1f2125", "erro": "#ff6b6b",
    },
    "meia-noite": {
        "nome": "Meia-noite", "escuro": True, "acento": "#6b9bff",
        "bg": "#0b1020", "surface": "#11182b", "surface2": "#172036", "field": "#0d1426",
        "line": "#1f2a44", "line2": "#2b3858", "text": "#e6eaf3", "muted": "#98a3bb",
        "faint": "#56617a", "hover": "#1a2440", "erro": "#ff6b6b",
    },
    "alto-contraste": {
        "nome": "Alto contraste", "escuro": True, "acento": "#f5c542",
        "bg": "#000000", "surface": "#0a0a0a", "surface2": "#141414", "field": "#000000",
        "line": "#3a3a3a", "line2": "#5c5c5c", "text": "#ffffff", "muted": "#cfcfcf",
        "faint": "#8a8a8a", "hover": "#1c1c1c", "erro": "#ff5c5c",
    },
    "dracula": {
        "nome": "Dracula", "escuro": True, "acento": "#bd93f9",
        "bg": "#21222c", "surface": "#282a36", "surface2": "#343746", "field": "#21222c",
        "line": "#383a4a", "line2": "#44475a", "text": "#f8f8f2", "muted": "#a6accd",
        "faint": "#6272a4", "hover": "#313343", "erro": "#ff5555",
    },
    "nord": {
        "nome": "Nord", "escuro": True, "acento": "#88c0d0",
        "bg": "#272c36", "surface": "#2e3440", "surface2": "#3b4252", "field": "#292e39",
        "line": "#3b4252", "line2": "#4c566a", "text": "#eceff4", "muted": "#b0b8c8",
        "faint": "#616e88", "hover": "#353c4a", "erro": "#bf616a",
    },
    "gruvbox-dark": {
        "nome": "Gruvbox Dark", "escuro": True, "acento": "#fe8019",
        "bg": "#1d2021", "surface": "#282828", "surface2": "#32302f", "field": "#1d2021",
        "line": "#3c3836", "line2": "#504945", "text": "#ebdbb2", "muted": "#a89984",
        "faint": "#665c54", "hover": "#2f2d2c", "erro": "#fb4934",
    },
    "catppuccin-mocha": {
        "nome": "Catppuccin Mocha", "escuro": True, "acento": "#cba6f7",
        "bg": "#181825", "surface": "#1e1e2e", "surface2": "#313244", "field": "#181825",
        "line": "#2a2b3c", "line2": "#45475a", "text": "#cdd6f4", "muted": "#a6adc8",
        "faint": "#6c7086", "hover": "#262637", "erro": "#f38ba8",
    },
    "tokyo-night": {
        "nome": "Tokyo Night", "escuro": True, "acento": "#7aa2f7",
        "bg": "#16161e", "surface": "#1a1b26", "surface2": "#24283b", "field": "#16161e",
        "line": "#232433", "line2": "#2f3549", "text": "#c0caf5", "muted": "#a9b1d6",
        "faint": "#565f89", "hover": "#202231", "erro": "#f7768e",
    },
    "one-dark": {
        "nome": "One Dark", "escuro": True, "acento": "#61afef",
        "bg": "#21252b", "surface": "#282c34", "surface2": "#2c313a", "field": "#21252b",
        "line": "#323842", "line2": "#3e4451", "text": "#d7dae0", "muted": "#9da5b4",
        "faint": "#5c6370", "hover": "#2a2f37", "erro": "#e06c75",
    },
    "solarized-dark": {
        "nome": "Solarized Dark", "escuro": True, "acento": "#268bd2",
        "bg": "#00212b", "surface": "#002b36", "surface2": "#073642", "field": "#00252f",
        "line": "#0a3a47", "line2": "#14505e", "text": "#eee8d5", "muted": "#93a1a1",
        "faint": "#586e75", "hover": "#04313d", "erro": "#dc322f",
    },
    "monokai": {
        "nome": "Monokai", "escuro": True, "acento": "#a6e22e",
        "bg": "#1e1f1c", "surface": "#272822", "surface2": "#31322c", "field": "#1e1f1c",
        "line": "#34352f", "line2": "#49483e", "text": "#f8f8f2", "muted": "#b4b2a2",
        "faint": "#75715e", "hover": "#2e2f29", "erro": "#f92672",
    },
    "github-dark": {
        "nome": "GitHub Dark", "escuro": True, "acento": "#4493f8",
        "bg": "#010409", "surface": "#0d1117", "surface2": "#161b22", "field": "#0d1117",
        "line": "#21262d", "line2": "#30363d", "text": "#e6edf3", "muted": "#9198a1",
        "faint": "#484f58", "hover": "#131820", "erro": "#f85149",
    },
    "rose-pine": {
        "nome": "Rosé Pine", "escuro": True, "acento": "#c4a7e7",
        "bg": "#191724", "surface": "#1f1d2e", "surface2": "#26233a", "field": "#191724",
        "line": "#2a273f", "line2": "#403d52", "text": "#e0def4", "muted": "#908caa",
        "faint": "#6e6a86", "hover": "#21202e", "erro": "#eb6f92",
    },
    # ---------------------------------------------------------------- claros
    "claro": {
        "nome": "Claro", "escuro": False, "acento": "#3ddc97",
        "bg": "#eceef1", "surface": "#ffffff", "surface2": "#f5f6f8", "field": "#ffffff",
        "line": "#e2e5e9", "line2": "#cfd4da", "text": "#14161a", "muted": "#59606a",
        "faint": "#a3a9b1", "hover": "#f1f3f5", "erro": "#d93838",
    },
    "sepia": {
        "nome": "Sépia", "escuro": False, "acento": "#c47a3a",
        "bg": "#ece4d6", "surface": "#faf6ef", "surface2": "#f3ece0", "field": "#fffdf8",
        "line": "#e2d8c6", "line2": "#d2c5ae", "text": "#2b2419", "muted": "#685d4c",
        "faint": "#a89c88", "hover": "#f0e8da", "erro": "#c0392b",
    },
    "catppuccin-latte": {
        "nome": "Catppuccin Latte", "escuro": False, "acento": "#8839ef",
        "bg": "#e6e9ef", "surface": "#eff1f5", "surface2": "#e6e9ef", "field": "#f7f8fa",
        "line": "#dce0e8", "line2": "#ccd0da", "text": "#4c4f69", "muted": "#5c5f77",
        "faint": "#9ca0b0", "hover": "#e9ecf1", "erro": "#d20f39",
    },
    "gruvbox-light": {
        "nome": "Gruvbox Light", "escuro": False, "acento": "#af3a03",
        "bg": "#f2e5bc", "surface": "#fbf1c7", "surface2": "#f2e5bc", "field": "#f9f5d7",
        "line": "#e5d5ad", "line2": "#d5c4a1", "text": "#3c3836", "muted": "#665c54",
        "faint": "#a89984", "hover": "#f5ead0", "erro": "#9d0006",
    },
    "solarized-light": {
        "nome": "Solarized Light", "escuro": False, "acento": "#268bd2",
        "bg": "#eee8d5", "surface": "#fdf6e3", "surface2": "#f5efdc", "field": "#fffbf0",
        "line": "#e8e1cc", "line2": "#d9d2bd", "text": "#073642", "muted": "#4f656c",
        "faint": "#93a1a1", "hover": "#f7f0dd", "erro": "#dc322f",
    },
    "github-light": {
        "nome": "GitHub Light", "escuro": False, "acento": "#0969da",
        "bg": "#f6f8fa", "surface": "#ffffff", "surface2": "#f6f8fa", "field": "#ffffff",
        "line": "#d8dee4", "line2": "#d0d7de", "text": "#1f2328", "muted": "#59636e",
        "faint": "#8c959f", "hover": "#f3f5f7", "erro": "#d1242f",
    },
    "rose-pine-dawn": {
        "nome": "Rosé Pine Dawn", "escuro": False, "acento": "#286983",
        "bg": "#faf4ed", "surface": "#fffaf3", "surface2": "#f2e9e1", "field": "#fffaf3",
        "line": "#e9e1da", "line2": "#dfdad9", "text": "#575279", "muted": "#625e7a",
        "faint": "#9893a5", "hover": "#f4ede8", "erro": "#b4637a",
    },
}

ACENTO_DO_TEMA = "tema"     # valor da configuração que significa "usar a cor de destaque do tema"
ACENTOS = [
    ("Menta", "#3ddc97"), ("Azul", "#6b9bff"), ("Laranja", "#ff9a4d"),
    ("Lilás", "#c58bff"), ("Rosa", "#ff6b9d"), ("Amarelo", "#f5c542"),
]

# Fontes preferidas, na ordem, quando a configuração está em "Automática".
FONTES_UI = ["Geist", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans"]
FONTES_MONO = ["Geist Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono"]

PASTA_FONTES = Path(__file__).parent / "recursos" / "fontes"

ALTURA_LINHA = {"compacta": 21, "confortavel": 29, "espacosa": 37}   # somado ao tamanho da fonte

def altura_botao(tamanho_fonte):
    """Altura (e lado dos botões quadrados de ícone) acompanhando o tamanho da fonte."""
    return int(tamanho_fonte) + 19

def altura_cabecalho(tamanho_fonte):
    """Altura do cabeçalho da tabela acompanhando o tamanho da fonte."""
    return int(tamanho_fonte) + 21


# ---------------------------------------------------------------------------- cores
def _rgba(hex_cor, alfa):
    c = QColor(hex_cor)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alfa})"


def _luminancia(hex_cor):
    c = QColor(hex_cor)

    def canal(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return 0.2126 * canal(c.red()) + 0.7152 * canal(c.green()) + 0.0722 * canal(c.blue())


def contraste(cor_a, cor_b):
    """Razão de contraste WCAG entre duas cores (texto normal deve ter pelo menos 4.5)."""
    a, b = sorted((_luminancia(cor_a), _luminancia(cor_b)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def _texto_sobre(hex_cor):
    """Preto ou branco, o que tiver mais contraste com a cor de destaque."""
    return max(("#0b0d0c", "#ffffff"), key=lambda cor: contraste(cor, hex_cor))


def acento_efetivo(tema_id, acento):
    """A cor de destaque que vale: a escolhida, ou a do tema quando a escolha é "Do tema"."""
    base = TEMAS.get(tema_id) or TEMAS["grafite"]
    if acento == ACENTO_DO_TEMA or not QColor(acento).isValid():
        return base.get("acento", ACENTOS[0][1])
    return QColor(acento).name()


def paleta(tema_id, acento):
    """Dicionário com todas as cores do tema + cor de destaque."""
    base = TEMAS.get(tema_id) or TEMAS["grafite"]
    cores = {k: v for k, v in base.items() if k not in ("nome", "acento")}
    acento = acento_efetivo(tema_id, acento)
    cores.update(
        accent=acento,
        on_accent=_texto_sobre(acento),
        accent_hover=QColor(acento).lighter(110).name(),
        sel=_rgba(acento, 40 if base["escuro"] else 46),
        sel_line=_rgba(acento, 115),
        tema=tema_id,
    )
    return cores


def temas_escuros():
    return {k: v["nome"] for k, v in TEMAS.items() if v["escuro"]}


def temas_claros():
    return {k: v["nome"] for k, v in TEMAS.items() if not v["escuro"]}


# ---------------------------------------------------------------------------- fontes
def registrar_fontes():
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
QPushButton:pressed { background: $surface2; }
QPushButton:disabled { color: $faint; }
QPushButton[tipo="primario"] { background: $accent; color: $on_accent; border: 1px solid $accent; }
QPushButton[tipo="primario"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[tipo="primario"]:disabled { background: $surface2; color: $faint; border-color: $line; }
QPushButton[tipo="fantasma"] { background: transparent; border-color: transparent; color: $muted; }
QPushButton[tipo="fantasma"]:hover { background: $hover; color: $text; }
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
QComboBox QAbstractItemView { background: $surface2; border: 1px solid $line2; selection-background-color: $sel; selection-color: $text; outline: 0; }
QSpinBox::up-button, QSpinBox::down-button { border: none; width: 18px; }
#busca { min-width: 220px; max-width: 300px; }
#busca:focus { border-color: $sel_line; }
QCheckBox, QRadioButton { spacing: 8px; }

/* ---------- Tabela ---------- */
QTableView {
    background: $surface; border: 1px solid $line; border-radius: 10px;
    gridline-color: transparent; outline: 0;
    selection-background-color: $sel; selection-color: $text;
}
QTableView::item { border-bottom: 1px solid $line; padding: 0 6px; }
QTableView::item:hover { background: $hover; }
QTableView::item:selected { background: $sel; color: $text; }
QTableView QLineEdit { border-radius: 0; min-height: 0; padding: 0 5px; border: 1px solid $accent; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: $surface2; color: $muted; border: none; border-bottom: 1px solid $line;
    padding: 0 6px; font-size: ${fs_s}px; font-weight: 500;
}
QHeaderView::section:hover { color: $text; }
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
#capa { background: $surface2; border: 1px solid $line2; border-radius: 10px; color: $muted; font-size: ${fs_s}px; }
#capa[arrastando="true"] { border: 2px dashed $accent; }
#painelVazioTitulo { font-weight: 500; }
#painelVazioTexto { color: $muted; font-size: ${fs_s}px; }

/* ---------- Tela vazia ---------- */
#zonaDrop { background: $surface; border: 2px dashed $line2; border-radius: 16px; }
#zonaDrop[ativo="true"] { border-color: $accent; }
#iconeDrop { background: $surface2; border: 1px solid $line; border-radius: 14px; }
#tituloVazio { font-size: ${fs_xxl}px; font-weight: 600; }
#textoVazio, #dicaVazio, #tituloRecentes { color: $muted; }
#tituloRecentes { font-size: ${fs_s}px; font-weight: 500; }
QLabel[papel="tecla"] { color: $muted; font-size: ${fs_xs}px; border: 1px solid $line2; border-radius: 5px; padding: 1px 6px; }

/* ---------- Configurações ---------- */
QTabWidget::pane { border: 1px solid $line; border-radius: 10px; background: $surface; top: -1px; }
QTabBar::tab { background: transparent; color: $muted; padding: 8px 14px; border: none; border-bottom: 2px solid transparent; font-weight: 500; }
QTabBar::tab:selected { color: $text; border-bottom: 2px solid $accent; }
QTabBar::tab:hover { color: $text; }
QLabel[papel="secao"] { font-weight: 600; font-size: ${fs}px; }
QLabel[papel="ajuda"] { color: $muted; font-size: ${fs_s}px; }
QLabel[papel="erroCampo"] { color: $erro; font-size: ${fs_s}px; }

/* ---------- Barra de status ---------- */
QStatusBar { background: $surface; border-top: 1px solid $line; min-height: 28px; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $muted; font-size: ${fs_s}px; padding: 0 8px; }
QStatusBar QLabel#destaqueStatus { color: $text; }
QProgressBar { background: $surface2; border: none; border-radius: 3px; max-height: 6px; min-width: 140px; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }

/* ---------- Splitter, rolagem, menus, diálogos ---------- */
QSplitter::handle { background: $line; }
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
QMenu::separator { height: 1px; background: $line; margin: 4px 8px; }
""")


def folha_de_estilo(cores, fonte_ui, fonte_mono, tamanho_fonte=13):
    valores = {k: v for k, v in cores.items() if isinstance(v, str)}
    fs = int(tamanho_fonte)
    return _QSS.substitute(
        valores,
        fonte=fonte_ui or "sans-serif", mono=fonte_mono or "monospace",
        fs=fs, fs_s=fs - 1, fs_xs=max(9, fs - 2), fs_l=fs + 1, fs_xl=fs + 2, fs_xxl=fs + 7,
        h_botao=fs + 17, h_campo=fs + 19,
    )


def repolir(widget):
    """Reaplica o QSS depois de mudar uma propriedade dinâmica (ex.: erro=true)."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()