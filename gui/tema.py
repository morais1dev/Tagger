"""
Tema visual do Tagger: cores (escuro/claro), fontes e a folha de estilo (QSS).

As cores são as mesmas do mockup. Para mudar a cor de destaque do app inteiro,
basta trocar ACENTO.
"""

from pathlib import Path
from string import Template

from PySide6.QtGui import QColor, QFontDatabase, QPalette

ACENTO = "#3ddc97"
SOBRE_ACENTO = "#07130c"      # texto/ícone em cima da cor de destaque

ESCURO = {
    "bg": "#0f1012", "surface": "#16171a", "surface2": "#1c1e22", "field": "#111214",
    "line": "#25282d", "line2": "#33373d", "text": "#e8e9eb", "muted": "#9ba0a8",
    "faint": "#5d626b", "hover": "#1f2125", "erro": "#ff6b6b",
}

CLARO = {
    "bg": "#eceef1", "surface": "#ffffff", "surface2": "#f5f6f8", "field": "#ffffff",
    "line": "#e2e5e9", "line2": "#cfd4da", "text": "#14161a", "muted": "#59606a",
    "faint": "#a3a9b1", "hover": "#f1f3f5", "erro": "#d93838",
}

# Fontes preferidas, na ordem. A primeira instalada é usada.
# Dica: coloque Geist-*.ttf e GeistMono-*.ttf em gui/fontes/ para usar a fonte do mockup.
FONTES_UI = ["Geist", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans"]
FONTES_MONO = ["Geist Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono"]

PASTA_FONTES = Path(__file__).parent / "fontes"


def _rgba(hex_cor, alfa):
    c = QColor(hex_cor)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alfa})"


def paleta(escuro):
    """Dicionário com todas as cores do tema escolhido."""
    cores = dict(ESCURO if escuro else CLARO)
    cores.update(
        accent=ACENTO,
        on_accent=SOBRE_ACENTO,
        accent_hover=QColor(ACENTO).lighter(110).name(),
        sel=_rgba(ACENTO, 40),
        sel_line=_rgba(ACENTO, 115),
        escuro=escuro,
    )
    return cores


def carregar_fontes():
    """Registra fontes da pasta gui/fontes (se existir) e escolhe as famílias."""
    if PASTA_FONTES.is_dir():
        for arquivo in PASTA_FONTES.iterdir():
            if arquivo.suffix.lower() in (".ttf", ".otf"):
                QFontDatabase.addApplicationFont(str(arquivo))

    instaladas = set(QFontDatabase.families())
    ui = next((f for f in FONTES_UI if f in instaladas), "")
    mono = next((f for f in FONTES_MONO if f in instaladas), "monospace")
    return ui, mono


def aplicar_paleta_qt(app, cores):
    """Cores que o QSS não alcança (placeholder, seleção de texto, menus nativos)."""
    p = app.palette()
    p.setColor(QPalette.Window, QColor(cores["bg"]))
    p.setColor(QPalette.WindowText, QColor(cores["text"]))
    p.setColor(QPalette.Base, QColor(cores["field"]))
    p.setColor(QPalette.AlternateBase, QColor(cores["surface2"]))
    p.setColor(QPalette.Text, QColor(cores["text"]))
    p.setColor(QPalette.Button, QColor(cores["surface2"]))
    p.setColor(QPalette.ButtonText, QColor(cores["text"]))
    p.setColor(QPalette.Highlight, QColor(ACENTO))
    p.setColor(QPalette.HighlightedText, QColor(SOBRE_ACENTO))
    p.setColor(QPalette.PlaceholderText, QColor(cores["muted"]))
    p.setColor(QPalette.ToolTipBase, QColor(cores["surface2"]))
    p.setColor(QPalette.ToolTipText, QColor(cores["text"]))
    app.setPalette(p)


