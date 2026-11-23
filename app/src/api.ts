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
  /** A capa frontal do arquivo, quando o núcleo a entrega (só existe se `temCapa`). */
  capa?: Capa;
  /** Capa pendente: "definir" (passa a ter, com `capaNova`) ou "remover" (deixa de ter); ausente = sem mudança. */
  capaPendente?: "definir" | "remover";
  /** A imagem que vai virar a capa quando `capaPendente` é "definir". */
  capaNova?: Capa;
}

/** Uma imagem de capa já lida (só JPEG e PNG servem de capa, como na v2). */
export interface Capa {
  /** Endereço para o <img>: data URL (ou blob:). */
  url: string;
  mime: "image/jpeg" | "image/png";
  largura: number;
  altura: number;
  /** Tamanho em bytes. */
  bytes: number;
}

/** O que mudar na capa: trocar por uma imagem, remover, ou `null` = manter a original (desfaz a pendência). */
export type AcaoCapa = { tipo: "definir"; capa: Capa } | { tipo: "remover" } | null;

export interface ResultadoCover {
  /** Pastas onde o arquivo foi gravado. */
  gravadas: number;
  /** Pastas onde a gravação falhou. */
  falhas: number;
}

export interface Ponte {
  /** Abre uma pasta (na real, o seletor do sistema) e devolve as faixas lidas. */
  abrirPasta(): Promise<Faixa[]>;
  /** Marca um valor como pendente (alteração não salva); devolve a faixa atualizada. */
  definirPendente(id: string, campo: CampoTag, valor: string): Promise<Faixa>;
  /** Como `definirPendente`, para várias faixas de uma vez (o painel de edição). */
  definirCampo(ids: string[], campo: CampoTag, valor: string): Promise<Faixa[]>;
  /**
   * Devolve o campo ao estado de antes (apagar o que digitou numa multisseleção com "vários valores").
   * `foto[id]` é o valor pendente que a faixa tinha (undefined = sem pendência).
   */
  restaurarCampo(campo: CampoTag, foto: Readonly<Record<string, string | undefined>>): Promise<Faixa[]>;
  /** Define, remove ou desfaz a capa pendente dessas faixas. */
  definirCapa(ids: string[], acao: AcaoCapa): Promise<Faixa[]>;
  /** Descarta todas as pendências dessas faixas; devolve as faixas atualizadas. */
  descartarPendencias(ids: string[]): Promise<Faixa[]>;
  /** Grava as pendências de todas as faixas (um único save por arquivo); devolve as faixas relidas. */
  salvar(): Promise<Faixa[]>;
  /** Seletor de imagem do sistema (.jpg, .jpeg, .png); null = cancelou ou não é imagem válida. */
  escolherImagem(): Promise<Capa | null>;
  /** Imagem da área de transferência, se houver. */
  lerImagemDaAreaDeTransferencia(): Promise<Capa | null>;
  /** Diálogo de salvar; devolve o nome do arquivo gravado, ou null se cancelou. */
  exportarCapa(capa: Capa, nomeSugerido: string): Promise<string | null>;
  /** Quais dessas faixas têm, na pasta, um arquivo com este nome (para perguntar antes de substituir). */
  pastasComCover(ids: string[], nome: string): Promise<string[]>;
  /** Grava `nome` (cover.jpg/cover.png) na pasta de cada faixa. */
  salvarCoverNaPasta(ids: string[], capa: Capa, nome: string): Promise<ResultadoCover>;
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

/** Caminho completo da pasta-pai (como `str(faixa.caminho.parent)` na v2). */
export function caminhoDaPasta(faixa: Faixa): string {
  const i = Math.max(faixa.caminho.lastIndexOf("\\"), faixa.caminho.lastIndexOf("/"));
  return i > 0 ? faixa.caminho.slice(0, i) : "";
}

export function nomeDaPasta(faixa: Faixa): string {
  const partes = faixa.caminho.split(/[\\/]/);
  return partes.length >= 2 ? partes[partes.length - 2] : "";
}
