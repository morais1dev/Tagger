"""Agrupamento das faixas por álbum: chave do grupo, título do cabeçalho e ordem disco/faixa.

Trabalha só com dicionários de tags ({"album": ..., "albumartist": ...}), sem depender da interface.
"""

SEM_ALBUM = "Sem álbum"


def _numero(texto, ausente=10**9):
    parte = (texto or "").split("/")[0].strip()
    return int(parte) if parte.isdigit() else ausente    # faixa sem número vai para o fim


def chave_grupo(tags):
    """Identifica o álbum de uma faixa; sem título de álbum, todas caem no mesmo grupo (que vai para o fim)."""
    album = (tags.get("album") or "").strip().casefold()
    if not album:
        return ("", "")
    return (album, (tags.get("albumartist") or "").strip().casefold())


def chave_ordem(tags):
    """Ordem dentro da lista agrupada: álbum, artista do álbum, disco e faixa."""
    album, artista = chave_grupo(tags)
    return (not album, album, artista, _numero(tags.get("discnumber"), 1), _numero(tags.get("tracknumber")))


def ordem_faixa(tags):
    """Só a parte de dentro do grupo: (disco, faixa). Sem disco vale como disco 1."""
    return (_numero(tags.get("discnumber"), 1), _numero(tags.get("tracknumber")))


def mais_de_um_album(lista_tags):
    """True quando há pelo menos dois grupos diferentes (só então vale agrupar)."""
    grupos = set()
    for tags in lista_tags:
        grupos.add(chave_grupo(tags))
        if len(grupos) > 1:
            return True
    return False


def titulo_cabecalho(lista_tags):
    """'Álbum — Artista do álbum, ano' para as faixas de um grupo (partes ausentes são omitidas).
    Sem artista do álbum usa o artista da primeira faixa; o ano é o primeiro encontrado."""
    primeira = lista_tags[0] if lista_tags else {}
    album = (primeira.get("album") or "").strip()
    if not album:
        return SEM_ALBUM
    artista = next((t["albumartist"].strip() for t in lista_tags if (t.get("albumartist") or "").strip()), "")
    if not artista:
        artista = (primeira.get("artist") or "").strip()
    ano = next((t["date"].strip()[:4] for t in lista_tags if (t.get("date") or "").strip()), "")
    texto = f"{album} — {artista}" if artista else album
    return f"{texto}, {ano}" if ano else texto
