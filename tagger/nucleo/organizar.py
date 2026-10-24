"""
Organizar arquivos em pastas pelas tags. Sem dependência de interface.

O padrão é o mesmo de padroes.py, mas com "/" separando as pastas:
    {albumartist}/{album}/{tracknumber:02} - {title}
Cada trecho passa por padroes.nome_pelas_tags (nomes seguros para o Windows). Além disso:
- tags vazias viram um texto padrão ("Unknown Artist", "Unknown Album"); o artista do álbum
  cai para o artista antes disso;
- as pastas são criadas; mover = renomear entre pastas (desfazer move de volta e recria as pastas);
- a capa da pasta (cover.jpg, folder.jpg...) vai junto quando todas as faixas dela vão para o mesmo lugar;
- opcionalmente, pastas de origem que ficarem vazias são removidas (nunca acima da pasta aberta).

Limitação no Windows: maiúsculas/minúsculas não diferenciam pastas. Se o destino já tem "Artista" e as
tags pedem "artista", os arquivos vão para a pasta existente; mudar só a caixa de uma pasta não é aplicado.
"""

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import uuid

from tagger.nucleo.metadata import EXTENSOES_SUPORTADAS
from tagger.nucleo.padroes import ItemRenomear, _chave, campos_do_padrao, executar_renomeacao, nome_pelas_tags

SEM_ARTISTA = "Unknown Artist"
SEM_ALBUM = "Unknown Album"
NOMES_CAPA = ("cover", "folder", "front")
EXTENSOES_CAPA = (".jpg", ".jpeg", ".png")
TAMANHO_MAX_CAMINHO = 255        # limite clássico do Windows (MAX_PATH tem 260)


def partes_do_padrao(padrao):
    """Quebra o padrão em trechos (pastas + nome do arquivo). Levanta ValueError se for inválido."""
    trechos = [t.strip() for t in re.split(r"[/\\]", padrao.strip())]
    trechos = [t for t in trechos if t]
    if not trechos:
        raise ValueError("Digite um padrão.")
    if re.match(r"^[A-Za-z]:", trechos[0]):
        raise ValueError("O padrão é relativo à pasta de destino (sem letra de unidade).")
    for trecho in trechos:
        campos_do_padrao(trecho)                       # campo desconhecido -> ValueError
        if trecho.strip(". ") == "":
            raise ValueError("Trecho do padrão inválido: " + trecho)
    if not campos_do_padrao(padrao):
        raise ValueError("Use pelo menos um campo, ex.: {artist}/{album}/{title}")
    return trechos


def valores_com_padroes(valores, sem_artista=SEM_ARTISTA, sem_album=SEM_ALBUM):
    """Preenche artista/álbum vazios. Passe "" em sem_artista/sem_album para não preencher."""
    v = dict(valores)
    artista = (v.get("artist") or "").strip()
    v["artist"] = artista or sem_artista
    v["albumartist"] = (v.get("albumartist") or "").strip() or artista or sem_artista
    v["album"] = (v.get("album") or "").strip() or sem_album
    return v


def caminho_relativo(padrao, valores, stem_original="", sem_artista=SEM_ARTISTA, sem_album=SEM_ALBUM):
    """
    Partes do caminho novo (pastas + nome sem extensão) para um arquivo com essas tags.
    Pasta que ficaria vazia vira "Unknown"; nome vazio usa o nome original do arquivo.
    """
    trechos = partes_do_padrao(padrao)
    v = valores_com_padroes(valores, sem_artista, sem_album)
    partes = [nome_pelas_tags(t, v) or "Unknown" for t in trechos[:-1]]
    partes.append(nome_pelas_tags(trechos[-1], v) or stem_original)
    return partes


@dataclass
class PlanoOrganizar:
    pasta: Path
    itens: list = field(default_factory=list)       # [ItemRenomear], um por faixa, na ordem recebida
    capas: list = field(default_factory=list)       # [ItemRenomear] das capas que vão junto

    def validos(self):
        """Tudo o que será movido (faixas + capas)."""
        return [i for i in self.itens if i.valido] + self.capas


def _capas_da_pasta(pasta):
    try:
        nomes = os.listdir(pasta)
    except OSError:
        return []
    return [Path(pasta) / n for n in sorted(nomes)
            if Path(n).stem.lower() in NOMES_CAPA and Path(n).suffix.lower() in EXTENSOES_CAPA]


def _planejar_capas(itens):
    """Capas que acompanham as faixas válidas: só se a pasta de origem fica sem outras faixas
    e todas as faixas dela vão para a mesma pasta nova."""
    por_pasta = {}
    for item in itens:
        if item.valido:
            por_pasta.setdefault(item.origem.parent, []).append(item)
    movem = {_chave(i.origem) for i in itens if i.valido}

    capas, alvos = [], set()
    for pasta, grupo in por_pasta.items():
        destinos = {_chave(i.destino.parent) for i in grupo}
        if len(destinos) != 1:
            continue
        try:
            restam = any(Path(n).suffix.lower() in EXTENSOES_SUPORTADAS and _chave(pasta / n) not in movem
                         for n in os.listdir(pasta))
        except OSError:
            continue
        if restam:
            continue
        destino = grupo[0].destino.parent
        for capa in _capas_da_pasta(pasta):
            alvo = destino / capa.name
            if _chave(alvo) != _chave(capa) and _chave(alvo) not in alvos and not alvo.exists():
                alvos.add(_chave(alvo))
                capas.append(ItemRenomear(capa, alvo))
    return capas


