import { type KeyboardEvent, type MouseEvent, useEffect, useRef } from "react";
import { type Faixa, temPendencia } from "../api";
import {
  COLUNAS, COLUNAS_DIREITA, COLUNAS_MONO, LARGURA_MINIMA, type ChaveColuna, celulaApagada, celulaPendente,
  temCapaEfetiva, textoDaCelula, tituloVazio, tooltipDaCelula,
} from "../colunas";
import { type Ordem } from "../ordenacao";
import { TECLAS_NAVEGACAO, type TeclaNavegacao } from "../selecao";

export interface PropsTabela {
  /** Faixas já filtradas e ordenadas, na ordem em que aparecem. */
  faixas: readonly Faixa[];
  selecionados: ReadonlySet<string>;
  /** Linha atual do teclado. */
  foco: string | null;
  /** Colunas visíveis, na ordem das COLUNAS. */
  visiveis: readonly ChaveColuna[];
  /** Largura escolhida pelo usuário, por coluna (sem entrada = a inicial). */
  larguras: Readonly<Partial<Record<ChaveColuna, number>>>;
  ordem: Ordem | null;
  /** Altura de uma linha em px (a densidade e o tamanho da fonte das Configurações). */
  alturaLinha: number;
  /** Botão do mouse apertado sobre a linha (clique, Ctrl, Shift e começo de um arrasto). */
  aoPressionarLinha(id: string, mod: { ctrl: boolean; shift: boolean }): void;
  /** Mouse com o botão apertado passou por esta linha (arrastar para selecionar). */
  aoArrastarSobre(id: string, ctrl: boolean): void;
  aoNavegar(tecla: TeclaNavegacao, shift: boolean, pagina: number): void;
  aoSelecionarTudo(): void;
  aoOrdenar(chave: ChaveColuna): void;
  aoRedimensionar(chave: ChaveColuna, largura: number): void;
  aoMenuColunas(x: number, y: number): void;
}

const PASSO_TECLADO = 10;
const PAGINA_PADRAO = 10;          // linhas por PgUp/PgDn quando a altura da tabela é desconhecida

function Indicador({ faixa, chave }: { faixa: Faixa; chave: "capa" | "estado" }) {
  if (chave === "capa") {
    return <span className={`capa ${temCapaEfetiva(faixa) ? "capa-cheia" : "capa-vazia"}`} aria-hidden="true" />;
  }
  return temPendencia(faixa) ? <span className="ponto-pendente" aria-hidden="true" /> : null;
}

