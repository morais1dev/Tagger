"""Interface sem tela (QT_QPA_PLATFORM=offscreen, pytest-qt): abrir pasta, editar, salvar, reler e fechar.

Sem rede e sem tocar nas configurações reais: o QSettings da janela vai para um .ini temporário e o
QMessageBox é trocado por um clique automático (nunca abre diálogo de verdade).
"""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtCore import QSettings, Qt  # noqa: E402
from PySide6.QtWidgets import QMessageBox  # noqa: E402

from tagger.gui import janela as modulo_janela  # noqa: E402
from tagger.gui.tabela import CHAVES, PAPEL_ORDEM  # noqa: E402
from tagger.nucleo import metadata  # noqa: E402

from conftest import criar_mp3  # noqa: E402

COL_TITULO, COL_ARTISTA, COL_ESTADO = CHAVES.index("title"), CHAVES.index("artist"), CHAVES.index("estado")


@pytest.fixture
def pasta_musicas(tmp_path):
    """Pasta com 3 MP3 sem tags."""
    pasta = tmp_path / "album"
    pasta.mkdir()
    for nome in ("01 - a.mp3", "02 - b.mp3", "03 - c.mp3"):
        criar_mp3(pasta / nome)
    return pasta


@pytest.fixture
def janela(qtbot, tmp_path, monkeypatch):
    """JanelaPrincipal real, com configurações num .ini temporário."""
    ini = str(tmp_path / "config" / "tagger.ini")
    monkeypatch.setattr(modulo_janela, "QSettings", lambda *_a: QSettings(ini, QSettings.IniFormat))
    j = modulo_janela.JanelaPrincipal()
    j.show()                         # sem qtbot.addWidget: ele fecharia a janela antes de eu limpar o rascunho
    yield j
    j.rascunho.descartar()           # o fechamento do teste nunca pergunta nada
    j.close()


@pytest.fixture
def clicar(monkeypatch):
    """Troca QMessageBox.exec por um clique no botão pedido; devolve a lista das perguntas feitas."""
    class Perguntas(list):
        def escolher(self, botao):
            escolha["botao"] = botao

    perguntas = Perguntas()
    escolha = {"botao": QMessageBox.Cancel}

    def exec_falso(caixa):
        perguntas.append((caixa.windowTitle(), caixa.text()))
        caixa.button(escolha["botao"]).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", exec_falso)
    return perguntas


def abrir(qtbot, janela, pasta):
    janela.carregar_caminhos([str(pasta)], substituir=True)
    qtbot.waitUntil(lambda: janela._carregador is None and len(janela.modelo.faixas) > 0, timeout=10000)


def editar(janela, linha, coluna, texto):
    modelo = janela.modelo
    assert modelo.setData(modelo.index(linha, coluna), texto, Qt.EditRole)


def texto(janela, linha, coluna):
    return janela.modelo.data(janela.modelo.index(linha, coluna), Qt.DisplayRole)


def tags_no_disco(caminho):
    return metadata.carregar(caminho).tags


# ---------------------------------------------------------------------------

def test_abrir_pasta_mostra_as_faixas_na_tabela(qtbot, janela, pasta_musicas):
    assert janela.telas.currentIndex() == 0                      # tela vazia antes de abrir
    abrir(qtbot, janela, pasta_musicas)
    assert janela.telas.currentIndex() == 1
    assert [f.nome for f in janela.modelo.faixas] == ["01 - a.mp3", "02 - b.mp3", "03 - c.mp3"]
    assert janela.modelo.rowCount() == 3
    assert janela.pasta_atual == pasta_musicas
    assert janela.rascunho.vazio
    assert texto(janela, 0, COL_TITULO) == "01 - a.mp3"           # sem título, a tabela mostra o nome do arquivo


def test_pasta_sem_audio_avisa_e_nao_abre(qtbot, janela, tmp_path):
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    janela.carregar_caminhos([str(vazia)], substituir=True)
    assert janela.modelo.rowCount() == 0 and janela.telas.currentIndex() == 0


def test_editar_campo_vira_pendencia_na_tabela(qtbot, janela, pasta_musicas):
    abrir(qtbot, janela, pasta_musicas)
    arquivo = janela.modelo.faixas[1].caminho
    editar(janela, 1, COL_ARTISTA, "Banda Teste")

    assert texto(janela, 1, COL_ARTISTA) == "Banda Teste"        # a tabela já mostra o valor novo
    assert janela.rascunho.tem(arquivo) and janela.rascunho.tem_campo(arquivo, "artist")
    assert len(janela.rascunho) == 1                              # só esse arquivo tem pendência
    assert janela.modelo.data(janela.modelo.index(1, COL_ESTADO), PAPEL_ORDEM) == 1
    assert janela.modelo.data(janela.modelo.index(0, COL_ESTADO), PAPEL_ORDEM) == 0
    assert "não salvo" in janela.modelo.data(janela.modelo.index(1, COL_ESTADO), Qt.ToolTipRole)
    assert tags_no_disco(arquivo).get("artist", "") == ""         # nada foi gravado ainda


