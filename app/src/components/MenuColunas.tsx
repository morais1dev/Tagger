import { useEffect } from "react";
import { COLUNAS, COLUNAS_FIXAS, type ChaveColuna } from "../colunas";

interface Props {
  x: number;
  y: number;
  visiveis: readonly ChaveColuna[];
  aoAlternar(chave: ChaveColuna): void;
  aoRestaurar(): void;
  aoFechar(): void;
}

/** Menu do cabeçalho (clique direito): mostra/esconde colunas; as fixas (Título e estado) não aparecem. */
export function MenuColunas({ x, y, visiveis, aoAlternar, aoRestaurar, aoFechar }: Props) {
  useEffect(() => {
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    document.addEventListener("keydown", fechar);
    return () => document.removeEventListener("keydown", fechar);
  }, [aoFechar]);

  return (
    <>
      <div className="menu-fundo" onClick={aoFechar} onContextMenu={(e) => { e.preventDefault(); aoFechar(); }} />
      <div role="menu" aria-label="Colunas" className="menu" style={{ left: x, top: y }}>
        {COLUNAS.filter((c) => !COLUNAS_FIXAS.has(c.chave)).map((c) => (
          <button
            key={c.chave}
            type="button"
            role="menuitemcheckbox"
            aria-checked={visiveis.includes(c.chave)}
            onClick={() => aoAlternar(c.chave)}
          >
            <span aria-hidden="true">{visiveis.includes(c.chave) ? "✓" : ""}</span> {c.titulo}
          </button>
        ))}
        <hr />
        <button type="button" role="menuitem" onClick={() => { aoRestaurar(); aoFechar(); }}>
          Restaurar colunas padrão
        </button>
      </div>
    </>
  );
}
