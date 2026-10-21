"""
Rascunho: tudo o que foi alterado e ainda NÃO foi gravado nos arquivos.

Cada arquivo tem seu próprio conjunto de alterações pendentes. Assim:
- dá para editar uma seleção, trocar de seleção e continuar editando outras;
- desfazer, numerar faixas, colar tags e editar na tabela viram alterações
  pendentes, iguais a uma edição normal, e só valem depois de "Salvar".

Este módulo não depende do Qt (dá para testar sem interface).
"""

from dataclasses import dataclass

from tagger.nucleo.metadata import carregar, carregar_varios, ler_capa, salvar, validar_valor

FALTA = object()          # "este campo não tinha rascunho"
SEM_CAPA = object()       # "a capa não fez parte desta alteração" (nos registros de desfazer)


class ArquivoModificado(Exception):
    """O arquivo mudou no disco (outro programa) depois de ser lido pelo Tagger."""


@dataclass
class Renomeacao:
    """Item do histórico de desfazer: arquivos renomeados, [(caminho_antigo, caminho_novo)].
    Diferente das tags, renomear não passa pelo rascunho: desfazer renomeia de volta na hora."""
    pares: list

    def inversa(self):
        return Renomeacao([(novo, antigo) for antigo, novo in self.pares])


def migrar_historico(pilha, mapa):
    """Atualiza os caminhos de uma pilha de desfazer/refazer depois de renomear arquivos.
    pilha: lista de itens (lista de registros de tags ou Renomeacao); mapa: {antigo: novo}."""
    for i, item in enumerate(pilha):
        if isinstance(item, Renomeacao):
            pilha[i] = Renomeacao([(antigo, mapa.get(novo, novo)) for antigo, novo in item.pares])
        else:
            pilha[i] = [(mapa.get(caminho, caminho), tags, capa) for caminho, tags, capa in item]