def test_valor_invalido_nao_entra_no_rascunho(qtbot, janela, pasta_musicas):
    abrir(qtbot, janela, pasta_musicas)
    coluna_ano = CHAVES.index("date")
    assert not janela.modelo.setData(janela.modelo.index(0, coluna_ano), "ano ruim", Qt.EditRole)
    assert janela.rascunho.vazio


def test_salvar_grava_e_rele_do_disco(qtbot, janela, pasta_musicas):
    abrir(qtbot, janela, pasta_musicas)
    arquivo = janela.modelo.faixas[0].caminho
    editar(janela, 0, COL_TITULO, "Primeira")
    editar(janela, 0, COL_ARTISTA, "Banda Teste")

    assert janela.salvar() is True
    qtbot.waitUntil(lambda: janela.rascunho.vazio and janela._salvador is None, timeout=10000)

    tags = tags_no_disco(arquivo)                                 # releitura de verdade, do arquivo
    assert tags["title"] == "Primeira" and tags["artist"] == "Banda Teste"
    assert texto(janela, 0, COL_TITULO) == "Primeira"             # e a tabela segue mostrando
    assert janela.modelo.data(janela.modelo.index(0, COL_ESTADO), PAPEL_ORDEM) == 0
    assert tags_no_disco(janela.modelo.faixas[1].caminho).get("title", "") == ""   # outras faixas intactas


def test_recarregar_do_disco_traz_o_que_foi_salvo(qtbot, janela, pasta_musicas):
    abrir(qtbot, janela, pasta_musicas)
    editar(janela, 2, COL_ARTISTA, "Outra Banda")
    janela.salvar()
    qtbot.waitUntil(lambda: janela.rascunho.vazio and janela._salvador is None, timeout=10000)
    abrir(qtbot, janela, pasta_musicas)                           # abrir de novo = ler tudo do disco
    assert texto(janela, 2, COL_ARTISTA) == "Outra Banda" and janela.rascunho.vazio


def test_fechar_com_pendencia_pergunta_e_cancelar_mantem_a_janela(qtbot, janela, pasta_musicas, clicar):
    abrir(qtbot, janela, pasta_musicas)
    editar(janela, 0, COL_ARTISTA, "Banda Teste")
    clicar.escolher(QMessageBox.Cancel)

    assert janela.close() is False
    assert janela.isVisible() and len(janela.rascunho) == 1       # nada se perdeu
    [(titulo, mensagem)] = clicar
    assert titulo == "Alterações não salvas" and "1 arquivo" in mensagem


def test_fechar_e_descartar_nao_grava(qtbot, janela, pasta_musicas, clicar):
    abrir(qtbot, janela, pasta_musicas)
    arquivo = janela.modelo.faixas[0].caminho
    editar(janela, 0, COL_ARTISTA, "Banda Teste")
    clicar.escolher(QMessageBox.Discard)

    assert janela.close() is True
    assert len(clicar) == 1 and janela.rascunho.vazio
    assert tags_no_disco(arquivo).get("artist", "") == ""


def test_fechar_e_salvar_grava_antes_de_fechar(qtbot, janela, pasta_musicas, clicar):
    abrir(qtbot, janela, pasta_musicas)
    arquivo = janela.modelo.faixas[0].caminho
    editar(janela, 0, COL_ARTISTA, "Banda Teste")
    clicar.escolher(QMessageBox.Save)

    assert janela.close() is True
    assert tags_no_disco(arquivo)["artist"] == "Banda Teste"


def test_fechar_sem_pendencia_nao_pergunta(qtbot, janela, pasta_musicas, clicar):
    abrir(qtbot, janela, pasta_musicas)
    assert janela.close() is True
    assert list(clicar) == []


def test_abrir_outra_pasta_com_pendencia_tambem_pergunta(qtbot, janela, pasta_musicas, tmp_path, clicar):
    abrir(qtbot, janela, pasta_musicas)
    editar(janela, 0, COL_ARTISTA, "Banda Teste")
    outra = tmp_path / "outra"
    outra.mkdir()
    criar_mp3(outra / "x.mp3")
    clicar.escolher(QMessageBox.Cancel)
    janela.carregar_caminhos([str(outra)], substituir=True)
    assert len(clicar) == 1
    assert [f.nome for f in janela.modelo.faixas][0] == "01 - a.mp3"     # cancelou: continua na pasta antiga
