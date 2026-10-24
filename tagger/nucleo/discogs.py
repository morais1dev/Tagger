"""
Busca de tags no Discogs: o mesmo papel do MusicBrainz (ano, faixa/disco, artista do álbum,
gravadora), útil para prensagens privadas e edições raras que só existem lá.

Fluxo igual ao de busca.py:
1. `ClienteDiscogs.buscar_releases` procura candidatos por artista/álbum;
2. o usuário escolhe um; `detalhar_release` traz a lista de faixas;
3. `analisar` / `montar_alteracoes` devolvem as alterações para o Rascunho: [(faixa, {campo: valor})].

Em vinil a posição vem como "A1", "B2" e a duração costuma estar vazia: `interpretar_posicao`
converte a posição em (disco, faixa) e o casamento confia mais na ordem e no nome.

Regras do Discogs (obrigatórias):
- credencial SEMPRE no cabeçalho Authorization (nunca na URL), vinda de fora como parâmetro;
- User-Agent identificando o app;
- no máximo 60 req/min: lê os cabeçalhos X-Discogs-Ratelimit-* e espera no 429;
- nada de cache persistente: só memória, e nunca mais de 6 h;
- capas e imagens do Discogs nunca são baixadas (capas só do Cover Art Archive);
- a GUI mostra "Data provided by Discogs." com link para `Release.url`.
"""

import difflib
import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from tagger.nucleo import busca, metadata, online
from tagger.nucleo.busca import ErroBusca, FaixaRelease, NAO_ENCONTRADO, USER_AGENT

URL_API = "https://api.discogs.com"
URL_SITE = "https://www.discogs.com"
ATRIBUICAO = "Data provided by Discogs."
AVISO_SOBRE = ("This application uses Discogs' API but is not affiliated with, sponsored or endorsed by "
               "Discogs. 'Discogs' is a trademark of Zink Media, LLC.")
MAXIMO_POR_MINUTO = 60
JANELA = 60.0             # segundos (o Discogs usa uma janela deslizante de 60 s)
TENTATIVAS = 3            # 1 + 2 novas tentativas depois de um 429
ESPERA_MAXIMA = 60.0      # nunca espera mais que isso por um Retry-After
TIMEOUT = busca.TIMEOUT
LIMITE_RESPOSTA = 5 * online.MB
CACHE_SEGUNDOS = 60 * 60          # bem abaixo do teto de 6 h das regras
TETO_CACHE = 6 * 60 * 60
SEM_CREDENCIAL = "Busca no Discogs desativada: configure uma chave nas Configurações."
DOMINIOS = ("discogs.com",)       # links do JSON só são aceitos nesses hosts (a GUI vai abri-los)
CAMPO_GRAVADORA = "gravadora"     # só é preenchido quando existir em metadata.CAMPOS

LIMITADOR = online.LimitadorJanela(MAXIMO_POR_MINUTO, JANELA, intervalo=JANELA / MAXIMO_POR_MINUTO)
CACHE = online.Cache(8 * online.MB, teto_segundos=TETO_CACHE)       # só memória, compartilhado


@dataclass
class Candidato:
    """Um release do Discogs encontrado na busca."""
    id: int
    titulo: str
    artista: str
    ano: str = ""
    pais: str = ""
    formato: str = ""
    gravadora: str = ""
    catalogo: str = ""
    url: str = ""             # página do release (para o link de atribuição)

    @property
    def descricao(self):
        partes = [p for p in (self.ano, self.pais, self.formato, self.gravadora, self.catalogo) if p]
        return f"{self.artista} — {self.titulo}" + (f"  ({', '.join(partes)})" if partes else "")


@dataclass
class FaixaDiscogs(FaixaRelease):
    posicao: str = ""         # como o Discogs mostra: "A1", "2-05"...
    duracao: int = 0          # segundos; 0 = desconhecida (comum em vinil)


