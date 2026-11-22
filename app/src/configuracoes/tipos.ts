// Tipos e valores padrão das Configurações (espelham tagger/gui/config.py PADROES, v2.3).

export type Densidade = "compacta" | "confortavel" | "espacosa";
export type VersaoId3 = 3 | 4;

/** "tema" = usa a cor de destaque do próprio tema; senão uma cor #rrggbb. */
export const ACENTO_DO_TEMA = "tema";

export const DENSIDADES: Record<Densidade, string> = {
  compacta: "Compacta",
  confortavel: "Confortável",
  espacosa: "Espaçosa",
};

/** Cores de destaque prontas (tagger/gui/tema.py ACENTOS). */
export const ACENTOS: ReadonlyArray<{ nome: string; cor: string }> = [
  { nome: "Menta", cor: "#3ddc97" },
  { nome: "Azul", cor: "#6b9bff" },
  { nome: "Laranja", cor: "#ff9a4d" },
  { nome: "Lilás", cor: "#c58bff" },
  { nome: "Rosa", cor: "#ff6b9d" },
  { nome: "Amarelo", cor: "#f5c542" },
];

export const TAMANHO_FONTE = { min: 11, max: 18 } as const;
export const LADO_CAPA = { min: 300, max: 3000, passo: 100 } as const;

export interface Config {
  // aparência
  usar_escuro: boolean;
  tema_escuro: string;
  tema_claro: string;
  acento: string;
  fonte: string; // "" = automática
  fonte_mono: string; // "" = automática
  tamanho_fonte: number;
  densidade: Densidade;
  // comportamento
  subpastas: boolean;
  reabrir_ultima: boolean;
  numerar_com_total: boolean;
  avisar_nova_versao: boolean;
  agrupar_por_album: boolean;
  // tags
  versao_id3: VersaoId3;
  multivalor: boolean;
  remover_id3v1: boolean;
  otimizar_capa: boolean;
  lado_max_capa: number;
  generos: string[];
  // serviços online (credencial própria, opcional; "" = chave do Tagger)
  discogs_token: string;
  // padrões de nome e recentes: não aparecem na janela, mas são guardados junto
  padrao_renomear: string;
  padrao_tags: string;
  padrao_organizar: string;
  recentes_renomear: string[];
  recentes_organizar: string[];
  recentes_tags: string[];
}

export const GENEROS_PADRAO: readonly string[] = [
  "Alternative", "Ambient", "Axé", "Blues", "Bossa Nova", "Classical", "Country", "Dance",
  "Disco", "Drum & Bass", "Electronic", "Folk", "Forró", "Funk", "Gospel", "Hard Rock",
  "Heavy Metal", "Hip-Hop", "House", "Indie", "Indie Rock", "Jazz", "Lo-Fi", "Metal",
  "MPB", "Pagode", "Pop", "Pop Rock", "Punk", "R&B", "Rap", "Reggae", "Rock", "Samba",
  "Sertanejo", "Soul", "Soundtrack", "Synthpop", "Techno", "Trap",
];

export const PADROES: Config = {
  usar_escuro: true,
  tema_escuro: "grafite",
  tema_claro: "claro",
  acento: ACENTO_DO_TEMA,
  fonte: "",
  fonte_mono: "",
  tamanho_fonte: 13,
  densidade: "compacta",
  subpastas: true,
  reabrir_ultima: false,
  numerar_com_total: true,
  avisar_nova_versao: true,
  agrupar_por_album: false,
  versao_id3: 3,
  multivalor: true,
  remover_id3v1: false,
  otimizar_capa: true,
  lado_max_capa: 1000,
  generos: [...GENEROS_PADRAO],
  discogs_token: "",
  padrao_renomear: "{tracknumber:02} - {artist} - {title}",
  padrao_tags: "%artist% - %title%",
  padrao_organizar: "{albumartist}/{album}/{tracknumber:02} - {title}",
  recentes_renomear: [],
  recentes_organizar: [],
  recentes_tags: [],
};

/** Chaves que guardam credencial: nunca passam pela prévia ao vivo nem voltam num Cancelar (CHAVES_CONFIG da v2). */
export const CHAVES_CREDENCIAL = ["discogs_token"] as const satisfies ReadonlyArray<keyof Config>;

/** Chaves que a janela não mostra e o "Restaurar padrões" preserva (padrao_* e recentes_*). */
export const CHAVES_DO_USUARIO = [
  "padrao_renomear", "padrao_tags", "padrao_organizar",
  "recentes_renomear", "recentes_organizar", "recentes_tags",
] as const satisfies ReadonlyArray<keyof Config>;

/**
 * Resultado da importação das configurações da v2 (J-25). A importação é automática, na 1ª execução,
 * feita no núcleo/src-tauri (só leitura do registro, sem apagar); não há botão nem tela. O tipo existe
 * para a ponte devolver o que foi trazido.
 */
export interface ImportacaoV2 {
  encontrada: boolean;
  /** Valores trazidos da v2, já no formato da v3. */
  config: Partial<Config>;
  /** Chaves da v2 que não existem na v3 (ex.: a chave antiga do Last.fm) e foram ignoradas. */
  ignoradas: string[];
}

/** Versão mostrada pela ponte simulada; a real vem do app. */
export const VERSAO_DO_APP_SIMULADA = "3.0.0-dev";

export interface InfoSobre {
  versao: string;
}

export function copiarConfig(c: Config): Config {
  return {
    ...c,
    generos: [...c.generos],
    recentes_renomear: [...c.recentes_renomear],
    recentes_organizar: [...c.recentes_organizar],
    recentes_tags: [...c.recentes_tags],
  };
}
