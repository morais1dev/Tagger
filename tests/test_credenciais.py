"""Credenciais das APIs: ordem de prioridade, chaves.json, cabeçalho do Discogs, log sem chaves e gerar_chaves.py."""

import importlib.util
import json
import logging
from pathlib import Path

import pytest

from tagger.nucleo import credenciais
from tagger.nucleo.credenciais import (
    FormatadorSemCredenciais, discogs_authorization, discogs_disponivel,
    ler_embutidas, ocultar_credenciais,
)


@pytest.fixture(autouse=True)
def ambiente_limpo(monkeypatch):
    """Nenhuma variável TAGGER_* da máquina vaza para os testes."""
    for variavel in credenciais.VARIAVEIS.values():
        monkeypatch.delenv(variavel, raising=False)


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    """Pasta do chaves.json de teste (o chaves.json real do projeto nunca é lido)."""
    monkeypatch.setattr(credenciais, "pasta_chaves", lambda: tmp_path)
    credenciais._avisar_uma_vez.cache_clear()
    yield tmp_path
    credenciais._avisar_uma_vez.cache_clear()


def gravar(pasta, conteudo):
    (pasta / "chaves.json").write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo),
                                       encoding="utf-8")


# --- ordem de prioridade -------------------------------------------------------------------------------

def test_discogs_configuracoes_vencem_ambiente_e_arquivo(pasta, monkeypatch):
    gravar(pasta, {"discogs_key": "k-arquivo", "discogs_secret": "s-arquivo"})
    monkeypatch.setenv("TAGGER_DISCOGS_TOKEN", "do-ambiente")
    assert discogs_authorization("da-config") == "Discogs token=da-config"


def test_discogs_ambiente_vence_arquivo(pasta, monkeypatch):
    gravar(pasta, {"discogs_key": "k-arquivo", "discogs_secret": "s-arquivo"})
    monkeypatch.setenv("TAGGER_DISCOGS_TOKEN", "do-ambiente")
    assert discogs_authorization("") == "Discogs token=do-ambiente"
    assert discogs_authorization(None) == "Discogs token=do-ambiente"


def test_discogs_cai_para_o_arquivo(pasta):
    gravar(pasta, {"discogs_key": "k-arquivo", "discogs_secret": "s-arquivo"})
    assert discogs_authorization(None) == "Discogs key=k-arquivo, secret=s-arquivo"
    assert discogs_disponivel(None)


def test_discogs_sem_nada_e_none(pasta):
    assert discogs_authorization(None) is None
    assert not discogs_disponivel("")


def test_chave_antiga_no_arquivo_e_ignorada(pasta):
    """chaves.json de versões anteriores (com a chave de uma API removida) não quebra nada nem vira credencial."""
    gravar(pasta, {"lastfm_api_key": "sobra-antiga-0123456789", "discogs_key": "k", "discogs_secret": "s"})
    assert ler_embutidas(pasta) == {"discogs_key": "k", "discogs_secret": "s"}
    assert "sobra-antiga-0123456789" not in credenciais.credenciais_conhecidas(pasta=pasta)
    gravar(pasta, {"lastfm_api_key": "sobra-antiga-0123456789"})
    assert ler_embutidas(pasta) == {} and not discogs_disponivel(None)


def test_chave_antiga_nas_configuracoes_e_ignorada():
    config = {"lastfm_api_key": "chave-colada-antiga-0123456789", "discogs_token": ""}
    assert credenciais.credenciais_da_config(config) == ()
    assert not credenciais.estado_servicos(config)["discogs"].disponivel


def test_valores_so_com_espacos_sao_ignorados(pasta, monkeypatch):
    gravar(pasta, {"discogs_key": "  k-arquivo  ", "discogs_secret": "s-arquivo"})
    monkeypatch.setenv("TAGGER_DISCOGS_TOKEN", "   ")
    assert discogs_authorization("  \t ") == "Discogs key=k-arquivo, secret=s-arquivo"


