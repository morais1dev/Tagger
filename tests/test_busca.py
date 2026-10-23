"""Busca online: HTTP sempre simulado, nunca usa a rede."""

import json
import urllib.error
from pathlib import Path

import pytest

from tagger.nucleo import busca
from tagger.nucleo.busca import ClienteMusicBrainz, ErroBusca, Limitador
from tagger.nucleo.metadata import Faixa

PNG = b"\x89PNG\r\n\x1a\n" + bytes(20)


class Resposta:
    def __init__(self, corpo, tipo="application/json"):
        self.corpo = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
        self.headers = {"Content-Type": tipo}

    def read(self, n=-1):
        return self.corpo[:n] if n >= 0 else self.corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Rede:
    """Substitui urlopen: responde por trecho da URL e guarda o que foi pedido."""
    def __init__(self, respostas):
        self.respostas, self.pedidos = respostas, []

    def __call__(self, pedido, timeout=None):
        self.pedidos.append((pedido, timeout))
        for trecho, resposta in self.respostas.items():
            if trecho in pedido.full_url:
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta
        raise AssertionError(f"URL inesperada: {pedido.full_url}")


def cliente(respostas):
    rede = Rede(respostas)
    return ClienteMusicBrainz(rede, Limitador(lambda s: None, lambda: 0.0)), rede


BUSCA = {"releases": [{
    "id": "abc", "title": "Album X", "score": 100, "date": "1999-05-03", "country": "BR", "track-count": 2,
    "artist-credit": [{"name": "Banda", "joinphrase": " feat. ", "artist": {"name": "Banda"}},
                      {"name": "Convidado", "joinphrase": "", "artist": {"name": "Convidado"}}],
    "label-info": [{"label": {"name": "Selo"}}]}, {"title": "sem id"}]}

DETALHE = {"id": "abc", "title": "Album X", "date": "1999-05", "artist-credit": [{"name": "Banda"}],
           "genres": [{"name": "rock", "count": 1}], "release-group": {"genres": [{"name": "indie rock", "count": 5}, {"name": "r&b", "count": 3}]},
           "media": [{"position": 1, "tracks": [
               {"position": 1, "title": "Primeira", "artist-credit": [{"name": "Banda"}]},
               {"position": 2, "title": "Segunda", "artist-credit": [{"name": "Banda"}]}]}]}


def faixa(nome="a.mp3", **tags):
    return Faixa(caminho=Path(nome), tags=tags)


def release():
    c, _ = cliente({"/release/abc?": Resposta(DETALHE)})
    return c.detalhar_release("abc")


def test_buscar_releases_monta_candidatos_e_user_agent():
    c, rede = cliente({"/release?": Resposta(BUSCA)})
    candidatos = c.buscar_releases('Ba"nda', "Album X")
    assert len(candidatos) == 1
    cand = candidatos[0]
    assert (cand.mbid, cand.artista, cand.gravadora, cand.faixas) == ("abc", "Banda feat. Convidado", "Selo", 2)
    pedido, timeout = rede.pedidos[0]
    assert pedido.get_header("User-agent").startswith("Tagger/")
    assert "%5C%22" in pedido.full_url          # aspas escapadas na consulta
    assert timeout == busca.TIMEOUT


def test_buscar_sem_termos_e_erro():
    c, _ = cliente({})
    with pytest.raises(ErroBusca):
        c.buscar_releases("", "  ")


def test_limite_de_uma_requisicao_por_segundo():
    esperas, tempo = [], [0.0]
    rede = Rede({"/release?": Resposta(BUSCA)})
    limitador = Limitador(esperas.append, lambda: tempo[0])
    c, c2 = ClienteMusicBrainz(rede, limitador), ClienteMusicBrainz(rede, limitador)   # instâncias dividem o limite
    c.buscar_releases("a", "b")
    assert esperas == []
    tempo[0] = 0.25
    c2.buscar_releases("a", "b")
    assert esperas == [pytest.approx(0.75)]


@pytest.mark.parametrize("erro,trecho", [
    (urllib.error.URLError("sem rede"), "conexão"),
    (TimeoutError(), "conexão"),
    (urllib.error.HTTPError("u", 503, "x", {}, None), "limitando"),
    (urllib.error.HTTPError("u", 500, "x", {}, None), "500"),
])
def test_erros_de_rede_viram_erro_busca(erro, trecho):
    c, _ = cliente({"/release?": erro})
    with pytest.raises(ErroBusca, match=trecho):
        c.buscar_releases("a", "b")


def test_resposta_que_nao_e_json():
    c, _ = cliente({"/release?": Resposta(b"<html>")})
    with pytest.raises(ErroBusca, match="inválida"):
        c.buscar_releases("a", "b")


