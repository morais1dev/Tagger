import os
from datetime import datetime
from pathlib import Path

import mutagen
import pytest
from mutagen.id3 import APIC, COMM, ID3, PRIV, TCON, TIT2, TXXX, USLT
from mutagen.mp3 import MP3

from tagger.nucleo import metadata
from tagger.nucleo.metadata import (
    VARIOS, analisar_extras, carregar, foi_modificado, ler_capa, limpar_extras, salvar, tem_id3v1,
    validar_valor, valores_comuns,
)

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-falso" * 10
PNG = b"\x89PNG\r\n\x1a\n" + b"png-falso" * 10


@pytest.fixture(autouse=True)
def config_padrao(monkeypatch):
    monkeypatch.setattr(metadata, "VERSAO_ID3", 3)
    monkeypatch.setattr(metadata, "MULTIVALOR", True)
    monkeypatch.setattr(metadata, "REMOVER_ID3V1", False)


def _tags(caminho):
    return MP3(caminho).tags


# ----------------------------------------------------------------- validação
@pytest.mark.parametrize("campo, valor, esperado", [
    ("date", "2024", "2024"),
    ("date", "2024-05-17", "2024-05-17"),
    ("date", "atual", str(datetime.now().year)),
    ("tracknumber", "3", "3"),
    ("tracknumber", "3/12", "3/12"),
    ("discnumber", " 1/2 ", "1/2"),
    ("genre", "Rock", "Rock"),
    ("title", "  Nome  ", "Nome"),
    ("title", "", ""),
    ("date", VARIOS, VARIOS),
])
def test_valores_validos(campo, valor, esperado):
    assert validar_valor(campo, valor) == (True, esperado)


@pytest.mark.parametrize("campo, valor", [
    ("date", "24"), ("date", "2024/05"), ("date", "0999"), ("date", str(datetime.now().year + 1)),
    ("tracknumber", "0"), ("tracknumber", "3/0"), ("tracknumber", "a"), ("discnumber", "-1"),
    ("genre", "17"),
])
def test_valores_invalidos(campo, valor):
    ok, mensagem = validar_valor(campo, valor)
    assert not ok and mensagem


# ----------------------------------------------------------------- ler / salvar
def test_arquivo_sem_tags(mp3):
    faixa = carregar(mp3)
    assert faixa.tags == {campo: "" for campo in metadata.CAMPOS}
    assert not faixa.tem_capa and faixa.duracao > 0 and faixa.bitrate == 128
    assert faixa.mtime == mp3.stat().st_mtime_ns


def test_ler_nao_grava(mp3):
    antes = mp3.read_bytes()
    carregar(mp3)
    ler_capa(mp3)
    analisar_extras(mp3)
    assert mp3.read_bytes() == antes


def test_salvar_e_reler(mp3):
    valores = {"title": "Música", "artist": "Artista", "album": "Álbum", "tracknumber": "3/12",
               "date": "2024", "genre": "Rock", "comment": "linha 1\nlinha 2", "lyrics": "lá lá\nlá"}
    salvar(mp3, valores)
    faixa = carregar(mp3)
    for campo, valor in valores.items():
        assert faixa.tags[campo] == valor
    assert _tags(mp3).version == (2, 3, 0)


def test_valor_vazio_remove_e_varios_ignora(mp3):
    salvar(mp3, {"title": "A", "artist": "B"})
    salvar(mp3, {"title": "", "artist": VARIOS})
    tags = carregar(mp3).tags
    assert tags["title"] == "" and tags["artist"] == "B"
    assert "TIT2" not in _tags(mp3)


def test_id3v24(mp3, monkeypatch):
    monkeypatch.setattr(metadata, "VERSAO_ID3", 4)
    salvar(mp3, {"title": "A"})
    assert _tags(mp3).version == (2, 4, 0)


def test_um_unico_save_por_arquivo(mp3, monkeypatch):
    chamadas = []
    original = MP3.save
    monkeypatch.setattr(MP3, "save", lambda self, *a, **k: chamadas.append(1) or original(self, *a, **k))
    salvar(mp3, {"title": "A"}, capa=("definir", JPEG, "image/jpeg"))
    assert len(chamadas) == 1
    assert carregar(mp3).tags["title"] == "A" and ler_capa(mp3) == (JPEG, "image/jpeg")


