/**
 * Ponte entre a interface e o núcleo (`tagger-core`).
 *
 * Hoje só existe a implementação simulada (`mock/ponteSimulada.ts`). A real chamará os comandos do
 * Tauri (`invoke`) quando o core estiver pronto; a interface depende apenas desta interface, então a
 * troca não mexe nos componentes.
 */

/** Campos de tag editáveis (os mesmos de `metadata.CAMPOS` na v2). */
export const CAMPOS_TAG = [
  "title", "artist", "album", "albumartist", "tracknumber", "discnumber", "date", "genre",
  "composer", "lyricist", "comment", "lyrics", "gravadora",
] as const;
export type CampoTag = (typeof CAMPOS_TAG)[number];

export interface Faixa {
  /** Identificador estável na sessão (o caminho do arquivo). */
  id: string;
  /** Caminho completo; o nome do arquivo e da pasta-pai saem daqui. */
  caminho: string;
  /** Tags como estão no arquivo; campo ausente = vazio. */
  tags: Partial<Record<CampoTag, string>>;
  /**
   * Alterações ainda não salvas, por célula: campo -> valor novo (pode ser "", que apaga a tag).
   * Um campo presente aqui é uma célula pendente.
   */
  pendentes: Partial<Record<CampoTag, string>>;
  /** Duração em segundos. */
  duracao: number;
  /** kbps; null = desconhecido. */
  bitrate: number | null;
  temCapa: boolean;
  /** Capa pendente: "definir" (passa a ter) ou "remover" (deixa de ter); ausente = sem mudança. */
  capaPendente?: "definir" | "remover";
}

export interface Ponte {
  /** Abre uma pasta (na real, o seletor do sistema) e devolve as faixas lidas. */
  abrirPasta(): Promise<Faixa[]>;
  /** Marca um valor como pendente (alteração não salva); devolve a faixa atualizada. */
  definirPendente(id: string, campo: CampoTag, valor: string): Promise<Faixa>;
  /** Descarta todas as pendências dessas faixas; devolve as faixas atualizadas. */
  descartarPendencias(ids: string[]): Promise<Faixa[]>;
}

/** Valor mostrado/ordenado de um campo: o pendente, se houver, senão o do arquivo. */
export function valorDoCampo(faixa: Faixa, campo: CampoTag): string {
  return faixa.pendentes[campo] ?? faixa.tags[campo] ?? "";
}

export function temPendencia(faixa: Faixa): boolean {
  return Object.keys(faixa.pendentes).length > 0 || faixa.capaPendente !== undefined;
}

export function nomeDoArquivo(faixa: Faixa): string {
  return faixa.caminho.split(/[\\/]/).pop() ?? faixa.caminho;
}

export function nomeDaPasta(faixa: Faixa): string {
  const partes = faixa.caminho.split(/[\\/]/);
  return partes.length >= 2 ? partes[partes.length - 2] : "";
}
