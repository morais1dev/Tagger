"""Histórico de desfazer/refazer (tagger/nucleo/historico.py), sem Qt.

Reproduz o que a janela faz: grava com executar_salvamento, entrega ao Historico o que deu certo
e usa Historico.retirar/preparar para desfazer e refazer."""

import os
from pathlib import Path

import pytest

from tagger.nucleo.historico import (
    ARQUIVOS, DESCARTAR, DESFAZER, NADA, ORGANIZAR, REFAZER, TAGS, Historico,
)
from tagger.nucleo.metadata import carregar, salvar
from tagger.nucleo.rascunho import Rascunho, Renomeacao, executar_salvamento


@pytest.fixture
def faixas(fabrica_mp3):
    caminhos = [fabrica_mp3(f"{i}.mp3") for i in (1, 2)]
    salvar(caminhos[0], {"title": "Um", "artist": "A"})
    salvar(caminhos[1], {"title": "Dois", "artist": "B"})
    return [carregar(c) for c in caminhos]


def _gravar(historico, rascunho, faixas):
    """O que JanelaPrincipal._ao_salvar faz depois de executar_salvamento. Devolve as faixas relidas."""
    mtimes = {f.caminho: f.mtime for f in faixas}
    registros, falhas, relidas = executar_salvamento(rascunho.trabalhos(), mtimes=mtimes)
    salvos = [f.caminho for f in relidas if f.caminho not in falhas]
    rascunho.descartar(salvos)
    historico.registrar_gravacao([r for r in registros if r[0] not in falhas])
    return relidas, falhas


def _por_caminho(faixas):
    return {f.caminho: f for f in faixas}


def _titulo(faixa):
    return carregar(faixa.caminho).tags["title"]


# ---------------------------------------------------------------- gravação
def test_gravacao_nova_vai_para_desfazer_e_limpa_refazer(faixas):
    h = Historico()
    h.refazer.append([("x", {}, None)])
    r = Rascunho()
    r.definir([faixas[0]], "title", "Novo")
    _gravar(h, r, faixas)
    assert len(h.desfazer) == 1 and h.refazer == []
    caminho, anteriores, _capa = h.desfazer[0][0]
    assert caminho == faixas[0].caminho and anteriores == {"title": "Um"}


def test_gravacao_com_falha_parcial_so_guarda_os_que_gravaram(faixas):
    h = Historico()
    r = Rascunho()
    r.definir(faixas, "title", "Novo")
    salvar(faixas[0].caminho, {"title": "De outro programa"})          # o 1º muda no disco depois de lido
    depois = faixas[0].mtime + 5_000_000_000
    os.utime(faixas[0].caminho, ns=(depois, depois))

    _relidas, falhas = _gravar(h, r, faixas)
    assert list(falhas) == [faixas[0].caminho]
    assert [reg[0] for reg in h.desfazer[0]] == [faixas[1].caminho]    # só o 2º entra no histórico
    assert r.tem(faixas[0].caminho) and not r.tem(faixas[1].caminho)   # o que falhou continua pendente


def test_gravacao_que_falhou_inteira_nao_mexe_nas_pilhas(faixas, monkeypatch):
    def falhar(*_a, **_k):
        raise PermissionError("somente leitura")
    monkeypatch.setattr("tagger.nucleo.rascunho.salvar", falhar)
    h = Historico()
    h.refazer.append([("x", {}, None)])
    r = Rascunho()
    r.definir([faixas[0]], "title", "X")
    _gravar(h, r, faixas)
    assert h.desfazer == [] and len(h.refazer) == 1                    # sem registro novo, refazer fica
    assert h.pendente is None


# ---------------------------------------------------------------- desfazer
def test_desfazer_volta_para_pendente_e_so_grava_ao_salvar(faixas):
    h = Historico()
    r = Rascunho()
    r.definir([faixas[0]], "title", "Novo")
    relidas, _ = _gravar(h, r, faixas)
    assert _titulo(faixas[0]) == "Novo"

    acao, registros = h.retirar(DESFAZER, r.vazio)
    assert acao == TAGS and h.desfazer == []
    mudou = h.preparar(registros, DESFAZER, r, _por_caminho(relidas))
    assert mudou == {faixas[0].caminho}
    assert h.pendente == (registros, DESFAZER)
    assert r.valor(relidas[0], "title") == "Um" and _titulo(faixas[0]) == "Novo"   # pendente, nada gravado

    _gravar(h, r, relidas)                                              # "Salvar" confirma o desfazer
    assert _titulo(faixas[0]) == "Um"
    assert h.pendente is None and h.desfazer == [] and len(h.refazer) == 1


