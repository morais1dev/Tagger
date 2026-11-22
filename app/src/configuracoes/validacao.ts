import { TEMAS } from "../temas";
import { ACENTO_DO_TEMA, DENSIDADES, LADO_CAPA, PADROES, TAMANHO_FONTE, copiarConfig, type Config } from "./tipos";

const COR = /^#[0-9a-fA-F]{6}$/;
const INTEIRO = /^\s*[+-]?\d+\s*$/;

export function corValida(valor: string): boolean {
  return COR.test(valor);
}

/** Mantém o número dentro do intervalo; texto que não é número vira `padrao`. */
export function limitar(valor: unknown, min: number, max: number, padrao: number): number {
  const texto = String(valor).trim();
  const n = typeof valor === "number" ? valor : Number(texto);
  if (!Number.isFinite(n) || texto === "") return padrao;
  return Math.min(max, Math.max(min, Math.round(n)));
}

/** Uma linha por gênero, sem linhas vazias nem espaços sobrando. */
export function dividirGeneros(texto: string): string[] {
  return texto.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
}

/** Erros por chave de uma configuração (vazio = válida). */
export function validarConfig(c: Config): Partial<Record<keyof Config, string>> {
  const erros: Partial<Record<keyof Config, string>> = {};
  if (!Number.isInteger(c.tamanho_fonte) || c.tamanho_fonte < TAMANHO_FONTE.min || c.tamanho_fonte > TAMANHO_FONTE.max)
    erros.tamanho_fonte = `Use um tamanho de ${TAMANHO_FONTE.min} a ${TAMANHO_FONTE.max} px.`;
  if (!Number.isInteger(c.lado_max_capa) || c.lado_max_capa < LADO_CAPA.min || c.lado_max_capa > LADO_CAPA.max)
    erros.lado_max_capa = `Use um lado de ${LADO_CAPA.min} a ${LADO_CAPA.max} px.`;
  if (c.acento !== ACENTO_DO_TEMA && !corValida(c.acento)) erros.acento = "Cor inválida. Use o formato #rrggbb.";
  return erros;
}

// --- leitura de valores guardados (config.carregar_config da v2, mais a validação que a janela faz) ---

/** bool(valor): bool de verdade fica como está; o resto vale `str(valor).lower() in ("true", "1")`. */
function lerBool(valor: unknown): boolean {
  return typeof valor === "boolean" ? valor : ["true", "1"].includes(String(valor).toLowerCase());
}

/** int(valor) do Python: número trunca, texto só se for inteiro; senão `undefined` (ValueError/TypeError). */
function lerInteiro(valor: unknown): number | undefined {
  if (typeof valor === "boolean") return Number(valor);
  if (typeof valor === "number") return Number.isFinite(valor) ? Math.trunc(valor) : undefined;
  if (typeof valor === "string" && INTEIRO.test(valor)) return parseInt(valor, 10);
  return undefined;
}

/** Texto vira lista de um item; lista fica lista; vazio/nulo vira []; outro tipo não é lista (`undefined`). */
function lerLista(valor: unknown): string[] | undefined {
  if (typeof valor === "string") return [valor];
  if (valor === null || valor === undefined || valor === false || valor === 0) return [];
  if (Array.isArray(valor)) return valor.map(String);
  return undefined;
}

const emTema = (id: string, escuro: boolean) => id in TEMAS && TEMAS[id].escuro === escuro;

/**
 * Configuração a partir de valores guardados de qualquer tipo (texto "true"/"1" do QSettings, número
 * em texto, lista como texto...). Replica `carregar_config` da v2: chave ausente ou inválida cai no
 * padrão. Além disso, descarta o que a janela nunca deixaria escolher (tema que não existe, densidade
 * desconhecida, cor fora de #rrggbb) e limita os números ao intervalo dos campos.
 */
export function lerConfig(bruto: Partial<Record<string, unknown>> = {}): Config {
  const novo = copiarConfig(PADROES) as unknown as Record<string, unknown>;
  const padroes = PADROES as unknown as Record<string, unknown>;
  for (const chave of Object.keys(padroes)) {
    const padrao = padroes[chave];
    const valor = bruto[chave];
    if (valor === undefined || valor === null) continue;
    if (typeof padrao === "boolean") novo[chave] = lerBool(valor);
    else if (typeof padrao === "number") novo[chave] = lerInteiro(valor) ?? padrao;
    else if (Array.isArray(padrao)) novo[chave] = lerLista(valor) ?? padrao;
    else novo[chave] = typeof valor === "string" ? valor : typeof valor === "object" ? padrao : String(valor);
  }
  const c = novo as unknown as Config;
  if (!emTema(c.tema_escuro, true)) c.tema_escuro = PADROES.tema_escuro;
  if (!emTema(c.tema_claro, false)) c.tema_claro = PADROES.tema_claro;
  if (!(c.densidade in DENSIDADES)) c.densidade = PADROES.densidade;
  if (c.acento !== ACENTO_DO_TEMA && !corValida(c.acento)) c.acento = PADROES.acento;
  c.acento = c.acento === ACENTO_DO_TEMA ? c.acento : c.acento.toLowerCase();
  c.tamanho_fonte = limitar(c.tamanho_fonte, TAMANHO_FONTE.min, TAMANHO_FONTE.max, PADROES.tamanho_fonte);
  c.lado_max_capa = limitar(c.lado_max_capa, LADO_CAPA.min, LADO_CAPA.max, PADROES.lado_max_capa);
  if (c.versao_id3 !== 3 && c.versao_id3 !== 4) c.versao_id3 = PADROES.versao_id3;
  c.discogs_token = c.discogs_token.trim();
  return c;
}

/** Normaliza uma configuração já montada (mesmas regras de `lerConfig`). */
export function normalizarConfig(c: Config): Config {
  return lerConfig(c as unknown as Record<string, unknown>);
}
