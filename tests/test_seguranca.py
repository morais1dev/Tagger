"""Checklist de segurança: nenhuma credencial (valor literal) pode vazar para log, erro ou URL exibida.

Valores de teste são falsos e óbvios de propósito (FAKE-...), nunca chaves reais.
"""

import pytest

from tagger.nucleo.credenciais import OCULTO, ocultar_credenciais

TOKEN_FALSO = "FAKE-TOKEN-0123456789abcdef"
KEY_FALSA = "FAKE-KEY-0123456789abcdef"
SECRET_FALSO = "FAKE-SECRET-0123456789abcdef"


def test_oculta_cabecalho_authorization_do_discogs_com_token():
    texto = f"Authorization: Discogs token={TOKEN_FALSO}"
    resultado = ocultar_credenciais(texto)
    assert TOKEN_FALSO not in resultado
    assert resultado == f"Authorization: Discogs token={OCULTO}"


def test_oculta_cabecalho_authorization_do_discogs_com_key_e_secret():
    texto = f"Discogs key={KEY_FALSA}, secret={SECRET_FALSO}"
    resultado = ocultar_credenciais(texto)
    assert KEY_FALSA not in resultado
    assert SECRET_FALSO not in resultado
    assert resultado == f"Discogs key={OCULTO}, secret={OCULTO}"


def test_oculta_token_mesmo_com_valor_curto_no_cabecalho():
    # abaixo do TAMANHO_MINIMO o valor não entra na lista de conhecidas, mas o padrão nome=valor cobre
    resultado = ocultar_credenciais("Discogs token=abc123")
    assert "abc123" not in resultado
    assert resultado == f"Discogs token={OCULTO}"


@pytest.mark.parametrize("url", [
    f"https://api.exemplo.com/v1/busca?api_key={KEY_FALSA}&q=teste",
    f"https://api.exemplo.com/v1/busca?q=teste&api_key={KEY_FALSA}",
    f"https://api.exemplo.com/v1/busca?api%5Fkey={KEY_FALSA}&q=teste",
    # URL já codificada (valor dentro de um parâmetro da própria URL)
    f"https://exemplo.com/redir?u=https%3A%2F%2Fapi.exemplo.com%2F%3Fapi_key%3D{KEY_FALSA}%26q%3Dteste",
])
def test_oculta_api_key_em_url(url):
    resultado = ocultar_credenciais(url)
    assert KEY_FALSA not in resultado
    assert "api_key=" in resultado or "api%5Fkey=" in resultado or "api_key%3D" in resultado


def test_oculta_api_key_em_mensagem_de_erro():
    texto = f"Erro ao consultar https://api.exemplo.com/?api_key={KEY_FALSA}: timeout"
    resultado = ocultar_credenciais(texto)
    assert KEY_FALSA not in resultado
    assert "timeout" in resultado


def test_oculta_valor_conhecido_que_aparece_sem_rotulo():
    texto = f"resposta contém {TOKEN_FALSO} solto"
    assert ocultar_credenciais(texto, conhecidas=(TOKEN_FALSO,)) == f"resposta contém {OCULTO} solto"


def test_texto_sem_credencial_fica_igual():
    texto = "Álbum 'Teste' (2001) — faixa 3 gravada em 2000"
    assert ocultar_credenciais(texto) == texto