export function TabelaFaixas(p: PropsTabela) {
  const colunas = COLUNAS.filter((c) => p.visiveis.includes(c.chave));
  const larguraDe = (chave: ChaveColuna) => p.larguras[chave] ?? COLUNAS.find((c) => c.chave === chave)?.largura ?? null;
  const modelo = colunas.map((c) => {
    const largura = larguraDe(c.chave);
    return largura === null ? "minmax(160px, 1fr)" : `${largura}px`;       // Título estica (mínimo 160 px)
  }).join(" ");
  const arrasto = useRef<{ chave: ChaveColuna; x: number; largura: number } | null>(null);
  const selecionando = useRef(false);                // botão apertado numa linha: arrastar seleciona
  const grade = useRef<HTMLDivElement>(null);
  const idFoco = p.foco === null ? -1 : p.faixas.findIndex((f) => f.id === p.foco);

  // mantém a linha do teclado à vista
  useEffect(() => {
    if (idFoco >= 0) document.getElementById(`linha-${idFoco}`)?.scrollIntoView?.({ block: "nearest" });
  }, [idFoco]);

  function pressionar(e: MouseEvent, id: string) {
    if (e.button !== 0) return;
    selecionando.current = true;
    const soltar = () => {
      selecionando.current = false;
      document.removeEventListener("mouseup", soltar);
    };
    document.addEventListener("mouseup", soltar);
    p.aoPressionarLinha(id, { ctrl: e.ctrlKey || e.metaKey, shift: e.shiftKey });
  }
  function comecarArrasto(e: MouseEvent, chave: ChaveColuna) {
    e.preventDefault();
    e.stopPropagation();
    const celula = (e.currentTarget as HTMLElement).parentElement!;
    arrasto.current = { chave, x: e.clientX, largura: larguraDe(chave) ?? celula.getBoundingClientRect().width };
    const mover = (ev: globalThis.MouseEvent) => {
      const a = arrasto.current;
      if (a) p.aoRedimensionar(a.chave, Math.max(LARGURA_MINIMA, Math.round(a.largura + ev.clientX - a.x)));
    };
    const soltar = () => {
      arrasto.current = null;
      document.removeEventListener("mousemove", mover);
      document.removeEventListener("mouseup", soltar);
    };
    document.addEventListener("mousemove", mover);
    document.addEventListener("mouseup", soltar);
  }

  function tecladoNaAlca(e: KeyboardEvent, chave: ChaveColuna, celula: HTMLElement) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const atual = larguraDe(chave) ?? celula.getBoundingClientRect().width;
    p.aoRedimensionar(chave, Math.max(LARGURA_MINIMA, atual + (e.key === "ArrowRight" ? PASSO_TECLADO : -PASSO_TECLADO)));
  }

  function aoTeclar(e: KeyboardEvent) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
      e.preventDefault();
      p.aoSelecionarTudo();
    } else if (TECLAS_NAVEGACAO.includes(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      const altura = grade.current?.clientHeight ?? 0;
      p.aoNavegar(e.key as TeclaNavegacao, e.shiftKey, altura > 0 ? Math.floor(altura / p.alturaLinha) - 1 : PAGINA_PADRAO);
    }
  }

  return (
    <div
      className="tabela"
      role="grid"
      aria-label="Faixas"
      aria-multiselectable="true"
      aria-rowcount={p.faixas.length + 1}
      tabIndex={0}
      ref={grade}
      aria-activedescendant={idFoco >= 0 ? `linha-${idFoco}` : undefined}
      onKeyDown={aoTeclar}
    >
      <div
        className="tabela-cabecalho"
        role="row"
        style={{ gridTemplateColumns: modelo }}
        onContextMenu={(e) => {
          e.preventDefault();
          p.aoMenuColunas(e.clientX, e.clientY);
        }}
      >
        {colunas.map((c) => {
          const ordenada = p.ordem?.chave === c.chave ? p.ordem.direcao : null;
          return (
            <div
              key={c.chave}
              role="columnheader"
              aria-sort={ordenada === "asc" ? "ascending" : ordenada === "desc" ? "descending" : "none"}
              className={COLUNAS_DIREITA.has(c.chave) ? "direita" : undefined}
            >
              {c.titulo ? (
                <button type="button" className="cabecalho-botao" onClick={() => p.aoOrdenar(c.chave)}>
                  {c.titulo}
                  {ordenada && <span aria-hidden="true"> {ordenada === "asc" ? "▲" : "▼"}</span>}
                </button>
              ) : (
                <span className="so-leitor">Estado</span>
              )}
              {c.chave !== "estado" && (
                <div
                  role="separator"
                  aria-orientation="vertical"
                  aria-label={`Redimensionar ${c.titulo}`}
                  tabIndex={0}
                  className="alca"
                  onMouseDown={(e) => comecarArrasto(e, c.chave)}
                  onKeyDown={(e) => tecladoNaAlca(e, c.chave, e.currentTarget.parentElement as HTMLElement)}
                />
              )}
            </div>
          );
        })}
      </div>
      <div className="tabela-corpo">
        {p.faixas.map((faixa, i) => {
          const selecionada = p.selecionados.has(faixa.id);
          return (
            <div
              key={faixa.id}
              id={`linha-${i}`}
              role="row"
              aria-rowindex={i + 2}
              aria-selected={selecionada}
              className={`linha${selecionada ? " selecionada" : ""}${p.foco === faixa.id ? " foco" : ""}`}
              style={{ gridTemplateColumns: modelo }}
              onMouseDown={(e) => pressionar(e, faixa.id)}
              onMouseEnter={(e) => selecionando.current && e.buttons === 1 && p.aoArrastarSobre(faixa.id, e.ctrlKey || e.metaKey)}
            >
              {colunas.map((c) => {
                const pendente = celulaPendente(faixa, c.chave);
                const classes = [
                  "celula",
                  pendente && "pendente",
                  celulaApagada(faixa, c.chave) && "apagada",
                  c.chave === "title" && tituloVazio(faixa) && "sem-titulo",
                  COLUNAS_MONO.has(c.chave) && "mono",
                  COLUNAS_DIREITA.has(c.chave) && "direita",
                ].filter(Boolean).join(" ");
                return (
                  <div key={c.chave} role="gridcell" className={classes} title={tooltipDaCelula(faixa, c.chave)} data-coluna={c.chave}
                    data-pendente={pendente ? "true" : undefined}>
                    {c.chave === "capa" || c.chave === "estado" ? <Indicador faixa={faixa} chave={c.chave} /> : textoDaCelula(faixa, c.chave)}
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </div>
  );
}
