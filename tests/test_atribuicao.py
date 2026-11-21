"""Conformidade com o Discogs: atribuição com link na busca, aviso no Sobre; e limpeza da config antiga.

Offscreen e sem rede (HTTP simulado).
"""

import re

import pytest

pytest.importorskip("PySide6")

from tagger.nucleo import discogs  # noqa: E402

from tests.test_busca_online import (  # noqa: E402
    BUSCA_DISCOGS, VINIL, Resposta, app, dialogo, esperar, fonte_discogs,
)

URL_RELEASE = "https://www.discogs.com/release/123-Banda-Disco-Raro"


def test_atribuicao_do_discogs_tem_link_para_o_release(app):
    dlg = dialogo({"discogs": fonte_discogs({"/database/search?": Resposta(BUSCA_DISCOGS),
                                             "/releases/123": Resposta(VINIL)})}, fonte_inicial="discogs")
    dlg.buscar()
    esperar(app, lambda: dlg.lista.count() == 1 and dlg.previa.rowCount() > 0)
    texto = dlg.atribuicao.text()
    assert discogs.ATRIBUICAO == "Data provided by Discogs." and discogs.ATRIBUICAO in texto
    assert re.findall(r'href="([^"]+)"', texto) == [URL_RELEASE]
    assert dlg.atribuicao.openExternalLinks()
    dlg.reject()


def test_atribuicao_do_discogs_aparece_antes_de_escolher_o_release(app):
    dlg = dialogo({"discogs": fonte_discogs({})}, fonte_inicial="discogs")
    assert discogs.ATRIBUICAO in dlg.atribuicao.text()
    assert 'href="https://www.discogs.com"' in dlg.atribuicao.text()
    dlg.reject()


def test_sobre_tem_o_aviso_completo_do_discogs():
    from tagger.gui.sobre import texto_sobre
    assert "This application uses Discogs' API but is not affiliated with" in texto_sobre().replace("&#x27;", "'")


def test_f1_e_o_atalho_do_sobre_e_o_dialogo_mostra_o_aviso(app):
    from PySide6.QtWidgets import QLabel
    from tagger.gui import janela
    from tagger.gui.sobre import DialogoSobre

    assert re.search(r'"Sobre o Tagger", \["F1"\]', open(janela.__file__, encoding="utf-8").read())
    dlg = DialogoSobre()
    assert "not affiliated with" in " ".join(r.text() for r in dlg.findChildren(QLabel))
    dlg.reject()


def test_carregar_config_remove_a_chave_antiga_do_lastfm(tmp_path):
    from PySide6.QtCore import QSettings
    from tagger.gui.config import carregar_config

    settings = QSettings(str(tmp_path / "t.ini"), QSettings.IniFormat)
    settings.setValue("config/lastfm_api_key", "FAKE-CHAVE-ANTIGA-0123456789")
    settings.setValue("config/discogs_token", "FAKE-TOKEN-0123456789abcdef")
    config = carregar_config(settings)
    assert not settings.contains("config/lastfm_api_key")
    assert "lastfm_api_key" not in config
    assert settings.value("config/discogs_token") == "FAKE-TOKEN-0123456789abcdef"      # o resto fica
    carregar_config(settings)                                                          # sem a chave: não falha
