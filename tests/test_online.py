"""Discogs e as peças comuns (online.py): HTTP sempre simulado, nunca usa a rede."""

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tagger.nucleo import discogs, online
from tagger.nucleo.busca import ErroBusca
from tagger.nucleo.discogs import ClienteDiscogs, interpretar_posicao, numerar
from tagger.nucleo.metadata import Faixa
from tagger.nucleo.rascunho import Rascunho

TOKEN = "Discogs token=SEGREDOtok123"


class Resposta:
    def __init__(self, corpo, cabecalhos=None):
        self.corpo = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
        self.headers = {"Content-Type": "application/json", **(cabecalhos or {})}

    def read(self, n=-1):
        return self.corpo[:n] if n >= 0 else self.corpo

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_erro(url, codigo, corpo=b"", cabecalhos=None):
    corpo = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()
    return urllib.error.HTTPError(url, codigo, "x", cabecalhos or {}, io.BytesIO(corpo))


class Rede:
    """Substitui urlopen: cada trecho da URL tem uma fila de respostas (a última se repete)."""
    def __init__(self, respostas):
        self.respostas = {k: (v if isinstance(v, list) else [v]) for k, v in respostas.items()}
        self.pedidos = []

    def __call__(self, pedido, timeout=None):
        self.pedidos.append(pedido)
        for trecho, fila in self.respostas.items():
            if trecho in pedido.full_url:
                resposta = fila.pop(0) if len(fila) > 1 else fila[0]
                if callable(resposta) and not isinstance(resposta, Resposta):
                    resposta = resposta(pedido)
                if isinstance(resposta, Exception):
                    raise resposta
                return resposta
        raise AssertionError(f"URL inesperada: {pedido.full_url}")


class Relogio:
    def __init__(self):
        self.agora, self.esperas = 0.0, []

    def __call__(self):
        return self.agora

    def dormir(self, s):
        self.esperas.append(s)
        self.agora += s


def limitador_falso(maximo=60, janela=60.0, intervalo=0.0):
    r = Relogio()
    return online.LimitadorJanela(maximo, janela, intervalo, dormir=r.dormir, relogio=r), r


def faixa(nome, **tags):
    return Faixa(caminho=Path(nome), tags=tags)


# ---------------------------------------------------------------------------
# online.py
# ---------------------------------------------------------------------------

def test_ocultar_api_key_header_e_literal():
    assert online.ocultar("GET https://x/?method=a&api_key=abc123&format=json") == \
        "GET https://x/?method=a&api_key=***&format=json"
    assert "SEGREDO" not in online.ocultar("Authorization: Discogs key=SEGREDOk, secret=SEGREDOs")
    literal = "SEGREDOliteral0123456789"            # credenciais.py só troca literais com 16+ caracteres
    texto = online.ocultar(f"Traceback ...\n  valor {literal} no meio\nfim", literal)
    assert "SEGREDO" not in texto and "fim" in texto
    assert online.ocultar("monkey=banana") == "monkey=banana"       # \b: não é 'key='


def test_limitador_janela_deslizante_e_intervalo():
    lim, r = limitador_falso(maximo=3, janela=60.0, intervalo=1.0)
    for _ in range(3):
        lim.esperar()
    assert r.esperas == [1.0, 1.0]
    lim.esperar()                         # a 4ª espera a 1ª sair da janela
    assert r.esperas[-1] == pytest.approx(58.0)
    lim.bloquear(30)
    lim.esperar()
    assert r.esperas[-1] == pytest.approx(30.0)


@pytest.mark.parametrize("cabecalhos,segundos", [
    ({"Cache-Control": "max-age=600"}, 600),
    ({"Cache-Control": "public, max-age=600", "Age": "100"}, 500),
    ({"Cache-Control": "no-store, max-age=600"}, 0),
    ({"Cache-Control": "no-cache"}, 0),
    ({"Expires": "Thu, 01 Jan 1970 00:10:00 GMT"}, 600),
    ({"Expires": "0"}, 0),
    ({}, 0),
])
def test_validade_pelos_cabecalhos(cabecalhos, segundos):
    assert online.validade(cabecalhos, agora=0) == segundos


