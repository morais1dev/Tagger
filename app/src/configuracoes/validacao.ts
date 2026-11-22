import { ACENTO_DO_TEMA, LADO_CAPA, TAMANHO_FONTE, type Config } from "./tipos";

const COR = /^#[0-9a-fA-F]{6}$/;

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

/** Corrige o que a janela nunca deixaria passar (ex.: valor lido de uma configuração antiga). */
export function normalizarConfig(c: Config): Config {
  return {
    ...c,
    tamanho_fonte: limitar(c.tamanho_fonte, TAMANHO_FONTE.min, TAMANHO_FONTE.max, 13),
    lado_max_capa: limitar(c.lado_max_capa, LADO_CAPA.min, LADO_CAPA.max, 1000),
    acento: c.acento === ACENTO_DO_TEMA || corValida(c.acento) ? c.acento : ACENTO_DO_TEMA,
    versao_id3: c.versao_id3 === 4 ? 4 : 3,
    discogs_token: c.discogs_token.trim(),
  };
}
