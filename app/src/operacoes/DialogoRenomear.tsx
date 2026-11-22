import { CAMPOS_TAG, valorDoCampo, type Faixa } from "../api";
import { celula, DialogoPadrao, type Calculo } from "./DialogoPadrao";
import { houveErro, itemValido, nomeDeCaminho, type ItemEntrada, type PlanoRenomear, type PonteOperacoes } from "./tipos";

export const EXEMPLOS_RENOMEAR = [
  "{tracknumber:02} - {artist} - {title}", "{tracknumber:02} - {title}", "{artist} - {title}",
  "{discnumber}-{tracknumber:02} {title}",
] as const;

/** Tags de cada faixa já com as alterações pendentes, como a tabela mostra. */
export function entradaDe(faixa: Faixa): ItemEntrada {
  return { caminho: faixa.caminho, valores: Object.fromEntries(CAMPOS_TAG.map((c) => [c, valorDoCampo(faixa, c)])) };
}

export function plural(n: number, um: string, varios: string): string {
  return n === 1 ? um : varios;
}

export interface PropsRenomear {
  faixas: Faixa[];
  padrao: string;
  recentes: readonly string[];
  /** Alguma faixa tem alteração pendente: o diálogo avisa que a prévia a usa. */
  temPendentes?: boolean;
  ponte: PonteOperacoes;
  /** Recebe o plano completo; quem executa renomeia só os itens válidos (`itemValido`). */
  aoConfirmar: (padrao: string, plano: PlanoRenomear) => void;
  aoCancelar: () => void;
}

/** F-01 a F-03: renomear arquivos pelas tags, com prévia ao vivo. */
export function DialogoRenomear({ faixas, padrao, recentes, temPendentes, ponte, aoConfirmar, aoCancelar }: PropsRenomear) {
  async function calcular(texto: string): Promise<Calculo<PlanoRenomear> | { erro: string }> {
    const plano = await ponte.previaRenomear(faixas.map(entradaDe), texto);
    if (houveErro(plano)) return plano;
    const linhas = [];
    let mudam = 0, iguais = 0, erros = 0;
    for (const item of plano) {
      const nome = nomeDeCaminho(item.origem);
      if (item.erro) {
        erros++;
        linhas.push([celula(nome, "", item.origem), celula(item.erro, "erro", item.erro)]);
      } else if (item.destino === null) {
        iguais++;
        linhas.push([celula(nome, "fraco", item.origem), celula("(sem mudança)", "fraco")]);
      } else {
        mudam++;
        linhas.push([celula(nome, "", item.origem), celula(nomeDeCaminho(item.destino))]);
      }
    }
    let resumo = `${mudam} serão renomeados`;
    if (iguais) resumo += ` · ${iguais} já estão com esse nome`;
    if (erros) resumo += ` · ${erros} com problema (não serão renomeados)`;
    return { cabecalhos: ["Nome atual", "Novo nome"], linhas, resumo, validos: mudam, resultado: plano };
  }

  let explicacao = "Monte o novo nome com os campos das tags. {tracknumber:02} completa com zeros (03). " +
    "Caracteres que o Windows não aceita são trocados. Dá para desfazer com Ctrl+Z.";
  if (temPendentes) explicacao += "\nUsa os valores mostrados na tabela, inclusive alterações ainda não salvas.";

  return (
    <DialogoPadrao<PlanoRenomear>
      titulo="Renomear arquivos pelas tags"
      explicacao={explicacao}
      padraoInicial={padrao}
      recentes={recentes}
      exemplos={EXEMPLOS_RENOMEAR}
      formatoCampo={(c) => `{${c}}`}
      calcular={calcular}
      textoOk={(n) => (n === 0 ? "Renomear" : `Renomear ${n} ${plural(n, "arquivo", "arquivos")}`)}
      aoConfirmar={aoConfirmar}
      aoCancelar={aoCancelar}
    />
  );
}

export { itemValido };
