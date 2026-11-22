import { useEffect, useMemo, useRef, useState } from "react";
import { type Faixa, type Ponte, nomeDoArquivo, temPendencia, valorDoCampo } from "../api";
import { GENEROS_PADRAO, listaDeGeneros } from "../generos";
import { Divisor, LARGURA_PAINEL_PADRAO, limitarLargura } from "./Divisor";
import { PainelEditor } from "./PainelEditor";
import { type ChaveColuna, COLUNAS, colunasPadrao } from "../colunas";
import { type Ordem, ordenar, proximaOrdem } from "../ordenacao";
import { type Selecao, SELECAO_VAZIA, arrastar, clicar, manterVisiveis, navegar, selecionarTudo } from "../selecao";
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

const CHAVE_PAINEL = "tagger.painel_visivel";
const CHAVE_LARGURA = "tagger.painel_largura";

function lerPreferencia(chave: string, padrao: string): string {
  try {
    return localStorage.getItem(chave) ?? padrao;
  } catch {
    return padrao;                       // sem armazenamento: usa o padrão
  }
}

function guardarPreferencia(chave: string, valor: string) {
  try {
    localStorage.setItem(chave, valor);
  } catch {
    /* não persiste, mas vale nesta sessão */
  }
}

/** Pergunta do sistema; nos testes é trocada por uma função que responde na hora. */
const confirmarPadrao = (texto: string) => window.confirm(texto);

export function Janela({ ponte, confirmar = confirmarPadrao }: { ponte: Ponte; confirmar?: (texto: string) => Promise<boolean> | boolean }) {
  const [tema, setTema] = useState(temaInicial);
  const [faixas, setFaixas] = useState<Faixa[]>([]);
  const [filtro, setFiltro] = useState("");
  const [ordem, setOrdem] = useState<Ordem | null>(null);       // null = ordem de carga
  const [selecao, setSelecao] = useState<Selecao>(SELECAO_VAZIA);
  const [visiveis, setVisiveis] = useState<ChaveColuna[]>(colunasPadrao);
  const [larguras, setLarguras] = useState<Partial<Record<ChaveColuna, number>>>({});
  const [menu, setMenu] = useState<{ x: number; y: number } | null>(null);
  const refFiltro = useRef<HTMLInputElement>(null);
  const baseDoArrasto = useRef<Selecao>(SELECAO_VAZIA);      // seleção logo depois de apertar o botão do mouse
  const [painelVisivel, setPainelVisivel] = useState(() => lerPreferencia(CHAVE_PAINEL, "1") !== "0");
  const [larguraPainel, setLarguraPainel] = useState(() => limitarLargura(Number(lerPreferencia(CHAVE_LARGURA, "")) || LARGURA_PAINEL_PADRAO));
  const [versaoPainel, setVersaoPainel] = useState(0);        // sobe quando o rascunho muda por fora do painel: ele recarrega os campos
  const [aviso, setAviso] = useState("");

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
    setAviso("");
  }

  // as faixas que o painel editou (devolvidas pela ponte) entram no lugar das antigas
  const aplicarFaixas = (novas: Faixa[]) =>
    setFaixas((atuais) => atuais.map((f) => novas.find((n) => n.id === f.id) ?? f));

  const selecionadas = useMemo(() => exibidas.filter((f) => selecao.ids.has(f.id)), [exibidas, selecao.ids]);
  const totalPendentes = useMemo(() => faixas.filter(temPendencia).length, [faixas]);
  const generos = useMemo(
    () => listaDeGeneros(GENEROS_PADRAO, faixas.map((f) => valorDoCampo(f, "genre"))), [faixas]);

  async function salvar() {
    if (totalPendentes === 0) return;
    setFaixas(await ponte.salvar());
    setVersaoPainel((v) => v + 1);
    setAviso(totalPendentes === 1 ? "1 arquivo salvo." : `${totalPendentes} arquivos salvos.`);
  }

  async function descartar() {
    const ids = faixas.filter(temPendencia).map((f) => f.id);
    if (ids.length === 0) return;
    aplicarFaixas(await ponte.descartarPendencias(ids));
    setVersaoPainel((v) => v + 1);
    setAviso("Alterações descartadas.");
  }

  function alternarPainel() {
    setPainelVisivel((v) => {
      guardarPreferencia(CHAVE_PAINEL, v ? "0" : "1");
      return !v;
    });
  }

  function mudarLarguraPainel(largura: number) {
    setLarguraPainel(largura);
    guardarPreferencia(CHAVE_LARGURA, String(largura));
  }

  const chavePainel = `${selecionadas.map((f) => f.id).join("|")}#${versaoPainel}`;

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
      } else if (tecla === "e") {
        e.preventDefault();
        alternarPainel();
      } else if (tecla === "s") {
        e.preventDefault();
        void salvar();
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
        painelVisivel={painelVisivel}
        aoAlternarPainel={alternarPainel}
      />
      <div className="corpo">
        {painelVisivel && (
          <>
            <div className="coluna-painel" style={{ width: larguraPainel }}>
              <PainelEditor
                key={chavePainel}
                faixas={selecionadas}
                totalPendentes={totalPendentes}
                ponte={ponte}
                generos={generos}
                aoAtualizar={aplicarFaixas}
                aoAvisar={setAviso}
                aoSalvar={() => void salvar()}
                aoDescartar={() => void descartar()}
                aoEscape={() => document.querySelector<HTMLElement>('[role="grid"]')?.focus()}
                confirmar={confirmar}
              />
            </div>
            <Divisor largura={larguraPainel} aoMudar={mudarLarguraPainel} />
          </>
        )}
        <div className="area-tabela">
          {faixas.length === 0 ? (
            <p className="vazio">Abra uma pasta para começar.</p>
          ) : (
            <TabelaFaixas
              faixas={exibidas}
              selecionados={selecao.ids}
              foco={selecao.foco}
              visiveis={visiveis}
              larguras={larguras}
              ordem={ordem}
              aoPressionarLinha={(id, mod) => {
                const nova = clicar(selecao, id, idsExibidos, mod);
                baseDoArrasto.current = nova;
                setSelecao(nova);
              }}
              aoArrastarSobre={(id, ctrl) => setSelecao(arrastar(baseDoArrasto.current, id, idsExibidos, ctrl))}
              aoNavegar={(tecla, shift, pagina) => setSelecao((s) => navegar(s, tecla, idsExibidos, shift, pagina))}
              aoSelecionarTudo={() => setSelecao((s) => selecionarTudo(idsExibidos, s))}
              aoOrdenar={(chave) => setOrdem((o) => proximaOrdem(o, chave))}
              aoRedimensionar={(chave, largura) => setLarguras((l) => ({ ...l, [chave]: largura }))}
              aoMenuColunas={(x, y) => setMenu({ x, y })}
            />
          )}
        </div>
      </div>
      <div className="status" role="status" aria-live="polite">{aviso}</div>
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
