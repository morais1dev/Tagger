"""
Padrões de nome de arquivo <-> tags. Sem dependência de interface.

Um padrão mistura texto fixo com campos, em qualquer uma das duas formas:
    {tracknumber:02} - {artist} - {title}       %artist% - %title%
- {campo:02} completa números com zeros à esquerda ("3/12" -> "03").
- Apelidos aceitos: track, disc, year (iguais a tracknumber, discnumber, date).
- Só para ler tags do nome: {*} (ou %*%) ignora um trecho, e "/" separa pastas
  (ex.: %artist%/%album%/%track% - %title% usa as duas pastas acima do arquivo).

Renomear usa os mesmos campos de metadata.CAMPOS e:
- limpa caracteres que o Windows não aceita em nomes de arquivo;
- detecta conflitos (dois arquivos com o mesmo nome novo, ou nome já existente);
- renomeia em duas etapas (via nome temporário), então trocas como A->B e B->A funcionam.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import time
import uuid

from tagger.nucleo.metadata import CAMPOS

APELIDOS = {"track": "tracknumber", "disc": "discnumber", "year": "date"}
CAMPOS_NUMERICOS = {"tracknumber", "discnumber"}
IGNORAR = "*"
TAMANHO_MAX_NOME = 180          # caracteres, sem a extensão (o caminho inteiro tem limite no Windows)

_RE_CAMPO = re.compile(r"\{(\w+|\*)(?::(\d+))?\}|%(\w+|\*)(?::(\d+))?%")
_TROCAS = str.maketrans({
    "/": "-", "\\": "-", ":": " -", "|": "-", '"': "'",
    "*": "", "?": "", "<": "", ">": "",
})
_RE_CONTROLE = re.compile(r"[\x00-\x1f\x7f]")
_RE_SEPARADORES_REPETIDOS = re.compile(r"(\s*-\s*){2,}")
_RESERVADOS = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


# ---------------------------------------------------------------------------
# Padrão
# ---------------------------------------------------------------------------

def analisar(padrao):
    """
    Quebra o padrão em partes: ("texto", str) ou ("campo", nome, largura | None).
    Levanta ValueError com uma mensagem amigável se houver campo desconhecido.
    """
    partes, inicio = [], 0
    for achado in _RE_CAMPO.finditer(padrao):
        if achado.start() > inicio:
            partes.append(("texto", padrao[inicio:achado.start()]))
        nome = (achado.group(1) or achado.group(3)).lower()
        largura = achado.group(2) or achado.group(4)
        nome = APELIDOS.get(nome, nome)
        if nome != IGNORAR and nome not in CAMPOS:
            raise ValueError(f"Campo desconhecido: {achado.group(0)}")
        partes.append(("campo", nome, int(largura) if largura else None))
        inicio = achado.end()
    if inicio < len(padrao):
        partes.append(("texto", padrao[inicio:]))
    return partes


def campos_do_padrao(padrao):
    """Campos usados no padrão, na ordem e sem repetir (sem o {*})."""
    vistos = []
    for parte in analisar(padrao):
        if parte[0] == "campo" and parte[1] != IGNORAR and parte[1] not in vistos:
            vistos.append(parte[1])
    return vistos


# ---------------------------------------------------------------------------
# Tags -> nome de arquivo
# ---------------------------------------------------------------------------

def sanitizar(texto):
    """Tira o que o Windows não aceita num nome de arquivo (e espaços/pontos sobrando)."""
    texto = _RE_CONTROLE.sub(" ", texto.translate(_TROCAS))
    return re.sub(r"\s+", " ", texto).strip()


def _valor_formatado(campo, valor, largura):
    valor = (valor or "").strip()
    if campo in CAMPOS_NUMERICOS:
        valor = valor.split("/")[0].strip()
        if largura and valor.isdigit():
            valor = valor.zfill(largura)
    return sanitizar(valor)


def nome_pelas_tags(padrao, valores):
    """
    Nome novo (sem extensão) para um arquivo com essas tags. "" se ficar vazio.
    valores: {campo: valor}. Campos vazios somem e os separadores sobrando são limpos
    ("Artista -  - Título" vira "Artista - Título").
    """
    if "/" in padrao or "\\" in padrao:
        raise ValueError("O padrão de nome não pode ter / ou \\ (organizar em pastas fica para a v2.1).")
    texto = ""
    for parte in analisar(padrao):
        if parte[0] == "texto":
            texto += parte[1]
        elif parte[1] != IGNORAR:
            texto += _valor_formatado(parte[1], valores.get(parte[1], ""), parte[2])

    texto = sanitizar(texto)
    texto = _RE_SEPARADORES_REPETIDOS.sub(" - ", texto)
    texto = texto.strip(" -_.")
    if len(texto) > TAMANHO_MAX_NOME:
        texto = texto[:TAMANHO_MAX_NOME].rstrip(" -_.")
    if texto.upper() in _RESERVADOS:
        texto += "_"
    return texto


@dataclass
class ItemRenomear:
    origem: Path
    destino: Path | None = None    # None = nome não muda
    erro: str = ""

    @property
    def valido(self):
        return self.destino is not None and not self.erro


def _chave(caminho):
    """Para comparar caminhos como o sistema compara (no Windows, sem diferenciar maiúsculas)."""
    return os.path.normcase(os.path.abspath(caminho))


def planejar_renomeacao(itens, padrao):
    """
    itens: [(caminho, {campo: valor})]. Devolve [ItemRenomear], um por item, na mesma ordem.
    Nada é renomeado aqui: é a prévia.
    """
    plano = []
    for caminho, valores in itens:
        caminho = Path(caminho)
        stem = nome_pelas_tags(padrao, valores)
        if not stem:
            plano.append(ItemRenomear(caminho, erro="O nome ficaria vazio (tags em branco?)"))
            continue
        destino = caminho.with_name(stem + caminho.suffix.lower())
        plano.append(ItemRenomear(caminho, None if destino.name == caminho.name else destino))

    origens = {_chave(item.origem) for item in plano}
    contagem = {}
    for item in plano:
        alvo = item.destino or item.origem
        contagem[_chave(alvo)] = contagem.get(_chave(alvo), 0) + 1

    for item in plano:
        if item.destino is None or item.erro:
            continue
        chave = _chave(item.destino)
        if contagem[chave] > 1:
            item.erro = "Outro arquivo ficaria com o mesmo nome"
        elif chave != _chave(item.origem) and chave not in origens and item.destino.exists():
            item.erro = "Já existe um arquivo com esse nome na pasta"
    return plano


def _renomear_com_tentativas(origem, destino, tentativas=3, espera=0.05):
    """os.rename com poucas novas tentativas se o Windows negar por instantes (antivírus, indexador)."""
    for tentativa in range(tentativas):
        try:
            return os.rename(origem, destino)
        except PermissionError:
            if tentativa == tentativas - 1:
                raise
            time.sleep(espera)


def executar_renomeacao(plano):
    """
    Renomeia os itens válidos do plano. Devolve (feitos [(origem, destino)], falhas {origem: erro}).
    Etapa 1: cada arquivo vai para um nome temporário. Etapa 2: do temporário para o nome final.
    Nunca sobrescreve um arquivo existente; se a etapa 2 falhar, o arquivo volta ao nome original.
    """
    feitos, falhas, temporarios = [], {}, []
    for item in plano:
        if not item.valido:
            continue
        temporario = item.origem.with_name(f".{uuid.uuid4().hex}.tagger-tmp")
        try:
            _renomear_com_tentativas(item.origem, temporario)
            temporarios.append((item, temporario))
        except OSError as erro:
            falhas[item.origem] = erro.strerror or str(erro)

    for item, temporario in temporarios:
        try:
            if item.destino.exists():
                raise FileExistsError("Já existe um arquivo com esse nome na pasta")
            _renomear_com_tentativas(temporario, item.destino)
            feitos.append((item.origem, item.destino))
        except OSError as erro:
            falhas[item.origem] = getattr(erro, "strerror", None) or str(erro)
            try:
                _renomear_com_tentativas(temporario, item.origem)
            except OSError:
                falhas[item.origem] += f" (o arquivo ficou como {temporario.name})"
    return feitos, falhas


# ---------------------------------------------------------------------------
# Nome de arquivo -> tags
# ---------------------------------------------------------------------------

def _regex_do_padrao(padrao):
    padrao = padrao.replace("\\", "/")
    expressao, grupos = "", []
    for parte in analisar(padrao):
        if parte[0] == "texto":
            expressao += re.escape(parte[1])
        elif parte[1] == IGNORAR:
            expressao += r"[^/]*?"
        else:
            grupos.append(parte[1])
            expressao += rf"(?P<g{len(grupos) - 1}>[^/]+?)"
    return re.compile(rf"^{expressao}$", re.IGNORECASE), grupos


def tags_pelo_nome(padrao, caminho, sublinhado_vira_espaco=False):
    """
    Lê tags do nome do arquivo (sem extensão) seguindo o padrão. Devolve {campo: valor}
    ou None se o nome não segue o padrão. Com "/" no padrão, usa também as pastas acima.
    """
    caminho = Path(caminho)
    niveis = padrao.replace("\\", "/").count("/")
    partes = [*caminho.parent.parts[len(caminho.parent.parts) - niveis:], caminho.stem] if niveis else [caminho.stem]
    if len(partes) != niveis + 1:
        return None
    texto = "/".join(partes)
    if sublinhado_vira_espaco:
        texto = texto.replace("_", " ")

    regex, grupos = _regex_do_padrao(padrao)
    achado = regex.match(texto)
    if not achado:
        return None
    resultado = {}
    for i, campo in enumerate(grupos):
        valor = re.sub(r"\s+", " ", achado.group(f"g{i}")).strip()
        if campo in CAMPOS_NUMERICOS and re.fullmatch(r"\d+(/\d+)?", valor):
            valor = "/".join(str(int(n)) for n in valor.split("/"))     # "03" -> "3"
        if campo not in resultado:
            resultado[campo] = valor
    return resultado
