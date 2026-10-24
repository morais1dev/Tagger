"""Janela de busca online (offscreen): fontes falsas ou clientes com HTTP simulado, nunca a rede."""

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from tagger.nucleo import busca, discogs, lastfm, online  # noqa: E402
from tagger.nucleo.busca import ErroBusca, NAO_ENCONTRADO  # noqa: E402
from tagger.nucleo.metadata import Faixa  # noqa: E402

from tests.test_online import (  # noqa: E402
    INFO, TOP, TOKEN, VINIL, BUSCA_DISCOGS, Rede, Resposta, limitador_falso,
)


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def esperar(app, condicao, limite=5):
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()
    assert condicao()


def faixa(nome, **tags):
    return Faixa(caminho=Path(nome), tags=tags)


def fonte_discogs(respostas):
    lim, _ = limitador_falso()
    from tagger.gui.busca_online import FonteDiscogs
    return FonteDiscogs(discogs.ClienteDiscogs(TOKEN, Rede(respostas), lim, online.Cache(10 ** 6)))


def fonte_lastfm(respostas):
    lim, _ = limitador_falso()
    from tagger.gui.busca_online import FonteLastfm
    return FonteLastfm(lastfm.ClienteLastfm("chave-lastfm-0123456789", Rede(respostas), lim, online.Cache(10 ** 6)))


class MusicBrainzVazio:
    nome, tem_capa = "musicbrainz", True

    def buscar(self, *termos):
        raise ErroBusca(NAO_ENCONTRADO)


def dialogo(fontes, faixas=None, **kw):
    from tagger.gui.busca_online import DialogoBuscaOnline
    faixas = faixas or [faixa("1.mp3", title="Abertura", artist="Banda", album="Disco Raro")]
    todas = {"musicbrainz": MusicBrainzVazio(), "discogs": None, "lastfm": None, **fontes}
    return DialogoBuscaOnline(faixas, fontes=todas, **kw)


def test_servico_sem_credencial_fica_desabilitado_com_dica(app):
    from tagger.gui.busca_online import SEM_CHAVE
    dlg = dialogo({})
    assert not dlg.botoes_fonte["discogs"].isEnabled() and not dlg.botoes_fonte["lastfm"].isEnabled()
    assert dlg.botoes_fonte["lastfm"].toolTip() == SEM_CHAVE["lastfm"]
    assert not dlg.ck_alternativa.isEnabled()
    dlg.reject()


def test_estados_da_janela_principal_desabilitam_com_a_dica_dela(app):
    estados = {"discogs": SimpleNamespace(disponivel=False, dica="Configure o token")}
    dlg = dialogo({"discogs": fonte_discogs({})}, estados=estados)
    assert not dlg.botoes_fonte["discogs"].isEnabled()
    assert dlg.botoes_fonte["discogs"].toolTip() == "Configure o token"
    dlg.reject()


def test_fluxo_discogs_previa_atribuicao_e_resultado(app):
    dlg = dialogo({"discogs": fonte_discogs({"/database/search?": Resposta(BUSCA_DISCOGS),
                                             "/releases/123": Resposta(VINIL)})}, fonte_inicial="discogs")
    assert dlg.fonte == "discogs"
    dlg.buscar()
    esperar(app, lambda: dlg.lista.count() == 1 and dlg.previa.rowCount() > 0)
    campos = {dlg.previa.item(i, 1).text(): dlg.previa.item(i, 3).text() for i in range(dlg.previa.rowCount())}
    assert campos["Faixa"] == "1/4" and campos["Gravadora"] == "Selo Independente"
    assert "Data provided by Discogs." in dlg.atribuicao.text()
    assert 'href="https://www.discogs.com/release/123-Banda-Disco-Raro"' in dlg.atribuicao.text()
    assert "nofollow" not in dlg.atribuicao.text()
    assert not dlg.ck_capa.isVisibleTo(dlg)                      # capa só do Cover Art Archive
    dlg.aplicar()
    res = dlg.resultado()
    assert res is not None and res.capa is None
    assert res.alteracoes[0][1]["tracknumber"] == "1/4" and res.alteracoes[0][1]["date"] == "1977"


def test_musicbrainz_sem_resultado_usa_o_discogs(app):
    dlg = dialogo({"discogs": fonte_discogs({"/database/search?": Resposta(BUSCA_DISCOGS),
                                             "/releases/123": Resposta(VINIL)})})
    assert dlg.fonte == "musicbrainz" and dlg.ck_alternativa.isChecked()
    dlg.buscar()
    esperar(app, lambda: dlg.lista.count() == 1)
    assert "Discogs" in dlg.estado.text() and "Data provided by Discogs." in dlg.atribuicao.text()
    esperar(app, lambda: dlg.btn_aplicar.isEnabled())
    dlg.reject()


def test_lastfm_versoes_pelo_playcount_e_links(app):
    dlg = dialogo({"lastfm": fonte_lastfm({"getTopAlbums": Resposta(TOP), "album.getInfo": Resposta(INFO)})},
                  faixas=[faixa("2.mp3", title="segunda", artist="Banda", album="Album X")], fonte_inicial="lastfm")
    dlg.buscar()
    esperar(app, lambda: dlg.lista.count() == 3 and dlg.previa.rowCount() > 0)
    textos = [dlg.lista.item(i).text() for i in range(dlg.lista.count())]
    assert textos[0].startswith("Banda — Album X  (9.000") and "mais scrobblado" in textos[0]
    texto = dlg.atribuicao.text()
    assert "powered by AudioScrobbler" in texto
    assert 'href="https://www.last.fm/music/Banda"' in texto and 'href="https://www.last.fm/music/Banda/Album+X"' in texto
    dlg.aplicar()
    assert dlg.resultado().alteracoes[0][1]["title"] == "Segunda"