def planejar_organizacao(itens, padrao, pasta_destino, levar_capa=True, sem_artista=SEM_ARTISTA, sem_album=SEM_ALBUM):
    """
    itens: [(caminho, {campo: valor})]. Nada é movido aqui: é a prévia.
    Conflitos: dois arquivos com o mesmo destino, destino que já existe, caminho longo demais.
    """
    pasta = Path(pasta_destino)
    plano = PlanoOrganizar(pasta)
    for caminho, valores in itens:
        caminho = Path(caminho)
        partes = caminho_relativo(padrao, valores, caminho.stem, sem_artista, sem_album)
        destino = pasta.joinpath(*partes[:-1], partes[-1] + caminho.suffix.lower())
        if _chave(destino) == _chave(caminho):
            plano.itens.append(ItemRenomear(caminho))
        elif len(str(destino)) > TAMANHO_MAX_CAMINHO:
            plano.itens.append(ItemRenomear(caminho, erro="O caminho novo ficaria longo demais"))
        else:
            plano.itens.append(ItemRenomear(caminho, destino))

    origens = {_chave(i.origem) for i in plano.itens}
    contagem = {}
    for item in plano.itens:
        alvo = _chave(item.destino or item.origem)
        contagem[alvo] = contagem.get(alvo, 0) + 1
    for item in plano.itens:
        if not item.valido:
            continue
        chave = _chave(item.destino)
        if contagem[chave] > 1:
            item.erro = "Outro arquivo ficaria no mesmo lugar"
        elif chave not in origens and item.destino.exists():
            item.erro = "Já existe um arquivo com esse nome no destino"

    if levar_capa:
        plano.capas = _planejar_capas(plano.itens)
    return plano


def _outra_unidade(item):
    return os.path.splitdrive(_chave(item.origem))[0] != os.path.splitdrive(_chave(item.destino))[0]


def _criar_pastas(pasta, criadas):
    """Cria a pasta e anota em `criadas` as que não existiam (de cima para baixo)."""
    novas, atual = [], Path(pasta)
    while not atual.exists() and atual != atual.parent:
        novas.append(atual)
        atual = atual.parent
    Path(pasta).mkdir(parents=True, exist_ok=True)
    criadas.extend(reversed(novas))


def _mover_entre_unidades(item):
    """Copia para um temporário no destino, renomeia para o nome final e só então apaga a origem.
    Nunca deixa cópia parcial nem arquivo duplicado: se algo falha, a origem continua intacta."""
    if item.destino.exists():
        raise FileExistsError("Já existe um arquivo com esse nome no destino")
    temporario = item.destino.with_name(f".{uuid.uuid4().hex}.tagger-tmp")
    try:
        shutil.copy2(item.origem, temporario)
        os.rename(temporario, item.destino)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise
    try:
        item.origem.unlink()
    except OSError:
        item.destino.unlink(missing_ok=True)          # não deixa duplicado sem registro
        raise


def executar_movimentos(itens, criadas=None):
    """
    Move os itens válidos (cria as pastas do destino). Serve para organizar e para desfazer/refazer.
    Devolve (feitos [(origem, destino)], falhas {origem: erro}). Nunca sobrescreve arquivo existente.
    Na mesma unidade usa executar_renomeacao (trocas A<->B funcionam); entre unidades, copia e apaga.
    Pastas criadas que ficaram vazias (por falhas) são removidas; `criadas`, se dada (lista), recebe
    as pastas novas que continuam existindo.
    """
    feitos, falhas, mesma_unidade, novas = [], {}, [], []
    for item in itens:
        if not item.valido:
            continue
        try:
            _criar_pastas(item.destino.parent, novas)
        except OSError as erro:
            falhas[item.origem] = erro.strerror or str(erro)
            continue
        if not _outra_unidade(item):
            mesma_unidade.append(item)
            continue
        try:
            _mover_entre_unidades(item)
            feitos.append((item.origem, item.destino))
        except (OSError, shutil.Error) as erro:
            falhas[item.origem] = getattr(erro, "strerror", None) or str(erro)

    ok, erros = executar_renomeacao(mesma_unidade)
    feitos.extend(ok)
    falhas.update(erros)

    remover_pastas_vazias(novas, permitidas=novas)
    if criadas is not None:
        criadas.extend(p for p in novas if p.exists())
    return feitos, falhas


def _dentro_de(pasta, raiz):
    return _chave(raiz) in {_chave(p) for p in Path(os.path.abspath(pasta)).parents}


