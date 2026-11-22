// Ponte simulada das Configurações. Depois o src-tauri entra no lugar, com a mesma forma;
// aqui nada toca o disco, o registro nem a rede (J-25 só devolve um resultado de mentira).

import { copiarConfig, PADROES, VERSAO_DO_APP_SIMULADA, type Config, type ImportacaoV2, type InfoSobre } from "./tipos";
import { normalizarConfig } from "./validacao";

export interface PonteConfig {
  carregar(): Promise<Config>;
  salvar(config: Config): Promise<void>;
  /** Famílias de fonte instaladas, para os dois seletores de fonte. */
  fontesInstaladas(): Promise<string[]>;
  /** J-25: traz as configurações da v2 (só leitura, nunca apaga). */
  importarDaV2(): Promise<ImportacaoV2>;
  sobre(): Promise<InfoSobre>;
}

export const FONTES_SIMULADAS = ["Arial", "Cascadia Mono", "Consolas", "Geist", "Geist Mono", "Segoe UI", "Segoe UI Variable Text"];

export function criarPonteSimulada(inicial: Partial<Config> = {}, v2?: ImportacaoV2): PonteConfig {
  let guardada = normalizarConfig({ ...copiarConfig(PADROES), ...inicial });
  return {
    carregar: async () => copiarConfig(guardada),
    salvar: async (config) => {
      guardada = normalizarConfig(copiarConfig(config));
    },
    fontesInstaladas: async () => [...FONTES_SIMULADAS],
    importarDaV2: async () => v2 ?? { encontrada: false, config: {}, ignoradas: [] },
    sobre: async () => ({ versao: VERSAO_DO_APP_SIMULADA }),
  };
}
