/** Seleção de linhas como na tabela da v2 (ExtendedSelection): clique, Ctrl, Shift e Ctrl+A. */

export interface Selecao {
  ids: ReadonlySet<string>;
  /** Linha onde o Shift começa o intervalo. */
  ancora: string | null;
}

export const SELECAO_VAZIA: Selecao = { ids: new Set(), ancora: null };

export interface Modificadores {
  ctrl: boolean;
  shift: boolean;
}

/** `visiveis`: ids na ordem em que aparecem (já filtrados e ordenados). */
export function clicar(atual: Selecao, id: string, visiveis: readonly string[], mod: Modificadores): Selecao {
  if (mod.shift && atual.ancora !== null && visiveis.includes(atual.ancora)) {
    const [a, b] = [visiveis.indexOf(atual.ancora), visiveis.indexOf(id)].sort((x, y) => x - y);
    const intervalo = visiveis.slice(a, b + 1);
    const ids = new Set(mod.ctrl ? [...atual.ids, ...intervalo] : intervalo);
    return { ids, ancora: atual.ancora };            // a âncora não muda ao esticar
  }
  if (mod.ctrl) {
    const ids = new Set(atual.ids);
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    return { ids, ancora: id };
  }
  return { ids: new Set([id]), ancora: id };
}

export function selecionarTudo(visiveis: readonly string[], atual: Selecao): Selecao {
  return { ids: new Set(visiveis), ancora: atual.ancora ?? visiveis[0] ?? null };
}

/** Tira da seleção o que não está mais na lista (ex.: o filtro mudou). */
export function manterVisiveis(atual: Selecao, visiveis: readonly string[]): Selecao {
  const presentes = new Set(visiveis);
  const ids = new Set([...atual.ids].filter((id) => presentes.has(id)));
  if (ids.size === atual.ids.size) return atual;
  return { ids, ancora: atual.ancora !== null && presentes.has(atual.ancora) ? atual.ancora : null };
}