@dataclass
class Release:
    """Mesmos campos que busca.Release usa em `analisar` (titulo, artista, data, generos, total_discos, faixas)."""
    id: int
    titulo: str
    artista: str
    data: str = ""
    gravadora: str = ""
    catalogo: str = ""
    estilos: list = field(default_factory=list)   # gêneros/estilos do Discogs (não aplicados por padrão)
    total_discos: int = 1
    faixas: list = field(default_factory=list)
    url: str = ""
    generos: list = field(default_factory=list)   # vazio: o Discogs não preenche o campo Gênero

    @property
    def atribuicao(self):
        """(texto, link) para a GUI mostrar ao lado dos dados."""
        return ATRIBUICAO, self.url


# ---------------------------------------------------------------------------
# Posição da faixa
# ---------------------------------------------------------------------------

_LADO = re.compile(r"([A-Za-z])\s*(\d*)(?:[.\-]?[a-z])?")         # A, A1, A01, A1a, A1.b
_DISCO_FAIXA = re.compile(r"(?:CD|DVD|LP|Disc|Disco)?\s*(\d+)\s*[-./]\s*(\d+)[a-z]?", re.IGNORECASE)
_NUMERO = re.compile(r"(\d+)[a-z]?")


def interpretar_posicao(texto):
    """
    ("lado", letra, nº no lado) para vinil/fita: "A1" -> ("lado", "A", 1), "B" -> ("lado", "B", 0);
    ("disco", disco, faixa) para "2-05", "CD2.5", "1/3";
    ("faixa", None, n) para "7"; None se não der para entender (vazio, "Video" etc.).
    I, V e X sem número são tratados como algarismos romanos (None): ver `numerar`.
    """
    texto = (texto or "").strip()
    if not texto:
        return None
    m = _DISCO_FAIXA.fullmatch(texto)
    if m:
        return ("disco", int(m.group(1)), int(m.group(2)))
    m = _NUMERO.fullmatch(texto)
    if m:
        return ("faixa", None, int(m.group(1)))
    m = _LADO.fullmatch(texto)
    if m and (m.group(2) or m.group(1).upper() not in "IVX"):
        return ("lado", m.group(1).upper(), int(m.group(2) or 0))
    return None


def numerar(posicoes):
    """
    [(disco, faixa)] para as posições na ordem do release.
    Vinil: cada disco tem dois lados (A/B = disco 1, C/D = disco 2...) e a faixa conta em ordem
    dentro do disco: A1, A2, B1 -> 1, 2, 3. Posição incompreensível: segue a ordem do disco atual.
    Sub-faixas numéricas ("4a", "4b") e números repetidos no disco também seguem a contagem.
    Letras sem número só são lados se o release inteiro for de lados ("A", "B"...): assim
    "I", "II", "III" não viram o lado I (disco 5).
    """
    posicoes = [(p or "").strip() for p in posicoes]
    preenchidas = [p for p in posicoes if p]
    so_lados = bool(preenchidas) and all(re.fullmatch(r"[A-Za-z]", p) for p in preenchidas)
    contagem, usados, saida, disco = {}, set(), [], 1
    for pos in posicoes:
        tipo = interpretar_posicao(pos)
        if tipo is None and so_lados and pos:
            tipo = ("lado", pos.upper(), 0)
        if tipo and tipo[0] in ("disco", "faixa"):
            if tipo[0] == "disco":
                disco = tipo[1] or 1
            numero = tipo[2]
            if (disco, numero) in usados or not numero:
                numero = contagem.get(disco, 0) + 1
        else:
            if tipo:                                      # lado
                disco = (ord(tipo[1]) - ord("A")) // 2 + 1
            numero = contagem.get(disco, 0) + 1
        contagem[disco] = max(contagem.get(disco, 0), numero)
        usados.add((disco, numero))
        saida.append((disco, numero))
    return saida


def _duracao(texto):
    """'3:45' -> 225, '1:02:03' -> 3723; vazio/ruim -> 0."""
    partes = (texto or "").strip().split(":")
    if not all(p.isdigit() for p in partes):
        return 0
    total = 0
    for p in partes:
        total = total * 60 + int(p)
    return total


# ---------------------------------------------------------------------------
# Nomes
# ---------------------------------------------------------------------------

_SUFIXO_DESAMBIGUACAO = re.compile(r"\s*\(\d+\)$")      # "Nirvana (2)" -> "Nirvana"


