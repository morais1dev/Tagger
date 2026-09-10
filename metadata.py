from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError


TAGS_EDITAVEIS = [
    "title",
    "artist",
    "album",
    "albumartist",
    "tracknumber",
    "genre",
    "date"
]


def formato(arquivo):
    extensao = Path(arquivo).suffix.lower()

    if extensao == ".mp3":
        return "mp3"

    return None


def abrir_arquivo(arquivo):
    if formato(arquivo) == "mp3":
        try:
            audio = EasyID3(arquivo)
            return audio
        except ID3NoHeaderError:
            audio = EasyID3()
            audio.save(arquivo)
            return audio

    return None


def ler_tags(arquivo):
    audio = abrir_arquivo(arquivo)

    if audio is None:
        return None

    return {
        tag: audio.get(tag, [""])[0]
        for tag in TAGS_EDITAVEIS
    }


def editar_tags(arquivo, tags):
    audio = abrir_arquivo(arquivo)

    if audio is None:
        return False

    for tag, valor in tags.items():
        if valor != "":
            audio[tag] = valor

    audio.save()

    return True