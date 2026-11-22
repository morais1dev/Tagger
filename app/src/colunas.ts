/** Colunas da tabela: mesmas chaves, títulos, larguras e visibilidade de `tabela.COLUNAS` na v2. */
import { type CampoTag, type Faixa, CAMPOS_TAG, nomeDaPasta, nomeDoArquivo, temPendencia, valorDoCampo } from "./api";

export type ChaveColuna = CampoTag | "duracao" | "bitrate" | "arquivo" | "pasta" | "capa" | "estado";

export interface Coluna {
  chave: ChaveColuna;
  titulo: string;
  /** Largura inicial em px; null = a coluna estica (Título). */
  largura: number | null;
  padrao: boolean;
}

export const COLUNAS: Coluna[] = [
  { chave: "tracknumber", titulo: "Nº", largura: 52, padrao: true },
  { chave: "title", titulo: "Título", largura: null, padrao: true },
  { chave: "artist", titulo: "Artista", largura: 170, padrao: true },
  { chave: "album", titulo: "Álbum", largura: 190, padrao: true },
  { chave: "albumartist", titulo: "Artista do álbum", largura: 170, padrao: false },
  { chave: "discnumber", titulo: "Disco", largura: 60, padrao: false },
  { chave: "date", titulo: "Ano", largura: 64, padrao: true },
  { chave: "genre", titulo: "Gênero", largura: 120, padrao: true },
  { chave: "composer", titulo: "Compositor", largura: 150, padrao: false },
  { chave: "lyricist", titulo: "Letrista", largura: 150, padrao: false },
  { chave: "gravadora", titulo: "Gravadora", largura: 150, padrao: false },
  { chave: "comment", titulo: "Comentário", largura: 200, padrao: false },
  { chave: "lyrics", titulo: "Letra", largura: 200, padrao: false },
  { chave: "duracao", titulo: "Duração", largura: 76, padrao: true },
  { chave: "bitrate", titulo: "Bitrate", largura: 84, padrao: false },
  { chave: "arquivo", titulo: "Arquivo", largura: 220, padrao: false },
  { chave: "pasta", titulo: "Pasta", largura: 180, padrao: false },
  { chave: "capa", titulo: "Capa", largura: 52, padrao: true },
  { chave: "estado", titulo: "", largura: 28, padrao: true },
];

export const COLUNAS_FIXAS: ReadonlySet<ChaveColuna> = new Set<ChaveColuna>(["title", "estado"]);   // não podem ser escondidas
export const COLUNAS_MONO: ReadonlySet<ChaveColuna> = new Set<ChaveColuna>(["tracknumber", "discnumber", "date", "duracao", "bitrate"]);
export const COLUNAS_DIREITA: ReadonlySet<ChaveColuna> = new Set<ChaveColuna>(["duracao", "bitrate"]);
export const COLUNAS_SECUNDARIAS: ReadonlySet<ChaveColuna> = new Set<ChaveColuna>([
  "tracknumber", "discnumber", "album", "date", "genre", "duracao", "bitrate", "pasta",
  "composer", "lyricist", "gravadora", "comment", "lyrics",
]);
const TEXTO_LONGO: ReadonlySet<ChaveColuna> = new Set<ChaveColuna>(["comment", "lyrics"]);
export const LARGURA_MINIMA = 28;

export function colunasPadrao(): ChaveColuna[] {
  return COLUNAS.filter((c) => c.padrao).map((c) => c.chave);
}

export const ehTag = (chave: ChaveColuna): chave is CampoTag => (CAMPOS_TAG as readonly string[]).includes(chave);

/** Se a célula é uma tag com alteração pendente (destaque na cor de destaque). */
export function celulaPendente(faixa: Faixa, chave: ChaveColuna): boolean {
  return ehTag(chave) && chave in faixa.pendentes;
}

export function duracaoFormatada(segundos: number): string {
  const total = Math.round(segundos);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/** Texto da célula, como em `ModeloFaixas.data` (DisplayRole). Capa e estado não têm texto. */
export function textoDaCelula(faixa: Faixa, chave: ChaveColuna): string {
  switch (chave) {
    case "capa":
    case "estado":
      return "";
    case "duracao":
      return duracaoFormatada(faixa.duracao);
    case "bitrate":
      return faixa.bitrate ? `${faixa.bitrate} kbps` : "—";
    case "arquivo":
      return nomeDoArquivo(faixa);
    case "pasta":
      return nomeDaPasta(faixa);
  }
  const valor = valorDoCampo(faixa, chave);
  if (chave === "tracknumber") return valor.split("/")[0] || "—";
  if (chave === "title") return valor || nomeDoArquivo(faixa);
  if (TEXTO_LONGO.has(chave)) return valor ? valor.split(/\r?\n/)[0] : "—";
  return valor || "—";
}

/** Célula em cor apagada: campo vazio ou coluna secundária (a pendente usa a cor normal). */
export function celulaApagada(faixa: Faixa, chave: ChaveColuna): boolean {
  if (celulaPendente(faixa, chave)) return false;
  if (!ehTag(chave)) return COLUNAS_SECUNDARIAS.has(chave);
  return !valorDoCampo(faixa, chave) || COLUNAS_SECUNDARIAS.has(chave);
}

export function tituloVazio(faixa: Faixa): boolean {
  return !valorDoCampo(faixa, "title");
}

/** Tem capa levando em conta a pendente. */
export function temCapaEfetiva(faixa: Faixa): boolean {
  if (faixa.capaPendente === "definir") return true;
  if (faixa.capaPendente === "remover") return false;
  return faixa.temCapa;
}

export function tooltipDaCelula(faixa: Faixa, chave: ChaveColuna): string | undefined {
  if (chave === "title" || chave === "arquivo" || chave === "pasta") return faixa.caminho;
  if (TEXTO_LONGO.has(chave)) return ehTag(chave) ? valorDoCampo(faixa, chave) || undefined : undefined;
  if (chave === "capa") return faixa.temCapa ? "Tem capa" : "Sem capa";      // como na v2: a do arquivo, não a pendente
  if (chave === "estado" && temPendencia(faixa)) return "Alterado, não salvo";
  return undefined;
}