def remover_pastas_vazias(pastas, raiz=None, permitidas=None, proteger=()):
    """
    Remove cada pasta se estiver vazia (rmdir nunca apaga conteúdo) e sobe removendo as de cima que
    também ficarem vazias, mas:
    - sem `raiz`, só tenta as próprias pastas; com `raiz`, sobe apenas enquanto a pasta está dentro dela
      (a própria raiz nunca é removida);
    - com `permitidas`, só remove pastas dessa lista (ex.: as que o Tagger criou) e pode subir por elas;
    - `proteger`: pastas que nunca são removidas.
    Devolve as pastas removidas.
    """
    bloqueadas = {_chave(p) for p in proteger}
    if raiz is not None:
        bloqueadas.add(_chave(raiz))
    liberadas = None if permitidas is None else {_chave(p) for p in permitidas}
    removidas = []
    for pasta in sorted({Path(os.path.abspath(p)) for p in pastas}, key=lambda p: -len(p.parts)):
        atual = pasta
        while _chave(atual) not in bloqueadas and (liberadas is None or _chave(atual) in liberadas):
            try:
                atual.rmdir()
            except OSError:
                break
            removidas.append(atual)
            pai = atual.parent
            if pai == atual or (liberadas is None and (raiz is None or not _dentro_de(pai, raiz))):
                break
            atual = pai
    return removidas


def executar_organizacao(plano, remover_vazias=False, raiz_origem=None, criadas=None):
    """
    Move faixas e capas do plano. Devolve (feitos, falhas, removidas):
    feitos = [(origem, destino)] de faixas e capas (guarde em Renomeacao para desfazer com executar_movimentos).
    remover_vazias: apaga as pastas de origem que ficaram vazias, subindo no máximo até `raiz_origem`
    (a pasta aberta no Tagger; ela mesma fica). Sem raiz_origem, só as próprias pastas de origem.
    criadas (lista): recebe as pastas de destino que o Tagger criou, para limpar ao desfazer.
    """
    feitos, falhas = executar_movimentos([i for i in plano.itens if i.valido], criadas)
    com_falha = {_chave(o.parent) for o in falhas}          # capa fica se alguma faixa da pasta não saiu
    capas = [c for c in plano.capas if _chave(c.origem.parent) not in com_falha]
    feitos_capas, falhas_capas = executar_movimentos(capas, criadas)
    feitos.extend(feitos_capas)
    falhas.update(falhas_capas)

    removidas = []
    protegidas = [plano.pasta] + ([raiz_origem] if raiz_origem is not None else [])
    if remover_vazias:
        for pasta in {o.parent for o, _d in feitos}:
            raiz = raiz_origem if raiz_origem is not None and _dentro_de(pasta, raiz_origem) else None
            removidas += remover_pastas_vazias([pasta], raiz=raiz, proteger=protegidas)
    return feitos, falhas, removidas


def _relativo(caminho, base):
    """Caminho relativo à base, se estiver dentro dela; senão o caminho inteiro."""
    try:
        return Path(caminho).relative_to(base)
    except ValueError:
        return Path(caminho)


def resumo_movimentos(feitos, base):
    """
    Linhas origem → destino do que foi movido, para mostrar ao usuário: [(origem, destino)] de texto.
    Caminhos dentro de `base` aparecem relativos a ela; ordenados pelo destino.
    """
    linhas = [(str(_relativo(o, base)), str(_relativo(d, base))) for o, d in feitos]
    return sorted(linhas, key=lambda linha: linha[1].lower())


def resumo_falhas(falhas, base):
    """Linhas arquivo → motivo do que não foi movido: [(origem, "Não movido: motivo")], como em resumo_movimentos."""
    return [(str(_relativo(o, base)), f"Não movido: {erro}") for o, erro in falhas.items()]


def pastas_de_destino(feitos):
    """Pastas onde os arquivos movidos foram parar (sem repetir, na ordem em que aparecem)."""
    return list(dict.fromkeys(d.parent for _o, d in feitos))


def pasta_comum(caminhos):
    """Pasta que contém todos os arquivos; None se não houver (lista vazia ou unidades diferentes)."""
    pastas = [os.path.abspath(Path(c).parent) for c in caminhos]
    try:
        return Path(os.path.commonpath(pastas)) if pastas else None
    except ValueError:
        return None


def pasta_apos_mover(pasta_atual, caminhos, preferidas=()):
    """
    Pasta que a migalha deve mostrar depois de mover arquivos. `caminhos`: onde as faixas da lista estão agora.
    - continua a pasta aberta se ainda há alguma faixa dentro dela (movimento parcial);
    - senão, a primeira das `preferidas` (ex.: o destino escolhido) que contém a pasta comum das faixas;
    - senão, a própria pasta comum. Sem pasta comum, nada muda.
    """
    if pasta_atual is None:
        return None
    pasta_atual = Path(pasta_atual)
    caminhos = [Path(c) for c in caminhos]
    if any(_dentro_de(c, pasta_atual) for c in caminhos):
        return pasta_atual
    comum = pasta_comum(caminhos)
    if comum is None:
        return pasta_atual
    for pasta in preferidas:
        if pasta is not None and (_chave(pasta) == _chave(comum) or _dentro_de(comum, pasta)):
            return Path(pasta)
    return comum
