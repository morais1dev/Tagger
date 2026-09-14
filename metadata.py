from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError


TAGS_EDITAVEIS = {
    1:"title",
    2:"artist",
    3:"album",
    4:"albumartist",
    5:"tracknumber",
    6:"genre",
    7:"date"
}
    

def formato(arquivo):
    extensao = Path(arquivo).suffix.lower()

    if extensao == ".mp3":
        return "mp3"

    return None


def abrir_arquivo(arquivo):
    if formato(arquivo) != "mp3":
        return None
    try:
        audio = EasyID3(arquivo)
    except ID3NoHeaderError:
        audio = EasyID3()
        audio.save(arquivo)

    return audio
    

def ler_tags(audio):
    return {
        numero:audio.get(tag, [""][0])
        for numero, tag in TAGS_EDITAVEIS.items()
    }


def editar_tags(audio, tag, valor):
    audio[tag]=valor
    audio.save()

    return True