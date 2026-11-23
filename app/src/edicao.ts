/** Regras do painel de edição que não dependem de React: valor comum à seleção e capa mostrada. */
import { type CampoTag, type Capa, type Faixa, valorDoCampo } from "./api";

/** Nome de cada campo no painel (`metadata.CAMPOS` na v2). */
export const ROTULOS: Record<CampoTag, string> = {
  title: "Título", artist: "Artista", album: "Álbum", albumartist: "Artista do álbum", tracknumber: "Faixa",
  discnumber: "Disco", date: "Ano", genre: "Gênero", composer: "Compositor", lyricist: "Letrista",
  comment: "Comentário", lyrics: "Letra", gravadora: "Gravadora",
};

/** Ordem do painel: linhas largas, os quatro curtos lado a lado, mais linhas largas e os de várias linhas. */
export const CAMPOS_LARGOS_1: CampoTag[] = ["title", "artist", "album", "albumartist"];
export const CAMPOS_PARES: CampoTag[] = ["tracknumber", "discnumber", "date", "genre"];
export const CAMPOS_LARGOS_2: CampoTag[] = ["composer", "lyricist", "gravadora"];
/** Campo de várias linhas -> linhas visíveis. */
export const CAMPOS_MULTILINHA: Partial<Record<CampoTag, number>> = { comment: 3, lyrics: 7 };

export const TEXTO_VARIOS = "‹vários valores›";
export const TEXTO_VARIAS_CAPAS = "‹várias capas›";

export interface ValorComum {
  /** Valor igual em todas as faixas; "" quando há vários. */
  texto: string;
  varios: boolean;
}

export function valorComum(faixas: readonly Faixa[], campo: CampoTag): ValorComum {
  const valores = new Set(faixas.map((f) => valorDoCampo(f, campo)));
  return valores.size > 1 ? { texto: "", varios: true } : { texto: [...valores][0] ?? "", varios: false };
}

/** Quem tem pendência neste campo (marca ● ao lado do rótulo). */
export function campoPendente(faixas: readonly Faixa[], campo: CampoTag): boolean {
  return faixas.some((f) => campo in f.pendentes);
}

/** A capa de uma faixa já considerando a pendente: Capa, ou null se não tem. */
export function capaEfetiva(faixa: Faixa): Capa | null {
  if (faixa.capaPendente === "definir") return faixa.capaNova ?? null;
  if (faixa.capaPendente === "remover") return null;
  return faixa.temCapa ? (faixa.capa ?? null) : null;
}

export type CapaMostrada =
  | { tipo: "capa"; capa: Capa }
  | { tipo: "sem" }
  | { tipo: "varias" };

/** O que o quadro mostra para a seleção: a capa se for a mesma em todas, "Sem capa" ou "‹várias capas›". */
export function capaDaSelecao(faixas: readonly Faixa[]): CapaMostrada {
  if (faixas.length === 0) return { tipo: "sem" };
  const efetivas = faixas.map(capaEfetiva);
  const chave = (c: Capa | null) => (c ? c.url : "");
  if (!efetivas.every((c) => chave(c) === chave(efetivas[0]))) return { tipo: "varias" };
  return efetivas[0] ? { tipo: "capa", capa: efetivas[0] } : { tipo: "sem" };
}

/** Capa pendente na seleção: "Nova capa" ou "Capa será removida" (todas as pendentes são remoções). */
export function textoCapaPendente(faixas: readonly Faixa[]): string | null {
  const pendentes = faixas.filter((f) => f.capaPendente !== undefined);
  if (pendentes.length === 0) return null;
  return pendentes.every((f) => f.capaPendente === "remover") ? "Capa será removida" : "Nova capa";
}

export function temAlgumaCapa(faixas: readonly Faixa[]): boolean {
  return faixas.some((f) => capaEfetiva(f) !== null || f.temCapa);
}
