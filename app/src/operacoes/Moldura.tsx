import { useId, type ReactNode } from "react";
import "./operacoes.css";

/** Fundo escurecido + caixa do diálogo; Esc chama `aoFechar`. */
export function Moldura({ titulo, aoFechar, larga, children }: {
  titulo: string;
  aoFechar: () => void;
  larga?: boolean;
  children: ReactNode;
}) {
  const id = useId();
  return (
    <div className="op-fundo" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); aoFechar(); } }}>
      <div role="dialog" aria-modal="true" aria-labelledby={id} className={larga ? "op-janela op-larga" : "op-janela"}>
        <h2 id={id} className="op-titulo">{titulo}</h2>
        {children}
      </div>
    </div>
  );
}

export function Ajuda({ children }: { children: ReactNode }) {
  return <p className="op-ajuda">{children}</p>;
}
