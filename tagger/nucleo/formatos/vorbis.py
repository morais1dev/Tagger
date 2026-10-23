"""
Vorbis comments: FLAC (.flac) e Ogg (.ogg: Vorbis, Opus ou FLAC dentro do Ogg).

As tags são pares CHAVE=valor; uma chave repetida é multivalor nativo (ARTIST=A, ARTIST=B).
- Faixa/disco: "3/12" é gravado como TRACKNUMBER=3 + TRACKTOTAL=12 (o padrão dos players);
  ao ler, TRACKTOTAL/TOTALTRACKS são juntados de volta em "3/12". Gravar só "4" mantém o
  total que já existia; apagar a faixa apaga o total junto.
- Nomes alternativos (DESCRIPTION, UNSYNCEDLYRICS, "ALBUM ARTIST"): lidos só se o principal
  faltar. Ao gravar, só é apagada a alternativa que foi a exibida, ou uma que repete o valor
  exibido; uma alternativa com outro conteúdo (que o usuário nunca viu) fica.
- Comentário e letra: só o 1º valor é exibido/trocado; outros COMMENT/LYRICS ficam como estão.
- Capa: no FLAC são blocos PICTURE do próprio arquivo; no Ogg, a chave METADATA_BLOCK_PICTURE
  (o mesmo bloco em base64). Os dois têm tipo de imagem, como o APIC do ID3. O jeito antigo do
  Ogg (COVERART em base64 + COVERARTMIME, sem tipo) conta como capa só se não houver outra, e
  sai do arquivo quando uma capa nova é definida.
"""

import base64
import binascii

from mutagen import MutagenError
from mutagen.flac import FLAC, Picture

from tagger.nucleo.formatos import TIPO_CAPA_FRONTAL, escolher_capa

CHAVES = {
    "title":       "TITLE",
    "artist":      "ARTIST",
    "album":       "ALBUM",
    "albumartist": "ALBUMARTIST",
    "tracknumber": "TRACKNUMBER",
    "discnumber":  "DISCNUMBER",
    "date":        "DATE",
    "genre":       "GENRE",
    "composer":    "COMPOSER",
    "lyricist":    "LYRICIST",
    "comment":     "COMMENT",
    "lyrics":      "LYRICS",
}

# Nomes que outros programas usam para o mesmo campo (ver regra no topo).
ALTERNATIVAS = {
    "albumartist": ("ALBUM ARTIST",),
    "comment":     ("DESCRIPTION",),
    "lyrics":      ("UNSYNCEDLYRICS",),
}

# Total de faixas/discos: o 1º nome é o que o Tagger grava.
TOTAIS = {
    "tracknumber": ("TRACKTOTAL", "TOTALTRACKS"),
    "discnumber":  ("DISCTOTAL", "TOTALDISCS"),
}

# Campos em que só o 1º valor é do Tagger (os outros são preservados).
SO_PRIMEIRO = {"comment", "lyrics"}

CHAVE_IMAGEM = "METADATA_BLOCK_PICTURE"
CHAVE_IMAGEM_ANTIGA = "COVERART"
CHAVE_MIME_ANTIGA = "COVERARTMIME"

# Chaves que o Tagger mostra/edita. O resto é "extra" para remover_extras().
CHAVES_DO_TAGGER = (
    set(CHAVES.values())
    | {chave for nomes in ALTERNATIVAS.values() for chave in nomes}
    | {chave for nomes in TOTAIS.values() for chave in nomes}
    | {CHAVE_IMAGEM, CHAVE_IMAGEM_ANTIGA, CHAVE_MIME_ANTIGA}
)


def _apagar(tags, chave):
    if chave in tags:
        del tags[chave]


def _fonte(tags, campo):
    """(chave, valores) de onde o campo é lido: o nome principal, senão a 1ª alternativa com valor."""
    for chave in (CHAVES[campo], *ALTERNATIVAS.get(campo, ())):
        valores = tags.get(chave, [])
        if valores:
            return chave, list(valores)
    return None, []


def ler(audio, campo):
    tags = audio.tags
    if tags is None:
        return []
    _chave, valores = _fonte(tags, campo)
    if not valores:
        return []

    if campo in SO_PRIMEIRO:
        return valores[:1]
    if campo in TOTAIS:
        numero = valores[0]
        if "/" not in numero:
            total = next((tags[chave][0] for chave in TOTAIS[campo] if chave in tags), "")
            if total:
                numero = f"{numero}/{total}"
        return [numero]
    return valores


