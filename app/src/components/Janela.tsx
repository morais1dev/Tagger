import { useEffect, useMemo, useRef, useState } from "react";
import { type Faixa, type Ponte, nomeDoArquivo, temPendencia, valorDoCampo } from "../api";
import { listaDeGeneros } from "../generos";
import { Divisor, LARGURA_PAINEL_PADRAO, limitarLargura } from "./Divisor";
import { PainelEditor } from "./PainelEditor";
import { type ChaveColuna, COLUNAS, colunasPadrao } from "../colunas";
import { type Ordem, ordenar, proximaOrdem } from "../ordenacao";
import { type Selecao, SELECAO_VAZIA, arrastar, clicar, manterVisiveis, navegar, selecionarTudo } from "../selecao";
import { aplicarAparencia, altura_linha } from "../aparencia";
import { DialogoConfiguracoes, Sobre, criarPonteSimulada, type Config, type PonteConfig } from "../configuracoes";
import { PADROES, copiarConfig } from "../configuracoes/tipos";
import { BarraTopo } from "./BarraTopo";
import { MenuColunas } from "./MenuColunas";
import { TabelaFaixas } from "./TabelaFaixas";

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

interface PropsJanela {
  ponte: Ponte;
  /** Configurações (carregar/salvar, fontes, versão); a simulada guarda só em memória. */
  ponteConfig?: PonteConfig;
  confirmar?: (texto: string) => Promise<boolean> | boolean;
}

export function Janela({ ponte, ponteConfig, confirmar = confirmarPadrao }: PropsJanela) {
  const [pontePadrao] = useState(() => criarPonteSimulada());
  const cfg = ponteConfig ?? pontePadrao;
  const [config, setConfig] = useState<Config>(() => copiarConfig(PADROES));    // a que vale agora (inclui a prévia ao vivo)
  const [dialogo, setDialogo] = useState<"config" | "sobre" | null>(null);
  const [versao, setVersao] = useState("");
  const quemAbriu = useRef<HTMLElement | null>(null);
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
    let vivo = true;
    cfg.carregar().then((c) => vivo && setConfig(c));
    return () => { vivo = false; };
  }, [cfg]);

  // tema, destaque, fontes, tamanho e altura das linhas: tudo vem das Configurações (e da prévia ao vivo)
  useEffect(() => aplicarAparencia(config), [config]);

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
    () => listaDeGeneros(config.generos, faixas.map((f) => f.tags.genre ?? "")), [config.generos, faixas]);   // só os dos arquivos (como a v2): o que se digita não vira sugestão

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

  function abrirDialogo(qual: "config" | "sobre") {
    quemAbriu.current = document.activeElement as HTMLElement | null;
    if (qual === "sobre") void cfg.sobre().then((i) => { setVersao(i.versao); setDialogo("sobre"); });
    else setDialogo("config");
  }

  function fecharDialogo() {
    setDialogo(null);
    queueMicrotask(() => quemAbriu.current?.focus());           // o foco volta para quem abriu
  }

  /** Botão sol/lua: troca o modo na hora e guarda (as outras escolhas ficam como estão). */
  function alternarModo() {
    const nova = { ...config, usar_escuro: !config.usar_escuro };
    setConfig(nova);
    void cfg.salvar(nova);
  }

  const chavePainel = `${selecionadas.map((f) => f.id).join("|")}#${versaoPainel}`;

  useEffect(() => {
    function atalhos(e: KeyboardEvent) {
      if (dialogo !== null) return;                      // com um diálogo aberto, os atalhos são dele
      if (e.key === "F1") {
        e.preventDefault();
        abrirDialogo("sobre");
        return;
      }
      if (!(e.ctrlKey || e.metaKey)) return;
      const tecla = e.key.toLowerCase();
      if (tecla === ",") {
        e.preventDefault();
        abrirDialogo("config");
      } else if (tecla === "f") {
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
        aoAbrirPasta={() => void abrirPasta()}
        filtro={filtro}
        aoMudarFiltro={setFiltro}
        mostrando={exibidas.length}
        total={faixas.length}
        painelVisivel={painelVisivel}
        aoAlternarPainel={alternarPainel}
        escuro={config.usar_escuro}
        aoAlternarModo={alternarModo}
        aoAbrirConfiguracoes={() => abrirDialogo("config")}
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
              alturaLinha={altura_linha(config.tamanho_fonte, config.densidade)}
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
      {dialogo === "config" && (
        <DialogoConfiguracoes config={config} ponte={cfg} aoMudar={setConfig} aoFechar={fecharDialogo} />
      )}
      {dialogo === "sobre" && <Sobre versao={versao} aoFechar={fecharDialogo} />}
    </main>
  );
}
