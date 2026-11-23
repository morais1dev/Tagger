// Tipos da janela "Buscar tags online" (G-01 a G-12). A rede, o casamento de faixas e as regras dos
// serviços são do núcleo Rust (busca.py, discogs.py e online.py na v2); a interface só usa a ponte.

import type { CampoTag } from "../api";

export type Fonte = "musicbrainz" | "discogs";
export const MUSICBRAINZ: Fonte = "musicbrainz";
export const DISCOGS: Fonte = "discogs";
export const FONTES: readonly Fonte[] = [MUSICBRAINZ, DISCOGS];

export const NOMES: Record<Fonte, string> = { musicbrainz: "MusicBrainz", discogs: "Discogs" };
/** Dica do botão de cada serviço disponível (e primeira mensagem ao trocar de fonte). */
export const DESCRICOES: Record<Fonte, string> = {
  musicbrainz: "Banco de dados aberto, com capas do Cover Art Archive.",
  discogs: "Bom para prensagens privadas, vinis e edições raras.",
};

export const ATRIBUICAO_MUSICBRAINZ = "Dados do MusicBrainz · capas do Cover Art Archive.";
export const ATRIBUICAO_DISCOGS = "Data provided by Discogs.";
export const URL_SITE_DISCOGS = "https://www.discogs.com";
export const DICA_SEM_DISCOGS =
  "Busca no Discogs indisponível: faltam as credenciais. Cole o seu token pessoal em Configurações → Serviços online.";
/** Mensagem do erro "nada encontrado": com a alternativa ligada, é ela que dispara a busca no Discogs. */
export const NAO_ENCONTRADO = "Nada encontrado.";

/** Estado de um serviço que precisa de credencial (credenciais.EstadoServico). */
export interface EstadoServico {
  disponivel: boolean;
  /** Texto do tooltip do botão desligado; null/ausente = a dica padrão. */
  dica?: string | null;
}
export interface EstadosServicos {
  discogs: EstadoServico;
}

export const ROTULOS: Record<CampoTag, string> = {
  title: "Título", artist: "Artista", album: "Álbum", albumartist: "Artista do álbum", tracknumber: "Faixa",
  discnumber: "Disco", date: "Ano", genre: "Gênero", composer: "Compositor", lyricist: "Letrista",
  comment: "Comentário", lyrics: "Letra", gravadora: "Gravadora",
};

/** Erro de rede ou de resposta já com mensagem legível (busca.ErroBusca). */
export class ErroBusca extends Error {
  constructor(mensagem: string) {
    super(mensagem);
    this.name = "ErroBusca";
  }
}

/** Uma faixa da seleção, com as tags já com as alterações pendentes (o que o usuário está vendo). */
export interface FaixaBusca {
  id: string;
  nome: string;
  valores: Partial<Record<CampoTag, string>>;
}

export interface Termos {
  artista: string;
  album: string;
  titulo: string;
}

/** Um release encontrado; `descricao` já vem montada pelo núcleo ("Artista — Álbum  (2020, BR, 10 faixas, Selo)"). */
export interface Candidato {
  id: string;
  descricao: string;
}

export interface Atribuicao {
  texto: string;
  /** Link do release (Discogs); só é mostrado como link se for https de um domínio do serviço. */
  url?: string;
  /** Texto do link; padrão "Ver o release no Discogs" (antes de escolher um release é "discogs.com", como na v2). */
  textoLink?: string;
}

export interface Mudancas {
  id: string;
  mudancas: Partial<Record<CampoTag, string>>;
}

/** Release analisado contra as faixas (fonte.detalhar + fonte.analisar). */
export interface Detalhe {
  atribuicao: Atribuicao;
  /** Só o que difere do que a faixa mostra; só as faixas que casaram recebem alguma coisa. */
  alteracoes: Mudancas[];
  casadas: string[];
  /** Faixas sem par: não mudam (nem a capa). */
  semPar: string[];
}

export interface Capa {
  dados: Uint8Array;
  mime: "image/jpeg" | "image/png";
}

/** O que a janela devolve ao aplicar: vai para o rascunho (nada é gravado). */
export interface Resultado {
  alteracoes: Mudancas[];
  capa: Capa | null;
  /** Ids que recebem a capa: só as faixas casadas. */
  casadas: string[];
  semPar: string[];
}

export interface PonteBusca {
  /** Levanta ErroBusca (mensagem legível) em falha de rede ou resposta estranha; `NAO_ENCONTRADO` quando não há nada. */
  buscar(fonte: Fonte, termos: Termos, sinal: AbortSignal): Promise<Candidato[]>;
  detalhar(fonte: Fonte, candidato: string, faixas: FaixaBusca[], sinal: AbortSignal): Promise<Detalhe>;
  /** Capa do Cover Art Archive (só o MusicBrainz); null = o release não tem capa. */
  baixarCapa(candidato: string, sinal: AbortSignal): Promise<Capa | null>;
}

/** Links só são links se forem https de um dos domínios do serviço (online.url_segura). */
export function urlSegura(url: string | undefined, dominios: readonly string[]): string {
  if (!url) return "";
  try {
    const u = new URL(url);
    const host = u.hostname.toLowerCase();
    const bate = dominios.some((d) => host === d || host.endsWith(`.${d}`));
    return u.protocol === "https:" && !u.username && !u.password && bate ? u.toString() : "";
  } catch {
    return "";
  }
}

export const DOMINIOS_DISCOGS = ["discogs.com"] as const;

/** Valor do campo na primeira faixa que o tem (gui.busca._primeiro_valor). */
export function primeiroValor(faixas: readonly FaixaBusca[], campo: CampoTag): string {
  for (const f of faixas) if (f.valores[campo]) return f.valores[campo] as string;
  return "";
}