def test_cache_em_disco_expira_e_respeita_teto(tmp_path):
    tempo = [0.0]
    cache = online.Cache(100, pasta=tmp_path, relogio=lambda: tempo[0])
    cache.guardar("a", b"x" * 60, 10)
    assert cache.obter("a") == b"x" * 60
    cache.guardar("nao", b"y", 0)                     # sem validade: não guarda
    assert cache.obter("nao") is None
    import os
    os.utime(next(tmp_path.glob("*.json")), (1, 1))   # "a" é o mais antigo
    cache.guardar("b", b"z" * 60, 10)                 # passa de 100 bytes: "a" sai
    assert cache.obter("a") is None and cache.obter("b") == b"z" * 60
    tempo[0] = 11
    assert cache.obter("b") is None


def test_cache_teto_de_tempo_em_memoria():
    tempo = [0.0]
    cache = online.Cache(1000, teto_segundos=5, relogio=lambda: tempo[0])
    cache.guardar("k", b"v", 3600)
    tempo[0] = 6
    assert cache.obter("k") is None


def test_redirecionamento_para_outro_host_tira_authorization():
    h = online._RedirecionamentoSeguro()
    pedido = urllib.request.Request("https://api.discogs.com/x", headers={"Authorization": TOKEN})
    novo = h.redirect_request(pedido, None, 302, "Found", {}, "https://outro.example/y")
    assert not any(k.lower() == "authorization" for k in novo.headers)
    mesmo = h.redirect_request(pedido, None, 302, "Found", {}, "https://api.discogs.com/z")
    assert mesmo.get_header("Authorization") == TOKEN


# ---------------------------------------------------------------------------
# Discogs
# ---------------------------------------------------------------------------

BUSCA_DISCOGS = {"results": [
    {"id": 123, "title": "Banda (2) - Disco Raro", "year": "1977", "country": "Brazil",
     "format": ["Vinyl", "LP", "Vinyl"], "label": ["Selo Independente"], "catno": "SI-001",
     "uri": "/release/123-Banda-Disco-Raro", "cover_image": "https://i.discogs.com/capa.jpg"},
    {"title": "sem id"}]}

VINIL = {"id": 123, "title": "Disco Raro", "year": 1977, "released": "1977-00-00",
         "uri": "https://www.discogs.com/release/123-Banda-Disco-Raro",
         "artists": [{"name": "Banda (2)", "anv": "", "join": "&"}, {"name": "Outro", "anv": "Outra", "join": ""}],
         "labels": [{"name": "Selo Independente (3)", "catno": "SI-001"}],
         "styles": ["MPB"], "genres": ["Latin"],
         "images": [{"uri": "https://i.discogs.com/capa.jpg"}],
         "tracklist": [
             {"position": "", "type_": "heading", "title": "Lado Um"},
             {"position": "A1", "type_": "track", "title": "Abertura", "duration": ""},
             {"position": "A2", "type_": "track", "title": "Canção do Mar", "duration": "3:05"},
             {"position": "B1", "type_": "track", "title": "Noite", "duration": "",
              "artists": [{"name": "Convidado", "join": ""}]},
             {"position": "B2", "type_": "track", "title": "Fim", "duration": ""},
             {"position": "C1", "type_": "track", "title": "Bônus", "duration": ""}]}


def cliente_discogs(respostas, authorization=TOKEN, **kw):
    rede = Rede(respostas)
    lim, relogio = limitador_falso(**kw)
    return ClienteDiscogs(authorization, rede, lim, online.Cache(10 ** 6)), rede, lim, relogio


@pytest.mark.parametrize("texto,esperado", [
    ("A1", ("lado", "A", 1)), ("b12", ("lado", "B", 12)), ("A", ("lado", "A", 0)), ("A1a", ("lado", "A", 1)),
    ("2-05", ("disco", 2, 5)), ("CD2.3", ("disco", 2, 3)), ("7", ("faixa", None, 7)),
    ("", None), ("Video", None),
])
def test_interpretar_posicao(texto, esperado):
    assert interpretar_posicao(texto) == esperado


