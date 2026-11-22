/**
 * Seleção de linhas como na tabela da v2 (SelectRows + ExtendedSelection): clique, Ctrl, Shift,
 * arrastar o mouse, Ctrl+A e navegação por teclado (setas, Shift+setas, Home/End, PgUp/PgDn).
 */

export interface Selecao {
  ids: ReadonlySet<string>;
  /** Linha onde o Shift (e o arrasto) começa o intervalo. */
  ancora: string | null;
  /** Linha atual do teclado (a que as setas movem). */
  foco: string | null;
}

export const SELECAO_VAZIA: Selecao = { ids: new Set(), ancora: null, foco: null };

export interface Modificadores {
  ctrl: boolean;
  shift: boolean;
}

function intervalo(visiveis: readonly string[], de: string, ate: string): string[] {
  const [a, b] = [visiveis.indexOf(de), visiveis.indexOf(ate)].sort((x, y) => x - y);
  return visiveis.slice(a, b + 1);
}

/** `visiveis`: ids na ordem em que aparecem (já filtrados e ordenados). */
export function clicar(atual: Selecao, id: string, visiveis: readonly string[], mod: Modificadores): Selecao {
  if (mod.shift && atual.ancora !== null && visiveis.includes(atual.ancora)) {
    const faixa = intervalo(visiveis, atual.ancora, id);
    const ids = new Set(mod.ctrl ? [...atual.ids, ...faixa] : faixa);
    return { ids, ancora: atual.ancora, foco: id };            // a âncora não muda ao esticar
  }
  if (mod.ctrl) {
    const ids = new Set(atual.ids);
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    return { ids, ancora: id, foco: id };
  }
  return { ids: new Set([id]), ancora: id, foco: id };
}

/**
 * Arrastar o mouse com o botão apertado: seleciona da âncora até a linha sob o mouse.
 * `base` é a seleção logo depois de apertar o botão (com Ctrl, o arrasto soma a ela).
 */
export function arrastar(base: Selecao, id: string, visiveis: readonly string[], ctrl: boolean): Selecao {
  if (base.ancora === null || !visiveis.includes(base.ancora)) return base;
  const faixa = intervalo(visiveis, base.ancora, id);
  return { ids: new Set(ctrl ? [...base.ids, ...faixa] : faixa), ancora: base.ancora, foco: id };
}

export type TeclaNavegacao = "ArrowUp" | "ArrowDown" | "Home" | "End" | "PageUp" | "PageDown";
export const TECLAS_NAVEGACAO: readonly string[] = ["ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"];

/** Move o foco com o teclado; sem Shift seleciona só a nova linha, com Shift estica a partir da âncora. */
export function navegar(
  atual: Selecao, tecla: TeclaNavegacao, visiveis: readonly string[], shift: boolean, pagina: number,
): Selecao {
  const n = visiveis.length;
  if (n === 0) return atual;
  const i = atual.foco === null ? -1 : visiveis.indexOf(atual.foco);
  const passo = Math.max(1, pagina);
  let novo: number;
  if (tecla === "Home") novo = 0;
  else if (tecla === "End") novo = n - 1;
  else if (i < 0) novo = 0;                                   // sem linha atual: começa pela primeira
  else if (tecla === "ArrowDown") novo = Math.min(i + 1, n - 1);
  else if (tecla === "ArrowUp") novo = Math.max(i - 1, 0);
  else if (tecla === "PageDown") novo = Math.min(i + passo, n - 1);
  else novo = Math.max(i - passo, 0);
  const id = visiveis[novo];
  if (shift) {
    const ancora = atual.ancora !== null && visiveis.includes(atual.ancora) ? atual.ancora : id;
    return { ids: new Set(intervalo(visiveis, ancora, id)), ancora, foco: id };
  }
  return { ids: new Set([id]), ancora: id, foco: id };
}

export function selecionarTudo(visiveis: readonly string[], atual: Selecao): Selecao {
  return { ids: new Set(visiveis), ancora: atual.ancora ?? visiveis[0] ?? null, foco: atual.foco };
}

/** Tira da seleção o que não está mais na lista (ex.: o filtro mudou). */
export function manterVisiveis(atual: Selecao, visiveis: readonly string[]): Selecao {
  const presentes = new Set(visiveis);
  const ids = new Set([...atual.ids].filter((id) => presentes.has(id)));
  const ancora = atual.ancora !== null && presentes.has(atual.ancora) ? atual.ancora : null;
  const foco = atual.foco !== null && presentes.has(atual.foco) ? atual.foco : null;
  if (ids.size === atual.ids.size && ancora === atual.ancora && foco === atual.foco) return atual;
  return { ids, ancora, foco };
}
