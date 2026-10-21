import os

import pytest

from tagger.nucleo import metadata
from tagger.nucleo.metadata import VARIOS, carregar, ler_capa, salvar
from tagger.nucleo.rascunho import (
    FALTA, SEM_CAPA, Rascunho, Renomeacao, executar_salvamento, migrar_historico,
)

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-falso" * 10


@pytest.fixture(autouse=True)
def config_padrao(monkeypatch):
    monkeypatch.setattr(metadata, "VERSAO_ID3", 3)
    monkeypatch.setattr(metadata, "MULTIVALOR", True)


@pytest.fixture
def faixas(fabrica_mp3):
    caminhos = [fabrica_mp3(f"{i}.mp3") for i in (1, 2)]
    salvar(caminhos[0], {"title": "Um", "artist": "A"})
    salvar(caminhos[1], {"title": "Dois", "artist": "B"})
    return [carregar(c) for c in caminhos]


def _salvar(rascunho, faixas):
    mtimes = {f.caminho: f.mtime for f in faixas}
    resultado = executar_salvamento(rascunho.trabalhos(), mtimes=mtimes)
    rascunho.descartar()
    return resultado


def test_definir_e_valor(faixas):
    r = Rascunho()
    avisos = []
    r.ao_mudar = avisos.append
    r.definir(faixas, "album", "Disco")
    assert r.valor(faixas[0], "album") == "Disco" and r.valor(faixas[0], "title") == "Um"
    assert len(r) == 2 and r.quantidade_campos() == 2
    assert avisos == [{f.caminho for f in faixas}]


def test_valor_igual_ao_do_arquivo_nao_fica_pendente(faixas):
    r = Rascunho()
    r.definir([faixas[0]], "title", "Outro")
    r.definir([faixas[0]], "title", "Um")
    assert r.vazio


def test_varios_valores_restaurar(faixas):
    """No painel, apagar o que foi digitado num campo ‹vários valores› volta ao estado anterior."""
    r = Rascunho()
    r.definir([faixas[0]], "artist", "Pendente")
    foto = r.fotografar([f.caminho for f in faixas], "artist")
    assert foto[faixas[1].caminho] is FALTA

    r.definir(faixas, "artist", "Novo")
    r.restaurar(foto, "artist")
    assert r.valor(faixas[0], "artist") == "Pendente"
    assert r.valor(faixas[1], "artist") == "B" and not r.tem(faixas[1].caminho)


def test_salvar_varios_e_ignorado(faixas):
    r = Rascunho()
    r.definir_por_faixa([(faixas[0], {"artist": VARIOS, "album": "X"})])
    _registros, falhas, relidas = _salvar(r, faixas)
    assert not falhas
    assert relidas[0].tags["artist"] == "A" and relidas[0].tags["album"] == "X"


def test_desfazer_tags(faixas):
    r = Rascunho()
    r.definir(faixas, "album", "Novo")
    registros, falhas, relidas = _salvar(r, faixas)
    assert not falhas and all(f.tags["album"] == "Novo" for f in relidas)
    assert registros == [(f.caminho, {"album": ""}, SEM_CAPA) for f in faixas]

    # desfazer = coloca os valores antigos no rascunho; nada é gravado até salvar
    mudou = r.aplicar_registros(registros, {f.caminho: f for f in relidas})
    assert mudou == {f.caminho for f in faixas}
    assert all(carregar(f.caminho).tags["album"] == "Novo" for f in faixas)
    _salvar(r, relidas)
    assert all(carregar(f.caminho).tags["album"] == "" for f in faixas)


def test_desfazer_capa(faixas):
    r = Rascunho()
    r.definir_capa([faixas[0].caminho], ("definir", JPEG, "image/jpeg"))
    r.definir([faixas[0]], "title", "Com capa")
    registros, falhas, relidas = _salvar(r, faixas)
    assert not falhas and ler_capa(faixas[0].caminho) == (JPEG, "image/jpeg")
    assert registros[0][2] is None                       # antes não havia capa

    r.aplicar_registros(registros, {f.caminho: f for f in relidas})
    assert r.capa(faixas[0].caminho) == ("remover",)
    _salvar(r, relidas)
    assert ler_capa(faixas[0].caminho) is None and carregar(faixas[0].caminho).tags["title"] == "Um"


def test_arquivo_modificado_por_fora_nao_e_sobrescrito(faixas):
    r = Rascunho()
    r.definir([faixas[0]], "title", "Meu")
    salvar(faixas[0].caminho, {"title": "De outro programa"})
    depois = faixas[0].mtime + 5_000_000_000
    os.utime(faixas[0].caminho, ns=(depois, depois))

    registros, falhas, _relidas = _salvar(r, faixas)
    assert faixas[0].caminho in falhas and not registros
    assert carregar(faixas[0].caminho).tags["title"] == "De outro programa"


def test_falha_de_gravacao_nao_gera_registro(faixas, monkeypatch):
    def falhar(*_a, **_k):
        raise PermissionError("somente leitura")
    monkeypatch.setattr("tagger.nucleo.rascunho.salvar", falhar)
    r = Rascunho()
    r.definir([faixas[0]], "title", "X")
    registros, falhas, _ = _salvar(r, faixas)
    assert not registros and "somente leitura" in falhas[faixas[0].caminho]


def test_validar(faixas):
    r = Rascunho()
    r.definir([faixas[0]], "date", "24")
    assert [(c, campo) for c, campo, _m in r.validar()] == [(faixas[0].caminho, "date")]


def test_renomear_leva_o_rascunho_junto(faixas, tmp_path):
    r = Rascunho()
    r.definir([faixas[0]], "title", "X")
    r.definir_capa([faixas[0].caminho], ("remover",))
    novo = tmp_path / "novo.mp3"
    r.renomear({faixas[0].caminho: novo})
    assert r.caminhos() == {novo}


def test_migrar_historico(tmp_path):
    a, b, c = (tmp_path / n for n in ("a.mp3", "b.mp3", "c.mp3"))
    pilha = [[(a, {"title": ""}, SEM_CAPA)], Renomeacao([(c, a)])]
    migrar_historico(pilha, {a: b})
    assert pilha[0] == [(b, {"title": ""}, SEM_CAPA)]
    assert pilha[1].pares == [(c, b)]
    assert pilha[1].inversa().pares == [(b, c)]
