// Implementação MÍNIMA do casamento de faixas e das posições do Discogs, só para a ponte simulada.
// A lógica real (busca.py e discogs.py na v2) é do núcleo Rust.

import type { CampoTag } from "../api";
import type { Atribuicao, Detalhe, FaixaBusca, Mudancas } from "./tipos";

// --- posições do Discogs (discogs.interpretar_posicao e numerar) ---
type Posicao = { tipo: "lado"; letra: string; numero: number } | { tipo: "disco"; disco: number; numero: number } | { tipo: "faixa"; numero: number };

export function interpretarPosicao(texto: string): Posicao | null {
  const t = (texto ?? "").trim();
  if (!t) return null;
  let m = /^(?:CD|DVD|LP|Disc|Disco)?\s*(\d+)\s*[-./]\s*(\d+)[a-z]?$/i.exec(t);
  if (m) return { tipo: "disco", disco: Number(m[1]), numero: Number(m[2]) };
  m = /^(\d+)[a-z]?$/.exec(t);
  if (m) return { tipo: "faixa", numero: Number(m[1]) };
  m = /^([A-Za-z])\s*(\d*)(?:[.\-]?[a-z])?$/.exec(t);
  if (m && (m[2] || !"IVX".includes(m[1].toUpperCase()))) return { tipo: "lado", letra: m[1].toUpperCase(), numero: Number(m[2] || 0) };
  return null;
}

/** [disco, faixa] para as posições na ordem do release. Vinil: A/B = disco 1, C/D = disco 2, e a faixa conta dentro do disco. */
export function numerar(posicoes: Array<string | null | undefined>): Array<[number, number]> {
  const ps = posicoes.map((p) => (p ?? "").trim());
  const preenchidas = ps.filter(Boolean);
  const soLados = preenchidas.length > 0 && preenchidas.every((p) => /^[A-Za-z]$/.test(p));
  const contagem = new Map<number, number>();
  const usados = new Set<string>();
  const saida: Array<[number, number]> = [];
  let disco = 1;
  for (const pos of ps) {
    let tipo = interpretarPosicao(pos);
    if (tipo === null && soLados && pos) tipo = { tipo: "lado", letra: pos.toUpperCase(), numero: 0 };
    let numero: number;
    if (tipo && (tipo.tipo === "disco" || tipo.tipo === "faixa")) {
      if (tipo.tipo === "disco") disco = tipo.disco || 1;
      numero = tipo.numero;
      if (usados.has(`${disco}:${numero}`) || !numero) numero = (contagem.get(disco) ?? 0) + 1;
    } else {
      if (tipo) disco = Math.floor((tipo.letra.charCodeAt(0) - 65) / 2) + 1;
      numero = (contagem.get(disco) ?? 0) + 1;
    }
    contagem.set(disco, Math.max(contagem.get(disco) ?? 0, numero));
    usados.add(`${disco}:${numero}`);
    saida.push([disco, numero]);
  }
  return saida;
}

// --- release simulado e casamento ---
export interface FaixaDoRelease {
  titulo: string;
  artista: string;
  /** Número na mídia (MusicBrainz). No Discogs vem de `posicao` ("A1", "2-05"...). */
  numero?: number;
  disco?: number;
  posicao?: string;
}

export interface ReleaseSimulado {
  id: string;
  /** Texto da lista de resultados. */
  descricao: string;
  titulo: string;
  artista: string;
  data: string;
  generos: string[];
  gravadora: string;
  faixas: FaixaDoRelease[];
  /** Página do release no Discogs (link de atribuição). */
  url?: string;
}

interface Par {
  titulo: string;
  artista: string;
  numero: number;
  disco: number;
  totalDisco: number;
}

const normalizar = (t: string): string => t.toLowerCase().replace(/[\W_]+/gu, " ").trim();
const numeroDe = (v: string | undefined): number => Number(/^\s*(\d+)/.exec(v ?? "")?.[1] ?? 0);

function bigramas(t: string): string[] {
  const n = normalizar(t);
  return n.length < 2 ? [n] : Array.from({ length: n.length - 1 }, (_, i) => n.slice(i, i + 2));
}
const parecidos = (a: string, b: string): boolean => {
  const A = bigramas(a), B = bigramas(b);
  const resto = [...B];
  let comum = 0;
  for (const g of A) {
    const i = resto.indexOf(g);
    if (i >= 0) { comum++; resto.splice(i, 1); }
  }
  return (2 * comum) / (A.length + B.length) >= 0.6;
};

