"""
Aviso de nova versão: pergunta ao GitHub qual é a última Release e compara com a versão instalada.

Sem Qt. Só avisa: nunca baixa nem instala nada. Regras:
- no máximo uma consulta por dia (`deve_consultar`; quem chama guarda o instante da última tentativa);
- a versão é comparada por partes numéricas (2.10.0 > 2.9.1), aceita o prefixo "v" e trata
  pré-release (2.3.0-rc1) como anterior à versão final;
- qualquer falha (sem internet, erro da API, JSON estranho) vira None e só um aviso no log,
  sem a URL completa nem credenciais (a consulta não usa nenhuma).
"""

import json
import logging
import re
import urllib.parse
import urllib.request

from tagger import __version__
from tagger.nucleo import online

log = logging.getLogger(__name__)

REPOSITORIO = "morais1dev/Tagger"
URL_API = f"https://api.github.com/repos/{REPOSITORIO}/releases/latest"
URL_RELEASES = f"https://github.com/{REPOSITORIO}/releases"
INTERVALO = 24 * 60 * 60        # segundos entre consultas
TIMEOUT = 10                    # segundos
LIMITE_RESPOSTA = 1024 * 1024   # a resposta da API tem poucos KB
USER_AGENT = f"Tagger/{__version__}"

_RE_VERSAO = re.compile(r"^[vV]?(\d+(?:\.\d+)*)(?:[-+]([0-9A-Za-z][0-9A-Za-z.+-]*))?$")


def interpretar_versao(texto):
    """Chave comparável da versão ("v2.10.0", "2.3.0-rc1"), ou None se o texto não for uma versão.

    (partes numéricas sem zeros à direita, 1 se for final / 0 se pré-release, partes do sufixo)."""
    if not isinstance(texto, str):
        return None
    achado = _RE_VERSAO.match(texto.strip())
    if not achado:
        return None
    numeros = [int(p) for p in achado.group(1).split(".")]
    while len(numeros) > 1 and numeros[-1] == 0:
        numeros.pop()
    sufixo = achado.group(2)
    if not sufixo:
        return (tuple(numeros), 1, ())
    # "rc10" > "rc2": letras e números do sufixo comparados cada um do seu jeito
    partes = tuple((0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in re.findall(r"\d+|[A-Za-z]+", sufixo))
    return (tuple(numeros), 0, partes)


def e_mais_nova(candidata, atual=__version__):
    """A versão `candidata` é mais nova que `atual`? Texto que não é versão nunca é mais novo."""
    nova, velha = interpretar_versao(candidata), interpretar_versao(atual)
    return nova is not None and velha is not None and nova > velha


def deve_consultar(ultima_consulta, agora):
    """Passou um dia desde a última tentativa (instantes em segundos, ex.: time.time())?
    Sem registro ou relógio que voltou no tempo: consulta."""
    try:
        decorrido = agora - float(ultima_consulta)
    except (TypeError, ValueError):
        return True
    return decorrido < 0 or decorrido >= INTERVALO


def _url_da_release(url):
    """Só https do github.com; qualquer outra coisa cai na página de Releases do projeto."""
    try:
        partes = urllib.parse.urlsplit(url)
    except (TypeError, ValueError, AttributeError):
        return URL_RELEASES
    if partes.scheme == "https" and partes.hostname in ("github.com", "www.github.com"):
        return url
    return URL_RELEASES


def analisar_resposta(corpo, atual=__version__):
    """(versão, link) se a resposta da API traz uma Release final mais nova que `atual`; senão None.

    `corpo`: bytes ou texto do JSON de /releases/latest."""
    try:
        dados = json.loads(corpo)
    except (ValueError, TypeError, RecursionError):
        return None
    if not isinstance(dados, dict) or dados.get("draft") or dados.get("prerelease"):
        return None
    tag = dados.get("tag_name")
    chave = interpretar_versao(tag)
    if chave is None or chave[1] == 0 or not e_mais_nova(tag, atual):
        return None
    return tag.strip().lstrip("vV"), _url_da_release(dados.get("html_url"))


def consultar(atual=__version__, abrir=None):
    """Pergunta ao GitHub. Devolve (versão, link) se há versão mais nova; None se não há ou se falhou
    (a falha só vai para o log). `abrir(pedido, timeout)` existe para os testes não usarem a rede."""
    abrir = abrir or online.abrir_sem_vazar
    pedido = urllib.request.Request(URL_API, headers={"User-Agent": USER_AGENT,
                                                      "Accept": "application/vnd.github+json"})
    try:
        with abrir(pedido, TIMEOUT) as resposta:
            corpo = resposta.read(LIMITE_RESPOSTA + 1)
    except Exception as erro:       # sem rede, HTTP 403/404/5xx, timeout, TLS...: nunca incomoda o usuário
        log.warning("Verificação de nova versão falhou (%s)", type(erro).__name__)
        return None
    if len(corpo) > LIMITE_RESPOSTA:
        log.warning("Verificação de nova versão: resposta grande demais")
        return None
    return analisar_resposta(corpo, atual)
