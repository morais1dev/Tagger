"""
Credenciais das APIs online (Last.fm e Discogs) e limpeza delas em textos de log/erro.

Sem Qt e sem estado global: o valor que o usuário colou nas Configurações entra por parâmetro.
Cada credencial é procurada nesta ordem:
1. valor das Configurações (se não estiver vazio);
2. variável de ambiente (TAGGER_LASTFM_API_KEY, TAGGER_DISCOGS_KEY, TAGGER_DISCOGS_SECRET, TAGGER_DISCOGS_TOKEN);
3. chaves.json embutido (gerado no build pelos Secrets do GitHub; fora do git);
4. nada: None (a busca daquele serviço fica desativada).

O token pessoal do Discogs nunca vem do chaves.json: só das Configurações ou do ambiente.
As chaves embutidas não são secretas de verdade (dá para extraí-las do .exe); o objetivo é tirá-las do GitHub.
"""

import json
import logging
import os
import re
import sys
from pathlib import Path

ARQUIVO = "chaves.json"
VARIAVEIS = {
    "lastfm_api_key": "TAGGER_LASTFM_API_KEY",
    "discogs_key": "TAGGER_DISCOGS_KEY",
    "discogs_secret": "TAGGER_DISCOGS_SECRET",
    "discogs_token": "TAGGER_DISCOGS_TOKEN",
}
EMBUTIDAS = ("lastfm_api_key", "discogs_key", "discogs_secret")
OCULTO = "***"
TAMANHO_MINIMO = 4        # credenciais literais menores que isso não são trocadas (evita estragar o texto)


def pasta_chaves():
    """Onde fica o chaves.json: ao lado deste módulo, ou dentro do pacote do PyInstaller no .exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "tagger" / "nucleo"
    return Path(__file__).parent


def _limpo(valor):
    """Texto sem espaços nas pontas, ou None se vazio/não for texto."""
    if not isinstance(valor, str):
        return None
    valor = valor.strip()
    return valor or None


def ler_embutidas(pasta=None):
    """{nome: valor} do chaves.json. Ausente, vazio ou inválido = {} (nunca levanta exceção)."""
    caminho = Path(pasta or pasta_chaves()) / ARQUIVO
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}
    return {nome: v for nome in EMBUTIDAS if (v := _limpo(dados.get(nome)))}


def _do_ambiente(nome, ambiente=None):
    return _limpo((os.environ if ambiente is None else ambiente).get(VARIAVEIS[nome]))


def lastfm_api_key(valor_config, pasta=None, ambiente=None):
    """API key do Last.fm (Configurações > ambiente > chaves.json), ou None."""
    return (_limpo(valor_config) or _do_ambiente("lastfm_api_key", ambiente)
            or ler_embutidas(pasta).get("lastfm_api_key"))


def discogs_authorization(token_usuario, pasta=None, ambiente=None):
    """Valor pronto do cabeçalho Authorization do Discogs, ou None (busca desativada).

    Token pessoal (Configurações > ambiente) tem prioridade sobre key/secret do app.
    Key e secret vêm sempre da mesma origem (ambiente, senão chaves.json), para não misturar pares.
    """
    token = _limpo(token_usuario) or _do_ambiente("discogs_token", ambiente)
    if token:
        return f"Discogs token={token}"
    key, secret = _do_ambiente("discogs_key", ambiente), _do_ambiente("discogs_secret", ambiente)
    if not (key and secret):
        embutidas = ler_embutidas(pasta)
        key, secret = embutidas.get("discogs_key"), embutidas.get("discogs_secret")
    if key and secret:
        return f"Discogs key={key}, secret={secret}"
    return None


def lastfm_disponivel(valor_config, pasta=None, ambiente=None):
    return lastfm_api_key(valor_config, pasta, ambiente) is not None


def discogs_disponivel(token_usuario, pasta=None, ambiente=None):
    return discogs_authorization(token_usuario, pasta, ambiente) is not None


def credenciais_conhecidas(extras=(), pasta=None, ambiente=None):
    """Todos os valores de credencial carregados agora (ambiente, chaves.json e extras), sem repetir."""
    valores = {_do_ambiente(nome, ambiente) for nome in VARIAVEIS}
    valores.update(ler_embutidas(pasta).values())
    valores.update(_limpo(v) for v in extras)
    return {v for v in valores if v and len(v) >= TAMANHO_MINIMO}


# api_key=... em URLs (também já codificado: api_key%3D...)
_RE_API_KEY = re.compile(r"(api_key(?:=|%3D))(?:(?!%26)[^&\s'\"<>])+", re.IGNORECASE)
# cabeçalho "Discogs token=..., key=..., secret=..." (com ou sem "Authorization:")
_RE_DISCOGS = re.compile(r"(Discogs\s+)((?:\w+=[^,\s'\"]+\s*,?\s*)+)", re.IGNORECASE)
_RE_PAR = re.compile(r"\b(token|key|secret)=([^,\s'\"]+)", re.IGNORECASE)


def ocultar_credenciais(texto, conhecidas=(), pasta=None, ambiente=None):
    """Troca credenciais por *** antes de o texto ir para o log ou para um diálogo de erro.

    Cobre api_key= em URLs, token/key/secret em cabeçalhos do Discogs e qualquer credencial
    carregada no momento (ambiente, chaves.json e as `conhecidas`, ex.: as das Configurações)
    que apareça literalmente no texto.
    """
    if not texto:
        return texto
    texto = str(texto)
    for valor in sorted(credenciais_conhecidas(conhecidas, pasta, ambiente), key=len, reverse=True):
        texto = texto.replace(valor, OCULTO)
    texto = _RE_API_KEY.sub(lambda m: m.group(1) + OCULTO, texto)
    return _RE_DISCOGS.sub(lambda m: m.group(1) + _RE_PAR.sub(lambda p: f"{p.group(1)}={OCULTO}", m.group(2)),
                           texto)


class FormatadorSemCredenciais(logging.Formatter):
    """Formatter que passa a linha pronta (mensagem e traceback) por ocultar_credenciais.

    `conhecidas`: função sem argumentos que devolve as credenciais das Configurações no momento.
    """

    def __init__(self, *args, conhecidas=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._conhecidas = conhecidas or (lambda: ())

    def format(self, record):
        try:
            extras = tuple(self._conhecidas())
        except Exception:
            extras = ()
        return ocultar_credenciais(super().format(record), extras)
