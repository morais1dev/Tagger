import { type KeyboardEvent, useId, useState } from "react";
import { type CampoTag, type Faixa, type Ponte, nomeDoArquivo, valorDoCampo } from "../api";
import { duracaoFormatada } from "../colunas";
import {
  CAMPOS_LARGOS_1, CAMPOS_LARGOS_2, CAMPOS_MULTILINHA, CAMPOS_PARES, ROTULOS, TEXTO_VARIOS, campoPendente, valorComum,
} from "../edicao";
import { validarValor } from "../validacao";
import { CapaEditor } from "./CapaEditor";

export interface PropsPainel {
  /** Faixas selecionadas, na ordem da tabela. */
  faixas: readonly Faixa[];
  /** Quantos arquivos têm alteração pendente (rodapé). */
  totalPendentes: number;
  ponte: Ponte;
  generos: readonly string[];
  /** Faixas que a ponte devolveu depois de uma edição (o painel não guarda cópia delas). */
  aoAtualizar(faixas: Faixa[]): void;
  aoAvisar(texto: string): void;
  aoSalvar(): void;
  aoDescartar(): void;
  /** Esc no painel: devolve o foco à tabela. */
  aoEscape(): void;
  confirmar(texto: string): Promise<boolean> | boolean;
}

const COMUNS = ["tracknumber", "discnumber", "date"];

interface PropsCampo {
  campo: CampoTag;
  faixas: readonly Faixa[];
  ponte: Ponte;
  idGeneros: string;
  aoAtualizar(faixas: Faixa[]): void;
  aoEnter(): void;
}

/**
 * Um campo do painel. O texto é local (o painel remonta o campo quando a seleção muda ou o rascunho muda por fora,
 * como o `carregar` da v2); cada digitação vira pendência na ponte.
 */
function Campo({ campo, faixas, ponte, idGeneros, aoAtualizar, aoEnter }: PropsCampo) {
  const id = useId();
  const [inicial] = useState(() => ({
    ...valorComum(faixas, campo),
    // valor pendente de cada faixa antes de editar: apagar o que se digitou numa multisseleção volta a isto
    foto: Object.fromEntries(faixas.map((f) => [f.id, f.pendentes[campo]])) as Record<string, string | undefined>,
  }));
  const [texto, setTexto] = useState(inicial.texto);
  const ids = faixas.map((f) => f.id);
  const validacao = validarValor(campo, texto);
  const erro = validacao.ok ? null : validacao.mensagem;
  const linhas = CAMPOS_MULTILINHA[campo];
  const pendente = campoPendente(faixas, campo);

  async function editar(novo: string) {
    setTexto(novo);
    if (inicial.varios && novo === "") aoAtualizar(await ponte.restaurarCampo(campo, inicial.foto));
    else aoAtualizar(await ponte.definirCampo(ids, campo, novo));
  }

  const comum = {
    id,
    value: texto,
    placeholder: inicial.varios ? TEXTO_VARIOS : "",
    "aria-invalid": erro !== null,
    "aria-describedby": erro ? `${id}-erro` : undefined,
    title: erro ?? undefined,
    "data-campo": campo,
    className: `${COMUNS.includes(campo) ? "mono " : ""}${erro ? "invalido" : ""}`,
  };

  return (
    <div className={`campo campo-${campo}`}>
      <div className="campo-rotulo">
        <label htmlFor={id}>{ROTULOS[campo]}</label>
        {pendente && <span className="marca" role="img" aria-label="Alterado, não salvo" title="Alterado, não salvo">●</span>}
      </div>
      {linhas ? (
        <textarea {...comum} rows={linhas} onChange={(e) => void editar(e.target.value)} />
      ) : (
        <input
          {...comum}
          type="text"
          list={campo === "genre" ? idGeneros : undefined}
          onChange={(e) => void editar(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && aoEnter()}
        />
      )}
      {erro && <div id={`${id}-erro`} className="erro-campo" role="alert">{erro}</div>}
    </div>
  );
}

function Rodape({ total, aoSalvar, aoDescartar }: { total: number; aoSalvar(): void; aoDescartar(): void }) {
  const texto = total === 0 ? "Salvar" : total === 1 ? "Salvar 1 arquivo" : `Salvar ${total} arquivos`;
  return (
    <div className="rodape-painel">
      <button type="button" disabled={total === 0} title="Descartar todas as alterações não salvas" onClick={aoDescartar}>Descartar</button>
      <button type="button" className="primario" disabled={total === 0} title="Salvar todas as alterações pendentes (Ctrl+S)" onClick={aoSalvar}>{texto}</button>
    </div>
  );
}

/** Painel lateral de edição: campos, capa e rodapé (Descartar/Salvar). */
export function PainelEditor(p: PropsPainel) {
  const idGeneros = useId();
  const aoTeclar = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      p.aoEscape();
    }
  };

  if (p.faixas.length === 0) {
    return (
      <aside className="painel" aria-label="Editor de tags" onKeyDown={aoTeclar}>
        <div className="painel-vazio">
          <strong>Nenhum arquivo selecionado</strong>
          <p>Clique em uma música para editar.<br />Use Ctrl, Shift ou arraste o mouse para editar várias.</p>
        </div>
        {p.totalPendentes > 0 && <Rodape total={p.totalPendentes} aoSalvar={p.aoSalvar} aoDescartar={p.aoDescartar} />}
      </aside>
    );
  }

  const unica = p.faixas.length === 1 ? p.faixas[0] : null;
  const salvarComEnter = () => { if (p.totalPendentes > 0) p.aoSalvar(); };
  const campo = (c: CampoTag) => (
    <Campo key={c} campo={c} faixas={p.faixas} ponte={p.ponte} idGeneros={idGeneros} aoAtualizar={p.aoAtualizar} aoEnter={salvarComEnter} />
  );

  return (
    <aside className="painel" aria-label="Editor de tags" onKeyDown={aoTeclar}>
      <div className="painel-corpo">
        <header className="painel-cabecalho">
          {unica ? (
            <>
              <h2>{valorDoCampo(unica, "title") || nomeDoArquivo(unica)}</h2>
              <p title={unica.caminho}>{nomeDoArquivo(unica)} · {duracaoFormatada(unica.duracao)} · {unica.bitrate ? `${unica.bitrate} kbps` : "—"}</p>
            </>
          ) : (
            <>
              <h2>{p.faixas.length} arquivos selecionados</h2>
              <p>Campos diferentes aparecem como {TEXTO_VARIOS} e só mudam se você editar.</p>
            </>
          )}
        </header>
        <CapaEditor faixas={p.faixas} ponte={p.ponte} aoAtualizar={p.aoAtualizar} aoAvisar={p.aoAvisar} confirmar={p.confirmar} />
        {CAMPOS_LARGOS_1.map(campo)}
        <div className="campos-pares">{CAMPOS_PARES.map(campo)}</div>
        {CAMPOS_LARGOS_2.map(campo)}
        {(["comment", "lyrics"] as const).map(campo)}
        <datalist id={idGeneros}>{p.generos.map((g) => <option key={g} value={g} />)}</datalist>
      </div>
      <Rodape total={p.totalPendentes} aoSalvar={p.aoSalvar} aoDescartar={p.aoDescartar} />
    </aside>
  );
}
