"""Fixtures: MP3s pequenos gerados na hora (só frames de silêncio, sem tags)."""

import pytest

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
