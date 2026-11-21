"""Rede: limite de taxa, cache e espera (backoff) do Discogs e do MusicBrainz.

Tudo com respostas simuladas: sem rede e sem dormir de verdade (relógio e espera injetados).
"""

import io
import json
import logging
import re
import urllib.error

import pytest

from tagger import __version__
from tagger.nucleo import busca, discogs, online
from tagger.nucleo.busca import ClienteMusicBrainz, ErroBusca, Limitador
from tagger.nucleo.discogs import ClienteDiscogs

AUTORIZACAO = "Discogs token=FAKE-TOKEN-0123456789abcdef"
SEGREDO = "FAKE-TOKEN-0123456789abcdef"
BUSCA = {"results": [{"id": 1, "title": "Banda - Disco", "year": "1977"}]}


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


def http_erro(codigo, cabecalhos=None, url="https://api.discogs.com/x"):
    return urllib.error.HTTPError(url, codigo, "x", cabecalhos or {}, io.BytesIO(b"{}"))


class Relogio:
    """Relógio falso: dormir só avança o tempo."""

    def __init__(self):
        self.agora, self.esperas = 0.0, []

    def __call__(self):
        return self.agora

    def dormir(self, segundos):
        self.esperas.append(segundos)
        self.agora += segundos


class Rede:
    """Substitui o urlopen: devolve as respostas da fila (a última se repete) e anota o instante."""

    def __init__(self, respostas, relogio):
        self.fila, self.relogio = list(respostas), relogio
        self.pedidos, self.instantes = [], []

    def __call__(self, pedido, timeout=None):
        self.pedidos.append(pedido)
        self.instantes.append(self.relogio.agora)
        item = self.fila.pop(0) if len(self.fila) > 1 else self.fila[0]
        if isinstance(item, Exception):
            raise item
        return item


def cliente(respostas, autorizacao=AUTORIZACAO):
    """ClienteDiscogs com o limitador do módulo (mesmos números), relógio falso e cache vazio."""
    relogio = Relogio()
    limitador = online.LimitadorJanela(discogs.MAXIMO_POR_MINUTO, discogs.JANELA,
                                       intervalo=discogs.JANELA / discogs.MAXIMO_POR_MINUTO,
                                       dormir=relogio.dormir, relogio=relogio)
    rede = Rede(respostas, relogio)
    return ClienteDiscogs(autorizacao, rede, limitador, online.Cache(10 ** 6)), rede, limitador, relogio


# ---------------------------------------------------------------------------
# Discogs: no máximo 60 requisições por minuto
# ---------------------------------------------------------------------------

def test_discogs_no_maximo_60_requisicoes_por_minuto():
    c, rede, _, _ = cliente([Resposta(BUSCA)])
    for i in range(130):
        c.buscar_releases("Banda", f"Disco {i}")          # álbuns diferentes: nunca vem do cache
    assert len(rede.pedidos) == 130
    t = rede.instantes
    for i in range(len(t) - 60):
        assert t[i + 60] - t[i] >= discogs.JANELA - 1e-6      # a 61ª só sai 60 s depois da 1ª


def test_discogs_a_61a_requisicao_espera_a_janela():
    c, rede, _, relogio = cliente([Resposta(BUSCA)])
    for i in range(60):
        c.buscar_releases("Banda", f"Disco {i}")
    c.buscar_releases("Banda", "Disco 60")
    assert rede.instantes[60] >= rede.instantes[0] + discogs.JANELA


def test_discogs_teto_do_modulo_e_60_por_minuto():
    assert discogs.MAXIMO_POR_MINUTO == 60 and discogs.JANELA == 60.0
    assert discogs.LIMITADOR.maximo <= 60


# ---------------------------------------------------------------------------
# Discogs: cabeçalhos X-Discogs-Ratelimit-*
# ---------------------------------------------------------------------------

def test_cabecalho_ratelimit_reduz_o_limite_sem_autenticacao():
    c, _, limitador, _ = cliente([Resposta(BUSCA, {"X-Discogs-Ratelimit": "25"})])
    c.buscar_releases("a", "b")
    assert limitador.maximo == 25


