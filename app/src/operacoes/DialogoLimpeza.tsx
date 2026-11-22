import { useState } from "react";
import { Ajuda, Moldura } from "./Moldura";
import { nomeExtra } from "./nomesExtras";
import type { AnaliseExtras, OpcoesLimpeza } from "./tipos";

export interface PropsLimpeza {
  /** Uma análise por arquivo selecionado (`ponte.analisarExtras`). */
  analises: AnaliseExtras[];
  /** As 3 opções escolhidas; quem executa grava na hora (não dá para desfazer). */
  aoConfirmar: (opcoes: OpcoesLimpeza) => void;
  aoCancelar: () => void;
}

/** F-14 a F-16: limpar tags extras, mostrando o que existe e deixando escolher o que remover. */
export function DialogoLimpeza({ analises, aoConfirmar, aoCancelar }: PropsLimpeza) {
  const n = analises.length;
  const comV1 = analises.filter((a) => a.id3v1).length;
  const comDesconhecidos = analises.filter((a) => a.desconhecidos).length;
  const comExtras = analises.filter((a) => Object.keys(a.extras).length > 0).length;
  const extras: Record<string, number> = {};
  for (const a of analises) for (const [chave, q] of Object.entries(a.extras)) extras[chave] = (extras[chave] ?? 0) + q;

  const [id3v1, setId3v1] = useState(comV1 > 0);
  const [desconhecidos, setDesconhecidos] = useState(comDesconhecidos > 0);
  const [todos, setTodos] = useState(false);

  const linhas = Object.entries(extras)
    .sort((a, b) => b[1] - a[1])
    .map(([chave, q]) => {
      const [curta, descricao] = nomeExtra(chave);
      return `•  ${curta} ×${q}  —  ${descricao}`;
    });

  return (
    <Moldura titulo="Limpar tags extras" aoFechar={aoCancelar}>
      <Ajuda>{`${n} arquivo(s) selecionado(s). A limpeza é gravada na hora e não pode ser desfeita.`}</Ajuda>
      <label className="op-opcao">
        <input type="checkbox" checked={id3v1} disabled={comV1 === 0} onChange={(e) => setId3v1(e.target.checked)} />
        {` Remover a tag ID3v1 antiga (só MP3) — ${comV1} de ${n} arquivo(s)`}
      </label>
      <label className="op-opcao">
        <input type="checkbox" checked={desconhecidos} disabled={comDesconhecidos === 0}
          onChange={(e) => setDesconhecidos(e.target.checked)} />
        {` Remover frames ID3 não reconhecidos (só MP3; corrompidos ou de formato desconhecido) — ${comDesconhecidos} arquivo(s)`}
      </label>
      <label className="op-opcao">
        <input type="checkbox" checked={todos} disabled={linhas.length === 0} onChange={(e) => setTodos(e.target.checked)} />
        {` Remover tudo o que o Tagger não mostra — ${comExtras} arquivo(s)`}
      </label>
      <ul className="op-detalhes" aria-label="Extras encontrados">
        {linhas.length ? linhas.map((l) => <li key={l}>{l}</li>) : <li>Nenhuma tag extra encontrada.</li>}
      </ul>
      <Ajuda>
        Título, artista, capa e todos os campos do editor são sempre mantidos. Em FLAC, Ogg e M4A só a última
        opção se aplica (ID3v1 e frames ID3 são coisa do MP3).
      </Ajuda>
      <div className="op-rodape">
        <span className="op-resumo" />
        <button type="button" className="op-botao" onClick={aoCancelar}>Cancelar</button>
        <button type="button" className="op-botao op-primario" disabled={!(id3v1 || desconhecidos || todos)}
          onClick={() => aoConfirmar({ id3v1, desconhecidos, extras: todos })}>
          Limpar
        </button>
      </div>
    </Moldura>
  );
}
