"""
Busca automática de tags no MusicBrainz e de capa no Cover Art Archive.

Sem Qt e sem dependências novas (só urllib). Fluxo:
1. `ClienteMusicBrainz.buscar_releases` procura candidatos por artista/álbum;
2. o usuário escolhe um; `detalhar_release` traz as faixas do release;
3. `montar_alteracoes` casa as faixas do usuário com as do release e devolve
   as alterações no formato do Rascunho: [(faixa, {campo: valor})];
4. `baixar_capa` devolve (bytes, mime), igual ao que o editor usa para a capa.

Regras do MusicBrainz: User-Agent identificado e no máximo 1 requisição por segundo.
"""

import difflib
import http.client
import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from tagger import __version__

CONTATO = "contato-do-projeto"     # TODO(dono): e-mail ou URL do projeto; o MusicBrainz exige um contato real
USER_AGENT = f"Tagger/{__version__} ( {CONTATO} )"
URL_MB = "https://musicbrainz.org/ws/2"
URL_CAPA = "https://coverartarchive.org/release"
INTERVALO = 1.0           # segundos entre requisições ao MusicBrainz
TIMEOUT = 15              # segundos
LIMITE_CAPA = 15 * 1024 * 1024
MIMES_CAPA = {"image/jpeg", "image/png"}
NAO_ENCONTRADO = "Nada encontrado."


class ErroBusca(Exception):
    """Falha de rede ou resposta inesperada; a mensagem já é legível para o usuário."""


@dataclass
class Candidato:
    """Um release do MusicBrainz encontrado na busca."""
    mbid: str
    titulo: str
    artista: str
    data: str = ""
    pais: str = ""
    faixas: int = 0
    gravadora: str = ""
    pontos: int = 0

    @property
    def descricao(self):
        partes = [p for p in (self.data[:4], self.pais, f"{self.faixas} faixas" if self.faixas else "",
                              self.gravadora) if p]
        return f"{self.artista} — {self.titulo}" + (f"  ({', '.join(partes)})" if partes else "")


@dataclass
class FaixaRelease:
    titulo: str
    artista: str
    numero: int          # posição na mídia
    disco: int
    total_disco: int     # faixas na mídia


@dataclass
class Release:
    mbid: str
    titulo: str
    artista: str
    data: str = ""
    generos: list = field(default_factory=list)
    gravadora: str = ""
    total_discos: int = 1
    faixas: list = field(default_factory=list)


@dataclass
class Resultado:
    """O que o diálogo devolve."""
    alteracoes: list           # [(faixa, {campo: valor})] — vai para Rascunho.definir_por_faixa
    capa: tuple = None         # (bytes, mime) ou None
    casadas: list = field(default_factory=list)    # faixas que tiveram par no release
    sem_par: list = field(default_factory=list)    # faixas sem par: não recebem nada (nem capa)

    @property
    def caminhos_capa(self):
        """Caminhos que devem receber a capa: só as faixas casadas."""
        return [f.caminho for f in self.casadas]

    @property
    def alteradas(self):
        return len(self.alteracoes)

    @property
    def acao_capa(self):
        """Pronto para Rascunho.definir_capa(resultado.caminhos_capa, resultado.acao_capa)."""
        return ("definir", self.capa[0], self.capa[1]) if self.capa else None


def _credito(credito):
    """Junta o 'artist-credit' do MusicBrainz: 'A feat. B'."""
    return "".join((c.get("name") or c.get("artist", {}).get("name", "")) + c.get("joinphrase", "")
                   for c in credito or []).strip()


def _capitalizar(nome):
    """'indie rock' -> 'Indie Rock', 'r&b' -> 'R&B'. Só a 1ª letra de cada palavra (str.title estraga "rock'n'roll")."""
    return " ".join(p.upper() if "&" in p else p[:1].upper() + p[1:] for p in nome.strip().split())


def _lucene(texto):
    """Escapa aspas e barras para usar o texto dentro de "..." na busca."""
    return texto.replace("\\", "\\\\").replace('"', '\\"')


class Limitador:
    """No máximo 1 requisição por INTERVALO, mesmo com várias threads/instâncias (o limite é por IP)."""
    def __init__(self, dormir=time.sleep, relogio=time.monotonic):
        self._dormir, self._relogio = dormir, relogio
        self._ultima = None
        self._trava = threading.Lock()

    def esperar(self):
        with self._trava:                      # quem chega depois espera na fila
            if self._ultima is not None:
                falta = INTERVALO - (self._relogio() - self._ultima)
                if falta > 0:
                    self._dormir(falta)
            self._ultima = self._relogio()


LIMITADOR = Limitador()       # compartilhado por todos os clientes do processo


