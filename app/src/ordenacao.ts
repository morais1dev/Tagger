import { type Faixa, nomeDaPasta, nomeDoArquivo, temPendencia, valorDoCampo } from "./api";
import { type ChaveColuna, ehTag } from "./colunas";

export type Direcao = "asc" | "desc";
export interface Ordem {
  chave: ChaveColuna;
  direcao: Direcao;
}

const SEM_NUMERO = 1e9;                    // sem número vai para o fim
const VAZIO = "￿";                    // texto vazio vai para o fim

function numero(texto: string): number {
  const parte = texto.split("/")[0].trim();
  return /^\d+$/.test(parte) ? Number(parte) : SEM_NUMERO;
}

/** Valor usado para ordenar a coluna (`PAPEL_ORDEM` na v2). */
export function valorDeOrdem(faixa: Faixa, chave: ChaveColuna): string | number {
  switch (chave) {
    case "tracknumber":
    case "discnumber":
      return numero(valorDoCampo(faixa, chave));
    case "duracao":
      return faixa.duracao;
    case "bitrate":
      return faixa.bitrate ?? 0;
    case "capa":
      return faixa.temCapa ? 1 : 0;
    case "estado":
      return temPendencia(faixa) ? 1 : 0;
    case "arquivo":
      return nomeDoArquivo(faixa).toLocaleLowerCase();
    case "pasta":
      return nomeDaPasta(faixa).toLocaleLowerCase();
    case "title":
      return (valorDoCampo(faixa, "title") || nomeDoArquivo(faixa)).toLocaleLowerCase();
  }
  return ehTag(chave) ? (valorDoCampo(faixa, chave) || VAZIO).toLocaleLowerCase() : 0;
}

/** Faixas na ordem pedida; sem `ordem`, a ordem de carga. Estável: empates ficam na ordem de carga. */
export function ordenar(faixas: readonly Faixa[], ordem: Ordem | null): Faixa[] {
  if (!ordem) return [...faixas];
  const sinal = ordem.direcao === "asc" ? 1 : -1;
  return faixas
    .map((faixa, posicao) => ({ faixa, posicao, valor: valorDeOrdem(faixa, ordem.chave) }))
    .sort((a, b) => {
      if (a.valor < b.valor) return -sinal;
      if (a.valor > b.valor) return sinal;
      return a.posicao - b.posicao;
    })
    .map((x) => x.faixa);
}

/** Clique no cabeçalho: coluna nova começa crescente; a mesma alterna crescente/decrescente. */
export function proximaOrdem(atual: Ordem | null, chave: ChaveColuna): Ordem {
  if (atual?.chave === chave) return { chave, direcao: atual.direcao === "asc" ? "desc" : "asc" };
  return { chave, direcao: "asc" };
}
