import { forwardRef } from "react";

interface Props {
  aoAbrirPasta(): void;
  filtro: string;
  aoMudarFiltro(texto: string): void;
  mostrando: number;
  total: number;
  painelVisivel: boolean;
  aoAlternarPainel(): void;
  /** Modo atual: o botão mostra o sol no escuro (vai para o claro) e a lua no claro, como a v2. */
  escuro: boolean;
  aoAlternarModo(): void;
  aoAbrirConfiguracoes(): void;
}

/** Barra do topo: abrir pasta, editor, filtro com contador, Configurações e modo claro/escuro. */
export const BarraTopo = forwardRef<HTMLInputElement, Props>(function BarraTopo(p, refFiltro) {
  return (
    <header className="barra" role="toolbar" aria-label="Barra principal">
      <strong className="nome-app">Tagger</strong>
      <button type="button" title="Abrir pasta (Ctrl+O)" onClick={p.aoAbrirPasta}>Abrir pasta</button>
      <button
        type="button"
        aria-pressed={p.painelVisivel}
        title={`${p.painelVisivel ? "Esconder" : "Mostrar"} o editor (Ctrl+E)`}
        onClick={p.aoAlternarPainel}
      >Editor</button>
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
      <button type="button" className="icone" aria-label="Configurações" title="Configurações (Ctrl+,)" onClick={p.aoAbrirConfiguracoes}>⚙</button>
      <button
        type="button"
        className="icone"
        aria-label="Alternar tema claro/escuro"
        title="Alternar tema claro/escuro"
        onClick={p.aoAlternarModo}
      >{p.escuro ? "☀" : "☾"}</button>
    </header>
  );
});