def test_detalhar_release():
    r = release()
    assert (r.titulo, r.artista, r.data, r.generos) == ("Album X", "Banda", "1999-05", ["Indie Rock", "R&B", "Rock"])
    assert [(f.titulo, f.numero, f.total_disco) for f in r.faixas] == [("Primeira", 1, 2), ("Segunda", 2, 2)]


def test_baixar_capa():
    c, _ = cliente({"coverartarchive": Resposta(PNG, "image/png")})
    assert c.baixar_capa("abc") == (PNG, "image/png")


def test_capa_sem_tipo_usa_assinatura_e_404_vira_none():
    c, _ = cliente({"coverartarchive": Resposta(PNG, "application/octet-stream")})
    assert c.baixar_capa("abc")[1] == "image/png"
    c, _ = cliente({"coverartarchive": urllib.error.HTTPError("u", 404, "x", {}, None)})
    assert c.baixar_capa("abc") is None
    c, _ = cliente({"coverartarchive": Resposta(b"nao e imagem", "text/html")})
    assert c.baixar_capa("abc") is None


def test_montar_alteracoes_casa_por_titulo_e_numero():
    por_titulo = faixa("1.mp3", title="segunda!", tracknumber="9")
    por_numero = faixa("2.mp3", title="outro nome", tracknumber="1/12")
    sem_par = faixa("3.mp3", title="xyz")
    itens = {f.caminho.name: v for f, v in busca.montar_alteracoes([por_titulo, por_numero, sem_par], release())}
    assert itens["1.mp3"]["tracknumber"] == "2/2" and itens["1.mp3"]["title"] == "Segunda"
    assert itens["2.mp3"]["tracknumber"] == "1/2" and "title" not in itens["2.mp3"]   # só número + título diferente
    assert "3.mp3" not in itens                    # sem par: não recebe nem os campos do álbum
    assert itens["1.mp3"]["date"] == "1999-05" and itens["1.mp3"]["genre"] == "Indie Rock; R&B; Rock"


def test_montar_alteracoes_ignora_iguais_e_respeita_campos():
    r = release()
    completa = faixa(title="Primeira", artist="Banda", album="Album X", albumartist="Banda", date="1999-05",
                     genre="Indie Rock; R&B; Rock", tracknumber="1/2")
    assert busca.montar_alteracoes([completa], r) == []
    (_, valores), = busca.montar_alteracoes([faixa(title="Primeira")], r, campos={"album"})
    assert valores == {"album": "Album X"}


def test_so_numero_com_titulo_diferente_nao_troca_titulo():
    (_, valores), = busca.montar_alteracoes([faixa(title="Faixa totalmente outra", tracknumber="2")], release())
    assert "title" not in valores and valores["tracknumber"] == "2/2"
    (_, valores), = busca.montar_alteracoes([faixa(title="Segunda parte", tracknumber="2")], release())
    assert valores["title"] == "Segunda"


def release_dois_discos():
    c, _ = cliente({"/release/abc?": Resposta({
        "id": "abc", "title": "Duplo", "date": "2001", "artist-credit": [{"name": "Banda"}],
        "media": [{"position": d, "tracks": [{"position": 1, "title": "Intro"}, {"position": 2, "title": f"Faixa {d}"}]}
                  for d in (1, 2)]})})
    return c.detalhar_release("abc")


def test_titulos_repetidos_em_varios_discos_sao_1_para_1():
    r = release_dois_discos()
    a = faixa("a.mp3", title="Intro", discnumber="2", tracknumber="1")
    b = faixa("b.mp3", title="Intro", discnumber="1", tracknumber="1")
    c = faixa("c.mp3", title="Intro")                   # os dois "Intro" já foram usados
    pares = [(f.caminho.name, par and par.disco) for f, par in busca.casar_faixas([c, a, b], r)]
    assert pares == [("c.mp3", None), ("a.mp3", 2), ("b.mp3", 1)]
    d = faixa("d.mp3", title="Intro", discnumber="1", tracknumber="1")
    e = faixa("e.mp3", title="Intro", discnumber="1", tracknumber="1")
    f = faixa("f.mp3", title="Intro", discnumber="1", tracknumber="1")
    g = faixa("g.mp3", title="Intro", discnumber="1", tracknumber="1")
    usadas = [par for _, par in busca.casar_faixas([d, e, f, g], r) if par]
    assert len(usadas) == 2 and len({id(p) for p in usadas}) == 2     # só há dois "Intro"


def test_valor_usa_edicao_pendente():
    r = release()
    f = faixa(title="Primera", tracknumber="1")
    pendente = {"title": "Primeira"}
    valor = lambda fx, campo: pendente.get(campo, fx.tags.get(campo, ""))
    itens = busca.montar_alteracoes([f], r, valor=valor)
    assert "title" not in itens[0][1]                   # o usuário já corrigiu para "Primeira"
    assert busca.montar_alteracoes([f], r)[0][1]["title"] == "Primeira"


