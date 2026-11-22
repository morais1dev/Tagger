import { useEffect, useId, useRef, useState, type ReactNode } from "react";
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
  return [padrao, ...recentes.filter((p) => p !== padrao)].slice(0, MAX_RECENTES);
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
  aoConfirmar: (padrao: string, resultado: R) => void;
  aoCancelar: () => void;
}

/** Base dos diálogos de padrão: campo com recentes, "Inserir campo", opções e prévia ao vivo (F-01, F-05, F-08). */
export function DialogoPadrao<R>(p: PropsPadrao<R>) {
  const [padrao, setPadrao] = useState(p.padraoInicial);
  const [calculo, setCalculo] = useState<Calculo<R> | null>(null);
  const [erro, setErro] = useState("");
  const [menu, setMenu] = useState(false);
  const campo = useRef<HTMLInputElement>(null);
  const calcularAtual = useRef(p.calcular);
  calcularAtual.current = p.calcular;
  const idLista = useId();
  const itensLista = lembrarPadrao([...p.recentes, ...p.exemplos], p.padraoInicial);
  const texto = padrao.trim();

  useEffect(() => {
    let atual = true;
    const espera = calculo === null && erro === "" ? 0 : ESPERA_PREVIA_MS; // a 1ª prévia sai na hora
    const timer = setTimeout(async () => {
      if (!texto) {
        if (atual) { setErro("Digite um padrão."); setCalculo(null); }
        return;
      }
      let r: Calculo<R> | { erro: string };
      try {
        r = await calcularAtual.current(texto);
      } catch (e) {
        r = { erro: e instanceof Error ? e.message : String(e) };
      }
      if (!atual) return;
      if ("erro" in r) {
        setErro(r.erro);
        setCalculo(null);
      } else {
        setErro("");
        setCalculo(r);
      }
    }, espera);
    return () => { atual = false; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [texto, ...(p.dependencias ?? [])]);

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

  const validos = erro || !calculo ? 0 : calculo.validos;
  const mostradas = calculo ? calculo.linhas.slice(0, MAX_LINHAS_PREVIA) : [];
  const resumo = calculo
    ? calculo.resumo + (calculo.linhas.length > MAX_LINHAS_PREVIA ? ` · prévia das primeiras ${MAX_LINHAS_PREVIA}` : "")
    : "";

  return (
    <Moldura titulo={p.titulo} aoFechar={p.aoCancelar} larga>
      <Ajuda>{p.explicacao}</Ajuda>
      <div className="op-linha-padrao">
        <input
          ref={campo}
          type="text"
          className="op-mono"
          aria-label="Padrão"
          list={idLista}
          value={padrao}
          spellCheck={false}
          onChange={(e) => setPadrao(e.target.value)}
        />
        <datalist id={idLista}>
          {itensLista.map((i) => <option key={i} value={i} />)}
        </datalist>
        <div className="op-menu-pai">
          <button type="button" className="op-botao" aria-haspopup="menu" aria-expanded={menu} onClick={() => setMenu((m) => !m)}>
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
          disabled={validos === 0}
          onClick={() => calculo && p.aoConfirmar(texto, calculo.resultado)}
        >
          {p.textoOk(validos)}
        </button>
      </div>
    </Moldura>
  );
}
