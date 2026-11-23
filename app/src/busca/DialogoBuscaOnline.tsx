import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import {
  ATRIBUICAO_DISCOGS, ATRIBUICAO_MUSICBRAINZ, DESCRICOES, DICA_SEM_DISCOGS, DISCOGS, DOMINIOS_DISCOGS,
  ErroBusca, FONTES, MUSICBRAINZ, NAO_ENCONTRADO, NOMES, ROTULOS, URL_SITE_DISCOGS, primeiroValor, urlSegura,
  type Atribuicao, type Candidato, type Capa, type Detalhe, type EstadosServicos, type FaixaBusca, type Fonte,
  type PonteBusca, type Resultado,
} from "./tipos";
import "./busca.css";

export interface PropsBusca {
  faixas: FaixaBusca[];
  ponte: PonteBusca;
  /** Serviços que dependem de credencial. Pode mudar com a janela aberta (Configurações salvas). */
  estados: EstadosServicos;
  fonteInicial?: Fonte;
  /** Aplicar ao rascunho: o resultado é o do estado mostrado na tela; nada é gravado. */
  aoAplicar: (resultado: Resultado) => void;
  aoCancelar: () => void;
  /** Link "Sobre" (versão e avisos dos serviços). */
  aoAbrirSobre?: () => void;
}

interface Lista {
  /** Fonte que realmente trouxe os itens (pode ser o Discogs como alternativa). */
  fonte: Fonte;
  itens: Candidato[];
}

const mensagemDe = (e: unknown): string => (e instanceof ErroBusca ? e.message : "Erro inesperado (detalhes no tagger.log).");
const foiInterrompido = (e: unknown): boolean => e instanceof Error && e.name === "AbortError";

function AtribuicaoTexto({ atribuicao, url, textoLink }: { atribuicao: string; url?: string; textoLink?: string }) {
  const link = urlSegura(url, DOMINIOS_DISCOGS);
  return (
    <>
      {atribuicao}
      {link && <>{" "}<a href={link} target="_blank" rel="noopener noreferrer">{textoLink ?? "Ver o release no Discogs"}</a></>}
    </>
  );
}

