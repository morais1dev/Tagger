// Tipos das operações em lote: renomear pelas tags, preencher tags pelo nome, organizar em pastas e
// limpar tags extras (F-01 a F-16). A lógica real (padrões, planos, conflitos) é do núcleo Rust;
// aqui só está o formato do que a ponte devolve e o que os diálogos mostram.

import type { CampoTag } from "../api";

/** Rótulos dos campos (metadata.CAMPOS da v2); "Faixa" e "Disco" são os números. */
export const ROTULOS: Record<CampoTag, string> = {
  title: "Título",
  artist: "Artista",
  album: "Álbum",
  albumartist: "Artista do álbum",
  tracknumber: "Faixa",
  discnumber: "Disco",
  date: "Ano",
  genre: "Gênero",
  composer: "Compositor",
  lyricist: "Letrista",
  comment: "Comentário",
  lyrics: "Letra",
  gravadora: "Gravadora",
};

/** Um arquivo da seleção, com as tags já com as alterações pendentes aplicadas (como a tabela mostra). */
export interface ItemEntrada {
  caminho: string;
  valores: Partial<Record<CampoTag, string>>;
}

/** Item de um plano de renomear/mover: `destino` nulo = não muda; `erro` preenchido = não será feito. */
export interface ItemPlano {
  origem: string;
  destino: string | null;
  erro: string;
}

/** Nome do arquivo de um caminho (aceita \ e /). */
export const nomeDeCaminho = (c: string): string => c.split(/[\\/]/).pop() ?? c;

export const itemValido = (i: ItemPlano): boolean => i.destino !== null && !i.erro;

export type PlanoRenomear = ItemPlano[];

export interface PlanoOrganizar {
  /** Pasta de destino (raiz). */
  pasta: string;
  itens: ItemPlano[];
  /** Capas (cover/folder/front) que vão junto. */
  capas: ItemPlano[];
}

/** Linha da prévia de "preencher tags pelo nome". */
export interface LinhaTagsDoNome {
  id: string;
  caminho: string;
  /** false = o nome não segue o padrão. */
  casa: boolean;
  campos: Array<{
    campo: CampoTag;
    /** Valor lido do nome. */
    novo: string;
    /** O arquivo já tinha valor e a opção "só os vazios" manteve o atual. */
    mantido: boolean;
    atual: string;
    /** Mensagem de validação (ex.: ano inválido); preenchida = o valor é ignorado. */
    erro: string;
  }>;
}

export interface PreviaTagsDoNome {
  campos: CampoTag[];
  linhas: LinhaTagsDoNome[];
}

export interface OpcoesTagsDoNome {
  sublinhado: boolean;
  soVazios: boolean;
}

/** Resultado aceito de "preencher tags pelo nome": o que vai para o rascunho (id da faixa -> campos). */
export interface ResultadoTagsDoNome {
  itens: Array<{ id: string; valores: Partial<Record<CampoTag, string>> }>;
}

export type PreviaOuErro<R> = R | { erro: string };

export function houveErro<R>(r: PreviaOuErro<R>): r is { erro: string } {
  return typeof r === "object" && r !== null && "erro" in r && typeof (r as { erro: unknown }).erro === "string";
}

/** Análise de extras de um arquivo (metadata.analisar_extras da v2). */
export interface AnaliseExtras {
  /** Tem a tag ID3v1 antiga (só MP3). */
  id3v1: boolean;
  /** Tem frames ID3 que o leitor não reconhece (só MP3). */
  desconhecidos: boolean;
  /** Chave do extra (frame, chave Vorbis ou átomo MP4) -> quantidade. */
  extras: Record<string, number>;
}

export interface OpcoesLimpeza {
  id3v1: boolean;
  desconhecidos: boolean;
  extras: boolean;
}

/** Ponte das operações em lote. A real chama o núcleo (`tagger-core`); a simulada fica em ponteOperacoes.ts. */
export interface PonteOperacoes {
  previaRenomear(itens: ItemEntrada[], padrao: string): Promise<PreviaOuErro<PlanoRenomear>>;
  previaTagsDoNome(itens: Array<ItemEntrada & { id: string }>, padrao: string, opcoes: OpcoesTagsDoNome): Promise<PreviaOuErro<PreviaTagsDoNome>>;
  previaOrganizar(itens: ItemEntrada[], padrao: string, pastaDestino: string, levarCapa: boolean): Promise<PreviaOuErro<PlanoOrganizar>>;
  /** Seletor de pasta do sistema; null = cancelou. */
  escolherPasta(inicial: string): Promise<string | null>;
  /** Abre a pasta no Explorer. */
  abrirPasta(caminho: string): Promise<void>;
  analisarExtras(caminhos: string[]): Promise<AnaliseExtras[]>;
}

/** Quantas linhas a prévia mostra; acima disso o resultado vale para todas (F-01). */
export const MAX_LINHAS_PREVIA = 500;
/** Quantos padrões recentes ficam guardados por tipo (F-07). */
export const MAX_RECENTES = 8;
/** Espera depois de parar de digitar antes de refazer a prévia. */
export const ESPERA_PREVIA_MS = 150;
