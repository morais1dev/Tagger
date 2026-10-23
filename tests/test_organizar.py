from pathlib import Path

import pytest

from tagger.nucleo.organizar import (
    caminho_relativo, executar_movimentos, executar_organizacao, partes_do_padrao, planejar_organizacao,
    remover_pastas_vazias,
)
from tagger.nucleo.padroes import ItemRenomear

PADRAO = "{albumartist}/{album}/{tracknumber:02} - {title}"
TAGS = {"albumartist": "Artista", "album": "Álbum", "tracknumber": "3/12", "title": "Música"}


def test_caminho_relativo():
    assert caminho_relativo(PADRAO, TAGS) == ["Artista", "Álbum", "03 - Música"]


def test_caracteres_invalidos_nas_pastas():
    tags = {**TAGS, "albumartist": "AC/DC", "album": "Who?"}
    assert caminho_relativo(PADRAO, tags)[:2] == ["AC-DC", "Who"]


def test_tags_vazias_usam_padrao():
    assert caminho_relativo(PADRAO, {"title": "T"}) == ["Unknown Artist", "Unknown Album", "T"]


def test_artista_do_album_cai_para_artista():
    assert caminho_relativo(PADRAO, {"artist": "Solo", "title": "T"})[0] == "Solo"


def test_nome_vazio_usa_nome_original():
    assert caminho_relativo(PADRAO, {"album": "A"}, "original")[-1] == "original"


@pytest.mark.parametrize("padrao", ["", "///", "{artista}/{title}", "C:/{title}", "sem campos", "../{title}/.."])
def test_padrao_invalido(padrao):
    with pytest.raises(ValueError):
        partes_do_padrao(padrao)


def test_planejar_e_mover_cria_pastas(fabrica_mp3, tmp_path):
    a = fabrica_mp3("origem/a.mp3")
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "destino", levar_capa=False)
    assert plano.itens[0].destino == tmp_path / "destino" / "Artista" / "Álbum" / "03 - Música.mp3"
    feitos, falhas, _ = executar_organizacao(plano)
    assert not falhas, falhas
    assert feitos == [(a, plano.itens[0].destino)]
    assert plano.itens[0].destino.exists() and not a.exists()


def test_ja_no_lugar(fabrica_mp3, tmp_path):
    a = fabrica_mp3("Artista/Álbum/03 - Música.mp3")
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path)
    assert plano.itens[0].destino is None and not plano.itens[0].erro


def test_conflitos(fabrica_mp3, tmp_path):
    a, b, c = fabrica_mp3("a.mp3"), fabrica_mp3("b.mp3"), fabrica_mp3("c.mp3")
    existente = fabrica_mp3("dest/X/Y/01 - Outra.mp3")
    iguais = {"albumartist": "P", "album": "Q", "title": "Mesma"}
    plano = planejar_organizacao(
        [(a, iguais), (b, iguais), (c, {"albumartist": "X", "album": "Y", "tracknumber": "1", "title": "Outra"})],
        PADRAO, tmp_path / "dest", levar_capa=False)
    assert plano.itens[0].erro and plano.itens[1].erro
    assert "Já existe" in plano.itens[2].erro and existente.exists()
    feitos, _, _ = executar_organizacao(plano)
    assert feitos == [] and a.exists() and b.exists() and c.exists()


def test_capa_vai_junto_so_se_a_pasta_fica_sem_faixas(fabrica_mp3, tmp_path):
    a, b = fabrica_mp3("p1/a.mp3"), fabrica_mp3("p1/b.mp3")
    (tmp_path / "p1" / "Cover.JPG").write_bytes(b"x")
    # só uma das faixas se move: a capa fica
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "d")
    assert plano.capas == []
    # as duas vão para o mesmo álbum: a capa acompanha
    plano = planejar_organizacao([(a, TAGS), (b, {**TAGS, "tracknumber": "4"})], PADRAO, tmp_path / "d")
    assert [c.destino for c in plano.capas] == [tmp_path / "d" / "Artista" / "Álbum" / "Cover.JPG"]
    # álbuns diferentes: a capa não vai para nenhum
    plano = planejar_organizacao([(a, TAGS), (b, {**TAGS, "album": "Outro"})], PADRAO, tmp_path / "d")
    assert plano.capas == []


