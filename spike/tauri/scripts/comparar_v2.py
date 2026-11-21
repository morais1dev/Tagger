"""
Compara a gravação do spike (lofty, via spike-tags) com a da v2 (tagger.nucleo.metadata) no mesmo arquivo.

Para cada formato (MP3, FLAC, M4A):
1. gera um arquivo sem tags com os geradores de tests/conftest.py, numa pasta temporária;
2. enche o arquivo pela v2 com todos os campos, capa frontal + contracapa e "extras" que o Tagger
   não mostra (TXXX/PRIV no MP3, chaves livres no FLAC, átomo freeform no M4A);
3. faz duas cópias e aplica a mesma edição: uma pela v2, outra pelo spike;
4. despeja TUDO o que o mutagen enxerga nas duas e compara (frames/chaves/átomos, imagens, versão do ID3).

Uso (da raiz do repositório, depois de `cargo build` em spike/tauri/nucleo):
    python spike/tauri/scripts/comparar_v2.py               # MP3 em ID3v2.3 (padrão da v2)
    SPIKE_ID3=4 python spike/tauri/scripts/comparar_v2.py   # MP3 em ID3v2.4 nos dois lados
Sai com código 1 se alguma comparação diferir. Nada de rede; os arquivos ficam só na pasta temporária.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from mutagen.flac import FLAC  # noqa: E402
from mutagen.id3 import APIC, ID3, PRIV, TXXX  # noqa: E402
from mutagen.mp4 import MP4, MP4Cover, MP4FreeForm  # noqa: E402

from tagger.nucleo import metadata  # noqa: E402
from tests.conftest import criar_flac, criar_m4a, criar_mp3  # noqa: E402

BINARIO = RAIZ / "spike" / "tauri" / "nucleo" / "target" / "debug" / "spike-tags.exe"
if not BINARIO.exists():
    BINARIO = BINARIO.with_suffix("")

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-falso" * 10
JPEG_NOVO = b"\xff\xd8\xff\xe0" + b"capa-nova" * 10
PNG = b"\x89PNG\r\n\x1a\n" + b"contracapa" * 10

CRIADORES = {"mp3": criar_mp3, "flac": criar_flac, "m4a": criar_m4a}
CAMPO_V2 = {"titulo": "title", "artista": "artist", "faixa": "tracknumber", "gravadora": "gravadora"}

# (descrição, campo do spike ou "capa", valor)
EDICOES = [
    ("título", "titulo", "Título novo"),
    ("artista multivalor", "artista", "Novo A; Novo B"),
    ("faixa com total", "faixa", "5/10"),
    ("gravadora", "gravadora", "Outro selo"),
    ("remover título", "titulo", ""),
    ("capa frontal", "capa", JPEG_NOVO),
]


def preencher(caminho, fmt):
    """Arquivo "real": todos os campos da v2, capa + contracapa e extras que o Tagger não mostra."""
    metadata.salvar(caminho, {
        "title": "Título", "artist": "A; B", "album": "Álbum", "albumartist": "Artista do álbum",
        "tracknumber": "3/12", "discnumber": "1/2", "date": "2001-05-06", "genre": "Rock; Pop",
        "composer": "Compositor", "lyricist": "Letrista", "comment": "comentário", "lyrics": "lá lá\nlá",
        "gravadora": "Selo",
    }, capa=("definir", JPEG, "image/jpeg"))
    if fmt == "mp3":
        tags = ID3(caminho)
        tags.add(TXXX(encoding=3, desc="REPLAYGAIN_TRACK_GAIN", text=["-6.00 dB"]))
        tags.add(PRIV(owner="WM/Provider", data=b"\x01\x02"))
        tags.add(APIC(encoding=3, mime="image/png", type=4, desc="contracapa", data=PNG))
        tags.save(caminho, v2_version=3, v23_sep=None)
    elif fmt == "flac":
        audio = FLAC(caminho)
        audio["REPLAYGAIN_TRACK_GAIN"] = "-6.00 dB"
        audio["MUSICBRAINZ_TRACKID"] = "00000000-0000-0000-0000-000000000000"
        from mutagen.flac import Picture
        pic = Picture()
        pic.type, pic.mime, pic.desc, pic.data = 4, "image/png", "contracapa", PNG
        audio.add_picture(pic)
        audio.save()
    else:
        audio = MP4(caminho)
        audio["----:com.apple.iTunes:REPLAYGAIN_TRACK_GAIN"] = [MP4FreeForm(b"-6.00 dB")]
        audio["covr"] = list(audio["covr"]) + [MP4Cover(PNG, imageformat=MP4Cover.FORMAT_PNG)]
        audio.save()


def despejar(caminho, fmt):
    """Tudo o que o mutagen lê, num formato comparável (lista ordenada de linhas)."""
    linhas = []
    if fmt == "mp3":
        tags = ID3(caminho)
        linhas.append(f"versão ID3v2.{tags.version[1]}")
        for chave in sorted(tags.keys()):
            frame = tags[chave]
            if isinstance(frame, APIC):
                linhas.append(f"{chave}: APIC tipo={frame.type} mime={frame.mime} {len(frame.data)} bytes")
            elif isinstance(frame, PRIV):
                linhas.append(f"{chave}: PRIV {frame.owner} {frame.data!r}")
            elif hasattr(frame, "text"):
                linhas.append(f"{chave}: {[str(t) for t in frame.text]}")
            else:
                linhas.append(f"{chave}: {frame!r}")
    elif fmt == "flac":
        audio = FLAC(caminho)
        pares = sorted((k.upper(), v) for k, v in (audio.tags or []))
        linhas += [f"{k}={v}" for k, v in pares]
        linhas += [f"PICTURE tipo={p.type} mime={p.mime} desc={p.desc!r} {len(p.data)} bytes" for p in audio.pictures]
    else:
        audio = MP4(caminho)
        for chave in sorted(audio.tags or {}):
            valores = audio.tags[chave]
            if chave == "covr":
                linhas.append(f"covr: {[(c.imageformat, len(c)) for c in valores]}")
            else:
                linhas.append(f"{chave}: {[bytes(v) if isinstance(v, MP4FreeForm) else v for v in valores]}")
    return linhas


VERSAO_ID3 = int(os.environ.get("SPIKE_ID3", "3"))     # o spike-tags lê a mesma variável


def editar_v2(caminho, campo, valor):
    opcoes = metadata.OpcoesGravacao(versao_id3=VERSAO_ID3)
    if campo == "capa":
        metadata.salvar(caminho, {}, capa=("definir", valor, "image/jpeg"), opcoes=opcoes)
    else:
        metadata.salvar(caminho, {CAMPO_V2[campo]: valor}, opcoes=opcoes)


def editar_spike(caminho, campo, valor, pasta):
    if campo == "capa":
        imagem = pasta / "capa.jpg"
        imagem.write_bytes(valor)
        args = ["capa", str(caminho), str(imagem), "image/jpeg"]
    else:
        args = ["gravar", str(caminho), campo, valor]
    subprocess.run([str(BINARIO), *args], check=True)


def main():
    if not BINARIO.exists():
        sys.exit(f"compile antes: cargo build (em spike/tauri/nucleo); não achei {BINARIO}")
    falhas = 0
    print("| Formato | Edição | v2 × spike | Campos não editados preservados (spike × original) | Diferenças |")
    print("|---|---|---|---|---|")
    with tempfile.TemporaryDirectory(prefix="spike-v2-") as tmp:
        pasta = Path(tmp)
        for fmt, criar in CRIADORES.items():
            base = criar(pasta / f"base.{fmt}")
            preencher(base, fmt)
            original = despejar(base, fmt)
            for descricao, campo, valor in EDICOES:
                v2, spike = pasta / f"v2.{fmt}", pasta / f"spike.{fmt}"
                shutil.copy(base, v2)
                shutil.copy(base, spike)
                editar_v2(v2, campo, valor)
                editar_spike(spike, campo, valor, pasta)
                d_v2, d_spike = despejar(v2, fmt), despejar(spike, fmt)
                diferencas = sorted(set(d_v2) ^ set(d_spike))
                # preservação: o que mudou em relação ao original deve ser igual ao que a v2 mudou
                mudou_v2 = set(original) ^ set(d_v2)
                mudou_spike = set(original) ^ set(d_spike)
                preservado = mudou_spike <= mudou_v2
                igual = not diferencas
                falhas += not igual
                texto = "; ".join(("só v2: " if d in d_v2 else "só spike: ") + d.replace("|", "\\|")
                                  for d in diferencas) or "—"
                print(f"| {fmt.upper()} | {descricao} | {'igual' if igual else 'DIFERENTE'} | "
                      f"{'sim' if preservado else 'NÃO'} | {texto} |")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
