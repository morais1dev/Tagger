"""
Peças comuns aos clientes do Discogs e do Last.fm (sem Qt, só urllib).

- `ocultar`: o ÚNICO ponto que limpa credenciais de mensagens de erro de rede (via credenciais.py);
- `LimitadorJanela`: no máximo N requisições numa janela de tempo deslizante;
- `Cache`: respostas guardadas pelo tempo que os cabeçalhos HTTP permitem, com teto de tamanho;
- `abrir_sem_vazar`: urlopen que não repassa o cabeçalho Authorization num redirecionamento
  para outro host.

Nenhum desses serviços fornece capas para o Tagger: as capas vêm só do Cover Art Archive
(ver busca.py). Por isso nada aqui baixa imagens, e os clientes nem expõem as URLs delas.
"""

import email.utils
import functools
import hashlib
import json
import logging
import os
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict, deque
from pathlib import Path

from tagger.nucleo.credenciais import ocultar_credenciais

MB = 1024 * 1024
REDIRECIONAMENTO_RECUSADO = "Redirecionamento inseguro recusado."

log = logging.getLogger(__name__)


def ocultar(texto, *conhecidas):
    """Troca por *** as credenciais do texto (credenciais.ocultar_credenciais): os padrões
    api_key=/token=/key=/secret=, as credenciais carregadas e as `conhecidas` (também na forma
    codificada para URL), onde aparecerem literalmente."""
    valores = [c for c in conhecidas if c]
    valores += [urllib.parse.quote(c, safe="") for c in valores]
    return ocultar_credenciais(str(texto), conhecidas=tuple(dict.fromkeys(valores)))


def erro_busca(mensagem, detalhe):
    """ErroBusca com a mensagem para o usuário e, em `detalhe`, o erro técnico já sem credenciais
    (o que pode ir para o tagger.log). Quem levanta usa `from None`: a exceção original, que
    costuma ter a URL completa, não fica encadeada no traceback."""
    from tagger.nucleo.busca import ErroBusca
    erro = ErroBusca(mensagem)
    erro.detalhe = detalhe
    return erro


class LimitadorJanela:
    """No máximo `maximo` requisições em qualquer intervalo de `janela` segundos, com um
    espaçamento mínimo entre elas. `bloquear(s)` faz todos esperarem (ex.: depois de um 429)."""

    def __init__(self, maximo, janela, intervalo=0.0, dormir=time.sleep, relogio=time.monotonic):
        self.maximo, self.janela, self.intervalo = maximo, janela, intervalo
        self._dormir, self._relogio = dormir, relogio
        self._feitas = deque()
        self._livre_em = 0.0
        self._trava = threading.Lock()

    def esperar(self):
        with self._trava:
            agora = self._relogio()
            espera = self._livre_em - agora
            if self._feitas:
                espera = max(espera, self.intervalo - (agora - self._feitas[-1]))
            while self._feitas and agora - self._feitas[0] >= self.janela:
                self._feitas.popleft()
            if len(self._feitas) >= self.maximo:
                espera = max(espera, self.janela - (agora - self._feitas[-self.maximo]))
            if espera > 0:
                self._dormir(espera)
            self._feitas.append(self._relogio())

    def bloquear(self, segundos):
        with self._trava:
            self._livre_em = max(self._livre_em, self._relogio() + segundos)


def validade(cabecalhos, agora=None):
    """Segundos que a resposta pode ficar em cache segundo os cabeçalhos HTTP (0 = não guardar).
    Cache-Control (no-store/no-cache/private/max-age) tem prioridade sobre Expires; Age é descontado."""
    cabecalhos = {k.lower(): v for k, v in (cabecalhos or {}).items()}
    controle = (cabecalhos.get("cache-control") or "").lower()
    diretivas = [d.strip() for d in controle.split(",") if d.strip()]
    if any(d in ("no-store", "no-cache") or d.startswith("no-cache=") for d in diretivas):
        return 0
    idade = _inteiro(cabecalhos.get("age"))
    for d in diretivas:
        if d.startswith("max-age="):
            return max(0, _inteiro(d[8:].strip('"')) - idade)
    if "expires" in cabecalhos:
        try:
            expira = email.utils.parsedate_to_datetime(cabecalhos["expires"]).timestamp()
        except (TypeError, ValueError, IndexError, OverflowError):
            return 0                       # Expires inválido (ex.: "0") = já expirou
        return max(0, int(expira - (agora if agora is not None else time.time())))
    return 0


def _inteiro(texto):
    try:
        return max(0, int(str(texto).strip()))
    except (TypeError, ValueError):
        return 0


