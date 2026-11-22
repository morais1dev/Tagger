import { type KeyboardEvent, type MouseEvent } from "react";

export const LARGURA_PAINEL_MIN = 240;
export const LARGURA_PAINEL_MAX = 560;
export const LARGURA_PAINEL_PADRAO = 380;
const PASSO = 16;

export function limitarLargura(largura: number): number {
  return Math.min(LARGURA_PAINEL_MAX, Math.max(LARGURA_PAINEL_MIN, Math.round(largura)));
}

interface Props {
  /** Largura atual do painel (à esquerda do divisor). */
  largura: number;
  aoMudar(largura: number): void;
}

/** Divisor arrastável entre o painel e a tabela; o painel fica entre 240 e 560 px. */
export function Divisor({ largura, aoMudar }: Props) {
  function arrastar(e: MouseEvent) {
    e.preventDefault();
    const inicio = { x: e.clientX, largura };
    const mover = (ev: globalThis.MouseEvent) => aoMudar(limitarLargura(inicio.largura + ev.clientX - inicio.x));
    const soltar = () => {
      document.removeEventListener("mousemove", mover);
      document.removeEventListener("mouseup", soltar);
    };
    document.addEventListener("mousemove", mover);
    document.addEventListener("mouseup", soltar);
  }

  function teclar(e: KeyboardEvent) {
    const novo = e.key === "ArrowRight" ? largura + PASSO : e.key === "ArrowLeft" ? largura - PASSO
      : e.key === "Home" ? LARGURA_PAINEL_MIN : e.key === "End" ? LARGURA_PAINEL_MAX : null;
    if (novo === null) return;
    e.preventDefault();
    aoMudar(limitarLargura(novo));
  }

  return (
    <div
      className="divisor"
      role="separator"
      aria-orientation="vertical"
      aria-label="Redimensionar o painel"
      aria-valuemin={LARGURA_PAINEL_MIN}
      aria-valuemax={LARGURA_PAINEL_MAX}
      aria-valuenow={largura}
      tabIndex={0}
      onMouseDown={arrastar}
      onKeyDown={teclar}
    />
  );
}