def test_cabecalho_ratelimit_maior_que_60_nao_passa_de_60():
    c, _, limitador, _ = cliente([Resposta(BUSCA, {"X-Discogs-Ratelimit": "240"})])
    c.buscar_releases("a", "b")
    assert limitador.maximo == 60


def test_cabecalho_remaining_zero_faz_a_proxima_esperar_a_janela():
    c, _, _, relogio = cliente([Resposta(BUSCA, {"X-Discogs-Ratelimit-Remaining": "0"})])
    c.buscar_releases("a", "b")
    c.buscar_releases("a", "c")
    assert relogio.esperas[-1] == pytest.approx(discogs.JANELA)


def test_cabecalho_remaining_positivo_nao_espera_alem_do_intervalo():
    c, _, _, relogio = cliente([Resposta(BUSCA, {"X-Discogs-Ratelimit-Remaining": "40"})])
    c.buscar_releases("a", "b")
    c.buscar_releases("a", "c")
    assert relogio.esperas == [pytest.approx(discogs.JANELA / discogs.MAXIMO_POR_MINUTO)]


# ---------------------------------------------------------------------------
# Discogs: espera no 429
# ---------------------------------------------------------------------------

def test_429_com_retry_after_espera_e_tenta_de_novo():
    c, rede, _, relogio = cliente([http_erro(429, {"Retry-After": "7"}), Resposta(BUSCA)])
    assert len(c.buscar_releases("a", "b")) == 1
    assert len(rede.pedidos) == 2
    assert rede.instantes[1] - rede.instantes[0] >= 7
    assert 7 in relogio.esperas


def test_429_sem_retry_after_espera_a_janela_inteira():
    c, rede, _, _ = cliente([http_erro(429), Resposta(BUSCA)])
    c.buscar_releases("a", "b")
    assert rede.instantes[1] - rede.instantes[0] >= discogs.JANELA


def test_429_retry_after_enorme_e_limitado_a_espera_maxima():
    c, rede, _, _ = cliente([http_erro(429, {"Retry-After": "86400"}), Resposta(BUSCA)])
    c.buscar_releases("a", "b")
    assert discogs.ESPERA_MAXIMA <= rede.instantes[1] - rede.instantes[0] < discogs.ESPERA_MAXIMA + 2


def test_429_persistente_desiste_depois_de_tentativas_e_nao_dorme_no_fim():
    c, rede, _, _ = cliente([http_erro(429, {"Retry-After": "2"})])
    with pytest.raises(ErroBusca, match="limitando"):
        c.buscar_releases("a", "b")
    assert len(rede.pedidos) == discogs.TENTATIVAS


# ---------------------------------------------------------------------------
# Cache: só memória, nunca mais de 6 h
# ---------------------------------------------------------------------------

def test_cache_do_discogs_e_so_memoria_e_com_teto_de_6_horas():
    assert discogs.CACHE.pasta is None
    assert discogs.CACHE.teto_segundos == 6 * 60 * 60 == discogs.TETO_CACHE
    assert discogs.CACHE_SEGUNDOS <= discogs.TETO_CACHE


def test_cache_nunca_guarda_por_mais_de_6_horas_mesmo_se_o_servidor_pedir():
    tempo = [0.0]
    cache = online.Cache(10 ** 6, teto_segundos=discogs.TETO_CACHE, relogio=lambda: tempo[0])
    cache.guardar("k", b"v", 100 * 3600)               # servidor pediu 100 h
    tempo[0] = discogs.TETO_CACHE - 1
    assert cache.obter("k") == b"v"
    tempo[0] = discogs.TETO_CACHE + 1
    assert cache.obter("k") is None


def test_discogs_guarda_a_resposta_por_menos_que_o_teto(monkeypatch):
    tempo = [0.0]
    c, rede, _, _ = cliente([Resposta(BUSCA)])
    c._cache = online.Cache(10 ** 6, teto_segundos=discogs.TETO_CACHE, relogio=lambda: tempo[0])
    c.buscar_releases("a", "b")
    c.buscar_releases("a", "b")
    assert len(rede.pedidos) == 1                       # a segunda veio do cache
    tempo[0] = discogs.TETO_CACHE + 1
    c.buscar_releases("a", "b")
    assert len(rede.pedidos) == 2                       # passou de 6 h: busca de novo