/** G-01 a G-12: busca de tags no MusicBrainz ou no Discogs, com prévia antes/depois, e aplicação ao rascunho. */
export function DialogoBuscaOnline({ faixas, ponte, estados, fonteInicial = MUSICBRAINZ, aoAplicar, aoCancelar, aoAbrirSobre }: PropsBusca) {
  const discogsOk = estados.discogs.disponivel;
  const dicaDiscogs = estados.discogs.dica || DICA_SEM_DISCOGS;
  const [fonte, setFonte] = useState<Fonte>(fonteInicial === DISCOGS && !discogsOk ? MUSICBRAINZ : fonteInicial);
  const [artista, setArtista] = useState(() => primeiroValor(faixas, "albumartist") || primeiroValor(faixas, "artist"));
  const [album, setAlbum] = useState(() => primeiroValor(faixas, "album"));
  const [titulo, setTitulo] = useState(() => (faixas.length === 1 ? primeiroValor(faixas, "title") : ""));
  const [alternativa, setAlternativa] = useState(true);
  const [baixarCapa, setBaixarCapa] = useState(true);
  const [lista, setLista] = useState<Lista | null>(null);
  const [selecionado, setSelecionado] = useState<string | null>(null);
  const [detalhes, setDetalhes] = useState<Record<string, Detalhe>>({});
  const [falhas, setFalhas] = useState<Record<string, true>>({});
  const [ocupado, setOcupado] = useState(false);
  const [mensagem, setMensagem] = useState(DESCRICOES[fonteInicial]);
  const [carregando, setCarregando] = useState(false);

  // geração: cada busca/troca de fonte a incrementa; respostas de gerações velhas são descartadas
  const geracao = useRef(0);
  const fechado = useRef(false);
  const controle = useRef(new AbortController());
  const idLista = useId();

  useEffect(() => () => { fechado.current = true; controle.current.abort(); }, []);

  const alternativaAtiva = alternativa && discogsOk;
  const avisoAlternativa = lista && lista.fonte !== fonte ? `O ${NOMES[fonte]} não achou nada; resultados do ${NOMES[lista.fonte]}. ` : "";
  const detalhe = selecionado ? detalhes[selecionado] : undefined;
  const faixaDe = useCallback((id: string) => faixas.find((f) => f.id === id), [faixas]);

  function reiniciar(texto: string) {
    geracao.current++;
    controle.current.abort();
    controle.current = new AbortController();
    setLista(null);
    setSelecionado(null);
    setDetalhes({});
    setFalhas({});
    setCarregando(false);
    setOcupado(false);
    setMensagem(texto);
  }

  function trocarFonte(nova: Fonte) {
    if (ocupado || nova === fonte) return;
    setFonte(nova);
    reiniciar(DESCRICOES[nova]);
  }

  // credenciais mudaram com a janela aberta: o Discogs pode ter ficado indisponível
  useEffect(() => {
    if (discogsOk) return;
    if (fonte === DISCOGS) setFonte(MUSICBRAINZ);
    if (lista?.fonte === DISCOGS) reiniciar("As credenciais do Discogs mudaram: busque de novo.");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [discogsOk]);

  async function buscar() {
    if (ocupado) return;
    const g = ++geracao.current;
    controle.current.abort();
    controle.current = new AbortController();
    const sinal = controle.current.signal;
    const termos = { artista, album, titulo };
    const comAlternativa = fonte === MUSICBRAINZ && alternativaAtiva;
    setLista(null);
    setSelecionado(null);
    setDetalhes({});
    setFalhas({});
    setOcupado(true);
    setMensagem(`Buscando no ${NOMES[fonte]}...`);
    try {
      let usada: Fonte = fonte;
      let itens: Candidato[];
      try {
        itens = await ponte.buscar(fonte, termos, sinal);
      } catch (e) {
        if (!comAlternativa || !(e instanceof ErroBusca) || e.message !== NAO_ENCONTRADO) throw e;
        itens = [];
      }
      if (!itens.length && comAlternativa) {
        usada = DISCOGS;
        itens = await ponte.buscar(DISCOGS, termos, sinal);   // sem nada também no Discogs: o erro "Nada encontrado." chega ao usuário
      }
      if (fechado.current || g !== geracao.current) return;
      setLista({ fonte: usada, itens });
      const aviso = usada !== fonte ? `O ${NOMES[fonte]} não achou nada; resultados do ${NOMES[usada]}. ` : "";
      setMensagem(itens.length ? `${aviso}${itens.length} resultado(s). Escolha o álbum certo e confira a prévia.` : "Nenhum resultado. Tente outro nome.");
      setSelecionado(itens[0]?.id ?? null);
    } catch (e) {
      if (fechado.current || g !== geracao.current || foiInterrompido(e)) return;
      setMensagem(mensagemDe(e));
    } finally {
      if (!fechado.current && g === geracao.current) setOcupado(false);
    }
  }

  // baixa o release escolhido e a prévia dele (uma consulta por vez; escolher outro enquanto ocupado fica na fila)
  useEffect(() => {
    if (!lista || !selecionado || ocupado || detalhes[selecionado] || falhas[selecionado]) return;
    const g = geracao.current;
    const sinal = controle.current.signal;
    const alvo = selecionado;
    setOcupado(true);
    setCarregando(true);
    setMensagem("Baixando dados do álbum...");
    ponte.detalhar(lista.fonte, alvo, faixas, sinal)
      .then((d) => {
        if (fechado.current || g !== geracao.current) return;
        setDetalhes((antes) => ({ ...antes, [alvo]: d }));
        setMensagem(`${lista.fonte !== fonte ? `O ${NOMES[fonte]} não achou nada; resultados do ${NOMES[lista.fonte]}. ` : ""}Confira a prévia e clique em Aplicar ao rascunho. Nada é gravado até você salvar.`);
      })
      .catch((e) => {
        if (fechado.current || g !== geracao.current || foiInterrompido(e)) return;
        setFalhas((antes) => ({ ...antes, [alvo]: true }));
        setMensagem(mensagemDe(e));
      })
      .finally(() => {
        if (fechado.current || g !== geracao.current) return;
        setCarregando(false);
        setOcupado(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lista, selecionado, ocupado, detalhes, falhas]);

  function escolher(id: string) {
    setSelecionado(id);
    if (detalhes[id]) setMensagem(`${avisoAlternativa}Confira a prévia e clique em Aplicar ao rascunho. Nada é gravado até você salvar.`);
  }

  const podeAplicar = !ocupado && !!lista && !!detalhe && detalhe.casadas.length > 0;

  async function aplicar() {
    if (!podeAplicar || !lista || !detalhe || !selecionado) return;
    const d = detalhe;
    const alvo = selecionado;
    const g = geracao.current;
    const sinal = controle.current.signal;
    let capa: Capa | null = null;
    if (lista.fonte === MUSICBRAINZ && baixarCapa) {
      setOcupado(true);
      setMensagem("Baixando a capa do Cover Art Archive...");
      try {
        capa = await ponte.baixarCapa(alvo, sinal);
      } catch (e) {
        if (fechado.current || g !== geracao.current || foiInterrompido(e)) return;
        setMensagem(`Capa não baixada: ${mensagemDe(e)}`);
      }
      if (fechado.current || g !== geracao.current) return;
      setOcupado(false);
    }
    if (!d.alteracoes.length && !capa) {
      setMensagem("Nada a alterar: as faixas já têm esses dados.");
      return;
    }
    fechado.current = true;
    controle.current.abort();
    aoAplicar({ alteracoes: d.alteracoes, capa, casadas: d.casadas, semPar: d.semPar });
  }

  /** Cancelar não espera a rede: interrompe o que estiver em andamento e fecha na hora. */
  function cancelar() {
    fechado.current = true;
    controle.current.abort();
    aoCancelar();
  }

  /** Setas escolhem o resultado anterior/seguinte (a lista inteira fica visível; nada de <datalist>). */
  function navegar(e: KeyboardEvent) {
    if (!lista?.itens.length || (e.key !== "ArrowDown" && e.key !== "ArrowUp")) return;
    e.preventDefault();
    const i = lista.itens.findIndex((c) => c.id === selecionado);
    const novo = Math.min(lista.itens.length - 1, Math.max(0, i + (e.key === "ArrowDown" ? 1 : -1)));
    escolher(lista.itens[novo].id);
  }


  const linhas = detalhe
    ? detalhe.alteracoes.flatMap((a) => {
        const f = faixaDe(a.id);
        return Object.entries(a.mudancas).map(([campo, depois]) => ({
          arquivo: f?.nome ?? a.id,
          campo: ROTULOS[campo as keyof typeof ROTULOS],
          antes: f?.valores[campo as keyof typeof ROTULOS] ?? "",
          depois: depois ?? "",
        }));
      })
    : [];
  let textoPrevia = "Prévia: escolha um resultado.";
  if (selecionado && detalhe) {
    if (!detalhe.casadas.length) textoPrevia = "Nenhuma das faixas casa com esse álbum (confira título e número da faixa).";
    else if (!detalhe.alteracoes.length) textoPrevia = "Nada a alterar nas tags: as faixas já têm esses dados.";
    else textoPrevia = `Prévia: ${detalhe.alteracoes.length} arquivo(s), ${linhas.length} alteração(ões).`;
    if (detalhe.semPar.length) {
      const nomes = detalhe.semPar.slice(0, 3).map((id) => faixaDe(id)?.nome ?? id).join(", ");
      textoPrevia += ` ${detalhe.semPar.length} faixa(s) sem par não mudam: ${nomes}`;
    }
  } else if (selecionado && falhas[selecionado]) textoPrevia = "Prévia indisponível.";
  else if (selecionado && carregando) textoPrevia = "Carregando a prévia...";

  const atribuicao: Atribuicao = detalhe
    ? detalhe.atribuicao
    : { texto: fonte === DISCOGS ? ATRIBUICAO_DISCOGS : ATRIBUICAO_MUSICBRAINZ, url: fonte === DISCOGS ? URL_SITE_DISCOGS : undefined, textoLink: "discogs.com" };
  const fonteComCapa = (lista?.fonte ?? fonte) === MUSICBRAINZ;
  const caixa = useRef<HTMLDivElement>(null);
  const cancelarAtual = useRef(cancelar);
  cancelarAtual.current = cancelar;
  useEffect(() => {
    caixa.current?.querySelector<HTMLElement>("[data-foco]")?.focus();
    // Esc vale em qualquer lugar do diálogo, inclusive depois que o botão focado fica desligado (o foco cai no corpo)
    const aoTeclar = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") cancelarAtual.current(); };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, []);

  return (
    <div className="bo-fundo">
      <div ref={caixa} role="dialog" aria-modal="true" aria-labelledby="bo-titulo" className="bo-janela">
        <h2 id="bo-titulo" className="bo-titulo">Buscar tags online</h2>

        <div className="bo-fonte" role="radiogroup" aria-label="Fonte">
          <span>Fonte</span>
          {FONTES.map((f) => {
            const disponivel = f === MUSICBRAINZ || discogsOk;
            return (
              <label key={f} title={disponivel ? DESCRICOES[f] : dicaDiscogs} className={disponivel ? undefined : "bo-desligado"}>
                <input type="radio" name="fonte" checked={fonte === f} disabled={ocupado || !disponivel} onChange={() => trocarFonte(f)} />
                {" "}{NOMES[f]}
              </label>
            );
          })}
        </div>
        {fonte === MUSICBRAINZ && (
          <label className="bo-opcao" title={discogsOk ? undefined : dicaDiscogs}>
            <input type="checkbox" checked={alternativaAtiva} disabled={!discogsOk} onChange={(e) => setAlternativa(e.target.checked)} />
            {" "}Se o MusicBrainz não achar, buscar no Discogs
          </label>
        )}

        <form className="bo-form" onSubmit={(e) => { e.preventDefault(); buscar(); }}>
          <label>Artista<input type="text" data-foco value={artista} onChange={(e) => setArtista(e.target.value)} /></label>
          <label>Álbum<input type="text" value={album} onChange={(e) => setAlbum(e.target.value)} /></label>
          <label>Título<input type="text" placeholder="só se não houver álbum" value={titulo} onChange={(e) => setTitulo(e.target.value)} /></label>
          <button type="submit" className="bo-botao" disabled={ocupado}>Buscar</button>
        </form>

        <ul id={idLista} role="listbox" aria-label="Resultados" className="bo-lista" tabIndex={0} onKeyDown={navegar}>
          {lista?.itens.map((c) => (
            <li key={c.id} role="option" aria-selected={c.id === selecionado} tabIndex={-1}
              onClick={() => escolher(c.id)} onDoubleClick={() => { escolher(c.id); if (c.id === selecionado) aplicar(); }}>
              {c.descricao}
            </li>
          ))}
        </ul>

        <p className="bo-ajuda" data-testid="texto-previa">{textoPrevia}</p>
        <div className="bo-previa">
          <table aria-label="Prévia">
            <thead><tr><th scope="col">Arquivo</th><th scope="col">Campo</th><th scope="col">Antes</th><th scope="col">Depois</th></tr></thead>
            <tbody>
              {linhas.map((l, i) => (
                <tr key={i}><td>{l.arquivo}</td><td>{l.campo}</td><td>{l.antes}</td><td>{l.depois}</td></tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bo-atribuicao">
          <span data-testid="atribuicao">
            <AtribuicaoTexto atribuicao={atribuicao.texto} url={atribuicao.url} textoLink={atribuicao.textoLink} />
          </span>
          {aoAbrirSobre && <button type="button" className="bo-link" title="Sobre o Tagger e os serviços online (F1)" onClick={aoAbrirSobre}>Sobre</button>}
        </div>
        <p className="bo-estado" role="status">{mensagem}</p>

        <div className="bo-rodape">
          {fonteComCapa && (
            <label className="bo-opcao" title="Capa do Cover Art Archive (só com o MusicBrainz)">
              <input type="checkbox" checked={baixarCapa} onChange={(e) => setBaixarCapa(e.target.checked)} /> Baixar a capa
            </label>
          )}
          <span className="bo-espaco" />
          <button type="button" className="bo-botao" onClick={cancelar}>Cancelar</button>
          <button type="button" className="bo-botao bo-primario" disabled={!podeAplicar} onClick={aplicar}>Aplicar ao rascunho</button>
        </div>
      </div>
    </div>
  );
}
