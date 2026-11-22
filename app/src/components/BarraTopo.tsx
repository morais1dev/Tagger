import { forwardRef } from "react";
import { TEMAS } from "../temas";

interface Props {
  tema: string;
  aoMudarTema(id: string): void;
  aoAbrirPasta(): void;
  filtro: string;
  aoMudarFiltro(texto: string): void;
  mostrando: number;
  total: number;
}

/** Barra do topo: abrir pasta, filtro com contador e seletor de tema. */
export const BarraTopo = forwardRef<HTMLInputElement, Props>(function BarraTopo(p, refFiltro) {
  const escuros = Object.entries(TEMAS).filter(([, t]) => t.escuro);
  const claros = Object.entries(TEMAS).filter(([, t]) => !t.escuro);
  return (
    <header className="barra" role="toolbar" aria-label="Barra principal">
      <strong className="nome-app">Tagger</strong>
      <button type="button" title="Abrir pasta (Ctrl+O)" onClick={p.aoAbrirPasta}>Abrir pasta</button>
      <div className="filtro">
        <input
          ref={refFiltro}
          type="search"
          aria-label="Filtrar faixas"
          placeholder="Filtrar (Ctrl+F)"
          title="Filtrar por título, artista, álbum ou arquivo (Ctrl+F)"
          value={p.filtro}
          onChange={(e) => p.aoMudarFiltro(e.target.value)}
        />
        <span className="contador" aria-live="polite">Mostrando {p.mostrando} de {p.total}</span>
      </div>
      <label className="seletor-tema">
        Tema{" "}
        <select value={p.tema} onChange={(e) => p.aoMudarTema(e.target.value)}>
          <optgroup label="Escuros">
            {escuros.map(([id, t]) => <option key={id} value={id}>{t.nome}</option>)}
          </optgroup>
          <optgroup label="Claros">
            {claros.map(([id, t]) => <option key={id} value={id}>{t.nome}</option>)}
          </optgroup>
        </select>
      </label>
    </header>
  );
});