def test_desfazer_com_pendencia_so_descarta(faixas):
    h = Historico()
    r = Rascunho()
    r.definir([faixas[0]], "title", "A")
    _gravar(h, r, faixas)
    r.definir([faixas[0]], "title", "B")                                # nova edição, ainda não salva
    assert h.retirar(DESFAZER, r.vazio) == (DESCARTAR, None)
    assert len(h.desfazer) == 1                                         # a pilha não foi tocada


def test_desfazer_com_desfazer_nao_confirmado_descarta_e_devolve_para_a_pilha(faixas):
    h = Historico()
    r = Rascunho()
    r.definir([faixas[0]], "title", "Novo")
    relidas, _ = _gravar(h, r, faixas)
    _acao, registros = h.retirar(DESFAZER, r.vazio)
    h.preparar(registros, DESFAZER, r, _por_caminho(relidas))
    r.descartar()                                                       # (o usuário descarta o rascunho)
    assert h.retirar(DESFAZER, r.vazio) == (DESCARTAR, None)            # ainda há desfazer não confirmado
    h.descartar_pendente()
    assert h.pendente is None and h.desfazer == [registros] and h.refazer == []


def test_desfazer_sem_nada_e_pilha_vazia(faixas):
    h = Historico()
    assert h.retirar(DESFAZER, True) == (NADA, None)
    assert h.retirar(REFAZER, True) == (NADA, None)
    assert not h.pode_desfazer(False) and not h.pode_refazer(False)


def test_desfazer_que_nao_muda_nada_perde_o_item_e_nao_deixa_pendente(faixas):
    h = Historico()
    r = Rascunho()
    r.definir([faixas[0]], "title", "Novo")
    relidas, _ = _gravar(h, r, faixas)
    salvar(faixas[0].caminho, {"title": "Um"})                          # o arquivo já voltou sozinho
    relidas = [carregar(f.caminho) for f in faixas]
    _acao, registros = h.retirar(DESFAZER, r.vazio)
    assert h.preparar(registros, DESFAZER, r, _por_caminho(relidas)) == set()
    assert h.pendente is None and h.desfazer == [] and h.refazer == []


# ---------------------------------------------------------------- refazer
def test_refazer_depois_de_desfazer(faixas):
    h = Historico()
    r = Rascunho()
    r.definir([faixas[0]], "title", "Novo")
    relidas, _ = _gravar(h, r, faixas)
    _acao, registros = h.retirar(DESFAZER, r.vazio)
    h.preparar(registros, DESFAZER, r, _por_caminho(relidas))
    relidas, _ = _gravar(h, r, relidas)
    assert _titulo(faixas[0]) == "Um" and h.pode_refazer(False)

    acao, registros = h.retirar(REFAZER, r.vazio)
    assert acao == TAGS and h.refazer == []
    h.preparar(registros, REFAZER, r, _por_caminho(relidas))
    assert r.valor(relidas[0], "title") == "Novo" and _titulo(faixas[0]) == "Um"
    _gravar(h, r, relidas)
    assert _titulo(faixas[0]) == "Novo"
    # gravar um REFAZER devolve o registro ao desfazer, sem apagar o que ainda houver para refazer
    assert len(h.desfazer) == 1 and h.pendente is None


def test_refazer_so_com_rascunho_vazio(faixas):
    h = Historico()
    h.refazer.append([("x", {}, None)])
    assert h.retirar(REFAZER, rascunho_vazio=False) == (NADA, None)
    assert len(h.refazer) == 1


def test_nova_alteracao_limpa_a_pilha_de_refazer(faixas):
    h = Historico()
    r = Rascunho()
    r.definir([faixas[0]], "title", "A")
    relidas, _ = _gravar(h, r, faixas)
    _acao, registros = h.retirar(DESFAZER, r.vazio)
    h.preparar(registros, DESFAZER, r, _por_caminho(relidas))
    relidas, _ = _gravar(h, r, relidas)
    assert len(h.refazer) == 1

    r.definir([relidas[0]], "title", "Outra")                           # edição nova
    _gravar(h, r, relidas)
    assert h.refazer == [] and len(h.desfazer) == 1


# ---------------------------------------------------------------- renomear / mover
def _pares(*nomes):
    return [(Path(f"{a}.mp3"), Path(f"{b}.mp3")) for a, b in nomes]


def test_renomear_vai_para_desfazer_e_limpa_refazer():
    h = Historico()
    h.refazer.append([("x", {}, None)])
    h.registrar_renomeacao(_pares(("a", "b")))
    assert h.desfazer == [Renomeacao(_pares(("a", "b")))] and h.refazer == []