def test_organizar_levando_capa_e_removendo_vazias_e_desfazer(fabrica_mp3, tmp_path):
    a = fabrica_mp3("bagunca/sub/a.mp3")
    capa = a.parent / "cover.jpg"
    capa.write_bytes(b"x")
    destino = tmp_path / "musicas"
    plano = planejar_organizacao([(a, TAGS)], PADRAO, destino)
    feitos, falhas, removidas = executar_organizacao(plano, remover_vazias=True)

    assert not falhas, falhas
    assert len(feitos) == 2
    assert (destino / "Artista" / "Álbum" / "cover.jpg").exists()
    assert not (tmp_path / "bagunca" / "sub").exists()          # a pasta de origem ficou vazia
    assert (tmp_path / "bagunca").exists()                      # mas nunca sobe sem uma raiz
    assert [p.name for p in removidas] == ["sub"]
    assert destino.exists()

    # desfazer: move de volta e recria as pastas
    volta, falhas = executar_movimentos([ItemRenomear(d, o) for o, d in feitos])
    assert not falhas, falhas
    assert len(volta) == 2
    assert a.exists() and capa.exists()


def test_nao_remove_pasta_com_arquivos_nem_o_destino(fabrica_mp3, tmp_path):
    a = fabrica_mp3("origem/a.mp3")
    (tmp_path / "origem" / "outro.txt").write_text("fica")
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "origem")
    _, _, removidas = executar_organizacao(plano, remover_vazias=True)
    assert removidas == [] and (tmp_path / "origem" / "outro.txt").exists()


def test_remover_pastas_vazias_para_no_limite(tmp_path):
    fundo = tmp_path / "a" / "b" / "c"
    fundo.mkdir(parents=True)
    removidas = remover_pastas_vazias([fundo], raiz=tmp_path / "a")
    assert [p.name for p in removidas] == ["c", "b"] and (tmp_path / "a").exists()


def test_vazias_nunca_sobe_alem_da_origem(fabrica_mp3, tmp_path):
    # Downloads/x/a.mp3 -> outra pasta: apaga x, mas não Downloads (nem pastas vazias irmãs)
    a = fabrica_mp3("Downloads/x/a.mp3")
    (tmp_path / "Downloads" / "vazia_do_usuario").mkdir()
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "Musicas", levar_capa=False)
    _, falhas, removidas = executar_organizacao(plano, remover_vazias=True)
    assert not falhas, falhas
    assert [p.name for p in removidas] == ["x"]
    assert (tmp_path / "Downloads" / "vazia_do_usuario").exists()


def test_vazias_sobe_ate_a_raiz_da_origem(fabrica_mp3, tmp_path):
    a = fabrica_mp3("Aberta/sub/sub2/a.mp3")
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "Musicas", levar_capa=False)
    _, _, removidas = executar_organizacao(plano, remover_vazias=True, raiz_origem=tmp_path / "Aberta")
    assert {p.name for p in removidas} == {"sub2", "sub"} and (tmp_path / "Aberta").exists()


def test_nao_deixa_pastas_vazias_no_destino_apos_falha(fabrica_mp3, tmp_path, monkeypatch):
    a = fabrica_mp3("a.mp3")
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "dest", levar_capa=False)
    monkeypatch.setattr("tagger.nucleo.organizar.executar_renomeacao", lambda itens: ([], {i.origem: "negado" for i in itens}))
    feitos, falhas, _ = executar_organizacao(plano)
    assert feitos == [] and a in falhas
    assert not (tmp_path / "dest" / "Artista").exists()