function paresDoRelease(r: ReleaseSimulado, discogs: boolean): { pares: Par[]; totalDiscos: number } {
  const numeracao = discogs ? numerar(r.faixas.map((f) => f.posicao)) : null;
  const base = r.faixas.map((f, i) => ({
    titulo: f.titulo, artista: f.artista,
    disco: numeracao ? numeracao[i][0] : f.disco ?? 1,
    numero: numeracao ? numeracao[i][1] : f.numero ?? i + 1,
  }));
  const porDisco = new Map<number, number>();
  for (const f of base) porDisco.set(f.disco, (porDisco.get(f.disco) ?? 0) + 1);
  return { pares: base.map((f) => ({ ...f, totalDisco: porDisco.get(f.disco) ?? 0 })), totalDiscos: porDisco.size || 1 };
}

/** Casamento 1:1: mesmo título, depois (disco, nº); o Discogs ainda tenta o título parecido e a ordem. */
function casar(faixas: FaixaBusca[], pares: Par[], discogs: boolean): Array<{ par: Par; porTitulo: boolean } | null> {
  const usadas = new Set<number>();
  const achadas: Array<{ par: Par; porTitulo: boolean } | null> = faixas.map(() => null);
  const chaves = faixas.map((f) => ({ disco: numeroDe(f.valores.discnumber) || 1, numero: numeroDe(f.valores.tracknumber), titulo: normalizar(f.valores.title ?? "") }));
  const marcar = (k: number, i: number, porTitulo: boolean) => { achadas[k] = { par: pares[i], porTitulo }; usadas.add(i); };
  chaves.forEach((c, k) => {
    const i = pares.findIndex((p, j) => !usadas.has(j) && c.titulo && normalizar(p.titulo) === c.titulo);
    if (i >= 0) marcar(k, i, true);
  });
  if (discogs) chaves.forEach((c, k) => {
    if (achadas[k] || !c.titulo) return;
    const i = pares.findIndex((p, j) => !usadas.has(j) && parecidos(c.titulo, p.titulo));
    if (i >= 0) marcar(k, i, true);
  });
  chaves.forEach((c, k) => {
    if (achadas[k] || !c.numero) return;
    const i = pares.findIndex((p, j) => !usadas.has(j) && p.disco === c.disco && p.numero === c.numero);
    if (i >= 0) marcar(k, i, false);
  });
  return achadas;
}

const ano = (t: string): string => (/^\d{4}(-\d{2}(-\d{2})?)?$/.test(t) ? t : /^\d{4}/.test(t) ? t.slice(0, 4) : "");

/** Release analisado contra as faixas, no formato que a ponte devolve (busca.analisar / discogs.analisar). */
export function analisarSimulado(faixas: FaixaBusca[], release: ReleaseSimulado, discogs: boolean, atribuicao: Atribuicao): Detalhe {
  const { pares, totalDiscos } = paresDoRelease(release, discogs);
  const doAlbum: Partial<Record<CampoTag, string>> = {
    album: release.titulo, albumartist: release.artista, date: ano(release.data), genre: release.generos.join("; "),
  };
  const alteracoes: Mudancas[] = [];
  const casadas: string[] = [], semPar: string[] = [];
  const achadas = casar(faixas, pares, discogs);
  faixas.forEach((f, k) => {
    const a = achadas[k];
    if (!a) { semPar.push(f.id); return; }
    casadas.push(f.id);
    const { par, porTitulo } = a;
    const novos: Partial<Record<CampoTag, string>> = { ...doAlbum };
    if (porTitulo || !f.valores.title || parecidos(f.valores.title, par.titulo)) novos.title = par.titulo;
    novos.artist = par.artista;
    novos.tracknumber = `${par.numero}/${par.totalDisco}`;
    if (totalDiscos > 1) novos.discnumber = `${par.disco}/${totalDiscos}`;
    if (discogs && release.gravadora) novos.gravadora = release.gravadora;
    const mudancas: Partial<Record<CampoTag, string>> = {};
    for (const [campo, v] of Object.entries(novos) as Array<[CampoTag, string]>) {
      if (v && v !== (f.valores[campo] ?? "")) mudancas[campo] = v;
    }
    if (Object.keys(mudancas).length) alteracoes.push({ id: f.id, mudancas });
  });
  return { atribuicao, alteracoes, casadas, semPar };
}
