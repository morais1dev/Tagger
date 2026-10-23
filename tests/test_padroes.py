from pathlib import Path

import pytest

from tagger.nucleo.padroes import (
    campos_do_padrao, executar_renomeacao, nome_pelas_tags, planejar_renomeacao, sanitizar, tags_pelo_nome,
)

PADRAO = "{tracknumber:02} - {artist} - {title}"


# ----------------------------------------------------------------- padrão
def test_campos_do_padrao():
    assert campos_do_padrao("%track% - %artist% - {*} - {title}") == ["tracknumber", "artist", "title"]


def test_campo_desconhecido():
    with pytest.raises(ValueError, match="desconhecido"):
        campos_do_padrao("{artista}")


# ----------------------------------------------------------------- tags -> nome
def test_nome_pelas_tags():
    valores = {"tracknumber": "3/12", "artist": "Artista", "title": "Música"}
    assert nome_pelas_tags(PADRAO, valores) == "03 - Artista - Música"
    assert nome_pelas_tags("%track% %title%", valores) == "3 Música"


def test_campos_vazios_nao_deixam_separadores_sobrando():
    assert nome_pelas_tags(PADRAO, {"title": "Só título"}) == "Só título"
    assert nome_pelas_tags(PADRAO, {"tracknumber": "1", "title": "T"}) == "01 - T"
    assert nome_pelas_tags(PADRAO, {}) == ""


@pytest.mark.parametrize("entrada, saida", [
    ('AC/DC: "Live"?', "AC-DC - 'Live'"),
    ("a\\b|c*d<e>f", "a-b-cdef"),
    ("  muitos    espaços  ", "muitos espaços"),
    ("tab\taqui\x00", "tab aqui"),
])
def test_sanitizar(entrada, saida):
    assert sanitizar(entrada) == saida


def test_nomes_reservados_e_pontos_no_fim():
    assert nome_pelas_tags("{title}", {"title": "CON"}) == "CON_"
    assert nome_pelas_tags("{title}", {"title": "Fim..."}) == "Fim"


def test_barra_no_padrao_e_recusada():
    with pytest.raises(ValueError):
        nome_pelas_tags("{artist}/{title}", {"title": "x"})


# ----------------------------------------------------------------- planejar / executar
def _itens(*pares):
    return [(Path(c), {"title": t}) for c, t in pares]


def test_planejar_sem_mudanca_e_conflitos(fabrica_mp3):
    a = fabrica_mp3("a.mp3")
    b = fabrica_mp3("b.mp3")
    c = fabrica_mp3("c.mp3")
    fabrica_mp3("existe.mp3")
    d = fabrica_mp3("d.mp3")
    plano = planejar_renomeacao(_itens((a, "a"), (b, "igual"), (c, "igual"), (d, "existe")), "{title}")
    assert plano[0].destino is None and not plano[0].erro          # nome não muda
    assert "mesmo nome" in plano[1].erro and "mesmo nome" in plano[2].erro
    assert "Já existe" in plano[3].erro
    assert not any(item.valido for item in plano)


def test_nome_vazio_e_erro(fabrica_mp3):
    a = fabrica_mp3("a.mp3")
    assert "vazio" in planejar_renomeacao([(a, {})], "{title}")[0].erro


def test_renomear_e_trocar_nomes(fabrica_mp3):
    a = fabrica_mp3("a.mp3")
    b = fabrica_mp3("b.mp3")
    a.write_bytes(a.read_bytes() + b"A")
    plano = planejar_renomeacao(_itens((a, "b"), (b, "a")), "{title}")   # troca: a->b e b->a
    assert all(item.valido for item in plano)
    feitos, falhas = executar_renomeacao(plano)
    assert not falhas, falhas
    assert len(feitos) == 2
    assert b.read_bytes().endswith(b"A")                                  # o conteúdo de "a" agora é "b"
    assert sorted(p.name for p in a.parent.iterdir()) == ["a.mp3", "b.mp3"]


def test_so_maiusculas_mudam(fabrica_mp3):
    a = fabrica_mp3("musica.mp3")
    plano = planejar_renomeacao(_itens((a, "Musica")), "{title}")
    assert plano[0].valido
    feitos, falhas = executar_renomeacao(plano)
    assert not falhas, falhas
    assert [p.name for p in a.parent.iterdir()] == ["Musica.mp3"]


def test_extensao_fica_minuscula(fabrica_mp3):
    a = fabrica_mp3("x.MP3")
    assert planejar_renomeacao(_itens((a, "y")), "{title}")[0].destino.name == "y.mp3"


def test_destino_criado_depois_da_previa_nao_e_sobrescrito(fabrica_mp3):
    a = fabrica_mp3("a.mp3")
    plano = planejar_renomeacao(_itens((a, "novo")), "{title}")
    fabrica_mp3("novo.mp3").write_bytes(b"de outro")
    feitos, falhas = executar_renomeacao(plano)
    assert not feitos and a in falhas
    assert a.exists() and (a.parent / "novo.mp3").read_bytes() == b"de outro"
    assert not list(a.parent.glob("*.tagger-tmp"))


# ----------------------------------------------------------------- nome -> tags
def test_tags_pelo_nome():
    assert tags_pelo_nome("%track% - %artist% - %title%", Path("03 - Artista - Nome - Com Hífen.mp3")) == {
        "tracknumber": "3", "artist": "Artista", "title": "Nome - Com Hífen"}


def test_tags_pelo_nome_nao_casa():
    assert tags_pelo_nome("%artist% - %title%", Path("sem separador.mp3")) is None


def test_tags_pelo_nome_ignorar_e_sublinhado():
    resultado = tags_pelo_nome("{*} {artist} - {title}", Path("[2020]_Banda_-_Faixa_boa.mp3"),
                               sublinhado_vira_espaco=True)
    assert resultado == {"artist": "Banda", "title": "Faixa boa"}


def test_tags_pelas_pastas():
    caminho = Path("musicas") / "Artista" / "Álbum (2001)" / "07 Faixa.mp3"
    assert tags_pelo_nome("%artist%/%album% (%year%)/%track% %title%", caminho) == {
        "artist": "Artista", "album": "Álbum", "date": "2001", "tracknumber": "7", "title": "Faixa"}


def test_renomear_tenta_de_novo_se_o_windows_negar(tmp_path, monkeypatch):
    import os
    a = tmp_path / "a.mp3"
    a.write_bytes(b"x")
    real, negou = os.rename, []

    def rename_instavel(origem, destino):
        if not negou:
            negou.append(1)
            raise PermissionError("em uso")
        return real(origem, destino)

    monkeypatch.setattr(os, "rename", rename_instavel)
    feitos, falhas = executar_renomeacao(planejar_renomeacao([(a, {"title": "B"})], "{title}"))
    assert not falhas, falhas
    assert feitos and (tmp_path / "B.mp3").exists()
