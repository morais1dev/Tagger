import { useEffect, useId, useRef, type ReactNode } from "react";
import "./operacoes.css";

const FOCAVEIS = 'input:not(:disabled), button:not(:disabled), select:not(:disabled), textarea:not(:disabled)';

/**
 * Fundo escurecido + caixa do diálogo. Ao abrir, o foco vai para o elemento com `data-foco` (ou para o
 * primeiro controle), para que o Esc funcione sem clicar antes; Esc chama `aoFechar`.
 */
export function Moldura({ titulo, aoFechar, larga, children }: {
  titulo: string;
  aoFechar: () => void;
  larga?: boolean;
  children: ReactNode;
}) {
  const id = useId();
  const caixa = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = caixa.current?.querySelector<HTMLElement>("[data-foco]") ?? caixa.current?.querySelector<HTMLElement>(FOCAVEIS);
    el?.focus();
  }, []);
  return (
    <div className="op-fundo" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); aoFechar(); } }}>
      <div ref={caixa} role="dialog" aria-modal="true" aria-labelledby={id} className={larga ? "op-janela op-larga" : "op-janela"}>
        <h2 id={id} className="op-titulo">{titulo}</h2>
        {children}
      </div>
    </div>
  );
}

export function Ajuda({ children }: { children: ReactNode }) {
  return <p className="op-ajuda">{children}</p>;
}
