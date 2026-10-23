"""Diálogo "Buscar tags online": MusicBrainz (tags) + Cover Art Archive (capa).

Uso:
    dlg = DialogoBusca(faixas, parent)
    if dlg.exec():
        resultado = dlg.resultado()          # tagger.nucleo.busca.Resultado
        rascunho.definir_por_faixa(resultado.alteracoes)
        if resultado.capa:
            rascunho.definir_capa(resultado.caminhos_capa, resultado.acao_capa)
        # resultado.alteradas = quantas faixas mudaram; resultado.sem_par = faixas sem par no álbum
`valor` (opcional) = função valor(faixa, campo) do que o usuário está vendo, como Rascunho.valor;
sem ela usa as tags lidas do arquivo. Nada é gravado nos arquivos: só se devolve ao rascunho.
"""

import logging

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout,
)

from tagger.nucleo.busca import ClienteMusicBrainz, ErroBusca, Resultado, analisar

log = logging.getLogger(__name__)

# Threads de rede de diálogos já fechados: ficam vivas aqui até terminarem (destruir uma QThread
# rodando derruba o programa) e saem sozinhas no finished.
_ORFAOS = set()


class Trabalhador(QThread):
    """Roda uma função de rede em segundo plano; devolve (resultado, mensagem_de_erro)."""
    concluido = Signal(object, str)

    def __init__(self, funcao, parent=None):
        super().__init__(parent)
        self._funcao = funcao

    def run(self):
        try:
            self.concluido.emit(self._funcao(), "")
        except ErroBusca as erro:
            self.concluido.emit(None, str(erro))
        except Exception:
            log.exception("Erro na busca online")
            self.concluido.emit(None, "Erro inesperado (detalhes no tagger.log).")


def _rotulo(texto, papel):
    lbl = QLabel(texto)
    lbl.setProperty("papel", papel)
    lbl.setWordWrap(True)
    return lbl


def _primeiro_valor(faixas, campo, valor):
    """Valor do campo na primeira faixa que o tem."""
    for faixa in faixas:
        if valor(faixa, campo):
            return valor(faixa, campo)
    return ""


class DialogoBusca(QDialog):
    def __init__(self, faixas, parent=None, cliente=None, valor=None):
        super().__init__(parent)
        self.faixas = list(faixas)
        self._cliente = cliente or ClienteMusicBrainz()
        self._valor = valor or (lambda faixa, campo: faixa.tags.get(campo, ""))
        self._fechado = False
        self._resultado = None
        self._trabalho = None
        self._candidatos = []
        self.setWindowTitle("Buscar tags online")
        self.setMinimumSize(560, 460)

        self.ed_artista = QLineEdit(_primeiro_valor(self.faixas, "albumartist", self._valor)
                                  or _primeiro_valor(self.faixas, "artist", self._valor))
        self.ed_album = QLineEdit(_primeiro_valor(self.faixas, "album", self._valor))
        self.ed_titulo = QLineEdit(_primeiro_valor(self.faixas, "title", self._valor) if len(self.faixas) == 1 else "")
        for ed in (self.ed_artista, self.ed_album, self.ed_titulo):
            ed.returnPressed.connect(self.buscar)
        form = QFormLayout()
        form.addRow("Artista", self.ed_artista)
        form.addRow("Álbum", self.ed_album)
        form.addRow("Título (se não houver álbum)", self.ed_titulo)

        self.btn_buscar = QPushButton("Buscar")
        self.btn_buscar.clicked.connect(self.buscar)
        self.lista = QListWidget()
        self.lista.itemSelectionChanged.connect(self._atualizar)
        self.lista.itemDoubleClicked.connect(lambda _item: self.aplicar())
        self.estado = _rotulo("Dados do MusicBrainz e capas do Cover Art Archive.", "ajuda")
        self.ck_capa = QCheckBox("Baixar a capa também")
        self.ck_capa.setChecked(True)

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
        v.addLayout(form)
        v.addWidget(self.btn_buscar, alignment=Qt.AlignRight)
        v.addWidget(self.lista, 1)
        v.addWidget(self.estado)
        v.addLayout(rodape)
        self._atualizar()

    # ------------------------------------------------------------ interface
    def _ocupado(self):
        return self._trabalho is not None and self._trabalho.isRunning()

    def _atualizar(self):
        livre = not self._ocupado()
        self.btn_buscar.setEnabled(livre)
        self.btn_aplicar.setEnabled(livre and bool(self.lista.selectedItems()))

    def _mensagem(self, texto):
        self.estado.setText(texto)

    def _executar(self, funcao, ao_concluir, texto):
        self._mensagem(texto)
        self._trabalho = Trabalhador(funcao, self)
        self._trabalho.concluido.connect(ao_concluir)
        self._trabalho.finished.connect(self._atualizar)
        self._trabalho.start()
        self._atualizar()

    # ------------------------------------------------------------ busca
    def buscar(self):
        if self._ocupado():
            return
        artista, album, titulo = (e.text() for e in (self.ed_artista, self.ed_album, self.ed_titulo))
        self._executar(lambda: self._cliente.buscar_releases(artista, album, titulo),
                       self._buscou, "Buscando...")

    def _buscou(self, candidatos, erro):
        if self._fechado:
            return
        self.lista.clear()
        self._candidatos = candidatos or []
        if erro:
            self._mensagem(erro)
            return
        for candidato in self._candidatos:
            item = QListWidgetItem(candidato.descricao)
            item.setData(Qt.UserRole, candidato)
            self.lista.addItem(item)
        if self._candidatos:
            self.lista.setCurrentRow(0)
            self._mensagem(f"{len(self._candidatos)} resultado(s). Escolha o álbum certo.")
        else:
            self._mensagem("Nenhum resultado. Tente outro nome.")

    # ------------------------------------------------------------ aplicar
    def aplicar(self):
        itens = self.lista.selectedItems()
        if self._ocupado() or not itens:
            return
        candidato = itens[0].data(Qt.UserRole)
        com_capa = self.ck_capa.isChecked()

        def trabalho():
            release = self._cliente.detalhar_release(candidato.mbid)
            capa = self._cliente.baixar_capa(candidato.mbid) if com_capa else None
            return release, capa

        self._executar(trabalho, self._detalhou, "Baixando dados do álbum...")

    def _detalhou(self, dados, erro):
        if self._fechado:
            return
        if erro:
            self._mensagem(erro)
            return
        release, capa = dados
        alteracoes, casadas, sem_par = analisar(self.faixas, release, valor=self._valor)
        if not casadas:
            self._mensagem("Nenhuma das faixas casa com esse álbum (confira título e número da faixa).")
            return
        if not alteracoes and not capa:
            self._mensagem("Nada a alterar: as faixas já têm esses dados.")
            return
        self._resultado = Resultado(alteracoes, capa, casadas, sem_par)
        self.accept()

    def resultado(self):
        """Resultado (alteracoes, capa) após exec() aceito; None se cancelado."""
        return self._resultado

    def done(self, codigo):
        self._fechado = True
        trabalho = self._trabalho
        if trabalho is not None and trabalho.isRunning():
            # não espera (travaria a janela): solta a thread, que termina sozinha
            trabalho.concluido.disconnect()
            trabalho.finished.disconnect()
            trabalho.setParent(None)
            _ORFAOS.add(trabalho)
            trabalho.finished.connect(lambda: (_ORFAOS.discard(trabalho), trabalho.deleteLater()))
        super().done(codigo)
