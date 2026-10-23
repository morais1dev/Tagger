"""
Backend de metadados do Tagger.

Toda a leitura e escrita de tags passa por aqui, sem nenhuma dependência de
interface. A CLI (tagger/cli.py) e a GUI (tagger/gui) usam as mesmas funções.

Princípios:
- Ler NUNCA grava nada no arquivo (só `salvar` e `limpar_extras` gravam).
- Uma gravação aplica várias tags (e a capa) de uma vez: um único save por arquivo.
- Valor vazio ("") significa "remover a tag".

Formatos: MP3 (ID3, aqui mesmo), FLAC e Ogg (Vorbis, Opus ou FLAC no Ogg; Vorbis comments,
formatos/vorbis.py) e M4A/MP4 (átomos do iTunes, formatos/mp4.py). Os mesmos campos valem
para todos. A capa é a imagem frontal (ver formatos.escolher_capa); no M4A/MP4, que não tem
tipo de imagem, é a 1ª do átomo covr (e só JPEG/PNG).
As opções de ID3 (VERSAO_ID3, REMOVER_ID3V1) e a limpeza de ID3v1 / frames
desconhecidos só se aplicam ao MP3; nos outros formatos são ignoradas.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re

from mutagen import MutagenError
from mutagen.flac import FLAC
from mutagen.id3 import delete as apagar_id3
from mutagen.id3 import (
    APIC, COMM, TALB, TCOM, TCON, TDRC, TEXT, TIT2, TPE1, TPE2, TPOS, TRCK, USLT,
)
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggflac import OggFLAC
from mutagen.oggopus import OggOpus
from mutagen.oggvorbis import OggVorbis

from tagger.nucleo.formatos import TIPO_CAPA_FRONTAL, TIPO_OUTRA, escolher_capa
from tagger.nucleo.formatos import mp4, vorbis

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

# Versão do ID3v2 usada ao salvar. 3 (ID3v2.3) é a mais compatível: Windows
# Explorer, carros e players antigos leem bem. Troque para 4 se preferir v2.4.
VERSAO_ID3 = 3

# "A; B" em artista, gênero etc. é gravado como vários valores (text=["A", "B"]).
# Players modernos (foobar2000, MusicBee, Plex...) mostram cada valor separado.
MULTIVALOR = True

# Remove a tag ID3v1 (128 bytes no fim do arquivo, formato dos anos 90) ao salvar.
REMOVER_ID3V1 = False

EXTENSOES_SUPORTADAS = {".mp3", ".flac", ".ogg", ".m4a", ".mp4"}

# formato (extensão sem ponto) -> módulo que lê/grava as tags. O MP3 (ID3) fica neste arquivo.
_MODULOS = {"flac": vorbis, "ogg": vorbis, "m4a": mp4, "mp4": mp4}

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
    "lyrics":      ("Letra",            USLT),
}

# Campos que fazem sentido aplicar igual em vários arquivos de uma vez.
# (Título, faixa e letra são únicos por música, então ficam de fora.)
CAMPOS_BULK = [
    "artist", "album", "albumartist", "discnumber", "date",
    "genre", "composer", "lyricist", "comment",
]

# Campos em que "A; B" vira vários valores ao salvar (se MULTIVALOR estiver ligado).
CAMPOS_MULTIVALOR = {"artist", "albumartist", "genre", "composer", "lyricist"}
SEPARADOR = "; "

# Marcador usado quando vários arquivos selecionados têm valores diferentes
# no mesmo campo. A interface mostra isso como "‹vários valores›".
VARIOS = "\x00<varios>\x00"

# Tipos de imagem tratados como "a capa" (TIPO_CAPA_FRONTAL, TIPO_OUTRA): ver
# formatos.escolher_capa. Contracapa, foto do artista etc. não são tocadas.

# Frames que o Tagger mostra/edita. O resto é "extra" para limpar_extras().
FRAMES_DO_TAGGER = {classe.__name__ for _rotulo, classe in CAMPOS.values()} | {"APIC"}


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
    mtime: int = 0                              # st_mtime_ns quando foi lido
    formato: str = ""                           # "mp3", "flac", "ogg", "m4a" ou "mp4"

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
    """'mp3', 'flac', 'ogg', 'm4a' ou 'mp4' pela extensão; None se não for suportado."""
    extensao = Path(arquivo).suffix.lower()
    return extensao[1:] if extensao in EXTENSOES_SUPORTADAS else None


def _abrir(arquivo, fmt):
    """Objeto do mutagen para o formato. Levanta MutagenError/OSError se o arquivo for inválido."""
    if fmt == "mp3":
        return MP3(arquivo)
    if fmt == "flac":
        return FLAC(arquivo)
    if fmt == "ogg":
        # .ogg pode ter Vorbis (o comum), Opus ou FLAC dentro; os três usam Vorbis comments
        for classe in (OggVorbis, OggOpus):
            try:
                return classe(arquivo)
            except MutagenError:
                continue
        return OggFLAC(arquivo)
    if fmt in ("m4a", "mp4"):
        return MP4(arquivo)
    raise MutagenError(f"formato não suportado: {Path(arquivo).name}")


def curingas_audio():
    """('*.flac', '*.m4a', '*.mp3', ...) para filtros de diálogos de arquivo."""
    return tuple(f"*{extensao}" for extensao in sorted(EXTENSOES_SUPORTADAS))


def nomes_formatos():
    """'FLAC, M4A, MP3, MP4, OGG': para textos da interface."""
    return ", ".join(extensao[1:].upper() for extensao in sorted(EXTENSOES_SUPORTADAS))


def listar_audios(pasta, recursivo=True):
    """Todos os arquivos suportados dentro de uma pasta, em ordem alfabética."""
    pasta = Path(pasta)
    padrao = "**/*" if recursivo else "*"
    return sorted(
        p for p in pasta.glob(padrao)
        if p.is_file() and p.suffix.lower() in EXTENSOES_SUPORTADAS
    )


def mtime_atual(arquivo):
    """st_mtime_ns do arquivo agora, ou None se ele não existe mais."""
    try:
        return Path(arquivo).stat().st_mtime_ns
    except OSError:
        return None


def foi_modificado(faixa):
    """True se o arquivo mudou no disco (outro programa) depois que a Faixa foi lida."""
    atual = mtime_atual(faixa.caminho)
    return atual is not None and atual != faixa.mtime


# ---------------------------------------------------------------------------
# Leitura (somente leitura, nunca grava)
# ---------------------------------------------------------------------------

def _texto_do_frame(campo, frame):
    if campo == "genre":
        # .genres converte códigos ID3v1 como "(17)" para "Rock"
        return SEPARADOR.join(frame.genres)
    return SEPARADOR.join(str(t) for t in frame.text)


def _frame_sem_descricao(tags, frame_id):
    """COMM/USLT: pode haver vários (iTunes grava alguns). Usa o de descrição vazia, senão o primeiro."""
    frames = tags.getall(frame_id)
    return next((f for f in frames if f.desc == ""), frames[0] if frames else None)


def _ler_campo_id3(tags, campo):
    if tags is None:
        return ""

    if campo == "comment":
        for frame in tags.getall("COMM"):
            if frame.desc == "":
                return SEPARADOR.join(frame.text)
        # Alguns programas (ex.: ffmpeg) gravam o comentário como TXXX:comment
        legado = tags.get("TXXX:comment")
        return SEPARADOR.join(legado.text) if legado else ""

    if campo == "lyrics":
        frame = _frame_sem_descricao(tags, "USLT")
        return str(frame.text) if frame else ""     # USLT tem um texto só, não uma lista

    frame_id = CAMPOS[campo][1].__name__
    frame = tags.get(frame_id)
    return _texto_do_frame(campo, frame) if frame else ""


def _frames_capa(tags):
    """Os frames APIC que o Tagger considera "a capa": os frontais; se não houver, o 1º do tipo "outra"."""
    if not tags:
        return []
    return escolher_capa(tags.getall("APIC"))


def _ler_campo(audio, fmt, campo):
    if fmt == "mp3":
        return _ler_campo_id3(audio.tags, campo)
    return SEPARADOR.join(_MODULOS[fmt].ler(audio, campo))


def _capas(audio, fmt):
    """[(dados, mime)] das imagens que são "a capa" (ver formatos.escolher_capa)."""
    if fmt == "mp3":
        return [(frame.data, frame.mime) for frame in _frames_capa(audio.tags)]
    return _MODULOS[fmt].capas(audio)


def carregar(arquivo):
    """Lê um arquivo e devolve uma Faixa, ou None se não for suportado/válido."""
    caminho = Path(arquivo)
    fmt = formato(caminho)
    if fmt is None:
        return None

    try:
        mtime = caminho.stat().st_mtime_ns
        audio = _abrir(caminho, fmt)
        tags = {campo: _ler_campo(audio, fmt, campo) for campo in CAMPOS}
        tem_capa = bool(_capas(audio, fmt))
    except (MutagenError, OSError):     # MutagenError cobre cabeçalho inválido, tag corrompida etc.
        return None

    return Faixa(
        caminho=caminho,
        tags=tags,
        tem_capa=tem_capa,
        duracao=audio.info.length or 0.0,
        bitrate=(audio.info.bitrate or 0) // 1000,
        mtime=mtime,
        formato=fmt,
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
    """Devolve (bytes, mime) da capa (ver formatos.escolher_capa), ou None."""
    fmt = formato(arquivo)
    if fmt is None:
        return None
    try:
        capas = _capas(_abrir(arquivo, fmt), fmt)
    except (MutagenError, OSError):
        return None
    return capas[0] if capas else None


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

def dividir_valores(campo, valor):
    """'A; B' -> ['A', 'B'] nos campos multivalor (se ligado); senão [valor]."""
    if not (MULTIVALOR and campo in CAMPOS_MULTIVALOR):
        return [valor]
    partes = [p.strip() for p in valor.split(";")]
    return [p for p in partes if p] or [valor]


def _aplicar_campo(tags, campo, valor):
    if campo == "comment":
        for chave in [k for k, f in tags.items() if k.startswith("COMM") and f.desc == ""]:
            del tags[chave]
        tags.delall("TXXX:comment")   # formato alternativo, ver _ler_campo_id3
        if valor:
            tags.add(COMM(encoding=3, lang="eng", desc="", text=[valor]))
        return

    if campo == "lyrics":
        # troca só a letra que o Tagger mostra (ver _ler_campo_id3); letras com outra descrição ficam
        frame = _frame_sem_descricao(tags, "USLT")
        if frame is not None:
            del tags[frame.HashKey]
        if valor:
            tags.add(USLT(encoding=3, lang="eng", desc="", text=valor))
        return

    classe = CAMPOS[campo][1]
    tags.delall(classe.__name__)
    if valor:
        tags.add(classe(encoding=3, text=dividir_valores(campo, valor)))


def _descricao_livre(tags):
    """Descrição para a nova capa que não sobrescreva outra imagem (a chave do APIC é a descrição)."""
    for descricao in ("", "Cover", *(f"Cover {n}" for n in range(2, 100))):
        if f"APIC:{descricao}" not in tags:
            return descricao
    return "Cover 100"


def _aplicar_capa(tags, capa):
    """capa: ("definir", dados, mime) ou ("remover",). Só a capa é trocada; outras imagens ficam."""
    for frame in _frames_capa(tags):
        del tags[frame.HashKey]
    if capa[0] == "definir":
        tags.add(APIC(encoding=3, mime=capa[2], type=TIPO_CAPA_FRONTAL,
                      desc=_descricao_livre(tags), data=capa[1]))


def _gravar(audio, remover_id3v1=False):
    audio.save(
        v1=0 if (REMOVER_ID3V1 or remover_id3v1) else 1,   # 0 = apaga o ID3v1; 1 = atualiza se já existir
        v2_version=VERSAO_ID3,
        # No v2.3 o padrão do mutagen junta vários valores com "/" ("AC/DC" vira ambíguo).
        # None usa o separador nulo, que é o que players modernos leem como multivalor.
        v23_sep=None if MULTIVALOR else "/",
    )


def salvar(arquivo, alteracoes, capa=None):
    """
    Grava várias tags (e, opcionalmente, a capa) em um arquivo, num único save.

    alteracoes: dict campo -> valor
      - "" remove a tag
      - VARIOS é ignorado (campo não foi tocado numa edição em lote)
    capa: None (não mexe), ("definir", dados, mime) ou ("remover",)
    Cria o cabeçalho de tags (ID3, Vorbis comment, ilst) só aqui, se o arquivo ainda não tiver um.
    """
    fmt = formato(arquivo)
    audio = _abrir(arquivo, fmt)
    if audio.tags is None:
        grava_algo = (any(valor and valor != VARIOS for campo, valor in alteracoes.items() if campo in CAMPOS)
                      or (capa is not None and capa[0] == "definir"))
        if grava_algo:
            audio.add_tags()
        elif capa is None or not _capas(audio, fmt):
            return            # só remoções num arquivo sem tags: não cria um cabeçalho vazio
        # (sobra o FLAC sem Vorbis comment mas com capa: as imagens dele ficam fora das tags)

    if audio.tags is not None:
        for campo, valor in alteracoes.items():
            if campo not in CAMPOS or valor == VARIOS:
                continue
            if fmt == "mp3":
                _aplicar_campo(audio.tags, campo, valor)
            else:
                _MODULOS[fmt].gravar(audio, campo, dividir_valores(campo, valor) if valor else [])
    if capa is not None:
        if fmt == "mp3":
            _aplicar_capa(audio.tags, capa)
        else:
            _MODULOS[fmt].aplicar_capa(audio, capa)

    if fmt == "mp3":
        _gravar(audio)
    else:
        audio.save()


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
    salvar(arquivo, {}, capa=("definir", dados, mime))


def remover_capa(arquivo):
    salvar(arquivo, {}, capa=("remover",))


# ---------------------------------------------------------------------------
# Limpeza (ID3v1, frames não reconhecidos e frames que o Tagger não mostra)
#
# Em FLAC/Ogg/M4A só existe a parte "extras" (chaves que o Tagger não mostra; capa e
# outras imagens nunca são apagadas). ID3v1 e frames desconhecidos são coisas do ID3:
# analisar_extras() devolve False/0 e limpar_extras() ignora essas opções.
# ---------------------------------------------------------------------------

def tem_id3v1(arquivo):
    """True se o MP3 termina numa tag ID3v1. Outros formatos: sempre False (não se corta o fim deles)."""
    if formato(arquivo) != "mp3":
        return False
    try:
        with open(arquivo, "rb") as f:
            f.seek(-128, 2)
            return f.read(3) == b"TAG"
    except OSError:
        return False


def _e_extra(frame):
    if frame.FrameID == "TXXX":
        return frame.desc != "comment"        # TXXX:comment é lido como Comentário
    return frame.FrameID not in FRAMES_DO_TAGGER


def analisar_extras(arquivo):
    """
    O que limpar_extras() removeria. Devolve
    {"id3v1": bool, "desconhecidos": int, "extras": {frame_id: quantidade}}.
    Em FLAC/Ogg/M4A as chaves de "extras" são as do formato (ex.: "REPLAYGAIN_TRACK_GAIN", "©too").
    """
    resultado = {"id3v1": tem_id3v1(arquivo), "desconhecidos": 0, "extras": {}}
    fmt = formato(arquivo)
    if fmt is None:
        return resultado
    try:
        audio = _abrir(arquivo, fmt)
    except (MutagenError, OSError):
        return resultado
    if fmt != "mp3":
        resultado["extras"] = _MODULOS[fmt].extras(audio)
        return resultado
    tags = audio.tags
    if tags is not None:
        resultado["desconhecidos"] = len(tags.unknown_frames)
        for frame in tags.values():
            if _e_extra(frame):
                resultado["extras"][frame.FrameID] = resultado["extras"].get(frame.FrameID, 0) + 1
    return resultado


def limpar_extras(arquivo, id3v1=False, desconhecidos=False, extras=False):
    """Remove o que foi pedido, num único save. Devolve False se não havia nada a fazer."""
    fmt = formato(arquivo)
    audio = _abrir(arquivo, fmt)
    if fmt != "mp3":
        if not (extras and _MODULOS[fmt].remover_extras(audio)):
            return False      # id3v1/desconhecidos não existem fora do MP3
        audio.save()
        return True

    tags = audio.tags
    mudou = False
    if tags is not None:
        if desconhecidos and tags.unknown_frames:
            tags.unknown_frames = []
            mudou = True
        if extras:
            for chave in [k for k, f in tags.items() if _e_extra(f)]:
                del tags[chave]
                mudou = True
    remover_v1 = id3v1 and tem_id3v1(arquivo)
    if not mudou and not remover_v1:
        return False
    if tags is None:
        apagar_id3(arquivo, delete_v1=True, delete_v2=False)   # só havia o ID3v1
    else:
        _gravar(audio, remover_id3v1=remover_v1)
    return True
