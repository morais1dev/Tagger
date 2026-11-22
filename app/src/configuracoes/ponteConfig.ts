// Ponte simulada das Configurações. Depois o src-tauri entra no lugar, com a mesma forma;
// aqui nada toca o disco, o registro nem a rede (a importação das configurações da v2 é automática, no núcleo).

import { copiarConfig, VERSAO_DO_APP_SIMULADA, type Config, type InfoSobre } from "./tipos";
import { lerConfig } from "./validacao";

export interface PonteConfig {
  carregar(): Promise<Config>;
  salvar(config: Config): Promise<void>;
  /** Famílias de fonte instaladas, para os dois seletores de fonte. */
  fontesInstaladas(): Promise<string[]>;
  sobre(): Promise<InfoSobre>;
}

export const FONTES_SIMULADAS = ["Arial", "Cascadia Mono", "Consolas", "Geist", "Geist Mono", "Segoe UI", "Segoe UI Variable Text"];

export function criarPonteSimulada(inicial: Partial<Record<string, unknown>> = {}): PonteConfig {
  let guardada = lerConfig(inicial);
  return {
    carregar: async () => copiarConfig(guardada),
    salvar: async (config) => {
      guardada = lerConfig(copiarConfig(config) as unknown as Record<string, unknown>);
    },
    fontesInstaladas: async () => [...FONTES_SIMULADAS],
    sobre: async () => ({ versao: VERSAO_DO_APP_SIMULADA }),
  };
}