def test_analisar_separa_sem_par_e_capa_so_das_casadas():
    r = release()
    ok, fora = faixa("ok.mp3", title="Primeira"), faixa("fora.mp3", title="Outro album")
    itens, casadas, sem_par = busca.analisar([ok, fora], r)
    assert [f for f, _ in itens] == [ok] and casadas == [ok] and sem_par == [fora]
    res = busca.Resultado(itens, (b"x", "image/png"), casadas, sem_par)
    assert res.caminhos_capa == [ok.caminho] and res.alteradas == 1


def test_erro_do_caa_nao_cita_musicbrainz_e_http_exception():
    import http.client
    c, _ = cliente({"coverartarchive": urllib.error.HTTPError("u", 429, "x", {}, None)})
    with pytest.raises(ErroBusca, match="Cover Art Archive"):
        c.baixar_capa("abc")
    c, _ = cliente({"coverartarchive": http.client.IncompleteRead(b"")})
    with pytest.raises(ErroBusca, match="conexão"):
        c.baixar_capa("abc")


def test_varios_discos_preenche_discnumber():
    r = release()
    r.total_discos = 2
    r.faixas[1].disco = 2
    (_, valores), = busca.montar_alteracoes([faixa(title="Segunda")], r, campos={"discnumber"})
    assert valores == {"discnumber": "2/2"}


def test_resultado_acao_capa():
    assert busca.Resultado([], (b"x", "image/png")).acao_capa == ("definir", b"x", "image/png")
    assert busca.Resultado([]).acao_capa is None


def test_dialogo_fluxo_completo(monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from tagger.gui.busca import DialogoBusca
    app = QApplication.instance() or QApplication([])
    c, _ = cliente({"/release?": Resposta(BUSCA), "/release/abc?": Resposta(DETALHE),
                    "coverartarchive": Resposta(PNG, "image/png")})
    dlg = DialogoBusca([faixa("a.mp3", title="Primeira", artist="Banda", album="Album Velho")], cliente=c)
    assert dlg.ed_artista.text() == "Banda" and dlg.ed_album.text() == "Album Velho"
    dlg.buscar()
    dlg._trabalho.wait()
    app.processEvents()
    assert dlg.lista.count() == 1
    dlg.aplicar()
    dlg._trabalho.wait()
    app.processEvents()
    res = dlg.resultado()
    assert res is not None and res.capa == (PNG, "image/png")
    assert res.alteracoes[0][1]["album"] == "Album X"
    assert res.alteracoes[0][1]["albumartist"] == "Banda"
    assert res.acao_capa == ("definir", PNG, "image/png")


def test_cancelar_com_thread_rodando_nao_trava_nem_aceita(monkeypatch):
    import threading
    import time
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from tagger.gui import busca as gui
    app = QApplication.instance() or QApplication([])
    solta, chamou = threading.Event(), threading.Event()

    def lenta(pedido, timeout=None):
        chamou.set()
        solta.wait(10)
        return Resposta(BUSCA)

    dlg = gui.DialogoBusca([faixa(title="Primeira", artist="Banda")],
                           cliente=ClienteMusicBrainz(lenta, Limitador(lambda s: None, lambda: 0.0)))
    dlg.buscar()
    assert chamou.wait(5)
    inicio = time.monotonic()
    dlg.reject()                                    # não pode esperar a rede
    assert time.monotonic() - inicio < 1
    assert len(gui._ORFAOS) == 1
    solta.set()
    limite = time.monotonic() + 5
    while gui._ORFAOS and time.monotonic() < limite:
        app.processEvents()
        time.sleep(0.01)
    assert not gui._ORFAOS
    assert dlg.resultado() is None and dlg.lista.count() == 0


def test_generos_vem_do_release_group_quando_o_release_nao_traz():
    detalhe = {k: v for k, v in DETALHE.items() if k not in ("genres", "release-group")}
    detalhe["release-group"] = {"id": "rg1"}
    c, rede = cliente({"/release/abc?": Resposta(detalhe),
                       "/release-group/rg1?": Resposta({"genres": [{"name": "shoegaze", "count": 2}]})})
    assert c.detalhar_release("abc").generos == ["Shoegaze"]
    assert len(rede.pedidos) == 2


def test_falha_no_release_group_nao_derruba_o_detalhe():
    detalhe = {k: v for k, v in DETALHE.items() if k not in ("genres", "release-group")}
    detalhe["release-group"] = {"id": "rg1"}
    c, _ = cliente({"/release/abc?": Resposta(detalhe), "/release-group/rg1?": urllib.error.URLError("x")})
    r = c.detalhar_release("abc")
    assert r.generos == [] and len(r.faixas) == 2