def test_leitura_fragil_vira_falha(mp3, monkeypatch):
    def quebrar(*_a, **_k):
        raise mutagen.MutagenError("ID3 corrompido")
    monkeypatch.setattr(metadata, "MP3", quebrar)
    assert carregar(mp3) is None
    assert ler_capa(mp3) is None


def test_arquivo_invalido(tmp_path):
    lixo = tmp_path / "lixo.mp3"
    lixo.write_bytes(b"isto nao e um mp3")
    assert carregar(lixo) is None
    assert carregar(tmp_path / "nao-existe.mp3") is None
    assert carregar(tmp_path / "texto.txt") is None


# ----------------------------------------------------------------- formatos legados
def test_comentario_legado_txxx(mp3):
    id3 = ID3()
    id3.add(TXXX(encoding=3, desc="comment", text=["do ffmpeg"]))
    id3.save(mp3)
    assert carregar(mp3).tags["comment"] == "do ffmpeg"

    salvar(mp3, {"comment": "novo"})
    assert "TXXX:comment" not in _tags(mp3)
    assert carregar(mp3).tags["comment"] == "novo"


def test_comentario_com_descricao_e_preservado(mp3):
    id3 = ID3()
    id3.add(COMM(encoding=3, lang="eng", desc="iTunNORM", text=["000"]))
    id3.add(COMM(encoding=3, lang="eng", desc="", text=["meu"]))
    id3.save(mp3)
    assert carregar(mp3).tags["comment"] == "meu"
    salvar(mp3, {"comment": ""})
    assert [f.desc for f in _tags(mp3).getall("COMM")] == ["iTunNORM"]


def test_genero_id3v1_numerico(mp3):
    id3 = ID3()
    id3.add(TCON(encoding=3, text=["(17)"]))
    id3.save(mp3)
    assert carregar(mp3).tags["genre"] == "Rock"


def test_letra_com_outra_descricao_e_preservada(mp3):
    id3 = ID3()
    id3.add(USLT(encoding=3, lang="eng", desc="", text="letra"))
    id3.add(USLT(encoding=3, lang="por", desc="traducao", text="tradução"))
    id3.save(mp3)
    assert carregar(mp3).tags["lyrics"] == "letra"
    salvar(mp3, {"lyrics": "nova"})
    letras = {f.desc: f.text for f in _tags(mp3).getall("USLT")}
    assert letras == {"": "nova", "traducao": "tradução"}


# ----------------------------------------------------------------- multivalor
def test_multivalor(mp3):
    salvar(mp3, {"artist": "A; B", "genre": "Rock;Pop", "title": "X; Y"})
    tags = _tags(mp3)
    assert tags["TPE1"].text == ["A", "B"]
    assert tags["TCON"].genres == ["Rock", "Pop"]
    assert tags["TIT2"].text == ["X; Y"]              # título não é multivalor
    assert carregar(mp3).tags["artist"] == "A; B"


def test_multivalor_desligado(mp3, monkeypatch):
    monkeypatch.setattr(metadata, "MULTIVALOR", False)
    salvar(mp3, {"artist": "A; B"})
    assert _tags(mp3)["TPE1"].text == ["A; B"]


def test_multivalor_sobrevive_ao_salvar_outro_campo(mp3):
    salvar(mp3, {"artist": "AC/DC; Outro"})
    salvar(mp3, {"title": "T"})
    assert _tags(mp3)["TPE1"].text == ["AC/DC", "Outro"]


# ----------------------------------------------------------------- capa
def _com_imagens(mp3, *imagens):
    id3 = ID3()
    for tipo, desc, dados in imagens:
        id3.add(APIC(encoding=3, mime="image/jpeg", type=tipo, desc=desc, data=dados))
    id3.save(mp3)


