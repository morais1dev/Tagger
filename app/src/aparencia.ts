/**
 * Aparência a partir das Configurações: tema do modo, cor de destaque derivada, fontes, tamanho e altura das linhas.
 * Espelha tagger/gui/tema.py (acento_efetivo, _texto_sobre, altura_linha...). Sem React: só conta e variáveis CSS.
 */
import { contraste } from "./contraste";
import { TEMAS, TEMA_PADRAO } from "./temas";
import { ACENTO_DO_TEMA, type Config, type Densidade } from "./configuracoes/tipos";

/** Fontes preferidas quando a configuração está em "Automática" (tema.FONTES_UI / FONTES_MONO). */
export const FONTES_UI = ["Geist", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", "DejaVu Sans"];
export const FONTES_MONO = ["Geist Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono"];

/** Altura da linha = tamanho da fonte + isto (tema.ALTURA_LINHA). */
export const ALTURA_LINHA: Record<Densidade, number> = { compacta: 21, confortavel: 29, espacosa: 37 };

export const altura_linha = (tamanho: number, densidade: Densidade): number => tamanho + (ALTURA_LINHA[densidade] ?? ALTURA_LINHA.compacta);
export const alturaCabecalho = (tamanho: number): number => tamanho + 21;
export const alturaBotao = (tamanho: number): number => tamanho + 19;

const TEXTO_ESCURO = "#0b0d0c";
const TEXTO_CLARO = "#ffffff";
const RE_COR = /^#[0-9a-f]{6}$/i;

/** Id do tema que vale: o escuro ou o claro, conforme o modo; um id desconhecido cai no padrão do modo. */
export function temaDaConfig(c: Pick<Config, "usar_escuro" | "tema_escuro" | "tema_claro">): string {
  const id = c.usar_escuro ? c.tema_escuro : c.tema_claro;
  if (id in TEMAS && TEMAS[id].escuro === c.usar_escuro) return id;
  return c.usar_escuro ? TEMA_PADRAO : "claro";
}

/** A cor de destaque que vale: a escolhida, ou a do tema quando é "Do tema" (ou quando a escolha é inválida). */
export function acentoEfetivo(temaId: string, acento: string): string {
  const base = TEMAS[temaId] ?? TEMAS[TEMA_PADRAO];
  if (acento === ACENTO_DO_TEMA || !RE_COR.test(acento)) return base.cores.acento;
  return acento.toLowerCase();
}

/** Preto ou branco, o que tiver mais contraste com a cor de destaque (tema._texto_sobre). */
export function textoSobreAcento(acento: string): string {
  return contraste(TEXTO_ESCURO, acento) >= contraste(TEXTO_CLARO, acento) ? TEXTO_ESCURO : TEXTO_CLARO;
}

/** HSV com saturação e valor em 0..65535, a precisão que o Qt usa por dentro (h em graus). */
function paraHsv16(hex: string): [number, number, number] {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  const max = Math.max(r, g, b);
  const d = max - Math.min(r, g, b);
  let h = 0;
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  return [Math.round(h * 100) / 100, max === 0 ? 0 : Math.floor((d * 65535) / max), max * 257];    // o Qt guarda o matiz em centésimos de grau
}

function deHsv(h: number, s: number, v: number): string {
  const c = v * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - c;
  const [r, g, b] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
  return "#" + [r, g, b].map((t) => Math.round((t + m) * 255).toString(16).padStart(2, "0")).join("");
}

/** QColor.lighter(110): valor (brilho) +10%; se passar do máximo, a saturação cai o que passou. */
export function clarear(hex: string): string {
  const [h, s0, v0] = paraHsv16(hex);
  let v = Math.floor((v0 * 110) / 100);
  let s = s0;
  if (v > 65535) {
    s = Math.max(0, s - (v - 65535));
    v = 65535;
  }
  return deHsv(h, s / 65535, v / 65535);
}

/** Família CSS: a escolhida (se houver) na frente das preferidas. */
function familia(escolhida: string, preferidas: readonly string[], generica: string): string {
  const aspas = (nome: string) => `"${nome.replace(/["\\]/g, "")}"`;
  const lista = [...(escolhida ? [escolhida] : []), ...preferidas].map(aspas);
  return [...lista, generica].join(", ");
}

export type Aparencia = Pick<Config, "usar_escuro" | "tema_escuro" | "tema_claro" | "acento" | "fonte" | "fonte_mono" | "tamanho_fonte" | "densidade">;

/** Variáveis CSS que a interface usa (as cores do tema vêm de temas.css pelo data-tema). */
export function variaveisDaAparencia(c: Aparencia): Record<string, string> {
  const acento = acentoEfetivo(temaDaConfig(c), c.acento);
  const tamanho = c.tamanho_fonte;
  return {
    "--acento": acento,
    "--texto-sobre-acento": textoSobreAcento(acento),
    "--acento-hover": clarear(acento),
    "--fonte-ui": familia(c.fonte, FONTES_UI, "system-ui, sans-serif"),
    "--fonte-mono": familia(c.fonte_mono, FONTES_MONO, "monospace"),
    "--tamanho-fonte": `${tamanho}px`,
    "--altura-linha": `${altura_linha(tamanho, c.densidade)}px`,
    "--altura-cabecalho": `${alturaCabecalho(tamanho)}px`,
    "--altura-botao": `${alturaBotao(tamanho)}px`,
  };
}

/** Aplica tema e variáveis na raiz do documento. */
export function aplicarAparencia(c: Aparencia, raiz: HTMLElement = document.documentElement): void {
  raiz.dataset.tema = temaDaConfig(c);
  for (const [nome, valor] of Object.entries(variaveisDaAparencia(c))) raiz.style.setProperty(nome, valor);
}
