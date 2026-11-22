import { useEffect, useMemo, useRef, useState } from "react";
import { type Faixa, type Ponte, nomeDoArquivo, valorDoCampo } from "../api";
import { type ChaveColuna, COLUNAS, colunasPadrao } from "../colunas";
import { type Ordem, ordenar, proximaOrdem } from "../ordenacao";
import { type Selecao, SELECAO_VAZIA, clicar, manterVisiveis, selecionarTudo } from "../selecao";
import { TEMAS, TEMA_PADRAO } from "../temas";
import { BarraTopo } from "./BarraTopo";
import { MenuColunas } from "./MenuColunas";
import { TabelaFaixas } from "./TabelaFaixas";

const CHAVE_TEMA = "tagger.tema";

/** Tema salvo, se ainda existir; senão o padrão. O armazenamento pode estar indisponível. */
function temaInicial(): string {
  try {
    const salvo = localStorage.getItem(CHAVE_TEMA);
    if (salvo && salvo in TEMAS) return salvo;
  } catch {
    /* sem armazenamento: usa o padrão */
  }
  return TEMA_PADRAO;
}

/** Filtro de busca: título, artista, álbum ou nome do arquivo, já com os valores pendentes. */
export function passaNoFiltro(faixa: Faixa, texto: string): boolean {
  const termo = texto.trim().toLocaleLowerCase();
  if (!termo) return true;
  const alvo = [valorDoCampo(faixa, "title"), valorDoCampo(faixa, "artist"), valorDoCampo(faixa, "album"), nomeDoArquivo(faixa)]
    .join(" ").toLocaleLowerCase();
  return alvo.includes(termo);
}

export function Janela({ ponte }: { ponte: Ponte }) {
  const [tema, setTema] = useState(temaInicial);
  const [faixas, setFaixas] = useState<Faixa[]>([]);
  const [filtro, setFiltro] = useState("");
  const [ordem, setOrdem] = useState<Ordem | null>(null);       // null = ordem de carga
  const [selecao, setSelecao] = useState<Selecao>(SELECAO_VAZIA);
  const [visiveis, setVisiveis] = useState<ChaveColuna[]>(colunasPadrao);
  const [larguras, setLarguras] = useState<Partial<Record<ChaveColuna, number>>>({});
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const refFiltro = useRef<HTMLInputElement>(null);

  useEffect(() => {
    document.documentElement.dataset.tema = tema;
    try {
      localStorage.setItem(CHAVE_TEMA, tema);
    } catch {
      /* não persiste, mas o tema continua valendo nesta sessão */
    }
  }, [tema]);

  const exibidas = useMemo(() => ordenar(faixas.filter((f) => passaNoFiltro(f, filtro)), ordem), [faixas, filtro, ordem]);
  const idsExibidos = useMemo(() => exibidas.map((f) => f.id), [exibidas]);

  // o que sumiu da lista (filtro) sai da seleção
  useEffect(() => setSelecao((s) => manterVisiveis(s, idsExibidos)), [idsExibidos]);

  async function abrirPasta() {
    setFaixas(await ponte.abrirPasta());
    setSelecao(SELECAO_VAZIA);
  }

  useEffect(() => {
    function atalhos(e: KeyboardEvent) {
      if (!(e.ctrlKey || e.metaKey)) return;
      const tecla = e.key.toLowerCase();
      if (tecla === "f") {
        e.preventDefault();
        refFiltro.current?.focus();
      } else if (tecla === "o") {
        e.preventDefault();
        void abrirPasta();
      }
    }
    document.addEventListener("keydown", atalhos);
    return () => document.removeEventListener("keydown", atalhos);
  });

  function alternarColuna(chave: ChaveColuna) {
    setVisiveis((atual) => COLUNAS.map((c) => c.chave).filter((k) => (k === chave ? !atual.includes(k) : atual.includes(k))));
  }

  return (
    <main className="janela">
      <BarraTopo
        ref={refFiltro}
        tema={tema}
        aoMudarTema={setTema}
        aoAbrirPasta={() => void abrirPasta()}
        filtro={filtro}
        aoMudarFiltro={setFiltro}
        mostrando={exibidas.length}
        total={faixas.length}
      />
      {faixas.length === 0 ? (
        <p className="vazio">Abra uma pasta para começar.</p>
      ) : (
        <TabelaFaixas
          faixas={exibidas}
          selecionados={selecao.ids}
          visiveis={visiveis}
          larguras={larguras}
          ordem={ordem}
          aoClicarLinha={(id, mod) => setSelecao((s) => clicar(s, id, idsExibidos, mod))}
          aoSelecionarTudo={() => setSelecao((s) => selecionarTudo(idsExibidos, s))}
          aoOrdenar={(chave) => setOrdem((o) => proximaOrdem(o, chave))}
          aoRedimensionar={(chave, largura) => setLarguras((l) => ({ ...l, [chave]: largura }))}
          aoMenuColunas={(x, y) => setMenu({ x, y })}
        />
      )}
      {menu && (
        <MenuColunas
          x={menu.x}
          y={menu.y}
          visiveis={visiveis}
          aoAlternar={alternarColuna}
          aoRestaurar={() => { setVisiveis(colunasPadrao()); setLarguras({}); }}
          aoFechar={() => setMenu(null)}
        />
      )}
    </main>
  );
}
