import base64
import os
from datetime import datetime
from pathlib import Path

import mutagen
import pytest
from mutagen.flac import FLAC, Picture
from mutagen.id3 import APIC, COMM, ID3, PRIV, TCON, TIT2, TXXX, USLT
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from tagger.nucleo import metadata
from tagger.nucleo.metadata import (
    VARIOS, analisar_extras, carregar, definir_capa, foi_modificado, formato, ler_capa, limpar_extras,
    listar_audios, remover_capa, salvar, salvar_varios, tem_id3v1, validar_valor, valores_comuns,
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


def test_gravadora_mp3(mp3):
    salvar(mp3, {"gravadora": "Selo; Dois"})
    assert str(_tags(mp3)["TPUB"]) == "Selo; Dois"          # TPUB não é multivalor
    assert carregar(mp3).tags["gravadora"] == "Selo; Dois"
    salvar(mp3, {"gravadora": ""})
    assert "TPUB" not in _tags(mp3) and carregar(mp3).tags["gravadora"] == ""


def test_valor_vazio_remove_e_varios_ignora(mp3):
    salvar(mp3, {"title": "A", "artist": "B"})
    salvar(mp3, {"title": "", "artist": VARIOS})
    tags = carregar(mp3).tags
    assert tags["title"] == "" and tags["artist"] == "B"
    assert "TIT2" not in _tags(mp3)


@pytest.mark.parametrize("alteracoes, capa", [
    ({"title": "", "artist": VARIOS}, None),
    ({}, ("remover",)),
    ({"comment": "", "lyrics": ""}, ("remover",)),
])
def test_so_remocoes_nao_cria_cabecalho_vazio(mp3, alteracoes, capa):
    antes = mp3.read_bytes()
    salvar(mp3, alteracoes, capa)
    assert _tags(mp3) is None
    assert mp3.read_bytes() == antes


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


# ----------------------------------------------------------------- FLAC, Ogg Vorbis e M4A
# A fixture `outro` roda cada teste uma vez por formato.
CLASSES = {".flac": FLAC, ".ogg": OggVorbis, ".m4a": MP4}
ARTISTA = {".flac": "ARTIST", ".ogg": "ARTIST", ".m4a": "\xa9ART"}


def _abrir(caminho):
    return CLASSES[caminho.suffix](caminho)


def _imagem_flac(tipo, dados, mime="image/jpeg"):
    imagem = Picture()
    imagem.type, imagem.mime, imagem.data = tipo, mime, dados
    return imagem


def _com_imagens_outro(caminho, *imagens):
    """imagens: (tipo, dados). No M4A não há tipo: entram na ordem dada."""
    audio = _abrir(caminho)
    if caminho.suffix == ".flac":
        for tipo, dados in imagens:
            audio.add_picture(_imagem_flac(tipo, dados))
    elif caminho.suffix == ".ogg":
        audio.tags["METADATA_BLOCK_PICTURE"] = [
            base64.b64encode(_imagem_flac(tipo, dados).write()).decode("ascii") for tipo, dados in imagens]
    else:
        if audio.tags is None:
            audio.add_tags()
        audio.tags["covr"] = [MP4Cover(dados) for _tipo, dados in imagens]
    audio.save()


def _imagens_outro(caminho):
    audio = _abrir(caminho)
    if caminho.suffix == ".flac":
        return [(p.type, p.data) for p in audio.pictures]
    if caminho.suffix == ".ogg":
        return [(p.type, p.data) for p in (Picture(base64.b64decode(t))
                                           for t in audio.tags.get("METADATA_BLOCK_PICTURE", []))]
    return [(None, bytes(c)) for c in audio.tags.get("covr", [])]


def test_formatos_suportados(tmp_path):
    assert [formato(f"a.{ext}") for ext in ("MP3", "flac", "ogg", "m4a", "mp4")] == \
        ["mp3", "flac", "ogg", "m4a", "mp4"]
    assert formato("a.wav") is None
    for nome in ("a.mp3", "b.FLAC", "c.ogg", "d.m4a", "e.mp4", "f.wav", "g.jpg"):
        (tmp_path / nome).write_bytes(b"")
    assert [p.name for p in listar_audios(tmp_path)] == ["a.mp3", "b.FLAC", "c.ogg", "d.m4a", "e.mp4"]


def test_outro_sem_tags(outro):
    faixa = carregar(outro)
    assert faixa.tags == {campo: "" for campo in metadata.CAMPOS}
    assert not faixa.tem_capa and faixa.duracao == pytest.approx(2.0)
    assert faixa.formato == outro.suffix[1:]
    assert ler_capa(outro) is None


def test_outro_ler_nao_grava(outro):
    antes = outro.read_bytes()
    carregar(outro)
    ler_capa(outro)
    analisar_extras(outro)
    assert outro.read_bytes() == antes


def test_outro_salvar_e_reler(outro):
    valores = {"title": "Música", "artist": "A; B", "album": "Álbum", "albumartist": "Vários",
               "tracknumber": "3/12", "discnumber": "1/2", "date": "2024-05-17", "genre": "Rock; Pop",
               "composer": "C", "lyricist": "L1; L2", "comment": "linha 1\nlinha 2", "lyrics": "lá lá\nlá",
               "gravadora": "Selo; Dois"}
    salvar(outro, valores)
    assert carregar(outro).tags == valores


def test_outro_multivalor_nativo(outro, monkeypatch):
    salvar(outro, {"artist": "A; B"})
    assert list(_abrir(outro).tags[ARTISTA[outro.suffix]]) == ["A", "B"]
    monkeypatch.setattr(metadata, "MULTIVALOR", False)
    salvar(outro, {"artist": "A; B"})
    assert list(_abrir(outro).tags[ARTISTA[outro.suffix]]) == ["A; B"]


def test_outro_faixa_sem_total(outro):
    salvar(outro, {"tracknumber": "3/12"})
    salvar(outro, {"tracknumber": "4"})
    # Vorbis: o total é outra chave (TRACKTOTAL) e fica; MP4: é o mesmo par (trkn), como no ID3
    esperado = "4" if outro.suffix == ".m4a" else "4/12"
    assert carregar(outro).tags["tracknumber"] == esperado
    salvar(outro, {"tracknumber": ""})            # apagar a faixa apaga o total junto
    assert carregar(outro).tags["tracknumber"] == ""
    assert len(_abrir(outro).tags.keys()) == 0


@pytest.mark.parametrize("campo, chave, total", [("tracknumber", "TRACKTOTAL", "TOTALTRACKS"),
                                                 ("discnumber", "DISCTOTAL", "TOTALDISCS")])
def test_vorbis_numero_sem_barra_mantem_total(criar_audio, campo, chave, total):
    caminho = criar_audio("flac")
    audio = FLAC(caminho)
    audio.add_tags()
    audio.tags[metadata.vorbis.CHAVES[campo]] = ["3"]
    audio.tags[total] = ["12"]                    # nome alternativo do total
    audio.save()
    salvar(caminho, {campo: "5"})
    gravado = FLAC(caminho).tags
    assert gravado[metadata.vorbis.CHAVES[campo]] == ["5"] and gravado[total] == ["12"]
    assert carregar(caminho).tags[campo] == "5/12"
    salvar(caminho, {campo: "6/7"})               # total novo: um só, com o nome principal
    gravado = FLAC(caminho).tags
    assert gravado[chave] == ["7"] and total not in gravado


def test_vorbis_alternativa_com_outro_conteudo_fica(criar_audio):
    caminho = criar_audio("flac")
    audio = FLAC(caminho)
    audio.add_tags()
    audio.tags["COMMENT"] = ["visto"]
    audio.tags["DESCRIPTION"] = ["nunca exibido"]     # outro conteúdo: o usuário nunca viu
    audio.tags["ALBUMARTIST"] = ["X"]
    audio.tags["ALBUM ARTIST"] = ["X"]                # cópia do mesmo valor
    audio.tags["LYRICS"] = ["letra"]
    audio.tags["UNSYNCEDLYRICS"] = ["outra letra"]
    audio.save()
    salvar(caminho, {"comment": "novo", "albumartist": "Y", "lyrics": ""})
    gravado = FLAC(caminho).tags
    assert gravado["COMMENT"] == ["novo"] and gravado["DESCRIPTION"] == ["nunca exibido"]
    assert gravado["ALBUMARTIST"] == ["Y"] and "ALBUM ARTIST" not in gravado
    assert "LYRICS" not in gravado and gravado["UNSYNCEDLYRICS"] == ["outra letra"]


@pytest.mark.parametrize("campo", ["comment", "lyrics"])
def test_outro_so_o_primeiro_comentario_ou_letra_e_trocado(outro, campo):
    chave = (metadata.mp4.CHAVES if outro.suffix == ".m4a" else metadata.vorbis.CHAVES)[campo]
    audio = _abrir(outro)
    if audio.tags is None:
        audio.add_tags()
    audio.tags[chave] = ["primeiro", "segundo"]
    audio.save()
    assert carregar(outro).tags[campo] == "primeiro"
    salvar(outro, {campo: "novo"})
    assert list(_abrir(outro).tags[chave]) == ["novo", "segundo"]


def test_mp4_limpeza_nao_toca_atomos_tecnicos(criar_audio):
    caminho = criar_audio("m4a")
    audio = MP4(caminho)
    audio.add_tags()
    audio.tags["\xa9too"] = ["Lavf"]
    audio.tags["pgap"] = True
    audio.tags["cpil"] = True
    audio.tags["tmpo"] = [120]
    audio.tags["----:com.apple.iTunes:iTunSMPB"] = [b" 00000000 00000840"]
    audio.tags["----:com.apple.iTunes:iTunNORM"] = [b" 0000031F"]
    audio.save()
    assert analisar_extras(caminho)["extras"] == {"\xa9too": 1}
    assert limpar_extras(caminho, extras=True)
    assert sorted(MP4(caminho).tags.keys()) == sorted(
        ["pgap", "cpil", "tmpo", "----:com.apple.iTunes:iTunSMPB", "----:com.apple.iTunes:iTunNORM"])


def test_mp4_capa_que_nao_e_jpeg_nem_png_e_recusada(criar_audio):
    caminho = criar_audio("m4a")
    antes = caminho.read_bytes()
    with pytest.raises(ValueError):
        salvar(caminho, {"title": "A"}, capa=("definir", b"GIF89a", "image/gif"))
    assert caminho.read_bytes() == antes          # nada gravado, nem o título


def test_ogg_coverart_antigo(criar_audio):
    caminho = criar_audio("ogg")
    audio = OggVorbis(caminho)
    audio.tags["COVERART"] = [base64.b64encode(PNG).decode("ascii")]
    audio.tags["COVERARTMIME"] = ["image/png"]
    audio.save()
    assert carregar(caminho).tem_capa and ler_capa(caminho) == (PNG, "image/png")
    definir_capa(caminho, JPEG)
    gravado = OggVorbis(caminho).tags
    assert "COVERART" not in gravado and "COVERARTMIME" not in gravado
    assert ler_capa(caminho) == (JPEG, "image/jpeg")


def test_ogg_opus(opus):
    faixa = carregar(opus)
    assert faixa is not None and faixa.formato == "ogg" and faixa.duracao == pytest.approx(2.0)
    salvar(opus, {"title": "Opus", "artist": "A; B"}, capa=("definir", JPEG, "image/jpeg"))
    assert list(OggOpus(opus).tags["ARTIST"]) == ["A", "B"]
    faixa = carregar(opus)
    assert faixa.tags["title"] == "Opus" and faixa.tags["artist"] == "A; B" and faixa.tem_capa
    assert ler_capa(opus) == (JPEG, "image/jpeg")


def test_outro_valor_vazio_remove_e_varios_ignora(outro):
    salvar(outro, {"title": "A", "artist": "B", "tracknumber": "3/12"})
    salvar(outro, {"title": "", "artist": VARIOS, "tracknumber": ""})
    tags = carregar(outro).tags
    assert tags["title"] == "" and tags["artist"] == "B" and tags["tracknumber"] == ""
    assert len(_abrir(outro).tags.keys()) == 1   # nem TRACKTOTAL sobra


def test_outro_um_unico_save(outro, monkeypatch):
    classe = CLASSES[outro.suffix]
    chamadas = []
    original = classe.save
    monkeypatch.setattr(classe, "save", lambda self, *a, **k: chamadas.append(1) or original(self, *a, **k))
    salvar(outro, {"title": "A"}, capa=("definir", JPEG, "image/jpeg"))
    assert len(chamadas) == 1
    assert carregar(outro).tags["title"] == "A" and ler_capa(outro) == (JPEG, "image/jpeg")


def test_outro_capa_definir_trocar_remover(outro):
    definir_capa(outro, JPEG)
    assert carregar(outro).tem_capa and ler_capa(outro) == (JPEG, "image/jpeg")
    definir_capa(outro, PNG, "image/png")
    assert ler_capa(outro) == (PNG, "image/png")
    assert len(_imagens_outro(outro)) == 1
    remover_capa(outro)
    assert ler_capa(outro) is None and not carregar(outro).tem_capa


def test_outro_outras_imagens_ficam(outro):
    _com_imagens_outro(outro, (3, b"frente"), (4, b"verso"))
    assert ler_capa(outro)[0] == b"frente"
    definir_capa(outro, JPEG)
    imagens = _imagens_outro(outro)
    assert len(imagens) == 2 and (b"verso" in [dados for _tipo, dados in imagens])
    assert ler_capa(outro) == (JPEG, "image/jpeg")
    remover_capa(outro)
    assert [dados for _tipo, dados in _imagens_outro(outro)] == [b"verso"]


@pytest.mark.parametrize("sufixo", [".flac", ".ogg"])
def test_vorbis_so_contracapa_nao_conta_como_capa(criar_audio, sufixo):
    caminho = criar_audio(sufixo[1:])
    _com_imagens_outro(caminho, (4, b"verso"))
    assert not carregar(caminho).tem_capa
    definir_capa(caminho, JPEG)
    assert sorted(tipo for tipo, _dados in _imagens_outro(caminho)) == [3, 4]


def test_flac_sem_vorbis_comment_remove_capa(criar_audio):
    caminho = criar_audio("flac")
    _com_imagens_outro(caminho, (3, b"frente"))
    assert FLAC(caminho).tags is None
    remover_capa(caminho)
    assert ler_capa(caminho) is None and FLAC(caminho).tags is None


def test_vorbis_nomes_alternativos(criar_audio):
    caminho = criar_audio("flac")
    audio = FLAC(caminho)
    audio.add_tags()
    audio.tags["DESCRIPTION"] = ["comentário antigo"]
    audio.tags["UNSYNCEDLYRICS"] = ["letra antiga"]
    audio.tags["TRACKNUMBER"] = ["5"]
    audio.tags["TOTALTRACKS"] = ["9"]
    audio.save()
    tags = carregar(caminho).tags
    assert (tags["comment"], tags["lyrics"], tags["tracknumber"]) == ("comentário antigo", "letra antiga", "5/9")

    salvar(caminho, {"comment": "novo", "lyrics": "", "tracknumber": "6/10"})
    gravado = FLAC(caminho).tags
    assert sorted(chave.upper() for chave in gravado.keys()) == ["COMMENT", "TRACKNUMBER", "TRACKTOTAL"]
    assert carregar(caminho).tags["tracknumber"] == "6/10"


def test_outro_analisar_e_limpar_extras(outro):
    salvar(outro, {"title": "fica", "tracknumber": "1/2"}, capa=("definir", JPEG, "image/jpeg"))
    audio = _abrir(outro)
    chave = "REPLAYGAIN_TRACK_GAIN" if outro.suffix != ".m4a" else "----:com.apple.iTunes:replaygain_track_gain"
    audio.tags[chave] = ["-6 dB"] if outro.suffix != ".m4a" else [b"-6 dB"]
    audio.save()

    analise = analisar_extras(outro)
    assert analise == {"id3v1": False, "desconhecidos": 0, "extras": {chave: 1}}
    assert not tem_id3v1(outro)

    assert limpar_extras(outro, id3v1=True, desconhecidos=True, extras=True)
    assert analisar_extras(outro)["extras"] == {}
    faixa = carregar(outro)
    assert faixa.tags["title"] == "fica" and faixa.tags["tracknumber"] == "1/2" and faixa.tem_capa
    assert not limpar_extras(outro, id3v1=True, desconhecidos=True, extras=True)   # nada mais a fazer


def test_outro_id3v1_nunca_corta_o_arquivo(outro):
    _com_id3v1(outro)          # 128 bytes que "parecem" ID3v1 no fim de um arquivo que não é MP3
    antes = outro.read_bytes()
    assert not tem_id3v1(outro) and not analisar_extras(outro)["id3v1"]
    assert not limpar_extras(outro, id3v1=True)
    assert outro.read_bytes() == antes


def test_outro_arquivo_invalido(tmp_path):
    lixo = tmp_path / "quebrado.flac"
    lixo.write_bytes(b"isto nao e audio" * 10)
    assert carregar(lixo) is None and ler_capa(lixo) is None
    assert analisar_extras(lixo) == {"id3v1": False, "desconhecidos": 0, "extras": {}}
    assert list(salvar_varios([lixo], {"title": "A"})) == [lixo]


def test_textos_de_formatos():
    assert metadata.curingas_audio() == ("*.flac", "*.m4a", "*.mp3", "*.mp4", "*.ogg")
    assert metadata.nomes_formatos() == "FLAC, M4A, MP3, MP4, OGG"


# ----------------------------------------------------------------- gravadora
CHAVE_GRAVADORA = {".flac": "ORGANIZATION", ".ogg": "ORGANIZATION", ".m4a": "----:com.apple.iTunes:LABEL"}


def test_gravadora_outro_gravar_e_apagar(outro):
    chave = CHAVE_GRAVADORA[outro.suffix]
    salvar(outro, {"gravadora": "Selo"})
    assert carregar(outro).tags["gravadora"] == "Selo"
    valor = _abrir(outro).tags[chave][0]
    assert (bytes(valor).decode() if outro.suffix == ".m4a" else valor) == "Selo"
    salvar(outro, {"gravadora": ""})
    assert carregar(outro).tags["gravadora"] == "" and chave not in _abrir(outro).tags


@pytest.mark.parametrize("fmt", ["flac", "ogg"])
def test_gravadora_vorbis_le_label(criar_audio, fmt):
    caminho = criar_audio(fmt)
    audio = _abrir(caminho)
    if audio.tags is None:
        audio.add_tags()
    audio.tags["LABEL"] = ["Selo Antigo"]
    audio.save()
    assert carregar(caminho).tags["gravadora"] == "Selo Antigo"
    salvar(caminho, {"gravadora": "Novo"})            # troca o que foi exibido, sem deixar o LABEL velho
    tags = _abrir(caminho).tags
    assert list(tags["ORGANIZATION"]) == ["Novo"] and "LABEL" not in tags
    salvar(caminho, {"gravadora": ""})
    assert carregar(caminho).tags["gravadora"] == ""


def test_gravadora_vorbis_organization_tem_prioridade(criar_audio):
    caminho = criar_audio("flac")
    audio = FLAC(caminho)
    audio.add_tags()
    audio.tags["ORGANIZATION"] = ["Principal"]
    audio.tags["LABEL"] = ["Outro"]
    audio.save()
    assert carregar(caminho).tags["gravadora"] == "Principal"
