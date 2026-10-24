"""
Busca de tags no Last.fm: deixar as tags exatamente como são scrobbladas.

- `album_mais_scrobblado(artista)`: o álbum com mais scrobbles do artista;
- `versoes(artista, album)`: as versões do álbum ("Deluxe", "Remastered"...) pelo playcount;
- `nome_canonico(artista)`: o nome como o Last.fm corrige;
- `detalhar_album(artista, album)`: nomes canônicos e lista de faixas;
- `analisar` / `montar_alteracoes`: alterações para o Rascunho, como em busca.py.

Regras do Last.fm (obrigatórias):
- só uso não comercial; a GUI mostra "powered by AudioScrobbler" (`ATRIBUICAO`) e os links de
  `Album.url` / `Album.url_artista`;
- 1–2 req/s, com backoff no erro 29;
- cache respeitando os cabeçalhos HTTP, com teto de 100 MB;
- imagens do Last.fm nunca são baixadas nem expostas (capas só do Cover Art Archive).

A API exige a api_key na URL: ela nunca entra na chave do cache e é ocultada em toda mensagem de erro.
"""

import http.client
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from tagger.nucleo import busca, online
from tagger.nucleo.busca import ErroBusca, FaixaRelease, NAO_ENCONTRADO, USER_AGENT

URL_API = "https://ws.audioscrobbler.com/2.0/"
URL_SITE = "https://www.last.fm/music"
ATRIBUICAO = "powered by AudioScrobbler"
INTERVALO = 0.5           # segundos entre requisições: no máximo 2 req/s
TENTATIVAS = 4            # depois do erro 29 espera BACKOFF, 2×BACKOFF, 4×BACKOFF
BACKOFF = 2.0
TIMEOUT = busca.TIMEOUT
LIMITE_RESPOSTA = 5 * online.MB
TETO_CACHE = 100 * online.MB
SEM_CREDENCIAL = "Busca no Last.fm desativada: configure uma chave nas Configurações."
DOMINIOS = ("last.fm",)           # links do JSON só são aceitos nesses hosts (a GUI vai abri-los)
ERRO_LIMITE = 29          # "Rate limit exceeded"
ERROS_CHAVE = {10, 26}    # chave inválida / suspensa
ERRO_NAO_ENCONTRADO = 6

LIMITADOR = online.LimitadorJanela(1, INTERVALO, intervalo=INTERVALO)


@dataclass
class Album:
    titulo: str
    artista: str
    playcount: int = 0
    mbid: str = ""
    url: str = ""                 # página do álbum no Last.fm (link de atribuição)
    url_artista: str = ""
    faixas: list = field(default_factory=list)      # [FaixaRelease], só depois de detalhar_album
    etiquetas: list = field(default_factory=list)   # tags dos usuários (não aplicadas por padrão)

    @property
    def descricao(self):
        return f"{self.artista} — {self.titulo}" + (f"  ({self.playcount:,} scrobbles)".replace(",", ".")
                                                     if self.playcount else "")

    @property
    def atribuicao(self):
        """(texto, [(rótulo, link)]) para a GUI."""
        return ATRIBUICAO, [(self.artista, self.url_artista), (self.titulo, self.url)]

    def como_release(self):
        """Na forma que busca.analisar espera (sem data nem gênero: o Last.fm não informa a data)."""
        return busca.Release(mbid=self.mbid, titulo=self.titulo, artista=self.artista,
                             total_discos=1, faixas=list(self.faixas))


def url_artista(nome):
    return f"{URL_SITE}/{urllib.parse.quote_plus(nome)}" if nome else ""


def url_album(artista, titulo):
    return f"{URL_SITE}/{urllib.parse.quote_plus(artista)}/{urllib.parse.quote_plus(titulo)}" if artista and titulo else ""


def _lista(valor):
    """O JSON do Last.fm vira dict quando há um item só e "" quando não há nenhum."""
    if isinstance(valor, list):
        return valor
    return [valor] if isinstance(valor, dict) else []


def _inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


_EDICAO = re.compile(r"\s*(?:[(\[][^)\]]*[)\]]|-\s+[^-]*\b(?:edition|remaster(?:ed)?|deluxe|version|reissue|anniversary)\b.*)\s*$",
                     re.IGNORECASE)


def base_do_album(titulo):
    """'Abbey Road (Remastered)' / 'Album X [Deluxe]' / 'Album X - 2011 Remaster' -> 'abbey road'."""
    anterior = None
    while anterior != titulo:
        anterior, titulo = titulo, _EDICAO.sub("", titulo)
    return busca._normalizar(titulo)