def _nome(artista):
    nome = (artista.get("anv") or artista.get("name") or "").strip()
    return _SUFIXO_DESAMBIGUACAO.sub("", nome).rstrip("*").strip()


def _credito(artistas):
    """Junta a lista 'artists' do Discogs: 'A, B & C', 'A Feat. B'."""
    texto = ""
    lista = artistas or []
    for i, a in enumerate(lista):
        texto += _nome(a)
        juncao = (a.get("join") or "").strip()
        if i < len(lista) - 1:
            texto += ", " if juncao in ("", ",") else f" {juncao} "
    return texto.strip()


def _data(released, ano):
    """'1999-05-03' / '1999-00-00' / '1999' -> AAAA[-MM[-DD]] sem os zeros do Discogs."""
    partes = [p for p in (released or "").split("-") if p and p.strip("0")]
    if partes and len(partes[0]) == 4 and partes[0].isdigit():
        return "-".join(partes[:3])
    return str(ano) if ano and str(ano).strip("0") else ""


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------

class ClienteDiscogs:
    def __init__(self, authorization, abrir=online.abrir_sem_vazar, limitador=None, cache=None):
        """`authorization`: cabeçalho pronto ("Discogs token=..." ou "Discogs key=..., secret=...")
        vindo de credenciais.discogs_authorization(); None/vazio = busca desativada.
        abrir/limitador/cache podem ser trocados nos testes."""
        self._authorization = (authorization or "").strip()
        self._abrir = abrir
        self._limitador = limitador or LIMITADOR
        self._cache = CACHE if cache is None else cache

    @property
    def disponivel(self):
        return bool(self._authorization)

    def _ocultar(self, texto):
        segredos = re.findall(r"=([^,\s]+)", self._authorization)
        return online.ocultar(texto, self._authorization, *segredos)

    def _ler_limite(self, cabecalhos):
        """Ajusta o limitador ao que o Discogs informa (sem autenticação o limite é menor)."""
        if not cabecalhos:
            return
        total = online._inteiro(cabecalhos.get("X-Discogs-Ratelimit")) if cabecalhos.get("X-Discogs-Ratelimit") else 0
        if total:
            self._limitador.maximo = min(MAXIMO_POR_MINUTO, total)
        restantes = cabecalhos.get("X-Discogs-Ratelimit-Remaining")
        if restantes is not None and online._inteiro(restantes) <= 0:
            self._limitador.bloquear(JANELA)

    def _requisitar(self, caminho, **params):
        if not self.disponivel:
            raise ErroBusca(SEM_CREDENCIAL)
        url = f"{URL_API}/{caminho}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
        guardado = self._cache.obter(url)          # a URL não tem credencial: pode ser chave
        if guardado is not None:
            return guardado
        for tentativa in range(TENTATIVAS):
            self._limitador.esperar()
            pedido = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT, "Accept": "application/vnd.discogs.v2.discogs+json"})
            pedido.add_unredirected_header("Authorization", self._authorization)   # nunca segue um redirect
            try:
                with self._abrir(pedido, timeout=TIMEOUT) as resposta:
                    self._ler_limite(getattr(resposta, "headers", None))
                    corpo = resposta.read(LIMITE_RESPOSTA + 1)
            except urllib.error.HTTPError as erro:
                self._ler_limite(erro.headers)
                if erro.code == 429 and tentativa < TENTATIVAS - 1:
                    espera = online._inteiro((erro.headers or {}).get("Retry-After"))
                    if espera or tentativa == 0:             # sem Retry-After: só uma nova tentativa
                        self._limitador.bloquear(min(espera or JANELA, ESPERA_MAXIMA))
                        continue
                raise self._erro_http(erro) from None
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as erro:
                raise online.erro_busca("Sem conexão com o Discogs. Verifique a internet.", self._ocultar(erro)) from None
            if len(corpo) > LIMITE_RESPOSTA:
                raise ErroBusca("Resposta grande demais do Discogs.")
            self._cache.guardar(url, corpo, CACHE_SEGUNDOS)
            return corpo
        raise ErroBusca("O Discogs está limitando as consultas. Tente de novo em instantes.")   # pragma: no cover

    def _erro_http(self, erro):
        detalhe = self._ocultar(f"HTTP {erro.code} {erro.reason} em {erro.url}")
        if erro.code == 429:
            return online.erro_busca("O Discogs está limitando as consultas. Tente de novo em instantes.", detalhe)
        if erro.code == 401:
            return online.erro_busca("O Discogs recusou a credencial. Confira o token nas Configurações.", detalhe)
        if erro.code == 404:
            return online.erro_busca(NAO_ENCONTRADO, detalhe)
        return online.erro_busca(f"Erro do servidor do Discogs ({erro.code}).", detalhe)

    def _json(self, caminho, **params):
        corpo = self._requisitar(caminho, **params)
        try:
            return json.loads(corpo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise ErroBusca("Resposta inválida do Discogs.") from None

    # ------------------------------------------------------------ consultas
    @online.resposta_invalida("Discogs")
    def buscar_releases(self, artista="", album="", titulo="", limite=10):
        """Candidatos para artista/álbum (o título da faixa só entra se não houver álbum)."""
        params = {"type": "release", "per_page": limite}
        if artista.strip():
            params["artist"] = artista.strip()
        if album.strip():
            params["release_title"] = album.strip()
        elif titulo.strip():
            params["track"] = titulo.strip()
        if len(params) == 2:
            raise ErroBusca("Informe ao menos o artista ou o álbum.")
        dados = self._json("database/search", **params)
        candidatos = []
        for r in dados.get("results") or []:
            if not r.get("id"):
                continue
            artista_r, _, titulo_r = (r.get("title") or "").partition(" - ")
            if not titulo_r:                    # sem " - ": o título inteiro é o do álbum
                artista_r, titulo_r = "", artista_r
            id_r = int(r["id"])
            candidatos.append(Candidato(
                id=id_r, titulo=titulo_r.strip(), artista=_SUFIXO_DESAMBIGUACAO.sub("", artista_r.strip()),
                ano=str(r.get("year") or ""), pais=r.get("country") or "",
                formato=", ".join(dict.fromkeys(r.get("format") or [])),
                gravadora=(r.get("label") or [""])[0], catalogo=r.get("catno") or "",
                url=_link(r.get("uri"), id_r)))
        return candidatos

    @online.resposta_invalida("Discogs")
    def detalhar_release(self, id_release):
        r = self._json(f"releases/{int(id_release)}")
        entradas = []
        for item in r.get("tracklist") or []:
            tipo = item.get("type_") or "track"
            if tipo == "heading":
                continue
            if tipo == "index" and item.get("sub_tracks"):
                entradas.extend(s for s in item["sub_tracks"] if (s.get("type_") or "track") == "track")
            else:
                entradas.append(item)
        artista = _credito(r.get("artists"))
        numeros = numerar([e.get("position", "") for e in entradas])
        totais = {}
        for disco, numero in numeros:
            totais[disco] = max(totais.get(disco, 0), numero)
        faixas = [FaixaDiscogs(
            titulo=(e.get("title") or "").strip(), artista=_credito(e.get("artists")) or artista,
            numero=numero, disco=disco, total_disco=totais[disco],
            posicao=(e.get("position") or "").strip(), duracao=_duracao(e.get("duration")))
            for e, (disco, numero) in zip(entradas, numeros)]
        rotulos = r.get("labels") or []
        id_r = int(r.get("id") or id_release)
        return Release(
            id=id_r, titulo=(r.get("title") or "").strip(), artista=artista,
            data=_data(r.get("released"), r.get("year")),
            gravadora=_SUFIXO_DESAMBIGUACAO.sub("", rotulos[0].get("name", "")) if rotulos else "",
            catalogo=rotulos[0].get("catno", "") if rotulos else "",
            estilos=list(dict.fromkeys((r.get("styles") or []) + (r.get("genres") or []))),
            total_discos=max(totais) if totais else 1, faixas=faixas,
            url=_link(r.get("uri"), id_r))


def _link(uri, id_release):
    """Página do release: a do JSON se for https num host do Discogs; senão a montada pelo id."""
    if isinstance(uri, str) and uri.startswith("/") and not uri.startswith("//"):
        uri = URL_SITE + uri
    return online.url_segura(uri, DOMINIOS, f"{URL_SITE}/release/{int(id_release)}")


# ---------------------------------------------------------------------------
# Casamento: nome, depois posição, depois ordem
# ---------------------------------------------------------------------------

def _casar(faixas, release, valor):
    """[(faixa, FaixaDiscogs | None, casou_por_titulo)], 1:1 como em busca._casar, mas:
    1) mesmo título; 2) título parecido (o mais parecido primeiro);
    3) (disco, nº) ou, sem disco na faixa, a posição na ordem geral do release (vinil com 1..N);
    4) se sobrar a mesma quantidade dos dois lados, pela ordem."""
    rf = release.faixas
    usadas, achadas = set(), [None] * len(faixas)
    norm = [busca._normalizar(f.titulo) for f in rf]
    chaves = [(busca._numero(valor(f, "discnumber")), busca._numero(valor(f, "tracknumber")),
               busca._normalizar(valor(f, "title"))) for f in faixas]

    def marcar(k, i, por_titulo):
        achadas[k] = (i, por_titulo)
        usadas.add(i)

    for k, (disco, _n, titulo) in enumerate(chaves):                   # 1
        livres = [i for i in range(len(rf)) if i not in usadas and titulo and norm[i] == titulo]
        livres.sort(key=lambda i: rf[i].disco != (disco or 1))
        if livres:
            marcar(k, livres[0], True)
    for k, (_d, _n, titulo) in enumerate(chaves):                      # 2
        if achadas[k] is None and titulo:
            notas = [(difflib.SequenceMatcher(None, titulo, norm[i]).ratio(), -i, i)
                     for i in range(len(rf)) if i not in usadas]
            notas = [n for n in notas if n[0] >= 0.6]
            if notas:
                marcar(k, max(notas)[2], True)
    for k, (disco, numero, _t) in enumerate(chaves):                   # 3
        if achadas[k] is None and numero:
            i = next((i for i in range(len(rf)) if i not in usadas and (rf[i].disco, rf[i].numero) == (disco or 1, numero)), None)
            if i is None and not disco and numero <= len(rf) and numero - 1 not in usadas:
                i = numero - 1
            if i is not None:
                marcar(k, i, False)
    sobra = [k for k in range(len(faixas)) if achadas[k] is None]       # 4
    livres = [i for i in range(len(rf)) if i not in usadas]
    if sobra and len(sobra) == len(livres):
        sobra.sort(key=lambda k: (chaves[k][0] or 1, chaves[k][1] or 0, k))
        for k, i in zip(sobra, livres):
            marcar(k, i, False)
    return [(f, rf[a[0]] if a else None, bool(a and a[1])) for f, a in zip(faixas, achadas)]


def casar_faixas(faixas, release, valor=None):
    return [(f, par) for f, par, _ in _casar(faixas, release, valor or busca._valor_padrao)]


def analisar(faixas, release, campos=None, valor=None):
    """(alteracoes, casadas, sem_par), no mesmo formato de busca.analisar (vai para Rascunho.definir_por_faixa).
    Além dos campos do MusicBrainz, a gravadora, quando o campo existir em metadata.CAMPOS."""
    valor = valor or busca._valor_padrao
    itens, casadas, sem_par = busca.analisar(faixas, release, campos, valor, casar=_casar)
    campo = CAMPO_GRAVADORA
    if release.gravadora and campo in metadata.CAMPOS and (campos is None or campo in campos):
        por_faixa = {id(f): m for f, m in itens}
        itens = []
        for f in casadas:
            mudancas = dict(por_faixa.get(id(f), {}))
            if valor(f, campo) != release.gravadora:
                mudancas[campo] = release.gravadora
            if mudancas:
                itens.append((f, mudancas))
    return itens, casadas, sem_par


def montar_alteracoes(faixas, release, campos=None, valor=None):
    return analisar(faixas, release, campos, valor)[0]