def gravar(audio, campo, valores):
    tags = audio.tags
    principal = CHAVES[campo]

    fonte, antigos = _fonte(tags, campo)
    restantes = []
    if fonte is not None:
        exibidos = antigos[:1] if campo in SO_PRIMEIRO else antigos
        restantes = antigos[1:] if campo in SO_PRIMEIRO else []
        del tags[fonte]
        for chave in (principal, *ALTERNATIVAS.get(campo, ())):
            if chave in tags and list(tags[chave]) == exibidos:
                del tags[chave]          # cópia do mesmo valor com outro nome

    if campo in TOTAIS:
        if not valores:
            for chave in TOTAIS[campo]:
                _apagar(tags, chave)
            return
        numero, _barra, total = valores[0].partition("/")
        valores = [numero]
        if total:
            for chave in TOTAIS[campo]:
                _apagar(tags, chave)
            tags[TOTAIS[campo][0]] = [total]

    novos = list(valores) + restantes
    if novos:
        tags[principal] = novos


# ---------------------------------------------------------------------------
# Capa
# ---------------------------------------------------------------------------

def _imagens_ogg(tags):
    """[(texto_base64, Picture ou None)] na ordem do arquivo. None = não decodificou (fica intacta)."""
    imagens = []
    for texto in tags.get(CHAVE_IMAGEM, []) if tags is not None else []:
        try:
            imagens.append((texto, Picture(base64.b64decode(texto))))
        except (binascii.Error, ValueError, MutagenError):
            imagens.append((texto, None))
    return imagens


def _capa_antiga(tags):
    """(dados, mime) do COVERART, ou None."""
    for texto in tags.get(CHAVE_IMAGEM_ANTIGA, []) if tags is not None else []:
        try:
            dados = base64.b64decode(texto)
        except (binascii.Error, ValueError):
            continue
        mimes = tags.get(CHAVE_MIME_ANTIGA, [])
        return dados, (mimes[0] if mimes else "image/jpeg")
    return None


def _nova_imagem(dados, mime):
    imagem = Picture()
    imagem.type = TIPO_CAPA_FRONTAL
    imagem.mime = mime
    imagem.data = dados
    return imagem


def capas(audio):
    if isinstance(audio, FLAC):
        return [(img.data, img.mime) for img in escolher_capa(audio.pictures)]
    imagens = escolher_capa([imagem for _texto, imagem in _imagens_ogg(audio.tags) if imagem is not None])
    if imagens:
        return [(img.data, img.mime) for img in imagens]
    antiga = _capa_antiga(audio.tags)
    return [antiga] if antiga else []


def aplicar_capa(audio, capa):
    """Só a capa é trocada; contracapa, foto do artista etc. ficam."""
    if isinstance(audio, FLAC):
        capa_atual = escolher_capa(audio.pictures)
        audio.metadata_blocks = [b for b in audio.metadata_blocks if not any(b is c for c in capa_atual)]
        if capa[0] == "definir":
            audio.add_picture(_nova_imagem(capa[1], capa[2]))
        return

    tags = audio.tags
    imagens = _imagens_ogg(tags)
    capa_atual = escolher_capa([imagem for _texto, imagem in imagens if imagem is not None])
    if capa[0] == "definir" or not capa_atual:
        # a capa nova substitui a antiga; ao remover, a antiga só sai se era ela a exibida
        _apagar(tags, CHAVE_IMAGEM_ANTIGA)
        _apagar(tags, CHAVE_MIME_ANTIGA)
    manter = [texto for texto, imagem in imagens if not any(imagem is c for c in capa_atual)]
    if capa[0] == "definir":
        manter.append(base64.b64encode(_nova_imagem(capa[1], capa[2]).write()).decode("ascii"))
    _apagar(tags, CHAVE_IMAGEM)
    if manter:
        tags[CHAVE_IMAGEM] = manter


# ---------------------------------------------------------------------------
# Limpeza
# ---------------------------------------------------------------------------

def _chaves_extras(tags):
    return [chave for chave in tags.keys() if chave.upper() not in CHAVES_DO_TAGGER]


def extras(audio):
    tags = audio.tags
    if tags is None:
        return {}
    return {chave.upper(): len(tags[chave]) for chave in _chaves_extras(tags)}


def remover_extras(audio):
    tags = audio.tags
    if tags is None:
        return False
    chaves = _chaves_extras(tags)
    for chave in chaves:
        del tags[chave]
    return bool(chaves)
