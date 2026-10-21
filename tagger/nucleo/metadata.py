"""
Backend de metadados do Tagger.

Toda a leitura e escrita de tags passa por aqui, sem nenhuma dependência de
interface. A CLI (tagger/cli.py) e a GUI (tagger/gui) usam as mesmas funções.

Princípios:
- Ler NUNCA grava nada no arquivo (só `salvar` e `limpar_extras` gravam).
- Uma gravação aplica várias tags (e a capa) de uma vez: um único save por arquivo.
- Valor vazio ("") significa "remover a tag".
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import re

from mutagen import MutagenError
from mutagen.id3 import delete as apagar_id3
from mutagen.id3 import (
    APIC, COMM, TALB, TCOM, TCON, TDRC, TEXT, TIT2, TPE1, TPE2, TPOS, TRCK, USLT,
)
from mutagen.mp3 import MP3

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

# Tipos de imagem (APIC) tratados como "a capa": 3 = capa frontal, 0 = "outra"
# (alguns programas gravam a capa assim). Contracapa, foto do artista etc. não são tocadas.
TIPO_CAPA_FRONTAL = 3
TIPO_OUTRA = 0

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


def _ler_campo(tags, campo):
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
    imagens = tags.getall("APIC")
    frontais = [img for img in imagens if img.type == TIPO_CAPA_FRONTAL]
    if frontais:
        return frontais
    outras = [img for img in imagens if img.type == TIPO_OUTRA]
    return outras[:1]


def carregar(arquivo):
    """Lê um arquivo e devolve uma Faixa, ou None se não for suportado/válido."""
    caminho = Path(arquivo)
    if formato(caminho) != "mp3":
        return None

    try:
        mtime = caminho.stat().st_mtime_ns
        audio = MP3(caminho)
    except (MutagenError, OSError):     # MutagenError cobre cabeçalho inválido, ID3 corrompido etc.
        return None

    tags = audio.tags
    return Faixa(
        caminho=caminho,
        tags={campo: _ler_campo(tags, campo) for campo in CAMPOS},
        tem_capa=bool(_frames_capa(tags)),
        duracao=audio.info.length,
        bitrate=audio.info.bitrate // 1000,
        mtime=mtime,
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
    """Devolve (bytes, mime) da capa (ver _frames_capa), ou None."""
    try:
        tags = MP3(arquivo).tags
    except (MutagenError, OSError):
        return None
    frames = _frames_capa(tags)
    if not frames:
        return None
    return frames[0].data, frames[0].mime


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
        tags.delall("TXXX:comment")   # formato alternativo, ver _ler_campo
        if valor:
            tags.add(COMM(encoding=3, lang="eng", desc="", text=[valor]))
        return

    if campo == "lyrics":
        # troca só a letra que o Tagger mostra (ver _ler_campo); letras com outra descrição ficam
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
    Cria o cabeçalho ID3 só aqui, se o arquivo ainda não tiver um.
    """
    audio = MP3(arquivo)
    if audio.tags is None:
        if not alteracoes and (capa is None or capa[0] == "remover"):
            return            # nada a gravar e nada a remover
        audio.add_tags()

    for campo, valor in alteracoes.items():
        if campo not in CAMPOS or valor == VARIOS:
            continue
        _aplicar_campo(audio.tags, campo, valor)
    if capa is not None:
        _aplicar_capa(audio.tags, capa)

    _gravar(audio)


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
# ---------------------------------------------------------------------------

def tem_id3v1(arquivo):
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
    """
    resultado = {"id3v1": tem_id3v1(arquivo), "desconhecidos": 0, "extras": {}}
    try:
        tags = MP3(arquivo).tags
    except (MutagenError, OSError):
        return resultado
    if tags is not None:
        resultado["desconhecidos"] = len(tags.unknown_frames)
        for frame in tags.values():
            if _e_extra(frame):
                resultado["extras"][frame.FrameID] = resultado["extras"].get(frame.FrameID, 0) + 1
    return resultado


def limpar_extras(arquivo, id3v1=False, desconhecidos=False, extras=False):
    """Remove o que foi pedido, num único save. Devolve False se não havia nada a fazer."""
    audio = MP3(arquivo)
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
