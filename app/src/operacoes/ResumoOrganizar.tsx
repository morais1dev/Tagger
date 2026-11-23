import { Moldura } from "./Moldura";
import { resumoFalhas, resumoMovimentos } from "./padroesSimulados";
import type { PonteOperacoes } from "./tipos";

export interface PropsResumo {
  /** [origem, destino] do que foi movido. */
  feitos: Array<[string, string]>;
  /** origem -> motivo do que não foi movido. */
  falhas: Record<string, string>;
  pasta: string;
  ponte: PonteOperacoes;
  aoFechar: () => void;
}

/** F-13: depois de mover, para onde cada arquivo foi (era → agora está em), com "Abrir pasta". */
export function ResumoOrganizar({ feitos, falhas, pasta, ponte, aoFechar }: PropsResumo) {
  const nFalhas = Object.keys(falhas).length;
  let titulo = feitos.length ? `${feitos.length} arquivo(s) movido(s) para ${pasta}` : "Nenhum arquivo foi movido.";
  if (nFalhas) titulo += `${feitos.length ? " · " : " "}${nFalhas} não foram movidos e continuam onde estavam:`;
  const linhas = [...resumoMovimentos(feitos, pasta), ...resumoFalhas(falhas, pasta)];
  return (
    <Moldura titulo="Arquivos organizados" aoFechar={aoFechar}>
      <p className="op-ajuda">{titulo}</p>
      <div className="op-previa">
        <table aria-label="Resumo">
          <thead>
            <tr><th scope="col">Era</th><th scope="col">{feitos.length ? "Agora está em" : "Motivo"}</th></tr>
          </thead>
          <tbody>
            {linhas.map(([origem, destino], i) => (
              <tr key={i}>
                <td title={origem}>{origem}</td>
                <td title={destino}>{destino}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="op-rodape">
        <span className="op-resumo" />
        <button type="button" className="op-botao" onClick={() => ponte.abrirPasta(pasta)}>Abrir pasta</button>
        <button type="button" className="op-botao op-primario" data-foco onClick={aoFechar}>Fechar</button>
      </div>
    </Moldura>
  );
}