def test_numerar_vinil_cd_e_numeros():
    assert numerar(["A1", "A2", "B1", "B2", "C1", "D1"]) == [(1, 1), (1, 2), (1, 3), (1, 4), (2, 1), (2, 2)]
    assert numerar(["A", "B"]) == [(1, 1), (1, 2)]
    assert numerar(["1-1", "1-2", "2-1"]) == [(1, 1), (1, 2), (2, 1)]
    assert numerar(["1", "2", "Video"]) == [(1, 1), (1, 2), (1, 3)]


def test_buscar_releases_discogs_credencial_so_no_cabecalho():
    c, rede, _, _ = cliente_discogs({"/database/search?": Resposta(BUSCA_DISCOGS)})
    candidatos = c.buscar_releases("Banda", "Disco Raro")
    assert len(candidatos) == 1
    cand = candidatos[0]
    assert (cand.id, cand.artista, cand.titulo, cand.ano, cand.formato, cand.gravadora) == \
        (123, "Banda", "Disco Raro", "1977", "Vinyl, LP", "Selo Independente")
    assert cand.url == "https://www.discogs.com/release/123-Banda-Disco-Raro"
    assert not hasattr(cand, "capa")
    pedido = rede.pedidos[0]
    assert pedido.get_header("Authorization") == TOKEN
    assert pedido.get_header("User-agent").startswith("Tagger/")
    assert "SEGREDO" not in pedido.full_url and "token" not in pedido.full_url.lower()


def test_sem_credencial_discogs_nao_faz_requisicao():
    c, rede, _, _ = cliente_discogs({}, authorization=None)
    assert not c.disponivel
    with pytest.raises(ErroBusca, match="indisponível"):
        c.buscar_releases("a", "b")
    assert rede.pedidos == []


def test_detalhar_release_vinil():
    c, _, _, _ = cliente_discogs({"/releases/123": Resposta(VINIL)})
    r = c.detalhar_release(123)
    assert (r.titulo, r.artista, r.data, r.gravadora, r.catalogo) == \
        ("Disco Raro", "Banda & Outra", "1977", "Selo Independente", "SI-001")
    assert r.total_discos == 2 and r.generos == [] and r.estilos == ["MPB", "Latin"]
    assert [(f.posicao, f.disco, f.numero, f.total_disco) for f in r.faixas] == \
        [("A1", 1, 1, 4), ("A2", 1, 2, 4), ("B1", 1, 3, 4), ("B2", 1, 4, 4), ("C1", 2, 1, 1)]
    assert r.faixas[2].artista == "Convidado" and r.faixas[1].duracao == 185
    assert r.atribuicao == ("Data provided by Discogs.", "https://www.discogs.com/release/123-Banda-Disco-Raro")


def test_respeita_cabecalhos_de_limite_e_espera_no_429():
    corpo = Resposta(BUSCA_DISCOGS, {"X-Discogs-Ratelimit": "25", "X-Discogs-Ratelimit-Remaining": "0"})
    c, rede, lim, relogio = cliente_discogs({"/database/search?": [
        http_erro("u", 429, cabecalhos={"Retry-After": "7"}), corpo]})
    assert len(c.buscar_releases("a", "b")) == 1
    assert len(rede.pedidos) == 2 and relogio.esperas == [7]          # esperou o Retry-After
    assert lim.maximo == 25                                           # limite informado pelo servidor
    c._cache = online.Cache(10 ** 6)
    c.buscar_releases("a", "c")
    assert relogio.esperas[-1] == pytest.approx(discogs.JANELA)       # Remaining=0: espera a janela


def test_429_persistente_vira_erro():
    c, rede, _, _ = cliente_discogs({"/database/search?": http_erro("u", 429, cabecalhos={"Retry-After": "1"})})
    with pytest.raises(ErroBusca, match="limitando"):
        c.buscar_releases("a", "b")
    assert len(rede.pedidos) == discogs.TENTATIVAS


