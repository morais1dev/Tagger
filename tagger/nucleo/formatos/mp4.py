"""
Tags MP4/iTunes: .m4a e .mp4.

- Texto em átomos ©nam, ©ART...; uma lista com vários valores é multivalor.
- Faixa/disco são pares de números (trkn/disk): "3/12" <-> (3, 12); só "3" <-> (3, 0).
- Letrista não tem átomo próprio: usa o campo livre ----:com.apple.iTunes:LYRICIST (como o Picard).
- Capa: o átomo covr é uma lista de imagens SEM tipo (frontal, contracapa...). O iTunes e os
  players mostram a 1ª como capa, então "a capa" é a 1ª imagem; as demais ficam como estão
  (remover a capa tira só a 1ª: se houver outra, ela passa a ser a capa). O MP4 só aceita
  JPEG e PNG: outra imagem levanta ValueError antes de gravar qualquer coisa.
- Comentário e letra: só o 1º valor é exibido/trocado; os outros ficam como estão.
- Átomos técnicos (gapless, normalização do iTunes, compilação, BPM...) nunca são "extras":
  apagá-los muda a reprodução, então a limpeza não os oferece.
"""

from mutagen.mp4 import MP4Cover, MP4FreeForm

CHAVES = {
    "title":       "\xa9nam",
    "artist":      "\xa9ART",
    "album":       "\xa9alb",
    "albumartist": "aART",
    "tracknumber": "trkn",
    "discnumber":  "disk",
    "date":        "\xa9day",
    "genre":       "\xa9gen",    # o gênero numérico antigo (gnre) o mutagen já lê como ©gen
    "composer":    "\xa9wrt",
    "lyricist":    "----:com.apple.iTunes:LYRICIST",
    "comment":     "\xa9cmt",
    "lyrics":      "\xa9lyr",
}

CAMPOS_NUMERICOS = {"tracknumber", "discnumber"}
SO_PRIMEIRO = {"comment", "lyrics"}
CHAVE_IMAGEM = "covr"

# Chaves que o Tagger mostra/edita. O resto é "extra" para remover_extras().
CHAVES_DO_TAGGER = set(CHAVES.values()) | {CHAVE_IMAGEM}

# Átomos técnicos que remover_extras() não toca (nem lista).
TECNICOS = {"pgap", "cpil", "stik", "tmpo", "rtng", "hdvd"}
TECNICOS_LIVRES = {"iTunSMPB", "iTunNORM", "Encoding Params"}   # nomes de "----:com.apple.iTunes:..."

_MIMES = {MP4Cover.FORMAT_JPEG: "image/jpeg", MP4Cover.FORMAT_PNG: "image/png"}
_FORMATOS = {"image/jpeg": MP4Cover.FORMAT_JPEG, "image/jpg": MP4Cover.FORMAT_JPEG,
             "image/png": MP4Cover.FORMAT_PNG}


def ler(audio, campo):
    tags = audio.tags
    if tags is None:
        return []
    valores = tags.get(CHAVES[campo], [])
    if not valores:
        return []

    if campo in CAMPOS_NUMERICOS:
        numero, total = valores[0]
        if not numero:
            return []
        return [f"{numero}/{total}" if total else str(numero)]
    if CHAVES[campo].startswith("----:"):
        valores = [bytes(v).decode("utf-8", "replace") for v in valores]
    if campo in SO_PRIMEIRO:
        return [str(valores[0])]
    return [str(v) for v in valores]


def gravar(audio, campo, valores):
    tags = audio.tags
    chave = CHAVES[campo]
    antigos = tags.pop(chave, [])
    if campo in SO_PRIMEIRO:
        valores = list(valores) + list(antigos[1:])
    if not valores:
        return
    if campo in CAMPOS_NUMERICOS:
        numero, _barra, total = valores[0].partition("/")
        tags[chave] = [(int(numero), int(total or 0))]
    elif chave.startswith("----:"):
        tags[chave] = [MP4FreeForm(v.encode("utf-8")) for v in valores]
    else:
        tags[chave] = valores


# ---------------------------------------------------------------------------
# Capa
# ---------------------------------------------------------------------------

def capas(audio):
    imagens = audio.tags.get(CHAVE_IMAGEM, []) if audio.tags is not None else []
    return [(bytes(img), _MIMES.get(img.imageformat, "application/octet-stream")) for img in imagens[:1]]


def aplicar_capa(audio, capa):
    """Troca/remove só a 1ª imagem (a capa); as outras ficam."""
    if capa[0] == "definir" and capa[2] not in _FORMATOS:
        raise ValueError(f"A capa de um arquivo M4A/MP4 precisa ser JPEG ou PNG (veio {capa[2]}).")
    tags = audio.tags
    imagens = list(tags.get(CHAVE_IMAGEM, []))[1:]
    if capa[0] == "definir":
        imagens.insert(0, MP4Cover(capa[1], imageformat=_FORMATOS[capa[2]]))
    tags.pop(CHAVE_IMAGEM, None)
    if imagens:
        tags[CHAVE_IMAGEM] = imagens


# ---------------------------------------------------------------------------
# Limpeza
# ---------------------------------------------------------------------------

def _e_tecnico(chave):
    if chave.startswith("----:"):
        return chave.rsplit(":", 1)[-1] in TECNICOS_LIVRES
    return chave in TECNICOS


def _chaves_extras(tags):
    return [chave for chave in tags.keys() if chave not in CHAVES_DO_TAGGER and not _e_tecnico(chave)]


def extras(audio):
    tags = audio.tags
    if tags is None:
        return {}
    return {chave: len(tags[chave]) if isinstance(tags[chave], list) else 1 for chave in _chaves_extras(tags)}


def remover_extras(audio):
    tags = audio.tags
    if tags is None:
        return False
    chaves = _chaves_extras(tags)
    for chave in chaves:
        del tags[chave]
    return bool(chaves)