def test_nenhum_cache_em_disco_no_discogs_nem_no_musicbrainz():
    for modulo in (discogs, busca):
        fonte = open(modulo.__file__, encoding="utf-8").read()
        assert "pasta=" not in fonte.replace("self.pasta", "")


# ---------------------------------------------------------------------------
# MusicBrainz: 1 requisição por segundo e User-Agent identificado
# ---------------------------------------------------------------------------

def test_musicbrainz_user_agent_no_formato_exigido():
    assert re.fullmatch(r"Tagger/\S+ \( .+ \)", busca.USER_AGENT)
    assert busca.USER_AGENT.startswith(f"Tagger/{__version__} ( ")
    assert busca.USER_AGENT == f"Tagger/{__version__} ( https://github.com/morais1dev/Tagger )"


def test_musicbrainz_envia_o_user_agent_em_toda_requisicao():
    relogio = Relogio()
    vistos = []

    def abrir(pedido, timeout=None):
        vistos.append(pedido.get_header("User-agent"))
        return Resposta({"releases": []})

    c = ClienteMusicBrainz(abrir, Limitador(relogio.dormir, relogio))
    c.buscar_releases("a", "b")
    c.buscar_releases("a", "c")
    assert vistos == [busca.USER_AGENT] * 2


def test_musicbrainz_uma_requisicao_por_segundo_em_sequencia():
    relogio = Relogio()
    instantes = []

    def abrir(pedido, timeout=None):
        instantes.append(relogio.agora)
        return Resposta({"releases": []})

    c = ClienteMusicBrainz(abrir, Limitador(relogio.dormir, relogio))
    for i in range(5):
        c.buscar_releases("a", f"b{i}")
    assert busca.INTERVALO == 1.0
    assert all(b - a >= 1.0 - 1e-9 for a, b in zip(instantes, instantes[1:]))


@pytest.mark.parametrize("codigo", [429, 503])
def test_musicbrainz_limitando_vira_erro_amigavel_sem_dormir(codigo):
    relogio = Relogio()

    def abrir(pedido, timeout=None):
        raise urllib.error.HTTPError(pedido.full_url, codigo, "x", {}, None)

    c = ClienteMusicBrainz(abrir, Limitador(relogio.dormir, relogio))
    with pytest.raises(ErroBusca, match="limitando"):
        c.buscar_releases("a", "b")
    assert relogio.esperas == []


# ---------------------------------------------------------------------------
# Nenhuma credencial em exceção nem em log
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("erro", [
    http_erro(429, {"Retry-After": "1"}, f"https://api.discogs.com/x?api_key={SEGREDO}&token={SEGREDO}"),
    http_erro(401, url=f"https://api.discogs.com/x?api_key={SEGREDO}"),
    http_erro(500, url=f"https://api.discogs.com/x?token={SEGREDO}"),
    urllib.error.URLError(f"falha em https://api.discogs.com/x?api_key={SEGREDO} {AUTORIZACAO}"),
])
def test_erros_do_discogs_nao_levam_credencial_na_mensagem_nem_no_detalhe(erro, caplog):
    c, _, _, _ = cliente([erro])
    with caplog.at_level(logging.DEBUG), pytest.raises(ErroBusca) as capturado:
        c.buscar_releases("a", "b")
    exc = capturado.value
    assert SEGREDO not in str(exc)
    assert SEGREDO not in getattr(exc, "detalhe", "")
    assert "Authorization" not in str(exc)
    assert exc.__cause__ is None and exc.__suppress_context__
    assert SEGREDO not in caplog.text


def test_pedido_do_discogs_leva_a_credencial_so_no_cabecalho_authorization():
    c, rede, _, _ = cliente([Resposta(BUSCA)])
    c.buscar_releases("a", "b")
    pedido = rede.pedidos[0]
    assert pedido.get_header("Authorization") == AUTORIZACAO
    assert "api_key" not in pedido.full_url.lower() and SEGREDO not in pedido.full_url