class ClienteLastfm:
    def __init__(self, api_key, abrir=online.abrir_sem_vazar, limitador=None, cache=None, pasta_cache=None):
        """`api_key` vem de credenciais.lastfm_api_key(); None/vazio = busca desativada.
        `pasta_cache`: onde guardar o cache em disco (None = só memória). abrir/limitador/cache: testes."""
        self._api_key = (api_key or "").strip()
        self._abrir = abrir
        self._limitador = limitador or LIMITADOR
        self._cache = cache if cache is not None else online.Cache(TETO_CACHE, pasta=pasta_cache)

    @property
    def disponivel(self):
        return bool(self._api_key)

    def _ocultar(self, texto):
        return online.ocultar(texto, self._api_key)

    def _json(self, metodo, **params):
        if not self.disponivel:
            raise ErroBusca(SEM_CREDENCIAL)
        params = {"method": metodo, **{k: v for k, v in params.items() if v not in (None, "")}, "format": "json"}
        chave = f"{URL_API}?{urllib.parse.urlencode(params)}"          # sem a api_key
        corpo = self._cache.obter(chave)
        if corpo is not None:
            return self._decodificar(corpo)
        url = f"{chave}&{urllib.parse.urlencode({'api_key': self._api_key})}"
        for tentativa in range(TENTATIVAS):
            self._limitador.esperar()
            pedido = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            cabecalhos, detalhe_http = {}, ""
            try:
                with self._abrir(pedido, timeout=TIMEOUT) as resposta:
                    cabecalhos = dict(resposta.headers.items()) if getattr(resposta, "headers", None) else {}
                    corpo = resposta.read(LIMITE_RESPOSTA + 1)
                status = 200
            except online.RedirecionamentoRecusado as erro:
                raise online.erro_busca(online.REDIRECIONAMENTO_RECUSADO, self._ocultar(erro)) from None
            except urllib.error.HTTPError as erro:
                status = erro.code
                try:
                    corpo = erro.read(LIMITE_RESPOSTA + 1) or b""
                except Exception:
                    corpo = b""
                detalhe_http = self._ocultar(f"HTTP {erro.code} {erro.reason} em {erro.url}")
            except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as erro:
                raise online.erro_busca("Sem conexão com o Last.fm. Verifique a internet.", self._ocultar(erro)) from None
            if len(corpo) > LIMITE_RESPOSTA:
                raise ErroBusca("Resposta grande demais do Last.fm.")
            try:
                dados = self._decodificar(corpo)
            except ErroBusca:
                if status != 200:
                    if status == 429 and tentativa < TENTATIVAS - 1:
                        self._limitador.bloquear(BACKOFF * 2 ** tentativa)
                        continue
                    raise online.erro_busca(f"Erro do servidor do Last.fm ({status}).", detalhe_http) from None
                raise
            if not isinstance(dados, dict):
                raise ErroBusca("Resposta inválida do Last.fm.")
            codigo = _inteiro(dados.get("error"))
            if codigo == ERRO_LIMITE or (status == 429 and not codigo):
                if tentativa < TENTATIVAS - 1:
                    self._limitador.bloquear(BACKOFF * 2 ** tentativa)
                    continue
                raise online.erro_busca("O Last.fm está limitando as consultas. Tente de novo em instantes.",
                            self._ocultar(dados.get("message", "")))
            if codigo:
                raise self._erro_api(codigo, dados.get("message", ""))
            if status != 200:
                raise online.erro_busca(f"Erro do servidor do Last.fm ({status}).", detalhe_http)
            self._cache.guardar(chave, corpo, online.validade(cabecalhos))
            return dados
        raise ErroBusca("O Last.fm está limitando as consultas. Tente de novo em instantes.")   # pragma: no cover

    def _erro_api(self, codigo, mensagem):
        detalhe = self._ocultar(f"erro {codigo}: {mensagem}")
        if codigo == ERRO_NAO_ENCONTRADO:
            return online.erro_busca(NAO_ENCONTRADO, detalhe)
        if codigo in ERROS_CHAVE:
            return online.erro_busca("O Last.fm recusou a chave da API. Confira a chave nas Configurações.", detalhe)
        return online.erro_busca(f"Erro do Last.fm ({codigo}).", detalhe)

    @staticmethod
    def _decodificar(corpo):
        try:
            return json.loads(corpo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, AttributeError, RecursionError):
            raise ErroBusca("Resposta inválida do Last.fm.") from None

    # ------------------------------------------------------------ consultas
    @online.resposta_invalida("Last.fm")
    def nome_canonico(self, artista):
        """Nome do artista corrigido pelo Last.fm ('the beatles' -> 'The Beatles'); sem correção, o próprio."""
        if not artista.strip():
            raise ErroBusca("Informe o artista.")
        dados = self._json("artist.getCorrection", artist=artista.strip())
        correcoes = _lista((dados.get("corrections") or {}).get("correction") if isinstance(dados.get("corrections"), dict) else None)
        for c in correcoes:
            nome = ((c.get("artist") or {}).get("name") or "").strip()
            if nome:
                return nome
        return artista.strip()

    @online.resposta_invalida("Last.fm")
    def top_albuns(self, artista, limite=50):
        """Álbuns do artista, do mais scrobblado ao menos."""
        if not artista.strip():
            raise ErroBusca("Informe o artista.")
        dados = self._json("artist.getTopAlbums", artist=artista.strip(), autocorrect=1, limit=limite)
        albuns = []
        for a in _lista((dados.get("topalbums") or {}).get("album")):
            titulo = (a.get("name") or "").strip()
            if not titulo or titulo == "(null)":
                continue
            nome = ((a.get("artist") or {}).get("name") or artista).strip()
            albuns.append(Album(titulo=titulo, artista=nome, playcount=_inteiro(a.get("playcount")),
                                mbid=a.get("mbid") or "",
                                url=online.url_segura(a.get("url"), DOMINIOS, url_album(nome, titulo)),
                                url_artista=online.url_segura((a.get("artist") or {}).get("url"), DOMINIOS,
                                                              url_artista(nome))))
        albuns.sort(key=lambda a: -a.playcount)
        return albuns

    def album_mais_scrobblado(self, artista):
        albuns = self.top_albuns(artista, limite=5)
        if not albuns:
            raise ErroBusca(NAO_ENCONTRADO)
        return albuns[0]

    def versoes(self, artista, album, limite=200):
        """As versões de `album` entre os álbuns do artista ('X', 'X (Deluxe)'...), pelo playcount."""
        alvo = base_do_album(album)
        if not alvo:
            raise ErroBusca("Informe o álbum.")
        return [a for a in self.top_albuns(artista, limite=limite) if base_do_album(a.titulo) == alvo]

    @online.resposta_invalida("Last.fm")
    def detalhar_album(self, artista, album):
        """Nomes canônicos (autocorrect) e lista de faixas do álbum."""
        if not artista.strip() or not album.strip():
            raise ErroBusca("Informe o artista e o álbum.")
        a = self._json("album.getInfo", artist=artista.strip(), album=album.strip(), autocorrect=1).get("album")
        if not isinstance(a, dict):
            raise ErroBusca(NAO_ENCONTRADO)
        nome = (a.get("artist") or artista).strip() if isinstance(a.get("artist"), str) else artista.strip()
        lista = _lista((a.get("tracks") or {}).get("track") if isinstance(a.get("tracks"), dict) else None)
        faixas = []
        for j, f in enumerate(lista, start=1):
            autor = f.get("artist")
            autor = (autor.get("name") if isinstance(autor, dict) else autor) or nome
            faixas.append(FaixaRelease(titulo=(f.get("name") or "").strip(), artista=autor.strip(),
                                       numero=_inteiro((f.get("@attr") or {}).get("rank")) or j,
                                       disco=1, total_disco=len(lista)))
        etiquetas = [t.get("name", "") for t in _lista((a.get("tags") or {}).get("tag") if isinstance(a.get("tags"), dict) else None)]
        titulo = (a.get("name") or album).strip()
        return Album(titulo=titulo, artista=nome, playcount=_inteiro(a.get("playcount")),
                     mbid=a.get("mbid") or "", url=online.url_segura(a.get("url"), DOMINIOS, url_album(nome, titulo)),
                     url_artista=url_artista(nome),
                     faixas=faixas, etiquetas=[e for e in etiquetas if e])


def analisar(faixas, album, campos=None, valor=None):
    """(alteracoes, casadas, sem_par) como busca.analisar; `album` vem de detalhar_album."""
    return busca.analisar(faixas, album.como_release(), campos, valor)


def montar_alteracoes(faixas, album, campos=None, valor=None):
    return analisar(faixas, album, campos, valor)[0]
