from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC


def formato(arquivo):
    extensao = Path(arquivo).suffix.lower()

    if extensao == ".mp3":
        return "mp3"
    elif extensao == ".flac":
        return "flac"

    return None


def abrir_arquivo(arquivo):
    tipo = formato(arquivo)

    if tipo == "mp3":
        return EasyID3(arquivo)

    elif tipo == "flac":
        return FLAC(arquivo)

    return None