def test_erro_mostrado_sem_credencial(app):
    class Vaza:
        nome, tem_capa = "discogs", False

        def buscar(self, *termos):
            raise ErroBusca("falhou com api_key=SEGREDO123456789012345")

    dlg = dialogo({"discogs": Vaza()}, fonte_inicial="discogs")
    dlg.buscar()
    esperar(app, lambda: "falhou" in dlg.estado.text())
    assert "SEGREDO" not in dlg.estado.text()
    dlg.reject()

    class VazaLiteral(Vaza):
        def buscar(self, *termos):
            raise ErroBusca("falhou com tokenColado0123456789abcdef no meio")

    dlg = dialogo({"discogs": VazaLiteral()}, fonte_inicial="discogs",
                  config={"discogs_token": "tokenColado0123456789abcdef"})
    dlg.buscar()
    esperar(app, lambda: "falhou" in dlg.estado.text())
    assert "tokenColado" not in dlg.estado.text()
    dlg.reject()


def test_link_inseguro_vira_texto():
    from tagger.gui.busca_online import _link
    assert _link("x", "javascript:alert(1)", discogs.DOMINIOS) == "x"
    assert _link("<b>", "https://www.discogs.com/r", discogs.DOMINIOS) == '<a href="https://www.discogs.com/r">&lt;b&gt;</a>'


def test_sobre_tem_o_aviso_do_discogs():
    from tagger.gui.sobre import texto_sobre
    assert "not affiliated with, sponsored or endorsed by Discogs" in texto_sobre()
    assert "Zink Media, LLC" in texto_sobre()


def test_criar_fontes_sem_credencial(monkeypatch, tmp_path):
    from tagger.gui import busca_online
    monkeypatch.setattr(busca_online.credenciais, "lastfm_api_key", lambda v: None)
    monkeypatch.setattr(busca_online.credenciais, "discogs_authorization", lambda v: "Discogs token=" + v if v else None)
    fontes = busca_online.criar_fontes({"lastfm_api_key": "", "discogs_token": "tok"}, tmp_path)
    assert fontes["lastfm"] is None and fontes["discogs"] is not None
    assert isinstance(fontes["musicbrainz"].cliente, busca.ClienteMusicBrainz)


class FonteContada:
    """Cada busca devolve um candidato NOVO; o detalhe diz de qual busca ele veio."""
    nome, tem_capa = "discogs", False

    def __init__(self):
        self.buscas = 0

    def buscar(self, *termos):
        self.buscas += 1
        return [(f"Resultado {self.buscas}", SimpleNamespace(n=self.buscas))]

    def detalhar(self, candidato):
        return SimpleNamespace(n=candidato.n)

    def analisar(self, faixas, release, valor):
        return [(faixas[0], {"album": f"Album {release.n}"})], list(faixas), []

    def atribuicao(self, release):
        return ""


def test_duas_buscas_seguidas_nao_reaproveitam_a_previa(app):
    fonte = FonteContada()
    dlg = dialogo({"discogs": fonte}, fonte_inicial="discogs")
    for n in (1, 2):
        dlg.buscar()
        esperar(app, lambda: dlg.lista.count() == 1 and dlg.lista.item(0).text() == f"Resultado {n}"
                and dlg.previa.rowCount() == 1 and not dlg._ocupado())
        assert dlg.previa.item(0, 3).text() == f"Album {n}"
    dlg.aplicar()
    assert dlg.resultado().alteracoes[0][1] == {"album": "Album 2"}


def test_detalhe_guardado_de_outro_objeto_com_o_mesmo_id_e_ignorado(app):
    dlg = dialogo({"discogs": FonteContada()}, fonte_inicial="discogs")
    novo, antigo = SimpleNamespace(), SimpleNamespace()
    dlg._detalhes[id(novo)] = (antigo, "release velho", [], [], [])     # como se o id tivesse sido reaproveitado
    assert dlg._detalhe(novo) is None
    dlg._detalhes[id(novo)] = (novo, "release", [], [], [])
    assert dlg._detalhe(novo) == ("release", [], [], [])
    dlg.reject()


def test_servicos_mudaram_com_a_janela_aberta(app, monkeypatch):
    from tagger.gui import busca_online
    dlg = dialogo({"discogs": FonteContada()}, fonte_inicial="discogs")
    dlg.atualizar_servicos({"discogs": SimpleNamespace(disponivel=False, dica="Sem token agora")}, {})
    assert not dlg.botoes_fonte["discogs"].isEnabled() and dlg.fonte == "musicbrainz"
    assert dlg.botoes_fonte["discogs"].toolTip() == "Sem token agora" and not dlg.ck_alternativa.isEnabled()
    monkeypatch.setattr(busca_online, "criar_fontes", lambda config, pasta: {"discogs": FonteContada(),
                                                                             "lastfm": None, "musicbrainz": None})
    dlg.atualizar_servicos({"discogs": SimpleNamespace(disponivel=True, dica=None)},
                           {"discogs_token": "tokenNovo0123456789abcdef"})
    assert dlg.botoes_fonte["discogs"].isEnabled() and dlg.ck_alternativa.isEnabled()
    assert "tokenNovo0123456789abcdef" in dlg._conhecidas
    dlg.reject()
