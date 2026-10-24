from tagger.nucleo.agrupar import (
    SEM_ALBUM, chave_grupo, chave_ordem, mais_de_um_album, ordem_faixa, titulo_cabecalho,
)


def test_chave_grupo_ignora_caixa_e_espacos():
    assert chave_grupo({"album": " Abbey Road ", "albumartist": "The Beatles"}) == \
        chave_grupo({"album": "abbey road", "albumartist": "the beatles"})
    assert chave_grupo({"album": "A"}) != chave_grupo({"album": "A", "albumartist": "X"})
    assert chave_grupo({}) == chave_grupo({"album": "  "})


def test_mais_de_um_album():
    a = {"album": "A"}
    assert not mais_de_um_album([])
    assert not mais_de_um_album([a, dict(a)])
    assert mais_de_um_album([a, {"album": "B"}])
    assert mais_de_um_album([a, {}])


def test_ordem_por_album_disco_faixa_e_sem_album_no_fim():
    faixas = [
        {"album": "B", "tracknumber": "1"},
        {},
        {"album": "A", "discnumber": "2/2", "tracknumber": "1"},
        {"album": "A", "discnumber": "1", "tracknumber": "10/12"},
        {"album": "A", "discnumber": "1", "tracknumber": "2"},
        {"album": "A", "tracknumber": ""},
    ]
    ordenadas = sorted(faixas, key=chave_ordem)
    assert [(f.get("album"), f.get("discnumber"), f.get("tracknumber")) for f in ordenadas] == [
        ("A", "1", "2"), ("A", "1", "10/12"), ("A", None, ""), ("A", "2/2", "1"), ("B", None, "1"),
        (None, None, None),
    ]


def test_ordem_faixa():
    assert ordem_faixa({"discnumber": "1/2", "tracknumber": "3/9"}) == (1, 3)
    assert ordem_faixa({}) > ordem_faixa({"tracknumber": "99"})


def test_titulo_cabecalho():
    faixas = [{"album": "Disco", "albumartist": "Banda", "date": "2019-05-01"}]
    assert titulo_cabecalho(faixas) == "Disco — Banda, 2019"
    assert titulo_cabecalho([{"album": "Disco", "artist": "Fulano"}]) == "Disco — Fulano"
    assert titulo_cabecalho([{"album": "Disco", "date": "1999"}]) == "Disco, 1999"
    assert titulo_cabecalho([{"album": "Disco"}, {"album": "Disco", "date": "2001"}]) == "Disco, 2001"
    assert titulo_cabecalho([{"artist": "X"}]) == SEM_ALBUM