class ClienteMusicBrainz:
    def __init__(self, abrir=urllib.request.urlopen, limitador=None):
        # abrir/limitador podem ser trocados nos testes (sem rede e sem esperar de verdade)
        self._abrir = abrir
        self._limitador = limitador or LIMITADOR

    def _requisitar(self, url, servico="MusicBrainz", limitar=True):
        """(corpo, tipo MIME). limitar=True respeita 1 req/s (só o MusicBrainz exige)."""
        if limitar:
            self._limitador.esperar()
        pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with self._abrir(pedido, timeout=TIMEOUT) as resposta:
                tipo = resposta.headers.get("Content-Type", "") if getattr(resposta, "headers", None) else ""
                return resposta.read(LIMITE_CAPA + 1), tipo.split(";")[0].strip().lower()
        except urllib.error.HTTPError as erro:
            if erro.code in (429, 503):
                raise ErroBusca(f"O {servico} está limitando as consultas. Tente de novo em instantes.") from erro
            if erro.code == 404:
                raise ErroBusca(NAO_ENCONTRADO) from erro
            raise ErroBusca(f"Erro do servidor ({erro.code}).") from erro
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as erro:
            raise ErroBusca("Sem conexão com o servidor. Verifique a internet.") from erro

    def _json(self, caminho, **params):
        params["fmt"] = "json"
        corpo, _ = self._requisitar(f"{URL_MB}/{caminho}?{urllib.parse.urlencode(params)}")
        try:
            return json.loads(corpo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as erro:
            raise ErroBusca("Resposta inválida do MusicBrainz.") from erro

    # ------------------------------------------------------------ consultas
    def buscar_releases(self, artista="", album="", titulo="", limite=10):
        """Candidatos para artista/álbum (o título da faixa só entra se não houver álbum)."""
        partes = []
        if artista.strip():
            partes.append(f'artist:"{_lucene(artista.strip())}"')
        if album.strip():
            partes.append(f'release:"{_lucene(album.strip())}"')
        elif titulo.strip():
            partes.append(f'recording:"{_lucene(titulo.strip())}"')
        if not partes:
            raise ErroBusca("Informe ao menos o artista ou o álbum.")
        dados = self._json("release", query=" AND ".join(partes), limit=limite)
        candidatos = []
        for r in dados.get("releases", []):
            if not r.get("id"):
                continue
            rotulos = r.get("label-info") or []
            candidatos.append(Candidato(
                mbid=r["id"], titulo=r.get("title", ""), artista=_credito(r.get("artist-credit")),
                data=r.get("date", ""), pais=r.get("country", ""), faixas=r.get("track-count", 0) or 0,
                gravadora=((rotulos[0].get("label") or {}).get("name", "") if rotulos else ""),
                pontos=int(r.get("score", 0) or 0)))
        return candidatos

    def detalhar_release(self, mbid):
        r = self._json(f"release/{urllib.parse.quote(mbid)}", inc="recordings+artist-credits+labels+genres+release-groups")
        midias = r.get("media") or []
        faixas = []
        for i, midia in enumerate(midias, start=1):
            disco = midia.get("position") or i
            lista = midia.get("tracks") or []
            for j, f in enumerate(lista, start=1):
                gravacao = f.get("recording") or {}
                faixas.append(FaixaRelease(
                    titulo=f.get("title") or gravacao.get("title", ""),
                    artista=_credito(f.get("artist-credit")) or _credito(gravacao.get("artist-credit")),
                    numero=f.get("position") or j, disco=disco, total_disco=len(lista)))
        rotulos = r.get("label-info") or []
        # gêneros do release e do release-group (o MusicBrainz costuma votar neste último)
        grupo = r.get("release-group") or {}
        generos = (r.get("genres") or []) + (grupo.get("genres") or [])
        if not generos and grupo.get("id"):
            # a resposta do release nem sempre traz os gêneros do grupo: pergunta direto (já com o limite de 1 req/s)
            try:
                generos = self._json(f"release-group/{urllib.parse.quote(grupo['id'])}", inc="genres").get("genres") or []
            except ErroBusca:
                generos = []             # gênero é opcional: não derruba o resto
        generos = sorted(generos, key=lambda g: -g.get("count", 0))
        nomes = []
        for g in generos:
            nome = _capitalizar(g.get("name", ""))
            if nome and nome not in nomes:
                nomes.append(nome)
        return Release(
            mbid=r.get("id", mbid), titulo=r.get("title", ""), artista=_credito(r.get("artist-credit")),
            data=r.get("date", ""), generos=nomes[:3],
            gravadora=(rotulos[0].get("label") or {}).get("name", "") if rotulos else "",
            total_discos=len(midias) or 1, faixas=faixas)

    def baixar_capa(self, mbid):
        """(bytes, mime) da capa frontal, ou None se o release não tiver capa."""
        try:
            dados, tipo = self._requisitar(f"{URL_CAPA}/{urllib.parse.quote(mbid)}/front-500", servico="Cover Art Archive", limitar=False)
        except ErroBusca as erro:
            if str(erro) == NAO_ENCONTRADO:
                return None
            raise
        if not dados or len(dados) > LIMITE_CAPA:
            return None
        if tipo not in MIMES_CAPA:      # o servidor pode não informar o tipo: olha os primeiros bytes
            tipo = ("image/png" if dados[:8] == b"\x89PNG\r\n\x1a\n"
                    else "image/jpeg" if dados[:2] == b"\xff\xd8" else "")
        return (dados, tipo) if tipo in MIMES_CAPA else None


# ---------------------------------------------------------------------------
# Casamento das faixas do usuário com as do release
# ---------------------------------------------------------------------------

def _normalizar(texto):
    return re.sub(r"[\W_]+", " ", texto.casefold()).strip()


def _numero(valor):
    """'3/12' -> 3; vazio ou inválido -> 0."""
    m = re.match(r"\s*(\d+)", valor or "")
    return int(m.group(1)) if m else 0


def _parecidos(a, b):
    return difflib.SequenceMatcher(None, _normalizar(a), _normalizar(b)).ratio() >= 0.6


def _valor_padrao(faixa, campo):
    return faixa.tags.get(campo, "")


def _casar(faixas, release, valor):
    """[(faixa, FaixaRelease | None, casou_por_titulo)]. Cada faixa do release é usada no máximo uma vez."""
    usadas = set()
    achadas = [None] * len(faixas)
    chaves = [(_numero(valor(f, "discnumber")) or 1, _numero(valor(f, "tracknumber")),
               _normalizar(valor(f, "title"))) for f in faixas]

    def livres(titulo):
        return [i for i, rf in enumerate(release.faixas) if i not in usadas and _normalizar(rf.titulo) == titulo]

    # 1) mesmo título e mesmo (disco, nº): resolve "Intro" repetida em vários discos
    # 2) mesmo título, sem conferir a posição (prefere o mesmo disco)
    for etapa in (1, 2):
        for k, (disco, numero, titulo) in enumerate(chaves):
            if achadas[k] is not None or not titulo:
                continue
            candidatas = livres(titulo)
            if etapa == 1:
                candidatas = [i for i in candidatas
                              if (release.faixas[i].disco, release.faixas[i].numero) == (disco, numero)]
            else:
                candidatas.sort(key=lambda i: release.faixas[i].disco != disco)
            if candidatas:
                achadas[k] = (candidatas[0], True)
                usadas.add(candidatas[0])
    # 3) o que sobrou, pelo número da faixa (+ disco)
    for k, (disco, numero, _titulo) in enumerate(chaves):
        if achadas[k] is None and numero:
            for i, rf in enumerate(release.faixas):
                if i not in usadas and (rf.disco, rf.numero) == (disco, numero):
                    achadas[k] = (i, False)
                    usadas.add(i)
                    break
    return [(f, release.faixas[a[0]] if a else None, bool(a and a[1])) for f, a in zip(faixas, achadas)]


def casar_faixas(faixas, release, valor=None):
    """[(faixa, FaixaRelease | None)] na ordem de `faixas`, 1:1: por título, senão por número (+ disco)."""
    return [(f, par) for f, par, _ in _casar(faixas, release, valor or _valor_padrao)]


def _data(texto):
    """AAAA, AAAA-MM ou AAAA-MM-DD; qualquer outra coisa cai para o ano, se houver."""
    if re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", texto):
        return texto
    return texto[:4] if texto[:4].isdigit() else ""


def analisar(faixas, release, campos=None, valor=None, casar=None):
    """
    (alteracoes, casadas, sem_par). Só as faixas que casaram com o release recebem alguma coisa
    (inclusive os campos do álbum): assim, selecionar dois álbuns não estraga o outro.
    alteracoes = [(faixa, {campo: valor})] para o Rascunho; só traz o que difere do que a faixa mostra.
    `campos`: conjunto de campos a preencher (padrão: todos).
    `valor(faixa, campo)`: o que o usuário está vendo (ex.: Rascunho.valor); padrão: tags do arquivo.
    Faixa casada só pelo número, com título muito diferente, não tem o título trocado.
    `casar(faixas, release, valor)`: troca o casamento (o Discogs confia mais na ordem); padrão: `_casar`.
    """
    valor = valor or _valor_padrao
    do_album = {"album": release.titulo, "albumartist": release.artista, "date": _data(release.data),
                "genre": "; ".join(release.generos)}
    itens, casadas, sem_par = [], [], []
    for faixa, par, por_titulo in (casar or _casar)(faixas, release, valor):
        if par is None:
            sem_par.append(faixa)
            continue
        casadas.append(faixa)
        novos = dict(do_album)
        if por_titulo or not valor(faixa, "title") or _parecidos(valor(faixa, "title"), par.titulo):
            novos["title"] = par.titulo
        novos["artist"] = par.artista
        novos["tracknumber"] = f"{par.numero}/{par.total_disco}"
        if release.total_discos > 1:
            novos["discnumber"] = f"{par.disco}/{release.total_discos}"
        mudancas = {campo: v for campo, v in novos.items()
                    if v and (campos is None or campo in campos) and v != valor(faixa, campo)}
        if mudancas:
            itens.append((faixa, mudancas))
    return itens, casadas, sem_par


def montar_alteracoes(faixas, release, campos=None, valor=None):
    """Só a lista de alterações de `analisar`."""
    return analisar(faixas, release, campos, valor)[0]
