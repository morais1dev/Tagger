"""JanelaPrincipal (offscreen): as opções de gravação das Configurações chegam ao núcleo.

O QSettings é trocado por um arquivo .ini em tmp_path: as configurações reais do usuário nunca são tocadas."""

import pytest
from PySide6.QtCore import QSettings

from tagger.gui import janela as modulo_janela
from tagger.nucleo.metadata import OpcoesGravacao


@pytest.fixture
def janela(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    ini = str(tmp_path / "config.ini")
    monkeypatch.setattr(modulo_janela, "QSettings", lambda *a: QSettings(ini, QSettings.IniFormat))
    prefs = QSettings(ini, QSettings.IniFormat)
    prefs.setValue("config/versao_id3", 4)
    prefs.setValue("config/multivalor", False)
    prefs.setValue("config/remover_id3v1", True)
    prefs.setValue("config/lado_max_capa", 640)
    prefs.sync()
    j = modulo_janela.JanelaPrincipal()
    yield j
    j.rascunho.descartar()           # sem pendências, o closeEvent não abre diálogo
    j.close()
    j.deleteLater()
    app.processEvents()


def test_construir_a_janela_aplica_a_config_da_capa(janela):
    assert janela.painel.lado_max_capa == 640


def test_opcoes_gravacao_vem_da_config(janela):
    assert janela.opcoes_gravacao() == OpcoesGravacao(versao_id3=4, multivalor=False, remover_id3v1=True)
    janela.config.update(versao_id3=3, multivalor=True, remover_id3v1=False)
    assert janela.opcoes_gravacao() == OpcoesGravacao()


def test_salvar_usa_as_opcoes_da_config(janela, monkeypatch):
    chamadas = []

    def gravar(trabalhos, progresso=None, mtimes=None, opcoes=None):
        chamadas.append(opcoes)
        return [], {}, []

    monkeypatch.setattr(modulo_janela, "executar_salvamento", gravar)
    monkeypatch.setattr(janela, "_trabalhos_conferidos", lambda: ([("x.mp3", {"title": "A"}, None)], {}))
    janela.rascunho.tags["x.mp3"] = {"title": "A"}
    janela.salvar(sincrono=True)
    assert chamadas == [OpcoesGravacao(versao_id3=4, multivalor=False, remover_id3v1=True)]
