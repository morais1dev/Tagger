import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { CAMPOS_TAG, type CampoTag } from "../api";
import { Ajuda, Moldura } from "./Moldura";
import { ESPERA_PREVIA_MS, MAX_LINHAS_PREVIA, MAX_RECENTES, ROTULOS } from "./tipos";

export type TipoCelula = "" | "fraco" | "erro";
export interface Celula {
  texto: string;
  tipo: TipoCelula;
  dica: string;
}

/** O que o diálogo mostra para um padrão: tabela de prévia, resumo e quantos itens valem. */
export interface Calculo<R> {
  cabecalhos: string[];
  linhas: Celula[][];
  resumo: string;
  validos: number;
  resultado: R;
}

export const celula = (texto: string, tipo: TipoCelula = "", dica = ""): Celula => ({ texto, tipo, dica });

/** Lista de padrões recentes com este no topo, sem repetir (padrao.lembrar_padrao da v2). */
export function lembrarPadrao(recentes: readonly string[], padrao: string): string[] {
  return [...new Set([padrao, ...recentes])].slice(0, MAX_RECENTES);
}

export interface PropsPadrao<R> {
  titulo: string;
  explicacao: string;
  padraoInicial: string;
  recentes: readonly string[];
  exemplos: readonly string[];
  /** "{campo}" ou "%campo%". */
  formatoCampo: (campo: CampoTag) => string;
  /** Itens extras do menu "Inserir campo" (ex.: "Ignorar trecho"). */
  extrasMenu?: ReadonlyArray<{ rotulo: string; texto: string }>;
  /** Calcula a prévia; `{ erro }` mostra a mensagem e desliga o botão. Não precisa ser estável. */
  calcular: (padrao: string) => Promise<Calculo<R> | { erro: string }>;
  /** Valores (opções extras) que, ao mudar, refazem a prévia. */
  dependencias?: readonly unknown[];
  textoOk: (n: number) => string;
  /** Opções extras, entre o campo do padrão e a prévia. */
  opcoes?: ReactNode;
  /** Recebe o padrão e o resultado DO MESMO cálculo (nunca o texto digitado depois). */
  aoConfirmar: (padrao: string, resultado: R) => void;
  aoCancelar: () => void;
}

/** Um cálculo pronto, com o padrão e as dependências com que foi feito. */
interface Pronto<R> {
  padrao: string;
  deps: string;
  calculo: Calculo<R> | null;
  erro: string;
}

