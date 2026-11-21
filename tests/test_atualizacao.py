"""Aviso de nova versão: comparação, regra de uma consulta por dia e falhas silenciosas (sem rede)."""

import io
import json
import logging
import urllib.error

import pytest

from tagger.nucleo import atualizacao
from tagger.nucleo.atualizacao import analisar_resposta, consultar, deve_consultar, e_mais_nova, interpretar_versao


def resposta_salva(tag="v2.3.0", **extras):
    """Trecho de uma resposta real de /releases/latest (só os campos que o Tagger lê)."""
    dados = {"tag_name": tag, "name": f"Tagger {tag}", "draft": False, "prerelease": False,
             "html_url": f"https://github.com/morais1dev/Tagger/releases/tag/{tag}",
             "assets": [{"name": "Tagger.exe", "browser_download_url": "https://github.com/x/Tagger.exe"}]}
    dados.update(extras)
    return json.dumps(dados).encode()


class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def abrir_com(corpo):
    pedidos = []

    def abrir(pedido, timeout):
        pedidos.append((pedido, timeout))
        return Resposta(corpo)
    abrir.pedidos = pedidos
    return abrir


# --- comparação de versões ---------------------------------------------------------------------------

@pytest.mark.parametrize("nova, velha", [
    ("2.10.0", "2.9.1"),            # por partes numéricas, não por texto
    ("v2.3.0", "2.2.0"),            # prefixo v
    ("V3.0.0", "v2.99.99"),
    ("2.2.1", "2.2.0"),
    ("2.2.0.1", "2.2.0"),
    ("2.3.0", "2.3.0-rc1"),         # a final vence a pré-release
    ("2.3.0-rc2", "2.3.0-rc1"),
    ("2.3.0-rc10", "2.3.0-rc2"),
    ("2.3.0-rc1", "2.2.9"),
])
def test_mais_nova(nova, velha):
    assert e_mais_nova(nova, velha)
    assert not e_mais_nova(velha, nova)


@pytest.mark.parametrize("a, b", [("2.2", "2.2.0"), ("v2.2.0", "2.2.0"), ("2.2.0", "2.2.0")])
def test_iguais_nao_sao_mais_novas(a, b):
    assert not e_mais_nova(a, b) and not e_mais_nova(b, a)


@pytest.mark.parametrize("texto", ["", "latest", "v", "2.x", "nightly-2026", None, 3, "2..1", "../2.3.0"])
def test_texto_que_nao_e_versao(texto):
    assert interpretar_versao(texto) is None
    assert not e_mais_nova(texto, "2.2.0")


# --- uma consulta por dia ----------------------------------------------------------------------------

def test_deve_consultar_uma_vez_por_dia():
    dia = atualizacao.INTERVALO
    assert deve_consultar(None, 1000) and deve_consultar("", 1000) and deve_consultar("lixo", 1000)
    assert not deve_consultar(1000, 1000 + 60)
    assert not deve_consultar("1000.5", 1000 + dia - 1)          # o QSettings pode devolver texto
    assert deve_consultar(1000, 1000 + dia)
    assert deve_consultar(5000, 1000)                            # relógio voltou: consulta


# --- resposta da API ---------------------------------------------------------------------------------

def test_versao_nova_devolve_versao_e_link():
    assert analisar_resposta(resposta_salva("v2.3.0"), "2.2.0") == (
        "2.3.0", "https://github.com/morais1dev/Tagger/releases/tag/v2.3.0")


def test_mesma_versao_ou_mais_velha_nao_avisa():
    assert analisar_resposta(resposta_salva("v2.2.0"), "2.2.0") is None
    assert analisar_resposta(resposta_salva("v2.1.0"), "2.2.0") is None


def test_pre_release_e_rascunho_nao_avisam():
    assert analisar_resposta(resposta_salva("v2.4.0", prerelease=True), "2.2.0") is None
    assert analisar_resposta(resposta_salva("v2.4.0", draft=True), "2.2.0") is None
    assert analisar_resposta(resposta_salva("v2.4.0-rc1"), "2.2.0") is None


def test_link_fora_do_github_cai_na_pagina_de_releases():
    for url in ("http://github.com/x", "https://evil.com/github.com", "javascript:alert(1)", None, 5):
        assert analisar_resposta(resposta_salva("v2.3.0", html_url=url), "2.2.0") == (
            "2.3.0", atualizacao.URL_RELEASES)


@pytest.mark.parametrize("corpo", [b"", b"nao e json", b"[]", b"null", b'{"tag_name": 5}', b'{"message": "Not Found"}',
                                   pytest.param(b"[" * 100000, id="profundo")])
def test_resposta_estranha_nao_avisa_nem_levanta(corpo):
    assert analisar_resposta(corpo, "2.2.0") is None


# --- consulta (rede simulada) ------------------------------------------------------------------------

def test_consultar_usa_a_url_da_api_sem_credenciais():
    abrir = abrir_com(resposta_salva("v2.3.0"))
    assert consultar("2.2.0", abrir)[0] == "2.3.0"
    [(pedido, timeout)] = abrir.pedidos
    assert pedido.full_url == "https://api.github.com/repos/morais1dev/Tagger/releases/latest"
    assert timeout == atualizacao.TIMEOUT
    assert not any(k.lower() == "authorization" for k in pedido.headers)


@pytest.mark.parametrize("erro", [
    urllib.error.URLError("sem rede"),
    urllib.error.HTTPError("https://api.github.com/x", 403, "rate limit", {}, None),
    TimeoutError(), OSError("conexão recusada"), ValueError("estranho"),
])
def test_falha_e_silenciosa_e_so_vai_para_o_log(erro, caplog):
    def abrir(pedido, timeout):
        raise erro
    with caplog.at_level(logging.WARNING):
        assert consultar("2.2.0", abrir) is None
    assert "api.github.com" not in caplog.text and "token" not in caplog.text.lower()
    assert len(caplog.records) == 1


def test_resposta_gigante_e_descartada(caplog):
    corpo = b" " * (atualizacao.LIMITE_RESPOSTA + 10)
    with caplog.at_level(logging.WARNING):
        assert consultar("2.2.0", abrir_com(corpo)) is None
    assert len(caplog.records) == 1
