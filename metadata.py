"""
Backend de metadados do Tagger.

Toda a leitura e escrita de tags passa por aqui, sem nenhuma dependência de
interface. A CLI (main.py) e a GUI (app.py) usam as mesmas funções.

Princípios:
- Ler NUNCA grava nada no arquivo (só `salvar` grava).
- Uma gravação aplica várias tags de uma vez (um único save por arquivo).
- Valor vazio ("") significa "remover a tag".
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re

from mutagen.id3 import (
    ID3, APIC, COMM, TALB, TCOM, TCON, TDRC, TEXT, TIT2, TPE1, TPE2, TPOS, TRCK,
)
from mutagen.mp3 import MP3, HeaderNotFoundError

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

# Versão do ID3v2 usada ao salvar. 3 (ID3v2.3) é a mais compatível: Windows
# Explorer, carros e players antigos leem bem. Troque para 4 se preferir v2.4.
VERSAO_ID3 = 3

EXTENSOES_SUPORTADAS = {".mp3"}

# Campos editáveis, na ordem em que aparecem na interface.
# chave interna -> (rótulo, frame ID3)
CAMPOS = {
    "title":       ("Título",           TIT2),
    "artist":      ("Artista",          TPE1),
    "album":       ("Álbum",            TALB),
    "albumartist": ("Artista do álbum", TPE2),
    "tracknumber": ("Faixa",            TRCK),
    "discnumber":  ("Disco",            TPOS),
    "date":        ("Ano",              TDRC),
    "genre":       ("Gênero",           TCON),
    "composer":    ("Compositor",       TCOM),
    "lyricist":    ("Letrista",         TEXT),
    "comment":     ("Comentário",       COMM),
}

# Campos que fazem sentido aplicar igual em vários arquivos de uma vez.
# (Título e faixa são únicos por música, então ficam de fora.)
CAMPOS_BULK = [
    "artist", "album", "albumartist", "discnumber", "date",
    "genre", "composer", "lyricist", "comment",
]

# Marcador usado quando vários arquivos selecionados têm valores diferentes
# no mesmo campo. A interface mostra isso como "‹vários valores›".
VARIOS = "\x00<varios>\x00"


def rotulo(campo):
    """Nome amigável do campo, ex.: 'albumartist' -> 'Artista do álbum'."""
    return CAMPOS[campo][0]


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------

@dataclass
class Faixa:
    """Retrato de um arquivo de áudio no momento em que foi lido."""
    caminho: Path
    tags: dict = field(default_factory=dict)   # campo -> str ("" se vazio)
    tem_capa: bool = False
    duracao: float = 0.0                        # segundos
    bitrate: int = 0                            # kbps

    @property
    def nome(self):
        return self.caminho.name

    @property
    def duracao_formatada(self):
        minutos, segundos = divmod(int(round(self.duracao)), 60)
        return f"{minutos}:{segundos:02d}"


# ---------------------------------------------------------------------------
# Arquivos
# ---------------------------------------------------------------------------

def formato(arquivo):
    extensao = Path(arquivo).suffix.lower()
    return extensao[1:] if extensao in EXTENSOES_SUPORTADAS else None


def listar_audios(pasta, recursivo=True):
    """Todos os arquivos suportados dentro de uma pasta, em ordem alfabética."""
    pasta = Path(pasta)
    padrao = "**/*" if recursivo else "*"
    return sorted(
        p for p in pasta.glob(padrao)
        if p.is_file() and p.suffix.lower() in EXTENSOES_SUPORTADAS
    )


# ---------------------------------------------------------------------------
# Leitura (somente leitura, nunca grava)
# ---------------------------------------------------------------------------

def _texto_do_frame(campo, frame):
    if campo == "genre":
        # .genres converte códigos ID3v1 como "(17)" para "Rock"
        return "; ".join(frame.genres)
    return "; ".join(str(t) for t in frame.text)


def _ler_campo(tags, campo):
    if tags is None:
        return ""

    if campo == "comment":
        # Pode haver vários COMM (iTunes grava alguns). Usamos o de descrição vazia.
        for frame in tags.getall("COMM"):
            if frame.desc == "":
                return "; ".join(frame.text)
        # Alguns programas (ex.: ffmpeg) gravam o comentário como TXXX:comment
        legado = tags.get("TXXX:comment")
        return "; ".join(legado.text) if legado else ""

    frame_id = CAMPOS[campo][1].__name__
    frame = tags.get(frame_id)
    return _texto_do_frame(campo, frame) if frame else ""


def carregar(arquivo):
    """Lê um arquivo e devolve uma Faixa, ou None se não for suportado/válido."""
    caminho = Path(arquivo)
    if formato(caminho) != "mp3":
        return None

    try:
        audio = MP3(caminho)
    except (HeaderNotFoundError, OSError):
        return None

    tags = audio.tags
    return Faixa(
        caminho=caminho,
        tags={campo: _ler_campo(tags, campo) for campo in CAMPOS},
        tem_capa=bool(tags and tags.getall("APIC")),
        duracao=audio.info.length,
        bitrate=audio.info.bitrate // 1000,
    )


def carregar_varios(arquivos):
    """Lê vários arquivos. Ignora (e devolve à parte) os que falharem."""
    faixas, falhas = [], []
    for arquivo in arquivos:
        faixa = carregar(arquivo)
        if faixa is None:
            falhas.append(Path(arquivo))
        else:
            faixas.append(faixa)
    return faixas, falhas


def valores_comuns(faixas):
    """
    Para uma seleção de faixas, devolve campo -> valor.
    Se todas têm o mesmo valor, devolve o valor; se diferem, devolve VARIOS.
    É o que alimenta o painel de edição quando vários arquivos estão selecionados.
    """
    if not faixas:
        return {campo: "" for campo in CAMPOS}

    resultado = {}
    for campo in CAMPOS:
        valores = {f.tags.get(campo, "") for f in faixas}
        resultado[campo] = valores.pop() if len(valores) == 1 else VARIOS
    return resultado


def ler_capa(arquivo):
    """Devolve (bytes, mime) da capa frontal (ou da primeira imagem), ou None."""
    try:
        tags = MP3(arquivo).tags
    except (HeaderNotFoundError, OSError):
        return None
    if not tags:
        return None

    imagens = tags.getall("APIC")
    if not imagens:
        return None
    frontal = next((img for img in imagens if img.type == 3), imagens[0])
    return frontal.data, frontal.mime


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------

_RE_DATA = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")   # 2024, 2024-05, 2024-05-17
_RE_NUMERO = re.compile(r"^\d+(/\d+)?$")            # 3 ou 3/12


def validar_valor(campo, valor):
    """
    Devolve (True, valor_normalizado) ou (False, mensagem_de_erro).
    Valor vazio é sempre válido: significa remover a tag.
    """
    valor = valor.strip()

    if valor == "" or valor == VARIOS:
        return True, valor

    if campo == "date":
        ano_atual = datetime.now().year
        if valor.lower() == "atual":
            return True, str(ano_atual)
        if not _RE_DATA.match(valor):
            return False, "Ano inválido. Use AAAA (ex.: 2024) ou AAAA-MM-DD."
        ano = int(valor[:4])
        if not 1000 <= ano <= ano_atual:
            return False, f"O ano deve estar entre 1000 e {ano_atual}."
        return True, valor

    if campo in ("tracknumber", "discnumber"):
        if not _RE_NUMERO.match(valor) or any(int(p) == 0 for p in valor.split("/")):
            return False, "Número inválido. Use números maiores que 0 (ex.: '3' ou '3/12')."
        return True, valor

    if campo == "genre" and valor.isdigit():
        return False, "Digite o nome do gênero por extenso (ex.: 'Rock')."

    return True, valor


def validar_alteracoes(alteracoes):
    """Valida um dicionário campo -> valor. Devolve (normalizado, erros)."""
    normalizado, erros = {}, {}
    for campo, valor in alteracoes.items():
        ok, resultado = validar_valor(campo, valor)
        if ok:
            normalizado[campo] = resultado
        else:
            erros[campo] = resultado
    return normalizado, erros


# ---------------------------------------------------------------------------
# Escrita
# ---------------------------------------------------------------------------

def _aplicar_campo(tags, campo, valor):
    if campo == "comment":
        for chave in [k for k, f in tags.items() if k.startswith("COMM") and f.desc == ""]:
            del tags[chave]
        tags.delall("TXXX:comment")   # formato alternativo, ver _ler_campo
        if valor:
            tags.add(COMM(encoding=3, lang="eng", desc="", text=[valor]))
        return

    classe = CAMPOS[campo][1]
    tags.delall(classe.__name__)
    if valor:
        tags.add(classe(encoding=3, text=[valor]))


def salvar(arquivo, alteracoes):
    """
    Grava várias tags de uma vez em um arquivo.

    alteracoes: dict campo -> valor
      - "" remove a tag
      - VARIOS é ignorado (campo não foi tocado numa edição em lote)
    Cria o cabeçalho ID3 só aqui, se o arquivo ainda não tiver um.
    """
    audio = MP3(arquivo)
    if audio.tags is None:
        audio.add_tags()

    for campo, valor in alteracoes.items():
        if campo not in CAMPOS or valor == VARIOS:
            continue
        _aplicar_campo(audio.tags, campo, valor)

    audio.save(v2_version=VERSAO_ID3)


def salvar_varios(arquivos, alteracoes):
    """
    Aplica as mesmas alterações em vários arquivos.
    Devolve {caminho: mensagem_de_erro} dos que falharam (vazio = tudo certo).
    """
    falhas = {}
    for arquivo in arquivos:
        try:
            salvar(arquivo, alteracoes)
        except Exception as erro:   # arquivo somente leitura, em uso, corrompido...
            falhas[Path(arquivo)] = str(erro)
    return falhas


def definir_capa(arquivo, dados, mime="image/jpeg"):
    """Substitui a capa frontal do arquivo pela imagem informada."""
    audio = MP3(arquivo)
    if audio.tags is None:
        audio.add_tags()
    audio.tags.delall("APIC")
    audio.tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=dados))
    audio.save(v2_version=VERSAO_ID3)


def remover_capa(arquivo):
    audio = MP3(arquivo)
    if audio.tags is None:
        return
    audio.tags.delall("APIC")
    audio.save(v2_version=VERSAO_ID3)