def test_429_sem_retry_after_tenta_so_mais_uma_vez():
    c, rede, _, _ = cliente_discogs({"/database/search?": http_erro("u", 429)})
    with pytest.raises(ErroBusca, match="limitando"):
        c.buscar_releases("a", "b")
    assert len(rede.pedidos) == 2


def test_cache_discogs_evita_segunda_requisicao():
    c, rede, _, _ = cliente_discogs({"/releases/123": Resposta(VINIL)})
    c.detalhar_release(123)
    c.detalhar_release(123)
    assert len(rede.pedidos) == 1
    assert discogs.CACHE.pasta is None and discogs.CACHE.teto_segundos <= 6 * 3600


def test_erro_de_rede_discogs_sem_credencial_no_detalhe_nem_no_traceback():
    erro_rede = urllib.error.URLError(f"falhou com {TOKEN}")
    c, _, _, _ = cliente_discogs({"/releases/": erro_rede})
    with pytest.raises(ErroBusca) as info:
        c.detalhar_release(1)
    assert "SEGREDO" not in info.value.detalhe and "SEGREDO" not in str(info.value)
    assert info.value.__cause__ is None and info.value.__suppress_context__


def test_casamento_discogs_por_nome_posicao_e_ordem():
    c, _, _, _ = cliente_discogs({"/releases/123": Resposta(VINIL)})
    r = c.detalhar_release(123)
    faixas = [faixa("1.mp3", title="abertura"),                     # nome exato
              faixa("2.mp3", title="Cancao do Mar (live)"),         # nome parecido
              faixa("3.mp3", title="xxx", tracknumber="3"),          # posição (B1)
              faixa("5.mp3", title="yyy", tracknumber="5"),          # 5 na ordem geral = C1
              faixa("4.mp3", title="")]                              # sobra 1 de cada: pela ordem (B2)
    pares = {f.caminho.name: par.posicao for f, par in discogs.casar_faixas(faixas, r)}
    assert pares == {"1.mp3": "A1", "2.mp3": "A2", "3.mp3": "B1", "5.mp3": "C1", "4.mp3": "B2"}
    itens = dict((f.caminho.name, v) for f, v in discogs.montar_alteracoes(faixas, r))
    assert itens["1.mp3"]["title"] == "Abertura" and itens["1.mp3"]["tracknumber"] == "1/4"
    assert itens["1.mp3"]["discnumber"] == "1/2" and itens["1.mp3"]["albumartist"] == "Banda & Outra"
    assert itens["1.mp3"]["date"] == "1977" and "genre" not in itens["1.mp3"]
    assert "title" not in itens["3.mp3"]                         # só pela posição e nome diferente
    assert itens["4.mp3"]["title"] == "Fim"                      # sem título: recebe
    assert itens["5.mp3"]["discnumber"] == "2/2" and itens["5.mp3"]["tracknumber"] == "1/1"


def test_resultado_discogs_entra_no_rascunho():
    c, _, _, _ = cliente_discogs({"/releases/123": Resposta(VINIL)})
    r = c.detalhar_release(123)
    f = faixa("1.mp3", title="Abertura")
    rascunho = Rascunho()
    rascunho.definir_por_faixa(discogs.montar_alteracoes([f], r, valor=rascunho.valor))
    assert rascunho.valor(f, "album") == "Disco Raro" and rascunho.valor(f, "tracknumber") == "1/4"
    assert not rascunho.capas                                     # nunca capa do Discogs


def test_ocultar_passa_as_conhecidas_para_credenciais_py(monkeypatch):
    chamadas = []

    def falso(texto, conhecidas=()):
        chamadas.append(conhecidas)
        return texto.replace("ESPECIAL", "***")

    monkeypatch.setattr(online, "ocultar_credenciais", falso)
    assert online.ocultar("x ESPECIAL y", "valorConhecido") == "x *** y"
    assert chamadas == [("valorConhecido",)]


# ---------------------------------------------------------------------------
# Revisão: redirecionamento, links, JSON estranho, numeração, gravadora
# ---------------------------------------------------------------------------

