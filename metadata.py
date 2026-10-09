from pathlib import Path
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3NoHeaderError
from datetime import datetime

TAGS_EDITAVEIS = {
    1: "title",
    2: "artist",
    3: "album",
    4: "albumartist",
    5: "tracknumber",
    6: "genre",
    7: "date"
}

TAGS_BULK = {
    "artist",
    "album",
    "albumartist",
    "genre",
    "date"
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
        # Reabre o ficheiro para o objeto ficar ligado ao caminho correto
        audio = EasyID3(arquivo)

    return audio


def ler_tags(audio):
    return {
        numero:audio.get(tag, [""])[0]
        for numero, tag in TAGS_EDITAVEIS.items()
    }

def validar_valor(tag, valor):
    valor = valor.strip()
    
    if tag == "date":
        ano_atual = datetime.now().year
        
        if valor.lower() == "atual":
            return True, str(ano_atual)
            
        if not valor.isdigit() or len(valor) != 4:
            return False, f"Ano inválido. Digite 4 dígitos numéricos ou 'atual' para {ano_atual}."
            
        ano_int = int(valor)
        if not (1000 <= ano_int <= ano_atual):
            return False, f"O ano deve estar entre 1000 e {ano_atual}."
            
        return True, str(ano_int)
            
    elif tag == "tracknumber":
        partes = valor.split('/')
        if len(partes) > 2 or not all(p.isdigit() and int(p) > 0 for p in partes):
            return False, "Faixa inválida. Use números maiores que 0 (ex: '3' ou '3/12')."
            
    else:
        if not valor:
            return False, "O valor não pode ficar em branco."
            
    return True, valor

def editar_tags(audio, tag, valor):
    audio[tag] = valor
    audio.save()

    return True

def tags_bulk():
    btags = []
    for tags in TAGS_EDITAVEIS.values():
        if tags in TAGS_BULK:
            btags.append(tags)
    return btags

def bulk_edit(arquivos, tag, valor):
    for arquivo in arquivos:
        audio = abrir_arquivo(arquivo)
        if audio is None:
            continue
        editar_tags(audio, tag, valor)
        
    
    return True