_QSS = Template("""
* { font-family: "$fonte"; font-size: 13px; color: $text; }
*[mono="true"] { font-family: "$mono"; }
QMainWindow, #raiz { background: $bg; }
QToolTip { background: $surface2; color: $text; border: 1px solid $line2; padding: 4px 8px; border-radius: 6px; }

/* ---------- Barra superior ---------- */
#barraTopo { background: $surface; border-bottom: 1px solid $line; }
#logo { background: $accent; border-radius: 7px; }
#nomeApp { font-size: 15px; font-weight: 600; }
#sep { background: $line; }

/* ---------- Botões ---------- */
QPushButton {
    background: $surface2; border: 1px solid $line; border-radius: 8px;
    padding: 0 12px; min-height: 30px; font-weight: 500;
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
QPushButton[tipo="icone"] { padding: 0; min-width: 32px; max-width: 32px; }

/* ---------- Campos ---------- */
QLineEdit, QPlainTextEdit {
    background: $field; border: 1px solid $line; border-radius: 8px;
    padding: 0 10px; min-height: 32px; selection-background-color: $sel_line; selection-color: $text;
}
QPlainTextEdit { padding: 6px 6px; }
QLineEdit:hover, QPlainTextEdit:hover { border-color: $line2; }
QLineEdit:focus, QPlainTextEdit:focus { border-color: $accent; }
QLineEdit[erro="true"], QPlainTextEdit[erro="true"] { border-color: $erro; }
#busca { min-width: 220px; max-width: 300px; }
#busca:focus { border-color: $sel_line; }

/* ---------- Tabela ---------- */
QTableView {
    background: $surface; border: 1px solid $line; border-radius: 10px;
    gridline-color: transparent; outline: 0;
    selection-background-color: $sel; selection-color: $text;
}
QTableView::item { border-bottom: 1px solid $line; padding: 0 6px; }
QTableView::item:hover { background: $hover; }
QTableView::item:selected { background: $sel; color: $text; }
QHeaderView { background: transparent; border: none; }
QHeaderView::section {
    background: $surface2; color: $muted; border: none; border-bottom: 1px solid $line;
    padding: 0 6px; min-height: 34px; font-size: 12px; font-weight: 500;
}
QHeaderView::section:hover { color: $text; }
QTableCornerButton::section { background: $surface2; border: none; }
#migalha { color: $muted; font-size: 12px; }
#contagem { color: $muted; font-size: 12px; }

/* ---------- Painel editor ---------- */
#painel, #corpoPainel, #viewportPainel { background: $surface; }
#painelTopo { background: $surface; border-bottom: 1px solid $line; }
#painelRodape { background: $surface; border-top: 1px solid $line; }
#tituloPainel { font-size: 14px; font-weight: 600; }
QLabel[papel="sub"] { color: $muted; font-size: 12px; }
QLabel[papel="rotulo"] { color: $muted; font-size: 12px; font-weight: 500; }
QLabel[papel="rotulo"][alterado="true"] { color: $text; }
QLabel[papel="info"] { color: $muted; font-size: 11px; }
#capa { background: $surface2; border: 1px solid $line2; border-radius: 10px; color: $muted; font-size: 12px; }
#painelVazioTitulo { font-weight: 500; }
#painelVazioTexto { color: $muted; font-size: 12px; }

/* ---------- Tela vazia ---------- */
#zonaDrop { background: $surface; border: 2px dashed $line2; border-radius: 16px; }
#zonaDrop[ativo="true"] { border-color: $accent; }
#iconeDrop { background: $surface2; border: 1px solid $line; border-radius: 14px; }
#tituloVazio { font-size: 20px; font-weight: 600; }
#textoVazio, #dicaVazio, #tituloRecentes { color: $muted; }
#tituloRecentes { font-size: 12px; font-weight: 500; }
QLabel[papel="tecla"] { color: $muted; font-size: 11px; border: 1px solid $line2; border-radius: 5px; padding: 1px 6px; }

/* ---------- Barra de status ---------- */
QStatusBar { background: $surface; border-top: 1px solid $line; min-height: 28px; }
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $muted; font-size: 12px; padding: 0 8px; }
QStatusBar QLabel#destaqueStatus { color: $text; }

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
QMessageBox, QDialog { background: $surface; }
QMenu { background: $surface2; border: 1px solid $line2; padding: 4px; }
QMenu::item { padding: 6px 16px; border-radius: 6px; }
QMenu::item:selected { background: $sel; }
""")


def folha_de_estilo(cores, fonte_ui, fonte_mono):
    valores = {k: v for k, v in cores.items() if isinstance(v, str)}
    return _QSS.substitute(valores, fonte=fonte_ui or "sans-serif", mono=fonte_mono or "monospace")


def repolir(widget):
    """Reaplica o QSS depois de mudar uma propriedade dinâmica (ex.: erro=true)."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