class Cache:
    """Respostas por chave, cada uma com prazo. Em memória ou numa pasta (pasta=None: só memória).
    `teto_bytes` limita o total (os mais antigos saem primeiro) e `teto_segundos` o prazo de cada uma.
    A chave nunca deve conter credencial: na pasta ela vira só um hash."""

    def __init__(self, teto_bytes, teto_segundos=None, pasta=None, relogio=time.time):
        self.teto_bytes, self.teto_segundos = teto_bytes, teto_segundos
        self.pasta = Path(pasta) if pasta else None
        self._relogio = relogio
        self._memoria = OrderedDict()      # chave -> (expira, corpo)
        self._trava = threading.Lock()

    def _arquivo(self, chave):
        return self.pasta / (hashlib.sha256(chave.encode("utf-8")).hexdigest() + ".json")

    def obter(self, chave):
        agora = self._relogio()
        with self._trava:
            if self.pasta is None:
                item = self._memoria.get(chave)
                if item is None:
                    return None
                if item[0] <= agora:
                    del self._memoria[chave]
                    return None
                self._memoria.move_to_end(chave)
                return item[1]
            arquivo = self._arquivo(chave)
            try:
                dados = json.loads(arquivo.read_text("utf-8"))
                if dados["expira"] > agora:
                    return dados["corpo"].encode("utf-8")
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                pass
            try:
                arquivo.unlink()
            except OSError:
                pass
            return None

    def guardar(self, chave, corpo, segundos):
        if self.teto_segundos is not None:
            segundos = min(segundos, self.teto_segundos)
        if segundos <= 0 or len(corpo) > self.teto_bytes:
            return
        expira = self._relogio() + segundos
        with self._trava:
            if self.pasta is None:
                self._memoria[chave] = (expira, corpo)
                self._memoria.move_to_end(chave)
                while sum(len(c) for _e, c in self._memoria.values()) > self.teto_bytes:
                    self._memoria.popitem(last=False)
                return
            destino = self._arquivo(chave)
            temporario = destino.with_name(f"{destino.stem}.{os.getpid()}.{threading.get_ident()}.tmp")
            try:
                self.pasta.mkdir(parents=True, exist_ok=True)
                temporario.write_text(json.dumps({"expira": expira, "corpo": corpo.decode("utf-8")}), "utf-8")
                os.replace(temporario, destino)       # quem lê nunca vê um arquivo pela metade
                self._podar()
            except (OSError, UnicodeDecodeError):
                try:                      # cache é só otimização: falha não derruba a busca
                    temporario.unlink()
                except OSError:
                    pass

    def _podar(self):
        arquivos = []
        for arquivo in self.pasta.glob("*.json"):
            try:
                info = arquivo.stat()
                arquivos.append((info.st_mtime, info.st_size, arquivo))
            except OSError:
                pass
        total = sum(tamanho for _m, tamanho, _a in arquivos)
        for _m, tamanho, arquivo in sorted(arquivos, key=lambda a: a[0]):
            if total <= self.teto_bytes:
                break
            try:
                os.remove(arquivo)
                total -= tamanho
            except OSError:
                pass


ERROS_DE_FORMATO = (AttributeError, TypeError, ValueError, KeyError, IndexError, RecursionError)


def resposta_invalida(servico):
    """Decorador das consultas: JSON com tipos inesperados (raiz lista, item que não é dict, número
    gigante, aninhamento profundo...) vira ErroBusca em vez de derrubar a thread da busca."""
    def decorar(funcao):
        @functools.wraps(funcao)
        def consulta(*args, **kwargs):
            try:
                return funcao(*args, **kwargs)
            except ERROS_DE_FORMATO:
                from tagger.nucleo.busca import ErroBusca
                limpar = getattr(args[0], "_ocultar", ocultar) if args else ocultar
                log.debug("Resposta inválida do %s:\n%s", servico, limpar(traceback.format_exc()))   # bug do parser?
                raise ErroBusca(f"Resposta inválida do {servico}.") from None
        return consulta
    return decorar


def url_segura(url, dominios, padrao=""):
    """`url` se for https num dos `dominios` (ou subdomínio), sem usuário/senha, porta estranha,
    barra invertida ou espaço; senão `padrao`. Para links vindos do JSON que a GUI vai abrir."""
    if not isinstance(url, str) or not url or any(c in url for c in "\\ \t\r\n\x00") or not url.isprintable():
        return padrao
    try:
        partes = urllib.parse.urlsplit(url)
        porta = partes.port
    except ValueError:
        return padrao
    host = (partes.hostname or "").lower()
    if (partes.scheme != "https" or "@" in partes.netloc or porta not in (None, 443)
            or not any(host == d or host.endswith("." + d) for d in dominios)):
        return padrao
    return url


def _origem(url):
    partes = urllib.parse.urlsplit(url)
    return partes.scheme.lower(), (partes.hostname or "").lower(), partes.port or {"https": 443, "http": 80}.get(partes.scheme.lower())


class RedirecionamentoRecusado(urllib.error.URLError):
    """O servidor tentou redirecionar para fora do https: a requisição não segue."""


class _RedirecionamentoSeguro(urllib.request.HTTPRedirectHandler):
    """Redirecionamento só para https (a api_key do Last.fm vai na URL). E o urllib repassa o
    Authorization num redirecionamento: para outra origem (esquema, host, porta), tira.
    (O Discogs ainda manda o Authorization com add_unredirected_header, que nunca é repassado.)"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme.lower() != "https":
            raise RedirecionamentoRecusado(f"redirecionamento {code} para fora do https recusado: {newurl}")
        novo = super().redirect_request(req, fp, code, msg, headers, newurl)
        if novo is not None and _origem(newurl) != _origem(req.full_url):
            for nome in list(novo.headers):
                if nome.lower() == "authorization":
                    del novo.headers[nome]
        return novo


_OPENER = urllib.request.build_opener(_RedirecionamentoSeguro)


def abrir_sem_vazar(pedido, timeout=None):
    return _OPENER.open(pedido, timeout=timeout)