def test_renomear_sem_nenhum_arquivo_nao_mexe_nas_pilhas():
    h = Historico()
    h.refazer.append([("x", {}, None)])
    h.registrar_renomeacao([])
    assert h.desfazer == [] and len(h.refazer) == 1


def test_desfazer_de_renomeacao_move_de_volta_e_refazer_move_de_novo():
    h = Historico()
    h.registrar_renomeacao(_pares(("a", "b"), ("c", "d")))
    acao, item = h.retirar(DESFAZER, True)
    assert acao == ARQUIVOS and item.inversa().pares == _pares(("b", "a"), ("d", "c"))

    h.concluir_reversao(DESFAZER, item, feitos=_pares(("b", "a"), ("d", "c")), falhas={})
    assert h.desfazer == [] and h.refazer == [Renomeacao(_pares(("b", "a"), ("d", "c")))]

    acao, item = h.retirar(REFAZER, True)
    assert acao == ARQUIVOS
    h.concluir_reversao(REFAZER, item, feitos=_pares(("a", "b"), ("c", "d")), falhas={})
    assert h.refazer == [] and h.desfazer == [Renomeacao(_pares(("a", "b"), ("c", "d")))]


def test_desfazer_de_renomeacao_com_falha_parcial_mantem_o_que_sobrou():
    h = Historico()
    h.registrar_renomeacao(_pares(("a", "b"), ("c", "d")))
    _acao, item = h.retirar(DESFAZER, True)
    h.concluir_reversao(DESFAZER, item, feitos=_pares(("b", "a")), falhas={Path("d.mp3"): "em uso"})
    assert h.refazer == [Renomeacao(_pares(("b", "a")))]
    assert h.desfazer == [Renomeacao(_pares(("c", "d")))]               # o que não voltou tenta de novo


def test_desfazer_de_renomeacao_que_falhou_inteira_devolve_tudo():
    h = Historico()
    h.registrar_renomeacao(_pares(("a", "b")))
    _acao, item = h.retirar(DESFAZER, True)
    h.concluir_reversao(DESFAZER, item, feitos=[], falhas={Path("b.mp3"): "em uso"})
    assert h.refazer == [] and h.desfazer == [Renomeacao(_pares(("a", "b")))]


def test_movimento_interrompido_numa_acao_nova():
    h = Historico()
    h.refazer.append([("x", {}, None)])
    h.registrar_movimento_interrompido(ORGANIZAR, _pares(("a", "b")))
    assert h.desfazer == [Renomeacao(_pares(("a", "b")))] and h.refazer == []
    h.registrar_movimento_interrompido(ORGANIZAR, [])                   # nada saiu do lugar
    assert len(h.desfazer) == 1


def test_movimento_interrompido_num_desfazer_devolve_o_que_faltou():
    h = Historico()
    h.registrar_renomeacao(_pares(("a", "b"), ("c", "d")))
    _acao, item = h.retirar(DESFAZER, True)
    h.registrar_movimento_interrompido(DESFAZER, _pares(("b", "a")), item)    # só o 1º voltou
    assert h.refazer == [Renomeacao(_pares(("b", "a")))]
    assert h.desfazer == [Renomeacao(_pares(("c", "d")))]


def test_migrar_atualiza_pilhas_e_pendente():
    h = Historico()
    h.registrar_renomeacao(_pares(("a", "b")))
    h.refazer.append(Renomeacao(_pares(("c", "b"))))
    h.pendente = ([(Path("b.mp3"), {"title": "X"}, None)], DESFAZER)
    h.migrar({Path("b.mp3"): Path("z.mp3")})
    assert h.desfazer == [Renomeacao(_pares(("a", "z")))]
    assert h.refazer == [Renomeacao(_pares(("c", "z")))]
    assert h.pendente[0][0][0] == Path("z.mp3") and h.pendente[1] == DESFAZER


def test_limpar_ao_abrir_outra_pasta():
    h = Historico()
    h.registrar_renomeacao(_pares(("a", "b")))
    h.refazer.append([("x", {}, None)])
    h.pendente = ([("x", {}, None)], REFAZER)
    h.limpar()
    assert h.desfazer == [] and h.refazer == [] and h.pendente is None


def test_pode_desfazer_e_refazer():
    h = Historico()
    assert not h.pode_desfazer(False) and h.pode_desfazer(True)         # pendência: o botão vira "descartar"
    h.pendente = ([], DESFAZER)
    assert h.pode_desfazer(False)
    h.refazer.append([])
    assert h.pode_refazer(False) and not h.pode_refazer(True)