PROFUNDO = b"[" * 100000 + b"]" * 100000     # aninhamento que estoura a recursão do json


def test_authorization_do_discogs_nunca_segue_redirect():
    c, rede, _, _ = cliente_discogs({"/releases/123": Resposta(VINIL)})
    c.detalhar_release(123)
    pedido = rede.pedidos[0]
    assert not any(k.lower() == "authorization" for k in pedido.headers)      # não é copiado num redirect
    assert pedido.unredirected_hdrs["Authorization"] == TOKEN


@pytest.mark.parametrize("destino", ["http://api.discogs.com/x", "ftp://api.discogs.com/x", "file:///etc/passwd"])
def test_redirect_para_fora_do_https_e_recusado(destino):
    h = online._RedirecionamentoSeguro()
    pedido = urllib.request.Request("https://api.discogs.com/x?token=chaveDISCOGS987")
    with pytest.raises(online.RedirecionamentoRecusado):
        h.redirect_request(pedido, None, 302, "Found", {}, destino)


def test_redirect_recusado_tem_mensagem_propria_sem_credencial():
    url = "http://api.discogs.com/x?token=chaveDISCOGS987"
    c, _, _, _ = cliente_discogs({"/releases/": online.RedirecionamentoRecusado(f"recusado: {url}")})
    with pytest.raises(ErroBusca, match="Redirecionamento inseguro recusado") as info:
        c.detalhar_release(1)
    assert "chaveDISCOGS987" not in info.value.detalhe
    d, _, _, _ = cliente_discogs({"/releases/": online.RedirecionamentoRecusado("recusado")})
    with pytest.raises(ErroBusca, match="Redirecionamento inseguro recusado"):
        d.detalhar_release(1)


def test_resposta_invalida_registra_o_erro_no_log_sem_credencial(caplog):
    c, _, _, _ = cliente_discogs({"/releases/1": Resposta({"tracklist": ["x"], "nota": TOKEN})})
    with caplog.at_level("DEBUG", logger="tagger.nucleo.online"), pytest.raises(ErroBusca, match="inválida"):
        c.detalhar_release(1)
    assert "AttributeError" in caplog.text and "SEGREDO" not in caplog.text


def test_redirect_com_outra_porta_tira_authorization():
    h = online._RedirecionamentoSeguro()
    pedido = urllib.request.Request("https://api.discogs.com/x", headers={"Authorization": TOKEN})
    novo = h.redirect_request(pedido, None, 302, "Found", {}, "https://api.discogs.com:8443/y")
    assert not any(k.lower() == "authorization" for k in novo.headers)
    mesmo = h.redirect_request(pedido, None, 302, "Found", {}, "https://api.discogs.com:443/z")
    assert mesmo.get_header("Authorization") == TOKEN


@pytest.mark.parametrize("url,aceita", [
    ("https://www.discogs.com/release/1-x", True),
    ("https://discogs.com/release/1", True),
    ("javascript:alert(1)", False),
    ("file:///C:/Windows/win.ini", False),
    ("httpx://www.discogs.com/release/1", False),
    ("http://www.discogs.com/release/1", False),
    ("https://www.discogs.com.evil.com/release/1", False),
    ("https://evildiscogs.com/release/1", False),
    ("https://user@www.discogs.com/release/1", False),
    ("https://evil.com\\@www.discogs.com/", False),
    ("https://www.discogs.com:8080/release/1", False),
    ("https://[::1/", False),
    (None, False), (123, False),
])
def test_url_segura(url, aceita):
    assert online.url_segura(url, discogs.DOMINIOS, "PADRAO") == (url if aceita else "PADRAO")


def test_links_falsos_do_json_trocados_pelos_montados():
    busca_falsa = {"results": [{"id": 5, "title": "A - B", "uri": "javascript:alert(1)"},
                               {"id": 6, "title": "A - C", "uri": "//evil.com/x"}]}
    vinil = dict(VINIL, uri="https://www.discogs.com.evil.com/release/123")
    c, _, _, _ = cliente_discogs({"/database/search?": Resposta(busca_falsa), "/releases/123": Resposta(vinil)})
    assert [cand.url for cand in c.buscar_releases("a", "b")] == \
        ["https://www.discogs.com/release/5", "https://www.discogs.com/release/6"]
    assert c.detalhar_release(123).url == "https://www.discogs.com/release/123"