class Rascunho:
    def __init__(self):
        self.tags = {}        # caminho -> {campo: valor}
        self.capas = {}       # caminho -> ("definir", dados, mime) | ("remover",)
        self.ao_mudar = None  # função chamada com o conjunto de caminhos afetados

    # ------------------------------------------------------------ consultas
    @property
    def vazio(self):
        return not self.tags and not self.capas

    def caminhos(self):
        return set(self.tags) | set(self.capas)

    def __len__(self):
        return len(self.caminhos())

    def tem(self, caminho):
        return caminho in self.tags or caminho in self.capas

    def tem_campo(self, caminho, campo):
        return campo in self.tags.get(caminho, {})

    def quantidade_campos(self):
        return sum(len(t) for t in self.tags.values()) + len(self.capas)

    def valor(self, faixa, campo):
        """Valor que o usuário está vendo: o do rascunho, se houver; senão o do arquivo."""
        return self.tags.get(faixa.caminho, {}).get(campo, faixa.tags.get(campo, ""))

    def capa(self, caminho):
        return self.capas.get(caminho)

    # ------------------------------------------------------------ alterações
    def _avisar(self, caminhos):
        if self.ao_mudar and caminhos:
            self.ao_mudar(set(caminhos))

    def _definir(self, faixa, campo, valor):
        """Grava no rascunho sem avisar. Valor igual ao do arquivo = sem rascunho."""
        atual = self.tags.get(faixa.caminho)
        if valor.strip() == faixa.tags.get(campo, ""):
            if atual and campo in atual:
                del atual[campo]
                if not atual:
                    del self.tags[faixa.caminho]
                return True
            return False
        if atual is None:
            atual = self.tags[faixa.caminho] = {}
        if atual.get(campo) == valor:
            return False
        atual[campo] = valor
        return True

    def definir(self, faixas, campo, valor):
        """Mesmo valor para várias faixas (edição no painel)."""
        self._avisar([f.caminho for f in faixas if self._definir(f, campo, valor)])

    def definir_por_faixa(self, itens):
        """Valores diferentes por faixa: itens = [(faixa, {campo: valor}), ...]."""
        mudou = set()
        for faixa, valores in itens:
            for campo, valor in valores.items():
                if self._definir(faixa, campo, valor):
                    mudou.add(faixa.caminho)
        self._avisar(mudou)

    def fotografar(self, caminhos, campo):
        return {c: self.tags.get(c, {}).get(campo, FALTA) for c in caminhos}

    def restaurar(self, foto, campo):
        """Volta um campo ao estado de uma fotografia (ex.: usuário apagou o que digitou)."""
        mudou = set()
        for caminho, valor in foto.items():
            atual = self.tags.get(caminho, {})
            if valor is FALTA:
                if campo in atual:
                    del atual[campo]
                    mudou.add(caminho)
                if caminho in self.tags and not self.tags[caminho]:
                    del self.tags[caminho]
            elif atual.get(campo) != valor:
                self.tags.setdefault(caminho, {})[campo] = valor
                mudou.add(caminho)
        self._avisar(mudou)

    def definir_capa(self, caminhos, acao):
        """acao: ("definir", dados, mime), ("remover",) ou None (tira do rascunho)."""
        mudou = set()
        for caminho in caminhos:
            if acao is None:
                if self.capas.pop(caminho, None) is not None:
                    mudou.add(caminho)
            else:
                self.capas[caminho] = acao
                mudou.add(caminho)
        self._avisar(mudou)

    def renomear(self, mapa):
        """Arquivos renomeados no disco: as alterações pendentes vão junto para o caminho novo."""
        for antigo, novo in mapa.items():
            if antigo in self.tags:
                self.tags[novo] = self.tags.pop(antigo)
            if antigo in self.capas:
                self.capas[novo] = self.capas.pop(antigo)

    def descartar(self, caminhos=None):
        alvo = self.caminhos() if caminhos is None else set(caminhos) & self.caminhos()
        for caminho in alvo:
            self.tags.pop(caminho, None)
            self.capas.pop(caminho, None)
        self._avisar(alvo)

    # ------------------------------------------------------------ salvar
    def validar(self):
        """[(caminho, campo, mensagem)] dos valores inválidos."""
        erros = []
        for caminho, valores in self.tags.items():
            for campo, valor in valores.items():
                ok, mensagem = validar_valor(campo, valor)
                if not ok:
                    erros.append((caminho, campo, mensagem))
        return erros

    def trabalhos(self):
        """Lista do que gravar: [(caminho, {campo: valor normalizado}, acao_capa | None)]."""
        lista = []
        for caminho in sorted(self.caminhos()):
            tags = {campo: validar_valor(campo, valor)[1]
                    for campo, valor in self.tags.get(caminho, {}).items()}
            lista.append((caminho, tags, self.capas.get(caminho)))
        return lista

    def aplicar_registros(self, registros, faixas_por_caminho):
        """
        Coloca no rascunho os valores de um registro de desfazer/refazer.
        Nada é gravado: o usuário revisa e decide se salva.
        """
        mudou = set()
        for caminho, tags, capa in registros:
            faixa = faixas_por_caminho.get(caminho)
            if faixa is None:
                continue
            for campo, valor in tags.items():
                if self._definir(faixa, campo, valor):
                    mudou.add(caminho)
            if capa is not SEM_CAPA:
                self.capas[caminho] = ("remover",) if capa is None else ("definir", capa[0], capa[1])
                mudou.add(caminho)
        self._avisar(mudou)
        return mudou


def executar_salvamento(trabalhos, progresso=None, mtimes=None):
    """
    Grava os trabalhos nos arquivos. Roda em segundo plano (ou direto, ao fechar o app).
    mtimes: {caminho: st_mtime_ns esperado}. Se o arquivo mudou no disco desde então,
    ele NÃO é gravado (vira falha) para não sobrescrever a alteração de outro programa.
    Devolve (registros_para_desfazer, falhas {caminho: erro}, faixas relidas do disco).
    """
    registros, falhas = [], {}
    mtimes = mtimes or {}
    total = len(trabalhos)
    for i, (caminho, tags, capa) in enumerate(trabalhos, start=1):
        try:
            faixa = carregar(caminho)
            if faixa is None:
                raise ValueError("arquivo inválido ou não suportado")
            esperado = mtimes.get(caminho)
            if esperado is not None and faixa.mtime != esperado:
                raise ArquivoModificado("o arquivo foi alterado por outro programa")
            capa_antes = ler_capa(caminho) if capa else SEM_CAPA
            registro = (caminho, {campo: faixa.tags[campo] for campo in tags}, capa_antes)
            salvar(caminho, tags, capa)          # tags + capa num único save
            registros.append(registro)
        except Exception as erro:          # somente leitura, em uso por outro programa...
            falhas[caminho] = str(erro)
        if progresso:
            progresso(i, total)
    faixas, _ = carregar_varios([t[0] for t in trabalhos])
    return registros, falhas, faixas
