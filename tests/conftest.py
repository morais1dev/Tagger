"""Fixtures: arquivos de áudio pequenos gerados na hora, sem tags.

O MP3 tem frames de silêncio de verdade. FLAC, Ogg e M4A têm só a estrutura que o mutagen
precisa (cabeçalhos com duração de 2 s); o áudio em si é lixo, o que basta para testar tags.
"""

import struct

import pytest
from mutagen.ogg import OggPage

# Cabeçalho de frame MPEG-1 Layer III, 128 kbps, 44,1 kHz, sem CRC: cada frame tem 417 bytes.
_FRAME = bytes.fromhex("FFFB9064") + bytes(413)


def criar_mp3(caminho, frames=40):
    caminho.write_bytes(_FRAME * frames)
    return caminho


@pytest.fixture
def mp3(tmp_path):
    """Um MP3 sem tags."""
    return criar_mp3(tmp_path / "musica.mp3")


@pytest.fixture
def fabrica_mp3(tmp_path):
    """Função que cria MP3s com o nome pedido: fabrica_mp3("01 - A.mp3")."""
    def criar(nome):
        caminho = tmp_path / nome
        caminho.parent.mkdir(parents=True, exist_ok=True)
        return criar_mp3(caminho)
    return criar


def criar_flac(caminho, segundos=2):
    # STREAMINFO: blocos de 4096, 44,1 kHz, 2 canais, 16 bits, N amostras, MD5 zerado
    taxa = 44100
    info = struct.pack(">HH", 4096, 4096) + bytes(6)
    info += ((taxa << 44) | (1 << 41) | (15 << 36) | taxa * segundos).to_bytes(8, "big") + bytes(16)
    caminho.write_bytes(b"fLaC" + b"\x80" + len(info).to_bytes(3, "big") + info + bytes(64))
    return caminho


def criar_ogg(caminho, segundos=2):
    # 3 páginas: identificação; comentários (vazio) + setup; um pacote de "áudio" com a posição final
    taxa = 44100
    identificacao = b"\x01vorbis" + struct.pack("<IBIiii", 0, 2, taxa, 0, 128000, 0) + b"\xb8\x01"
    comentarios = b"\x03vorbis" + struct.pack("<I", 6) + b"Tagger" + struct.pack("<I", 0) + b"\x01"
    setup = b"\x05vorbis" + bytes(30)
    paginas = [([identificacao], 0), ([comentarios, setup], 0), ([bytes(100)], taxa * segundos)]
    return _gravar_ogg(caminho, paginas)


def criar_opus(caminho, segundos=2):
    # Opus num .ogg: OpusHead; OpusTags (vazio); um pacote de "áudio" (Opus conta sempre a 48 kHz)
    cabecalho = b"OpusHead" + struct.pack("<BBHIhB", 1, 2, 0, 48000, 0, 0)
    comentarios = b"OpusTags" + struct.pack("<I", 6) + b"Tagger" + struct.pack("<I", 0)
    paginas = [([cabecalho], 0), ([comentarios], 0), ([bytes(100)], 48000 * segundos)]
    return _gravar_ogg(caminho, paginas)


def _gravar_ogg(caminho, paginas):
    """paginas: [(pacotes, posição)] de um único fluxo lógico."""
    dados = b""
    for numero, (pacotes, posicao) in enumerate(paginas):
        pagina = OggPage()
        pagina.serial, pagina.sequence, pagina.packets, pagina.position = 1, numero, pacotes, posicao
        pagina.first, pagina.last = numero == 0, numero == len(paginas) - 1
        dados += pagina.write()
    caminho.write_bytes(dados)
    return caminho


def _atomo(nome, conteudo):
    return struct.pack(">I", 8 + len(conteudo)) + nome + conteudo


def criar_m4a(caminho, segundos=2):
    # ftyp + moov (mvhd + uma trilha de som com mdhd/hdlr) + mdat
    mvhd = _atomo(b"mvhd", bytes(4) + struct.pack(">IIII", 0, 0, 1000, 1000 * segundos) + bytes(80))
    mdhd = _atomo(b"mdhd", bytes(4) + struct.pack(">IIII", 0, 0, 44100, 44100 * segundos) + bytes(4))
    hdlr = _atomo(b"hdlr", bytes(8) + b"soun" + bytes(13))
    moov = _atomo(b"moov", mvhd + _atomo(b"trak", _atomo(b"mdia", mdhd + hdlr)))
    caminho.write_bytes(_atomo(b"ftyp", b"M4A " + bytes(4) + b"M4A mp42isom") + moov + _atomo(b"mdat", bytes(64)))
    return caminho


CRIADORES = {"mp3": criar_mp3, "flac": criar_flac, "ogg": criar_ogg, "m4a": criar_m4a}


@pytest.fixture(params=["flac", "ogg", "m4a"])
def outro(request, tmp_path):
    """Um arquivo sem tags de cada formato além do MP3 (o teste roda uma vez por formato)."""
    return CRIADORES[request.param](tmp_path / f"musica.{request.param}")


@pytest.fixture
def criar_audio(tmp_path):
    """Função que cria um arquivo sem tags do formato pedido: criar_audio("flac")."""
    def criar(fmt, nome="musica"):
        return CRIADORES[fmt](tmp_path / f"{nome}.{fmt}")
    return criar


@pytest.fixture
def opus(tmp_path):
    """Um Ogg Opus sem tags, com a extensão .ogg (o Tagger descobre o codec ao abrir)."""
    return criar_opus(tmp_path / "opus.ogg")
