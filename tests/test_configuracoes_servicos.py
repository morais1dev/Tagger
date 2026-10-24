"""Aba Serviços online: a chave colada só chega à janela principal no OK (nunca pela prévia ao vivo)."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

CHAVE = "chave-colada-0123456789"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def config():
    from tagger.gui.config import PADROES
    return deepcopy(PADROES)


def test_previa_ao_vivo_nunca_leva_a_chave(app, config):
    from tagger.gui.configuracoes import DialogoConfiguracoes
    dlg = DialogoConfiguracoes(config)
    emitidos = []
    dlg.mudou.connect(emitidos.append)
    dlg.ed_lastfm.setText(CHAVE)
    dlg.ed_discogs.setText("token-colado-0123456789")
    dlg.ck_agrupar.setChecked(not config["agrupar_por_album"])    # outra mudança, que vai para a prévia
    dlg._restaurar_padroes()
    assert emitidos
    assert all(c["lastfm_api_key"] == "" and c["discogs_token"] == "" for c in emitidos)
    assert dlg.credenciais_aceitas() == {"lastfm_api_key": CHAVE, "discogs_token": "token-colado-0123456789"}


class _Sinal:
    def __init__(self):
        self.emitidos = []

    def emit(self, valor):
        self.emitidos.append(valor)


def _abrir(monkeypatch, config, aceitar):
    """Roda JanelaPrincipal.abrir_configuracoes com uma janela falsa; o diálogo cola a chave e fecha."""
    from tagger.gui import janela
    from tagger.gui.configuracoes import DialogoConfiguracoes
    salvos = []

    class Dialogo(DialogoConfiguracoes):
        def __init__(self, cfg, parent=None):
            super().__init__(cfg)

        def exec(self):
            self.ed_lastfm.setText(CHAVE)
            self.ck_agrupar.setChecked(True)
            self.accept() if aceitar else self.reject()
            return 0

    monkeypatch.setattr(janela, "DialogoConfiguracoes", Dialogo)
    monkeypatch.setattr(janela, "salvar_config", lambda settings, cfg: salvos.append(deepcopy(cfg)))
    falsa = SimpleNamespace(config=config, settings=None, _pendente=None, servicos_mudaram=_Sinal())
    falsa.aplicar_config = lambda cfg: setattr(falsa, "_pendente", dict(cfg))
    falsa._aplicar_config_pendente = lambda: falsa._pendente and setattr(falsa, "config", falsa._pendente)
    falsa.estado_servicos = lambda: janela.estado_servicos(falsa.config)
    janela.JanelaPrincipal.abrir_configuracoes(falsa)
    return falsa, salvos


def test_cancelar_nao_deixa_a_chave_na_sessao(app, config, monkeypatch):
    falsa, salvos = _abrir(monkeypatch, config, aceitar=False)
    assert falsa.config["lastfm_api_key"] == ""
    assert falsa.config["agrupar_por_album"] is False       # a prévia também volta
    assert salvos == [] and falsa.servicos_mudaram.emitidos == []


def test_ok_aplica_salva_e_avisa(app, config, monkeypatch):
    falsa, salvos = _abrir(monkeypatch, config, aceitar=True)
    assert falsa.config["lastfm_api_key"] == CHAVE
    assert salvos and salvos[-1]["lastfm_api_key"] == CHAVE
    [estado] = falsa.servicos_mudaram.emitidos
    assert estado["lastfm"].disponivel