def test_trocar_capa_mantem_outras_imagens(mp3):
    _com_imagens(mp3, (3, "", b"frente"), (4, "Cover", b"verso"), (8, "artista", b"foto"))
    salvar(mp3, {}, capa=("definir", PNG, "image/png"))
    imagens = {f.type: f.data for f in _tags(mp3).getall("APIC")}
    assert imagens == {3: PNG, 4: b"verso", 8: b"foto"}
    assert ler_capa(mp3) == (PNG, "image/png")


def test_remover_capa_mantem_outras_imagens(mp3):
    _com_imagens(mp3, (3, "", b"frente"), (4, "verso", b"verso"))
    salvar(mp3, {}, capa=("remover",))
    assert [f.type for f in _tags(mp3).getall("APIC")] == [4]
    assert not carregar(mp3).tem_capa and ler_capa(mp3) is None


def test_capa_do_tipo_outra(mp3):
    _com_imagens(mp3, (0, "", b"outra"), (4, "verso", b"verso"))
    assert ler_capa(mp3) == (b"outra", "image/jpeg")
    salvar(mp3, {}, capa=("definir", JPEG, "image/jpeg"))
    imagens = sorted((f.type, f.data) for f in _tags(mp3).getall("APIC"))
    assert imagens == [(3, JPEG), (4, b"verso")]


def test_so_contracapa_nao_conta_como_capa(mp3):
    _com_imagens(mp3, (4, "", b"verso"))
    assert not carregar(mp3).tem_capa
    salvar(mp3, {}, capa=("definir", JPEG, "image/jpeg"))
    assert sorted(f.type for f in _tags(mp3).getall("APIC")) == [3, 4]


def test_remover_capa_sem_tags_nao_cria_cabecalho(mp3):
    antes = mp3.read_bytes()
    salvar(mp3, {}, capa=("remover",))
    assert mp3.read_bytes() == antes


# ----------------------------------------------------------------- mtime
def test_foi_modificado(mp3):
    faixa = carregar(mp3)
    assert not foi_modificado(faixa)
    salvar(mp3, {"title": "por outro programa"})
    depois = faixa.mtime + 5_000_000_000
    os.utime(mp3, ns=(depois, depois))
    assert foi_modificado(faixa)


# ----------------------------------------------------------------- limpeza
def _com_id3v1(mp3):
    with open(mp3, "ab") as f:
        f.write(b"TAG" + b"Titulo v1".ljust(30, b"\0") + bytes(94) + b"\xff")   # 0xFF = sem gênero


def test_remover_id3v1_ao_salvar(mp3, monkeypatch):
    _com_id3v1(mp3)
    salvar(mp3, {"title": "A"})
    assert tem_id3v1(mp3)                         # padrão: só atualiza
    monkeypatch.setattr(metadata, "REMOVER_ID3V1", True)
    salvar(mp3, {"title": "B"})
    assert not tem_id3v1(mp3)


def test_analisar_e_limpar_extras(mp3):
    id3 = ID3()
    id3.add(TXXX(encoding=3, desc="comment", text=["fica"]))
    id3.add(TXXX(encoding=3, desc="REPLAYGAIN_TRACK_GAIN", text=["-6 dB"]))
    id3.add(PRIV(owner="WM/Provider", data=b"x"))
    id3.add(TIT2(encoding=3, text=["título"]))
    id3.save(mp3)
    _com_id3v1(mp3)

    analise = analisar_extras(mp3)
    assert analise["id3v1"] and analise["extras"] == {"TXXX": 1, "PRIV": 1}

    assert limpar_extras(mp3, id3v1=True, desconhecidos=True, extras=True)
    assert sorted(_tags(mp3).keys()) == ["TIT2", "TXXX:comment"]
    assert not tem_id3v1(mp3)
    assert not limpar_extras(mp3, id3v1=True, desconhecidos=True, extras=True)   # nada mais a fazer


def test_valores_comuns():
    vazio = {c: "" for c in metadata.CAMPOS}
    a = metadata.Faixa(Path("a.mp3"), vazio | {"artist": "X", "album": "1"})
    b = metadata.Faixa(Path("b.mp3"), vazio | {"artist": "X", "album": "2"})
    comuns = valores_comuns([a, b])
    assert comuns["artist"] == "X" and comuns["album"] == VARIOS and comuns["title"] == ""
