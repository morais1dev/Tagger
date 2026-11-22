import { useState } from "react";
import type { CampoTag, Faixa } from "../api";
import { celula, DialogoPadrao, type Calculo, type Celula } from "./DialogoPadrao";
import { entradaDe, plural } from "./DialogoRenomear";
import { houveErro, nomeDeCaminho, ROTULOS, type PonteOperacoes, type ResultadoTagsDoNome } from "./tipos";

export const EXEMPLOS_TAGS = [
  "%artist% - %title%", "%track% - %artist% - %title%", "%track% - %title%", "%track%. %title%",
  "%artist%/%album%/%track% - %title%",
] as const;

export interface PropsTagsDoNome {
  faixas: Faixa[];
  padrao: string;
  recentes: readonly string[];
  ponte: PonteOperacoes;
  /** Os valores lidos vão para o rascunho (nada é gravado até salvar). */
  aoConfirmar: (padrao: string, resultado: ResultadoTagsDoNome) => void;
  aoCancelar: () => void;
}

/** F-05 e F-06: preencher tags pelo nome do arquivo (e pelas pastas), com "Trocar _ por espaço" e "só os vazios". */
export function DialogoTagsDoNome({ faixas, padrao, recentes, ponte, aoConfirmar, aoCancelar }: PropsTagsDoNome) {
  const [sublinhado, setSublinhado] = useState(false);
  const [soVazios, setSoVazios] = useState(false);

  async function calcular(texto: string): Promise<Calculo<ResultadoTagsDoNome> | { erro: string }> {
    const itens = faixas.map((f) => ({ ...entradaDe(f), id: f.id }));
    const previa = await ponte.previaTagsDoNome(itens, texto, { sublinhado, soVazios });
    if (houveErro(previa)) return previa;

    const resultado: ResultadoTagsDoNome = { itens: [] };
    const linhas: Celula[][] = [];
    let naoCasam = 0, invalidos = 0;
    for (const l of previa.linhas) {
      const nome = nomeDeCaminho(l.caminho);
      if (!l.casa) {
        naoCasam++;
        linhas.push([celula(nome, "fraco", l.caminho), celula("não segue o padrão", "fraco"),
          ...Array.from({ length: Math.max(0, previa.campos.length - 1) }, () => celula(""))]);
        continue;
      }
      const valores: Partial<Record<CampoTag, string>> = {};
      const celulas = [celula(nome, "", l.caminho)];
      for (const c of l.campos) {
        if (c.mantido) celulas.push(celula(c.atual, "fraco", "Já tem valor: mantido"));
        else if (c.erro) {
          invalidos++;
          celulas.push(celula(c.novo, "erro", c.erro));
        } else {
          valores[c.campo] = c.novo;
          celulas.push(celula(c.novo));
        }
      }
      if (Object.keys(valores).length) resultado.itens.push({ id: l.id, valores });
      linhas.push(celulas);
    }
    const n = resultado.itens.length;
    let resumo = `${n} ${plural(n, "arquivo", "arquivos")} com tags lidas`;
    if (naoCasam) resumo += ` · ${naoCasam} não seguem o padrão`;
    if (invalidos) resumo += ` · ${invalidos} valores inválidos ignorados`;
    return { cabecalhos: ["Arquivo", ...previa.campos.map((c) => ROTULOS[c])], linhas, resumo, validos: n, resultado };
  }

  return (
    <DialogoPadrao<ResultadoTagsDoNome>
      titulo="Preencher tags pelo nome do arquivo"
      explicacao={'Lê as tags do nome de cada arquivo. %*% ignora um trecho e "/" usa as pastas acima ' +
        "(ex.: %artist%/%album%/%track% - %title%). Os valores ficam pendentes até você salvar."}
      padraoInicial={padrao}
      recentes={recentes}
      exemplos={EXEMPLOS_TAGS}
      formatoCampo={(c) => `%${c}%`}
      extrasMenu={[{ rotulo: "Ignorar trecho", texto: "%*%" }]}
      calcular={calcular}
      dependencias={[sublinhado, soVazios]}
      textoOk={(n) => (n === 0 ? "Preencher" : `Preencher ${n} ${plural(n, "arquivo", "arquivos")}`)}
      opcoes={
        <>
          <label className="op-opcao"><input type="checkbox" checked={sublinhado} onChange={(e) => setSublinhado(e.target.checked)} /> Trocar _ por espaço</label>
          <label className="op-opcao"><input type="checkbox" checked={soVazios} onChange={(e) => setSoVazios(e.target.checked)} /> Preencher só os campos que estão vazios</label>
        </>
      }
      aoConfirmar={aoConfirmar}
      aoCancelar={aoCancelar}
    />
  );
}