/** Base dos diálogos de padrão: campo com recentes, "Inserir campo", opções e prévia ao vivo (F-01, F-05, F-08). */
export function DialogoPadrao<R>(p: PropsPadrao<R>) {
  const [padrao, setPadrao] = useState(p.padraoInicial);
  const [pronto, setPronto] = useState<Pronto<R> | null>(null);
  const [menu, setMenu] = useState(false);
  const [lista, setLista] = useState(false);
  const campo = useRef<HTMLInputElement>(null);
  const calcularAtual = useRef(p.calcular);
  calcularAtual.current = p.calcular;
  const itensLista = lembrarPadrao([...p.recentes, ...p.exemplos], p.padraoInicial);
  const texto = padrao.trim();
  const deps = JSON.stringify(p.dependencias ?? []);

  useEffect(() => {
    let atual = true;
    const espera = pronto === null ? 0 : ESPERA_PREVIA_MS; // a 1ª prévia sai na hora
    const timer = setTimeout(async () => {
      let r: Calculo<R> | { erro: string };
      if (!texto) r = { erro: "Digite um padrão." };
      else {
        try {
          r = await calcularAtual.current(texto);
        } catch (e) {
          r = { erro: e instanceof Error ? e.message : String(e) };
        }
      }
      if (!atual) return;
      setPronto("erro" in r ? { padrao: texto, deps, calculo: null, erro: r.erro } : { padrao: texto, deps, calculo: r, erro: "" });
    }, espera);
    return () => { atual = false; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [texto, deps]);

  function inserir(token: string) {
    const el = campo.current;
    const ini = el?.selectionStart ?? padrao.length;
    const fim = el?.selectionEnd ?? padrao.length;
    setPadrao(padrao.slice(0, ini) + token + padrao.slice(fim));
    setMenu(false);
    requestAnimationFrame(() => {
      el?.focus();
      el?.setSelectionRange(ini + token.length, ini + token.length);
    });
  }

  function escolherRecente(item: string) {
    setPadrao(item);
    setLista(false);
    campo.current?.focus();
  }

  /** Esc com o menu ou a lista aberta fecha só ele; sem nenhum, o Esc chega à moldura e cancela. */
  function aoTeclar(e: KeyboardEvent) {
    if (e.key === "Escape" && (menu || lista)) {
      e.stopPropagation();
      setMenu(false);
      setLista(false);
      campo.current?.focus();
    }
  }

  const atualizado = pronto !== null && pronto.padrao === texto && pronto.deps === deps;
  const erro = atualizado ? pronto.erro : "";
  const calculo = pronto?.calculo ?? null;
  const validos = calculo?.validos ?? 0;
  const mostradas = calculo ? calculo.linhas.slice(0, MAX_LINHAS_PREVIA) : [];
  const resumo = calculo
    ? calculo.resumo + (calculo.linhas.length > MAX_LINHAS_PREVIA ? ` · prévia das primeiras ${MAX_LINHAS_PREVIA}` : "")
    : "";
  // o OK só vale para o que está na tela: texto ou opções diferentes do último cálculo o desligam
  const podeConfirmar = atualizado && !pronto.erro && validos > 0;

  return (
    <Moldura titulo={p.titulo} aoFechar={p.aoCancelar} larga>
      <div className="op-conteudo" onKeyDown={aoTeclar}>
        <Ajuda>{p.explicacao}</Ajuda>
        <div className="op-linha-padrao">
          <input
            ref={campo}
            data-foco
            type="text"
            className="op-mono"
            aria-label="Padrão"
            value={padrao}
            spellCheck={false}
            onChange={(e) => setPadrao(e.target.value)}
          />
          <div className="op-menu-pai">
            <button type="button" className="op-botao op-seta" aria-label="Padrões recentes" aria-haspopup="listbox"
              aria-expanded={lista} onClick={() => { setLista((l) => !l); setMenu(false); }}>
              <span aria-hidden="true">▾</span>
            </button>
            {lista && (
              <ul role="listbox" className="op-menu op-lista" aria-label="Padrões recentes">
                {itensLista.map((item) => (
                  <li key={item} role="none">
                    <button type="button" role="option" aria-selected={item === padrao} className="op-mono"
                      onClick={() => escolherRecente(item)}>
                      {item}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="op-menu-pai">
            <button type="button" className="op-botao" aria-haspopup="menu" aria-expanded={menu}
              onClick={() => { setMenu((m) => !m); setLista(false); }}>
              Inserir campo
            </button>
            {menu && (
              <ul role="menu" className="op-menu" aria-label="Campos">
                {CAMPOS_TAG.map((c) => (
                  <li key={c} role="none">
                    <button type="button" role="menuitem" onClick={() => inserir(p.formatoCampo(c))}>
                      {`${ROTULOS[c]}    ${p.formatoCampo(c)}`}
                    </button>
                  </li>
                ))}
                {p.extrasMenu && <li role="separator" className="op-separador" />}
                {p.extrasMenu?.map((x) => (
                  <li key={x.texto} role="none">
                    <button type="button" role="menuitem" onClick={() => inserir(x.texto)}>{`${x.rotulo}    ${x.texto}`}</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
        {erro && <p role="alert" className="op-erro">{erro}</p>}
        {p.opcoes && <div className="op-opcoes">{p.opcoes}</div>}

        <div className="op-previa">
          <table aria-label="Prévia">
            <thead>
              <tr>{(calculo?.cabecalhos ?? []).map((c, i) => <th key={`${c}${i}`} scope="col">{c}</th>)}</tr>
            </thead>
            <tbody>
              {mostradas.map((linha, i) => (
                <tr key={i}>
                  {linha.map((c, j) => (
                    <td key={j} className={c.tipo ? `op-${c.tipo}` : undefined} title={c.dica || undefined}>{c.texto}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="op-rodape">
          <span className="op-resumo" aria-live="polite">{resumo}</span>
          <button type="button" className="op-botao" onClick={p.aoCancelar}>Cancelar</button>
          <button
            type="button"
            className="op-botao op-primario"
            disabled={!podeConfirmar}
            onClick={() => podeConfirmar && calculo && p.aoConfirmar(pronto.padrao, calculo.resultado)}
          >
            {p.textoOk(pronto && !pronto.erro ? validos : 0)}
          </button>
        </div>
      </div>
    </Moldura>
  );
}
