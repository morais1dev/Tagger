"""
Diálogos de padrão de nome, com prévia ao vivo:
- Renomear pelas tags: {tracknumber:02} - {artist} - {title}  ->  "03 - Artista - Música.mp3"
- Tags pelo nome:      %artist% - %title%                     ->  preenche o rascunho

Nada é feito enquanto o diálogo está aberto: a janela principal lê o resultado
(plano de renomeação ou valores das tags) depois do OK.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QHBoxLayout, QHeaderView, QLabel, QMenu, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from tagger.nucleo.metadata import CAMPOS, rotulo, validar_valor
from tagger.nucleo.padroes import campos_do_padrao, planejar_renomeacao, tags_pelo_nome

MAX_LINHAS_PREVIA = 500       # acima disso a prévia mostra só as primeiras (o resultado vale para todas)
MAX_RECENTES = 8


def _rotulo(texto, papel):
    lbl = QLabel(texto)
    lbl.setProperty("papel", papel)
    lbl.setWordWrap(True)
    return lbl


def lembrar_padrao(recentes, padrao):
    """Lista de padrões recentes com este no topo (sem repetir)."""
    return ([padrao] + [p for p in recentes if p != padrao])[:MAX_RECENTES]


class DialogoPadrao(QDialog):
    """Base: campo do padrão (com recentes) + "Inserir campo" + opções + tabela de prévia."""
    formato_campo = "{{{}}}"
    exemplos = ()

    def __init__(self, titulo, explicacao, faixas, padrao, recentes, cores, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setMinimumSize(720, 520)
        self.faixas = faixas
        self.cores = cores or {}

        self.cb_padrao = QComboBox()
        self.cb_padrao.setEditable(True)
        self.cb_padrao.setInsertPolicy(QComboBox.NoInsert)
        for item in lembrar_padrao(list(recentes) + list(self.exemplos), padrao):
            self.cb_padrao.addItem(item)
        self.cb_padrao.setCurrentText(padrao)
        self.cb_padrao.lineEdit().textChanged.connect(lambda _t: self._timer.start())
        self.cb_padrao.setProperty("mono", True)

        btn_campo = QPushButton("Inserir campo")
        menu = QMenu(btn_campo)
        for campo in CAMPOS:
            token = self.formato_campo.format(campo)
            menu.addAction(f"{rotulo(campo)}    {token}", lambda t=token: self._inserir(t))
        self._extras_menu(menu)
        btn_campo.setMenu(menu)

        linha = QHBoxLayout()
        linha.addWidget(self.cb_padrao, 1)
        linha.addWidget(btn_campo)

        self.lbl_erro = _rotulo("", "erroCampo")
        self.lbl_erro.setVisible(False)

        self.tabela = QTableWidget()
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.setSelectionMode(QAbstractItemView.NoSelection)
        self.tabela.setFocusPolicy(Qt.NoFocus)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setShowGrid(False)
        self.tabela.setWordWrap(False)
        self.tabela.horizontalHeader().setHighlightSections(False)
        self.tabela.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.lbl_resumo = _rotulo("", "ajuda")
        btn_cancelar = QPushButton("Cancelar")
        btn_cancelar.clicked.connect(self.reject)
        self.btn_ok = QPushButton("OK")
        self.btn_ok.setProperty("tipo", "primario")
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        rodape = QHBoxLayout()
        rodape.addWidget(self.lbl_resumo, 1)
        rodape.addWidget(btn_cancelar)
        rodape.addWidget(self.btn_ok)

        self.layout_opcoes = QVBoxLayout()
        self.layout_opcoes.setSpacing(6)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 16)
        v.setSpacing(10)
        v.addWidget(_rotulo(explicacao, "ajuda"))
        v.addLayout(linha)
        v.addWidget(self.lbl_erro)
        v.addLayout(self.layout_opcoes)
        v.addWidget(self.tabela, 1)
        v.addLayout(rodape)

        self._timer = QTimer(self, singleShot=True, interval=150)
        self._timer.timeout.connect(self._atualizar)
        QTimer.singleShot(0, self._atualizar)

    # ------------------------------------------------------------------ para as subclasses
    def _extras_menu(self, menu):
        pass

    def calcular(self, padrao):
        """Devolve (cabeçalhos, linhas, resumo, n_validos). linhas = [[(texto, tipo, dica), ...]].
        tipo: "" normal, "fraco" (sem mudança) ou "erro". Levanta ValueError se o padrão é inválido."""
        raise NotImplementedError

    def texto_ok(self, n):
        raise NotImplementedError

    # ------------------------------------------------------------------ comum
    @property
    def padrao(self):
        return self.cb_padrao.currentText().strip()

    def _inserir(self, token):
        self.cb_padrao.lineEdit().insert(token)
        self.cb_padrao.setFocus()

    def _cor(self, tipo):
        chave = {"erro": "erro", "fraco": "muted"}.get(tipo)
        return QColor(self.cores[chave]) if chave in self.cores else None

    def _atualizar(self):
        try:
            if not self.padrao:
                raise ValueError("Digite um padrão.")
            cabecalhos, linhas, resumo, validos = self.calcular(self.padrao)
        except ValueError as erro:
            self.lbl_erro.setText(str(erro))
            self.lbl_erro.setVisible(True)
            self.btn_ok.setEnabled(False)
            self.btn_ok.setText(self.texto_ok(0))
            return
        self.lbl_erro.setVisible(False)

        self.tabela.setUpdatesEnabled(False)
        self.tabela.clear()
        self.tabela.setColumnCount(len(cabecalhos))
        self.tabela.setHorizontalHeaderLabels(cabecalhos)
        mostradas = linhas[:MAX_LINHAS_PREVIA]
        self.tabela.setRowCount(len(mostradas))
        for i, celulas in enumerate(mostradas):
            for j, (texto, tipo, dica) in enumerate(celulas):
                item = QTableWidgetItem(texto)
                cor = self._cor(tipo)
                if cor is not None:
                    item.setForeground(cor)
                if dica:
                    item.setToolTip(dica)
                self.tabela.setItem(i, j, item)
        cabecalho = self.tabela.horizontalHeader()
        for j in range(len(cabecalhos)):
            cabecalho.setSectionResizeMode(j, QHeaderView.Stretch if j < 2 else QHeaderView.ResizeToContents)
        self.tabela.setUpdatesEnabled(True)

        if len(linhas) > MAX_LINHAS_PREVIA:
            resumo += f" · prévia das primeiras {MAX_LINHAS_PREVIA}"
        self.lbl_resumo.setText(resumo)
        self.btn_ok.setEnabled(validos > 0)
        self.btn_ok.setText(self.texto_ok(validos))


class DialogoRenomear(DialogoPadrao):
    formato_campo = "{{{}}}"
    exemplos = ("{tracknumber:02} - {artist} - {title}", "{tracknumber:02} - {title}", "{artist} - {title}",
                "{discnumber}-{tracknumber:02} {title}")

    def __init__(self, faixas, valor, padrao, recentes, cores, tem_pendentes=False, parent=None):
        """valor: função(faixa, campo) -> texto mostrado (inclui alterações não salvas)."""
        self.valor = valor
        self.plano = []
        explicacao = ("Monte o novo nome com os campos das tags. {tracknumber:02} completa com zeros (03). "
                      "Caracteres que o Windows não aceita são trocados. Dá para desfazer com Ctrl+Z.")
        if tem_pendentes:
            explicacao += "\nUsa os valores mostrados na tabela, inclusive alterações ainda não salvas."
        super().__init__("Renomear arquivos pelas tags", explicacao, faixas, padrao, recentes, cores, parent)

    def calcular(self, padrao):
        campos = campos_do_padrao(padrao)
        itens = [(f.caminho, {c: self.valor(f, c) for c in campos}) for f in self.faixas]
        self.plano = planejar_renomeacao(itens, padrao)
        linhas, mudam, iguais, erros = [], 0, 0, 0
        for item in self.plano:
            if item.erro:
                erros += 1
                linhas.append([(item.origem.name, "", str(item.origem)), (item.erro, "erro", item.erro)])
            elif item.destino is None:
                iguais += 1
                linhas.append([(item.origem.name, "fraco", str(item.origem)), ("(sem mudança)", "fraco", "")])
            else:
                mudam += 1
                linhas.append([(item.origem.name, "", str(item.origem)), (item.destino.name, "", "")])
        resumo = f"{mudam} serão renomeados"
        if iguais:
            resumo += f" · {iguais} já estão com esse nome"
        if erros:
            resumo += f" · {erros} com problema (não serão renomeados)"
        return ["Nome atual", "Novo nome"], linhas, resumo, mudam

    def texto_ok(self, n):
        return "Renomear" if n == 0 else f"Renomear {n} {'arquivo' if n == 1 else 'arquivos'}"


class DialogoTagsDoNome(DialogoPadrao):
    formato_campo = "%{}%"
    exemplos = ("%artist% - %title%", "%track% - %artist% - %title%", "%track% - %title%", "%track%. %title%",
                "%artist%/%album%/%track% - %title%")

    def __init__(self, faixas, valor, padrao, recentes, cores, parent=None):
        self.valor = valor
        self.resultado = []
        explicacao = ("Lê as tags do nome de cada arquivo. %*% ignora um trecho e \"/\" usa as pastas acima "
                      "(ex.: %artist%/%album%/%track% - %title%). Os valores ficam pendentes até você salvar.")
        super().__init__("Preencher tags pelo nome do arquivo", explicacao, faixas, padrao, recentes, cores, parent)
        self.ck_sublinhado = QCheckBox("Trocar _ por espaço")
        self.ck_so_vazios = QCheckBox("Preencher só os campos que estão vazios")
        for ck in (self.ck_sublinhado, self.ck_so_vazios):
            ck.toggled.connect(lambda _on: self._timer.start())
            self.layout_opcoes.addWidget(ck)

    def _extras_menu(self, menu):
        menu.addSeparator()
        menu.addAction("Ignorar trecho    %*%", lambda: self._inserir("%*%"))

    def calcular(self, padrao):
        campos = campos_do_padrao(padrao)
        if not campos:
            raise ValueError("Use pelo menos um campo, ex.: %artist% - %title%")
        sublinhado = getattr(self, "ck_sublinhado", None) is not None and self.ck_sublinhado.isChecked()
        so_vazios = getattr(self, "ck_so_vazios", None) is not None and self.ck_so_vazios.isChecked()

        self.resultado, linhas, nao_casam, invalidos = [], [], 0, 0
        for faixa in self.faixas:
            lidos = tags_pelo_nome(padrao, faixa.caminho, sublinhado)
            if lidos is None:
                nao_casam += 1
                linhas.append([(faixa.nome, "fraco", str(faixa.caminho)), ("não segue o padrão", "fraco", "")]
                              + [("", "", "")] * (len(campos) - 1))
                continue
            valores, celulas = {}, [(faixa.nome, "", str(faixa.caminho))]
            for campo in campos:
                novo = lidos.get(campo, "")
                atual = self.valor(faixa, campo)
                if so_vazios and atual:
                    celulas.append((atual, "fraco", "Já tem valor: mantido"))
                    continue
                ok, mensagem = validar_valor(campo, novo)
                if not ok:
                    invalidos += 1
                    celulas.append((novo, "erro", mensagem))
                    continue
                valores[campo] = novo
                celulas.append((novo, "", ""))
            if valores:
                self.resultado.append((faixa, valores))
            linhas.append(celulas)
        n = len(self.resultado)
        resumo = f"{n} {'arquivo' if n == 1 else 'arquivos'} com tags lidas"
        if nao_casam:
            resumo += f" · {nao_casam} não seguem o padrão"
        if invalidos:
            resumo += f" · {invalidos} valores inválidos ignorados"
        return ["Arquivo"] + [rotulo(c) for c in campos], linhas, resumo, n

    def texto_ok(self, n):
        return "Preencher" if n == 0 else f"Preencher {n} {'arquivo' if n == 1 else 'arquivos'}"
