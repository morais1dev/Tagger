"""
Histórico de desfazer/refazer: as pilhas e as regras de qual pilha recebe o quê.

Sem Qt e sem tocar em arquivos: a janela faz o trabalho (gravar, mover) e conta o resultado
a este módulo, que decide o que fica em cada pilha. Cada item de uma pilha é uma lista de
registros de tags [(caminho, {campo: valor anterior}, capa anterior)] (veja
rascunho.executar_salvamento) ou uma Renomeacao (arquivos renomeados/movidos).

Desfazer e refazer de tags NÃO gravam na hora: o registro vira alteração pendente no Rascunho
(Historico.preparar) e só vale depois de "Salvar". Enquanto isso o registro fica em `pendente`
e, se o usuário descartar, volta para a pilha de onde saiu. Renomear/mover não passa pelo
Rascunho: desfazer/refazer move de volta na hora.
"""

from tagger.nucleo.rascunho import Renomeacao, migrar_historico

# Tipos de ação: o que está sendo desfeito/refeito ou, no caso de "organizar", o que acabou de ser feito.
DESFAZER = "desfazer"
REFAZER = "refazer"
ORGANIZAR = "organizar"

# O que Historico.retirar devolve junto com o item
NADA = "nada"
DESCARTAR = "descartar"      # havia alteração pendente: o desfazer só descarta
TAGS = "tags"                # item é uma lista de registros de tags
ARQUIVOS = "arquivos"        # item é uma Renomeacao


class Historico:
    def __init__(self):
        self.desfazer = []
        self.refazer = []
        self.pendente = None        # (registros, DESFAZER | REFAZER) aguardando "Salvar"

    # ------------------------------------------------------------ consulta
    def pode_desfazer(self, rascunho_pendente):
        return rascunho_pendente or bool(self.desfazer) or self.pendente is not None

    def pode_refazer(self, rascunho_pendente):
        return not rascunho_pendente and bool(self.refazer)

    def _pilhas(self, tipo):
        """(pilha de onde o item sai, pilha oposta onde o resultado entra)."""
        if tipo == DESFAZER:
            return self.desfazer, self.refazer
        return self.refazer, self.desfazer

    # ------------------------------------------------------------ nova pasta
    def limpar(self):
        """Abrir outra pasta: nada do que veio antes pode ser desfeito."""
        self.pendente = None
        self.desfazer.clear()
        self.refazer.clear()

    # ------------------------------------------------------------ gravação
    def registrar_gravacao(self, registros_ok):
        """Depois de gravar as tags. `registros_ok`: os registros dos arquivos que gravaram sem falha.
        Se a gravação confirmava um desfazer, o registro vai para o refazer (e vice-versa); uma
        gravação nova vai para o desfazer e invalida o refazer. Sem registros (tudo falhou) as pilhas
        não mudam. Em qualquer caso o pendente é encerrado: o que falhou fica só no Rascunho."""
        if registros_ok:
            tipo = self.pendente[1] if self.pendente else None
            if tipo == DESFAZER:
                self.refazer.append(registros_ok)
            else:
                self.desfazer.append(registros_ok)
                if tipo != REFAZER:
                    self.refazer.clear()
        self.pendente = None

    def registrar_renomeacao(self, feitos):
        """Depois de renomear ou organizar arquivos (uma ação nova): [(antigo, novo)] dos que deram certo."""
        if feitos:
            self.desfazer.append(Renomeacao(list(feitos)))
            self.refazer.clear()

    # ------------------------------------------------------------ desfazer / refazer
    def retirar(self, tipo, rascunho_vazio):
        """Decide o que fazer com Ctrl+Z (DESFAZER) ou Ctrl+Y (REFAZER). Devolve (ação, item):
        - (DESCARTAR, None): só no desfazer, com alteração pendente (do rascunho ou de um desfazer
          não confirmado): o desfazer descarta em vez de voltar mais um passo;
        - (TAGS, registros) ou (ARQUIVOS, Renomeacao): o item foi tirado da pilha;
        - (NADA, None): nada a fazer (refazer com pendências, ou pilha vazia)."""
        if tipo == DESFAZER and (not rascunho_vazio or self.pendente):
            return DESCARTAR, None
        origem, _oposta = self._pilhas(tipo)
        if tipo == REFAZER and not rascunho_vazio:
            return NADA, None
        if not origem:
            return NADA, None
        item = origem.pop()
        return (ARQUIVOS if isinstance(item, Renomeacao) else TAGS), item

    def preparar(self, registros, tipo, rascunho, faixas_por_caminho):
        """Coloca os registros no Rascunho como alteração pendente. Devolve o conjunto de caminhos
        que mudaram. Se nada mudou (os arquivos já estão assim) o item NÃO volta à pilha e não há
        pendente: a janela só avisa."""
        mudou = rascunho.aplicar_registros(registros, faixas_por_caminho)
        if mudou:
            self.pendente = (registros, tipo)
        return mudou

    def descartar_pendente(self):
        """Descartar/Esc: o desfazer ou refazer não confirmado volta à pilha de onde saiu."""
        if self.pendente:
            registros, tipo = self.pendente
            origem, _oposta = self._pilhas(tipo)
            origem.append(registros)
            self.pendente = None

    # ------------------------------------------------------------ desfazer/refazer de arquivos movidos
    def concluir_reversao(self, tipo, item, feitos, falhas):
        """Depois de mover de volta (ou de novo) os arquivos de `item` (Renomeacao já retirada da pilha).
        `feitos`: [(de, para)] dos movimentos feitos; `falhas`: {caminho: erro}, com a chave sendo o
        caminho atual (o "novo" do item). O que deu certo vai para a pilha oposta; o que falhou volta
        à de origem, para tentar de novo."""
        origem, oposta = self._pilhas(tipo)
        if feitos:
            oposta.append(Renomeacao(list(feitos)))
        if falhas:
            origem.append(Renomeacao([(a, n) for a, n in item.pares if n in falhas]))

    def registrar_movimento_interrompido(self, tipo, feitos, item=None):
        """A tarefa de mover quebrou no meio; `feitos` é o que já saiu do lugar. `tipo` é ORGANIZAR
        (ação nova) ou DESFAZER/REFAZER (com o `item` retirado da pilha). Mesmo parcial, o que foi
        movido entra no histórico; numa ação nova o refazer é invalidado; numa reversão o que
        não voltou continua na pilha de onde saiu."""
        feitos = list(feitos)
        if tipo == ORGANIZAR:
            if feitos:
                self.desfazer.append(Renomeacao(feitos))
            self.refazer.clear()
            return
        origem, oposta = self._pilhas(tipo)
        if feitos:
            oposta.append(Renomeacao(feitos))
        feitos_inversos = {(d, o) for o, d in feitos}
        faltam = [(a, n) for a, n in item.pares if (a, n) not in feitos_inversos]
        if faltam:
            origem.append(Renomeacao(faltam))

    # ------------------------------------------------------------ arquivos renomeados por fora do histórico
    def migrar(self, mapa):
        """Atualiza os caminhos de tudo (pilhas e pendente) depois de renomear arquivos: {antigo: novo}."""
        migrar_historico(self.desfazer, mapa)
        migrar_historico(self.refazer, mapa)
        if self.pendente:
            registros, tipo = self.pendente
            pilha = [registros]
            migrar_historico(pilha, mapa)
            self.pendente = (pilha[0], tipo)