def test_criadas_permite_limpar_destino_ao_desfazer(fabrica_mp3, tmp_path):
    a = fabrica_mp3("a.mp3")
    (tmp_path / "dest").mkdir()
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "dest", levar_capa=False)
    criadas = []
    feitos, _, _ = executar_organizacao(plano, criadas=criadas)
    assert {p.name for p in criadas} == {"Artista", "Álbum"}
    volta, falhas = executar_movimentos([ItemRenomear(d, o) for o, d in feitos])
    assert not falhas, falhas
    removidas = remover_pastas_vazias({d.parent for _o, d in feitos}, permitidas=criadas)
    assert {p.name for p in removidas} == {"Álbum", "Artista"} and (tmp_path / "dest").exists()


def test_capas_com_mesmo_alvo_nao_duplicam(fabrica_mp3, tmp_path):
    a, b = fabrica_mp3("p1/a.mp3"), fabrica_mp3("p2/b.mp3")
    (tmp_path / "p1" / "cover.jpg").write_bytes(b"1")
    (tmp_path / "p2" / "cover.jpg").write_bytes(b"2")
    plano = planejar_organizacao([(a, TAGS), (b, {**TAGS, "tracknumber": "4"})], PADRAO, tmp_path / "d")
    assert len(plano.capas) == 1


def test_entre_unidades_nao_deixa_temporario_nem_duplicado(fabrica_mp3, tmp_path, monkeypatch):
    from tagger.nucleo import organizar
    a = fabrica_mp3("a.mp3")
    item = ItemRenomear(a, tmp_path / "dest" / "a.mp3")
    monkeypatch.setattr(organizar, "_outra_unidade", lambda _i: True)

    # apagar a origem falha: a cópia é removida, a origem continua e nada fica registrado
    original = Path.unlink
    def unlink_negado(self, missing_ok=False):
        if self == a:
            raise PermissionError("em uso")
        return original(self, missing_ok=missing_ok)
    monkeypatch.setattr(Path, "unlink", unlink_negado)
    feitos, falhas = executar_movimentos([item])
    assert feitos == [] and a in falhas and a.exists()
    assert [p.name for p in (tmp_path / "dest").glob("*")] == [] if (tmp_path / "dest").exists() else True
    monkeypatch.setattr(Path, "unlink", original)

    # caminho feliz entre unidades
    feitos, falhas = executar_movimentos([item])
    assert not falhas, falhas
    assert feitos == [(a, item.destino)] and item.destino.exists() and not a.exists()
    assert [p.name for p in item.destino.parent.iterdir()] == ["a.mp3"]


def test_troca_de_lugar_entre_dois_arquivos(fabrica_mp3, tmp_path):
    # A ocupa o lugar de B e B o de A: a ordem em duas etapas resolve
    a = fabrica_mp3("Artista/Álbum/01 - X.mp3")
    b = fabrica_mp3("Artista/Álbum/02 - Y.mp3")
    a.write_bytes(a.read_bytes() + b"A")
    pa = {**TAGS, "tracknumber": "2", "title": "Y"}
    pb = {**TAGS, "tracknumber": "1", "title": "X"}
    plano = planejar_organizacao([(a, pa), (b, pb)], PADRAO, tmp_path)
    feitos, falhas, _ = executar_organizacao(plano)
    assert not falhas, falhas
    assert len(feitos) == 2
    assert (tmp_path / "Artista" / "Álbum" / "02 - Y.mp3").read_bytes().endswith(b"A")


def test_pasta_aberta_nunca_e_removida(fabrica_mp3, tmp_path):
    a = fabrica_mp3("aberta/a.mp3")
    plano = planejar_organizacao([(a, TAGS)], PADRAO, tmp_path / "dest", levar_capa=False)
    _, falhas, removidas = executar_organizacao(plano, remover_vazias=True, raiz_origem=tmp_path / "aberta")
    assert not falhas, falhas
    assert removidas == [] and (tmp_path / "aberta").exists()
