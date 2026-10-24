"""
Diálogo "Organizar em pastas pelas tags", com prévia ao vivo:
    {albumartist}/{album}/{tracknumber:02} - {title}  ->  Destino/Artista/Álbum/03 - Música.ext

Reaproveita DialogoPadrao (campo do padrão, recentes, tabela de prévia). Nada é movido enquanto o
diálogo está aberto: a janela principal lê `plano`, `remover_vazias` e `pasta_destino` depois do OK
e chama nucleo.organizar.executar_organizacao.
"""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from tagger.gui.padrao import DialogoPadrao
from tagger.nucleo.organizar import PlanoOrganizar, planejar_organizacao, resumo_falhas, resumo_movimentos
from tagger.nucleo.padroes import campos_do_padrao


class DialogoOrganizar(DialogoPadrao):
    formato_campo = "{{{}}}"
    exemplos = ("{albumartist}/{album}/{tracknumber:02} - {title}", "{artist}/{album}/{tracknumber:02} - {title}",
                "{albumartist}/{date} - {album}/{tracknumber:02} - {title}", "{genre}/{artist} - {title}")

    def __init__(self, faixas, valor, padrao, recentes, cores, pasta_destino="", tem_pendentes=False, parent=None):
        """valor: função(faixa, campo) -> texto mostrado (inclui alterações não salvas)."""
        self.valor = valor
        self.plano = PlanoOrganizar(Path(pasta_destino or "."))
        explicacao = ("Move cada arquivo para uma pasta montada com as tags: \"/\" separa as pastas. "
                      "Tags vazias viram Unknown Artist / Unknown Album, as pastas são criadas e a capa "
                      "(cover.jpg) vai junto. Dá para desfazer com Ctrl+Z.")
        if tem_pendentes:
            explicacao += "\nUsa os valores mostrados na tabela, inclusive alterações ainda não salvas."
        super().__init__("Organizar arquivos em pastas", explicacao, faixas, padrao, recentes, cores, parent)
        self.setMinimumSize(760, 560)

        self.ed_destino = QLineEdit(str(pasta_destino or ""))
        self.ed_destino.setPlaceholderText("Pasta de destino")
        self.ed_destino.textChanged.connect(lambda _t: self._timer.start())
        btn_escolher = QPushButton("Escolher…")
        btn_escolher.clicked.connect(self._escolher_destino)
        linha = QHBoxLayout()
        linha.addWidget(self.ed_destino, 1)
        linha.addWidget(btn_escolher)
        self.layout_opcoes.addLayout(linha)

        self.ck_capa = QCheckBox("Levar a capa da pasta junto (cover.jpg, folder.jpg)")
        self.ck_capa.setChecked(True)
        self.ck_vazias = QCheckBox("Remover as pastas que ficarem vazias")
        for ck in (self.ck_capa, self.ck_vazias):
            ck.toggled.connect(lambda _on: self._timer.start())
            self.layout_opcoes.addWidget(ck)

    # ------------------------------------------------------------------ resultado
    @property
    def pasta_destino(self):
        return Path(self.ed_destino.text().strip())

    @property
    def remover_vazias(self):
        return self.ck_vazias.isChecked()

    def _escolher_destino(self):
        pasta = QFileDialog.getExistingDirectory(self, "Pasta de destino", self.ed_destino.text())
        if pasta:
            self.ed_destino.setText(pasta)

    # ------------------------------------------------------------------ prévia
    def calcular(self, padrao):
        campos = campos_do_padrao(padrao)
        if not campos:
            raise ValueError("Use pelo menos um campo, ex.: {artist}/{album}/{title}")
        ed = getattr(self, "ed_destino", None)
        destino = ed.text().strip() if ed is not None else ""
        if not destino:
            raise ValueError("Escolha a pasta de destino.")
        levar_capa = getattr(self, "ck_capa", None) is None or self.ck_capa.isChecked()

        itens = [(f.caminho, {c: self.valor(f, c) for c in campos}) for f in self.faixas]
        self.plano = planejar_organizacao(itens, padrao, destino, levar_capa)

        linhas, mudam, no_lugar, erros = [], 0, 0, 0
        for item in self.plano.itens:
            if item.erro:
                erros += 1
                linhas.append([(item.origem.name, "", str(item.origem)), (item.erro, "erro", item.erro)])
            elif item.destino is None:
                no_lugar += 1
                linhas.append([(item.origem.name, "fraco", str(item.origem)), ("(já está no lugar)", "fraco", "")])
            else:
                mudam += 1
                relativo = item.destino.relative_to(self.plano.pasta)
                linhas.append([(item.origem.name, "", str(item.origem)), (str(relativo), "", str(item.destino))])
        resumo = f"{mudam} serão movidos"
        if self.plano.capas:
            resumo += f" · {len(self.plano.capas)} capa(s) vão junto"
        if no_lugar:
            resumo += f" · {no_lugar} já estão no lugar"
        if erros:
            resumo += f" · {erros} com problema (não serão movidos)"
        return ["Arquivo atual", "Novo local"], linhas, resumo, mudam

    def texto_ok(self, n):
        return "Organizar" if n == 0 else f"Organizar {n} {'arquivo' if n == 1 else 'arquivos'}"


class DialogoResumoOrganizar(QDialog):
    """Depois de mover: para onde cada arquivo foi (origem → destino), com atalho para abrir a pasta."""

    def __init__(self, feitos, falhas, pasta, parent=None):
        super().__init__(parent)
        self.pasta = Path(pasta)
        self.setWindowTitle("Arquivos organizados")
        self.setMinimumSize(420, 300)

        if feitos:
            titulo = f"{len(feitos)} arquivo(s) movido(s) para {self.pasta}"
        else:
            titulo = "Nenhum arquivo foi movido."
        if falhas:
            titulo += f"{' · ' if feitos else ' '}{len(falhas)} não foram movidos e continuam onde estavam:"
        rotulo = QLabel(titulo)
        rotulo.setWordWrap(True)
        rotulo.setProperty("papel", "ajuda")

        # movidos (origem -> destino) e, no fim, as falhas (arquivo -> motivo)
        linhas = resumo_movimentos(feitos, self.pasta) + resumo_falhas(falhas, self.pasta)
        tabela = QTableWidget(len(linhas), 2)
        tabela.setHorizontalHeaderLabels(["Era", "Agora está em" if feitos else "Motivo"])
        tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        tabela.verticalHeader().setVisible(False)
        tabela.horizontalHeader().setStretchLastSection(True)
        for i, (origem, destino) in enumerate(linhas):
            for j, texto in enumerate((origem, destino)):
                item = QTableWidgetItem(texto)
                item.setToolTip(texto)
                tabela.setItem(i, j, item)
        tabela.resizeColumnToContents(0)
        tabela.setColumnWidth(0, min(tabela.columnWidth(0), 260))

        btn_abrir = QPushButton("Abrir pasta")
        btn_abrir.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pasta))))
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setProperty("tipo", "primario")
        btn_fechar.clicked.connect(self.accept)
        btn_fechar.setDefault(True)
        rodape = QHBoxLayout()
        rodape.addStretch()
        rodape.addWidget(btn_abrir)
        rodape.addWidget(btn_fechar)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 16)
        v.setSpacing(10)
        v.addWidget(rotulo)
        v.addWidget(tabela, 1)
        v.addLayout(rodape)
