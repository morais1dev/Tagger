"""JanelaPrincipal (offscreen): as opções de gravação das Configurações chegam ao núcleo.

O QSettings é trocado por um arquivo .ini em tmp_path: as configurações reais do usuário nunca são tocadas."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from tagger.gui import janela as modulo_janela  # noqa: E402
from tagger.nucleo.metadata import OpcoesGravacao  # noqa: E402


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


def test_janela_usa_o_historico_do_nucleo(janela):
    """Depois da ligação ao núcleo: sem histórico, desfazer/refazer ficam desabilitados e o Esc não faz nada."""
    janela._atualizar_estado()
    assert janela.historico.desfazer == [] and janela.historico.refazer == [] and janela.historico.pendente is None
    assert not janela.btn_desfazer.isEnabled() and not janela.btn_refazer.isEnabled()
    janela.historico.registrar_renomeacao([("a.mp3", "b.mp3")])
    janela._atualizar_estado()
    assert janela.btn_desfazer.isEnabled()