@pytest.mark.parametrize("corpo", [
    [1, 2],
    {"results": ["texto"]},
    {"results": [{"id": "abc"}]},
    {"results": [{"id": "9" * 5000}]},
    {"results": [{"id": 1, "title": 5}]},
    pytest.param(PROFUNDO, id="profundo"),
])
def test_json_estranho_do_discogs_na_busca_vira_erro_busca(corpo):
    c, _, _, _ = cliente_discogs({"/database/search?": Resposta(corpo)})
    with pytest.raises(ErroBusca, match="inválida"):
        c.buscar_releases("a", "b")


@pytest.mark.parametrize("corpo", [
    {"tracklist": ["x"]},
    {"tracklist": [{"position": "A1", "title": "x", "artists": ["nome"]}]},
    {"tracklist": [], "labels": ["selo"]},
    {"tracklist": [], "artists": [{"name": ["lista"]}]},
    {"id": "não numérico", "tracklist": []},
])
def test_json_estranho_do_discogs_no_release_vira_erro_busca(corpo):
    c, _, _, _ = cliente_discogs({"/releases/1": Resposta(corpo)})
    with pytest.raises(ErroBusca, match="inválida"):
        c.detalhar_release(1)


def test_numerar_subfaixas_numericas_seguem_a_contagem():
    assert numerar(["1", "2", "3", "4a", "4b", "4c", "5"]) == [(1, n) for n in range(1, 8)]
    assert numerar(["1-1", "1-1", "2-1"]) == [(1, 1), (1, 2), (2, 1)]


def test_numerar_romanos_nao_viram_lado():
    assert interpretar_posicao("I") is None and interpretar_posicao("V") is None
    assert numerar(["I", "II", "III", "IV"]) == [(1, 1), (1, 2), (1, 3), (1, 4)]
    assert numerar(["A", "B", "C", "D"]) == [(1, 1), (1, 2), (2, 1), (2, 2)]     # release só de lados
    assert numerar(["A1", "B1", "I1", "J1"]) == [(1, 1), (1, 2), (5, 1), (5, 2)]  # com número: lado


def test_gravadora_entra_nas_alteracoes(monkeypatch):
    from tagger.nucleo import metadata
    c, _, _, _ = cliente_discogs({"/releases/123": Resposta(VINIL)})
    r = c.detalhar_release(123)
    f = faixa("1.mp3", title="Abertura", album="Disco Raro", albumartist="Banda & Outra", date="1977",
              tracknumber="1/4", discnumber="1/2", artist="Banda & Outra")
    assert "gravadora" in metadata.CAMPOS
    assert discogs.montar_alteracoes([f], r) == [(f, {"gravadora": "Selo Independente"})]
    rascunho = Rascunho()
    rascunho.definir_por_faixa(discogs.montar_alteracoes([f], r, valor=rascunho.valor))
    assert rascunho.valor(f, "gravadora") == "Selo Independente" and rascunho.validar() == []
    assert discogs.montar_alteracoes([f], r, campos={"title"}) == []
    r.gravadora = ""
    assert discogs.montar_alteracoes([f], r) == []
    r.gravadora = "Selo Independente"
    monkeypatch.setattr(metadata, "CAMPOS", {k: v for k, v in metadata.CAMPOS.items() if k != "gravadora"})
    assert discogs.montar_alteracoes([f], r) == []                  # sem o campo: nada de gravadora


def test_cache_em_disco_nao_deixa_temporario(tmp_path):
    cache = online.Cache(10 ** 6, pasta=tmp_path)
    cache.guardar("a", b"corpo", 60)
    assert [p.suffix for p in tmp_path.iterdir()] == [".json"]
    assert cache.obter("a") == b"corpo"
