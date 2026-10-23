"""
Formatos além do MP3 (o ID3 continua em metadata.py, onde estão as opções dele).

Cada módulo aqui tem a mesma interface, usada por metadata.py:
- ler(audio, campo) -> lista de valores (vazia = sem a tag)
- gravar(audio, campo, valores): troca a tag; lista vazia remove
- capas(audio) -> [(dados, mime)] das imagens que contam como "a capa"
- aplicar_capa(audio, capa): ("definir", dados, mime) ou ("remover",)
- extras(audio) -> {chave: quantidade} do que o Tagger não mostra
- remover_extras(audio) -> True se removeu algo

Nenhuma função daqui chama save(): a gravação é sempre um único save, em metadata.py.
"""

# Tipos de imagem tratados como "a capa" (mesma numeração no APIC do ID3 e no bloco
# PICTURE do FLAC/Vorbis): 3 = capa frontal, 0 = "outra" (alguns programas gravam a capa assim).
TIPO_CAPA_FRONTAL = 3
TIPO_OUTRA = 0


def escolher_capa(imagens):
    """Das imagens (com .type), as que são "a capa": as frontais; se não houver, a 1ª do tipo "outra"."""
    frontais = [img for img in imagens if img.type == TIPO_CAPA_FRONTAL]
    if frontais:
        return frontais
    outras = [img for img in imagens if img.type == TIPO_OUTRA]
    return outras[:1]