def test_pasta_no_exe_usa_meipass(monkeypatch, tmp_path):
    monkeypatch.setattr(credenciais.sys, "frozen", True, raising=False)
    monkeypatch.setattr(credenciais.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert credenciais.pasta_chaves() == tmp_path / "tagger" / "nucleo"


def test_pasta_fora_do_exe_e_a_do_modulo():
    assert credenciais.pasta_chaves() == Path(credenciais.__file__).parent


# --- chaves.json ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("conteudo", ["", "{não é json", "[1, 2]", '"texto"', "null"])
def test_arquivo_vazio_ou_invalido_e_sem_chave(pasta, conteudo):
    gravar(pasta, conteudo)
    assert ler_embutidas() == {}
    assert discogs_authorization(None) is None


def test_arquivo_ausente_e_sem_chave(pasta, caplog):
    with caplog.at_level(logging.WARNING):
        assert ler_embutidas() == {}
    assert not caplog.records


def test_arquivo_com_bom_e_lido(pasta):
    (pasta / "chaves.json").write_text(json.dumps({"discogs_key": "k", "discogs_secret": "s"}), encoding="utf-8-sig")
    assert discogs_authorization(None) == "Discogs key=k, secret=s"


def test_arquivo_invalido_avisa_no_log_sem_valores(pasta, caplog):
    gravar(pasta, '{"discogs_key": "valor-que-nao-pode-aparecer"')
    with caplog.at_level(logging.WARNING, logger="tagger"):
        assert ler_embutidas() == {}
    assert len(caplog.records) == 1
    assert "chaves.json" in caplog.text and "valor-que-nao-pode-aparecer" not in caplog.text


def test_arquivo_invalido_avisa_uma_vez_so(pasta, caplog):
    gravar(pasta, "{quebrado de novo")
    with caplog.at_level(logging.WARNING, logger="tagger"):
        for _ in range(3):
            discogs_authorization(None)
    assert len(caplog.records) == 1


def test_ocultar_nao_avisa_nem_entra_em_recursao(pasta, caplog):
    gravar(pasta, "{quebrado")
    with caplog.at_level(logging.WARNING, logger="tagger"):
        ocultar_credenciais("texto")
    assert not caplog.records


def test_no_exe_le_o_arquivo_uma_vez(monkeypatch, tmp_path):
    pasta = tmp_path / "tagger" / "nucleo"
    pasta.mkdir(parents=True)
    gravar(pasta, {"discogs_key": "primeira", "discogs_secret": "s"})
    monkeypatch.setattr(credenciais.sys, "frozen", True, raising=False)
    monkeypatch.setattr(credenciais.sys, "_MEIPASS", str(tmp_path), raising=False)
    credenciais._ler_em_cache.cache_clear()
    try:
        assert discogs_authorization(None) == "Discogs key=primeira, secret=s"
        gravar(pasta, {"discogs_key": "segunda", "discogs_secret": "s"})
        assert discogs_authorization(None) == "Discogs key=primeira, secret=s"
    finally:
        credenciais._ler_em_cache.cache_clear()


def test_arquivo_ignora_valores_vazios_e_nao_texto(pasta):
    gravar(pasta, {"discogs_key": 123, "discogs_secret": "s"})
    assert ler_embutidas() == {"discogs_secret": "s"}


def test_token_no_arquivo_nunca_e_usado(pasta):
    gravar(pasta, {"discogs_token": "token-embutido"})
    assert discogs_authorization(None) is None


# --- Discogs -------------------------------------------------------------------------------------------

def test_discogs_token_tem_prioridade(pasta, monkeypatch):
    gravar(pasta, {"discogs_key": "k", "discogs_secret": "s"})
    monkeypatch.setenv("TAGGER_DISCOGS_TOKEN", "token-ambiente")
    assert discogs_authorization(" meu-token ") == "Discogs token=meu-token"
    assert discogs_authorization("") == "Discogs token=token-ambiente"


def test_discogs_key_secret_do_arquivo(pasta):
    gravar(pasta, {"discogs_key": "k", "discogs_secret": "s"})
    assert discogs_authorization(None) == "Discogs key=k, secret=s"
    assert discogs_disponivel(None)


def test_discogs_key_secret_do_ambiente_vencem_arquivo(pasta, monkeypatch):
    gravar(pasta, {"discogs_key": "k", "discogs_secret": "s"})
    monkeypatch.setenv("TAGGER_DISCOGS_KEY", "ka")
    monkeypatch.setenv("TAGGER_DISCOGS_SECRET", "sa")
    assert discogs_authorization(None) == "Discogs key=ka, secret=sa"


def test_discogs_par_incompleto_nao_mistura_origens(pasta, monkeypatch):
    gravar(pasta, {"discogs_key": "k", "discogs_secret": "s"})
    monkeypatch.setenv("TAGGER_DISCOGS_KEY", "ka")      # sem o secret no ambiente
    assert discogs_authorization(None) == "Discogs key=k, secret=s"


def test_discogs_sem_secret_e_none(pasta):
    gravar(pasta, {"discogs_key": "k"})
    assert discogs_authorization(None) is None
    assert not discogs_disponivel("  ")


# --- ocultar_credenciais -------------------------------------------------------------------------------

def test_oculta_api_key_na_url(pasta):
    url = "https://api.exemplo.com/2.0/?method=album.getinfo&api_key=abc123&format=json"
    assert ocultar_credenciais(url) == ("https://api.exemplo.com/2.0/?method=album.getinfo"
                                        "&api_key=***&format=json")
    assert ocultar_credenciais("...?api_key%3Dabc123%26x") == "...?api_key%3D***%26x"


def test_oculta_cabecalho_discogs_com_token(pasta):
    texto = "Authorization: Discogs token=AbC123xyz"
    assert ocultar_credenciais(texto) == "Authorization: Discogs token=***"


def test_oculta_cabecalho_discogs_com_key_secret(pasta):
    texto = "{'Authorization': 'Discogs key=minhakey, secret=meusecret', 'User-Agent': 'Tagger/2.1'}"
    assert ocultar_credenciais(texto) == ("{'Authorization': 'Discogs key=***, secret=***', "
                                          "'User-Agent': 'Tagger/2.1'}")


def test_oculta_credencial_literal_num_traceback(pasta, monkeypatch):
    gravar(pasta, {"discogs_key": "chave-embutida-123", "discogs_secret": "s"})
    monkeypatch.setenv("TAGGER_DISCOGS_TOKEN", "token-do-ambiente")
    rastro = ("Traceback (most recent call last):\n"
              '  File "busca.py", line 10, in buscar\n'
              "urllib.error.HTTPError: HTTP Error 403 for chave-embutida-123 / token-do-ambiente / config-xyz-0123456789\n")
    oculto = ocultar_credenciais(rastro, conhecidas=["config-xyz-0123456789"])
    assert "chave-embutida-123" not in oculto
    assert "token-do-ambiente" not in oculto
    assert "config-xyz-0123456789" not in oculto
    assert oculto.count("***") == 3
    assert oculto.startswith("Traceback (most recent call last):")


@pytest.mark.parametrize("texto, esperado", [
    ("{'api_key': 'abc123', 'x': 1}", "{'api_key': '***', 'x': 1}"),
    ('{"api_key":"abc123","format":"json"}', '{"api_key":"***","format":"json"}'),
    ("https://ws/2.0/?api%5Fkey=abc123&x=1", "https://ws/2.0/?api%5Fkey=***&x=1"),
    ("https://ws/2.0/?API_KEY=abc123", "https://ws/2.0/?API_KEY=***"),
    ('Authorization: Discogs token="AbC123xyz"', 'Authorization: Discogs token="***"'),
    ("token = AbC123xyz fim", "token = *** fim"),
    ("token: AbC123xyz", "token: ***"),
    ("https://api.discogs.com/database/search?q=x&key=minhakey&secret=meusecret&page=2",
     "https://api.discogs.com/database/search?q=x&key=***&secret=***&page=2"),
    ("{'Authorization': 'Discogs key=k1, secret=s1'}", "{'Authorization': 'Discogs key=***, secret=***'}"),
    ("u=https%3A%2F%2Fws%2F2.0%2F%3Fmethod%3Dx%26api_key%3Dabc123def", "u=https%3A%2F%2Fws%2F2.0%2F%3Fmethod%3Dx%26api_key%3D***"),
    ("x%3Fapi_key%3Dabc123", "x%3Fapi_key%3D***"),
    ("x%3fapi_key%3dabc123%26y", "x%3fapi_key%3d***%26y"),
    ("x%26key%3Dk1%26secret%3Ds1", "x%26key%3D***%26secret%3D***"),
    ("TAGGER_DISCOGS_TOKEN=TOK", "TAGGER_DISCOGS_TOKEN=***"),
    ("discogs_secret: S1", "discogs_secret: ***"),
    ("discogs_key=K1 resto", "discogs_key=*** resto"),
])
def test_oculta_outras_formas(pasta, texto, esperado):
    assert ocultar_credenciais(texto) == esperado


def test_nao_confunde_palavras_que_terminam_em_key(pasta):
    texto = "monkey=banana; hotkey: F5; KeyError: 'title'"
    assert ocultar_credenciais(texto) == texto


def test_nao_atravessa_quebra_de_linha(pasta):
    texto = 'secret:\n  File "busca.py", line 10'
    assert ocultar_credenciais(texto) == texto
    assert ocultar_credenciais("token =\nAbC123") == "token =\nAbC123"


def test_credencial_literal_curta_nao_e_trocada(pasta):
    texto = "Falha ao abrir a pasta rock/abc"
    assert ocultar_credenciais(texto, conhecidas=["abc", "rock"]) == texto


def test_nao_estraga_texto_sem_credenciais(pasta):
    texto = "Falha ao ler 01 - Faixa.mp3: arquivo corrompido"
    assert ocultar_credenciais(texto) == texto
    assert ocultar_credenciais("") == ""
    assert ocultar_credenciais(None) is None


def test_formatador_do_log_oculta_mensagem_e_excecao(pasta):
    formatador = FormatadorSemCredenciais("%(message)s", conhecidas=lambda: ["segredo-da-config"])
    try:
        raise OSError("falha em https://x/?api_key=abc123 com segredo-da-config")
    except OSError:
        import sys
        registro = logging.LogRecord("tagger", logging.ERROR, __file__, 1, "erro: %s", ("api_key=zzz9",),
                                     sys.exc_info())
    linha = formatador.format(registro)
    assert "abc123" not in linha and "zzz9" not in linha and "segredo-da-config" not in linha
    assert "api_key=***" in linha


# --- scripts/gerar_chaves.py ---------------------------------------------------------------------------

@pytest.fixture
def gerar_chaves():
    caminho = Path(__file__).resolve().parent.parent / "scripts" / "gerar_chaves.py"
    spec = importlib.util.spec_from_file_location("gerar_chaves", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_gerar_chaves_grava_o_json(gerar_chaves, tmp_path, capsys):
    destino = tmp_path / "nucleo" / "chaves.json"
    avisos = gerar_chaves.gerar(destino, {"LASTFM_API_KEY": "lf", "DISCOGS_KEY": " dk ", "DISCOGS_SECRET": "ds"})
    assert avisos == []
    assert json.loads(destino.read_text(encoding="utf-8")) == {
        "discogs_key": "dk", "discogs_secret": "ds"}
    assert ler_embutidas(destino.parent) == {"discogs_key": "dk", "discogs_secret": "ds"}


def test_gerar_chaves_avisa_sem_falhar_e_nao_imprime_valores(gerar_chaves, tmp_path, monkeypatch, capsys):
    destino = tmp_path / "chaves.json"
    monkeypatch.setattr(gerar_chaves, "DESTINO", destino)
    monkeypatch.setenv("DISCOGS_KEY", "valor-secreto-key")
    monkeypatch.delenv("DISCOGS_SECRET", raising=False)
    assert gerar_chaves.main() == 0
    saida = capsys.readouterr()
    texto = saida.out + saida.err
    assert "::warning::Sem DISCOGS_SECRET:" in texto
    assert "valor-secreto" not in texto
    assert json.loads(destino.read_text(encoding="utf-8"))["discogs_secret"] == ""


# --- estado para a GUI ---------------------------------------------------------------------------------

def test_estado_servicos_sem_nada_traz_dicas(pasta):
    estado = credenciais.estado_servicos({"discogs_token": "  "})
    assert not estado["discogs"].disponivel and "token" in estado["discogs"].dica
    assert credenciais.estado_servicos(None) == estado


def test_estado_servicos_com_valores_da_config(pasta):
    estado = credenciais.estado_servicos({"discogs_token": "meu"})
    assert estado["discogs"] == credenciais.EstadoServico(True, None)


def test_estado_servicos_com_chaves_embutidas(pasta):
    gravar(pasta, {"discogs_key": "k", "discogs_secret": "s"})
    estado = credenciais.estado_servicos({})
    assert estado["discogs"].disponivel


def test_credenciais_da_config_vao_para_a_ocultacao(pasta):
    config = {"discogs_token": " chave-colada-0123456789 ", "tema_escuro": "grafite"}
    assert credenciais.credenciais_da_config(config) == ("chave-colada-0123456789",)
    texto = ocultar_credenciais("falhou com chave-colada-0123456789", credenciais.credenciais_da_config(config))
    assert texto == "falhou com ***"
