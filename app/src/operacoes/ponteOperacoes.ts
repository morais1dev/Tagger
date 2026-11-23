// Ponte simulada das operações em lote. Nada toca o disco: os planos vêm da implementação mínima em
// padroesSimulados.ts e o núcleo Rust (tagger-core) entra no lugar com a mesma interface.

import type { AnaliseExtras, PonteOperacoes } from "./tipos";
import { camposDoPadrao, planejarOrganizacao, planejarRenomeacao, previaTagsDoNome, type OpcoesSimuladas } from "./padroesSimulados";

export interface OpcoesPonteSimulada extends OpcoesSimuladas {
  /** O que o seletor de pasta devolve (null = o usuário cancelou). */
  pastaEscolhida?: string | null;
  /** Análise de extras por caminho; arquivo sem entrada não tem nada de extra. */
  extras?: Record<string, AnaliseExtras>;
}

export interface PonteOperacoesSimulada extends PonteOperacoes {
  /** Pastas que a interface mandou abrir no Explorer (para os testes). */
  readonly pastasAbertas: string[];
}

/** Mensagem de um erro de padrão (campo desconhecido etc.), como o núcleo a devolveria. */
const comoErro = (e: unknown): { erro: string } => ({ erro: e instanceof Error ? e.message : String(e) });

export function criarPonteSimulada(opcoes: OpcoesPonteSimulada = {}): PonteOperacoesSimulada {
  const pastasAbertas: string[] = [];
  return {
    pastasAbertas,
    previaRenomear: async (itens, padrao) => {
      try {
        return planejarRenomeacao(itens, padrao, new Set(opcoes.existentes ?? []));
      } catch (e) {
        return comoErro(e);
      }
    },
    previaTagsDoNome: async (itens, padrao, o) => {
      try {
        return previaTagsDoNome(itens, padrao, o);
      } catch (e) {
        return comoErro(e);
      }
    },
    previaOrganizar: async (itens, padrao, pasta, levarCapa) => {
      try {
        // ordem da v2: campo desconhecido, nenhum campo, destino vazio, e só então planejar
        if (!camposDoPadrao(padrao).length) throw new Error("Use pelo menos um campo, ex.: {artist}/{album}/{title}");
        if (!pasta.trim()) throw new Error("Escolha a pasta de destino.");
        return planejarOrganizacao(itens, padrao, pasta, levarCapa, opcoes);
      } catch (e) {
        return comoErro(e);
      }
    },
    escolherPasta: async (inicial) => (opcoes.pastaEscolhida === undefined ? inicial : opcoes.pastaEscolhida),
    abrirPasta: async (caminho) => {
      pastasAbertas.push(caminho);
    },
    analisarExtras: async (caminhos) =>
      caminhos.map((c) => opcoes.extras?.[c] ?? { id3v1: false, desconhecidos: false, extras: {} }),
  };
}
