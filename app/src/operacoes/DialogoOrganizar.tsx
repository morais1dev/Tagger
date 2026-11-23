import { useState } from "react";
import type { Faixa } from "../api";
import { celula, DialogoPadrao, type Calculo } from "./DialogoPadrao";
import { entradaDe, plural } from "./DialogoRenomear";
import { relativoA } from "./padroesSimulados";
import { houveErro, nomeDeCaminho, type PlanoOrganizar, type PonteOperacoes } from "./tipos";

export const EXEMPLOS_ORGANIZAR = [
  "{albumartist}/{album}/{tracknumber:02} - {title}", "{artist}/{album}/{tracknumber:02} - {title}",
  "{albumartist}/{date} - {album}/{tracknumber:02} - {title}", "{genre}/{artist} - {title}",
] as const;

/** O que o diálogo devolve ao OK; quem executa move os itens válidos do plano (e as capas). */
export interface ResultadoOrganizar {
  padrao: string;
  plano: PlanoOrganizar;
  pastaDestino: string;
  removerVazias: boolean;
}

export interface PropsOrganizar {
  faixas: Faixa[];
  padrao: string;
  recentes: readonly string[];
  /** Pasta de destino inicial (a pasta aberta ou a da primeira faixa). */
  pastaDestino: string;
  temPendentes?: boolean;
  ponte: PonteOperacoes;
  aoConfirmar: (r: ResultadoOrganizar) => void;
  aoCancelar: () => void;
}

/** F-08 a F-10: organizar em pastas pelas tags, com destino, capa junto e remoção de pastas vazias. */
export function DialogoOrganizar({ faixas, padrao, recentes, pastaDestino, temPendentes, ponte, aoConfirmar, aoCancelar }: PropsOrganizar) {
  const [destino, setDestino] = useState(pastaDestino);
  const [levarCapa, setLevarCapa] = useState(true);
  const [removerVazias, setRemoverVazias] = useState(false);

  async function calcular(texto: string): Promise<Calculo<PlanoOrganizar> | { erro: string }> {
    const plano = await ponte.previaOrganizar(faixas.map(entradaDe), texto, destino.trim(), levarCapa);
    if (houveErro(plano)) return plano;
    const linhas = [];
    let mudam = 0, noLugar = 0, erros = 0;
    for (const item of plano.itens) {
      const nome = nomeDeCaminho(item.origem);
      if (item.erro) {
        erros++;
        linhas.push([celula(nome, "", item.origem), celula(item.erro, "erro", item.erro)]);
      } else if (item.destino === null) {
        noLugar++;
        linhas.push([celula(nome, "fraco", item.origem), celula("(já está no lugar)", "fraco")]);
      } else {
        mudam++;
        linhas.push([celula(nome, "", item.origem), celula(relativoA(item.destino, plano.pasta), "", item.destino)]);
      }
    }
    let resumo = `${mudam} serão movidos`;
    if (plano.capas.length) resumo += ` · ${plano.capas.length} capa(s) vão junto`;
    if (noLugar) resumo += ` · ${noLugar} já estão no lugar`;
    if (erros) resumo += ` · ${erros} com problema (não serão movidos)`;
    return { cabecalhos: ["Arquivo atual", "Novo local"], linhas, resumo, validos: mudam, resultado: plano };
  }

  async function escolher() {
    const pasta = await ponte.escolherPasta(destino);
    if (pasta) setDestino(pasta);
  }

  let explicacao = 'Move cada arquivo para uma pasta montada com as tags: "/" separa as pastas. ' +
    "Tags vazias viram Unknown Artist / Unknown Album, as pastas são criadas e a capa " +
    "(cover.jpg) vai junto. Dá para desfazer com Ctrl+Z.";
  if (temPendentes) explicacao += "\nUsa os valores mostrados na tabela, inclusive alterações ainda não salvas.";

  return (
    <DialogoPadrao<PlanoOrganizar>
      titulo="Organizar arquivos em pastas"
      explicacao={explicacao}
      padraoInicial={padrao}
      recentes={recentes}
      exemplos={EXEMPLOS_ORGANIZAR}
      formatoCampo={(c) => `{${c}}`}
      calcular={calcular}
      dependencias={[destino, levarCapa]}
      textoOk={(n) => (n === 0 ? "Organizar" : `Organizar ${n} ${plural(n, "arquivo", "arquivos")}`)}
      opcoes={
        <>
          <div className="op-linha-destino">
            <input type="text" aria-label="Pasta de destino" placeholder="Pasta de destino" value={destino}
              onChange={(e) => setDestino(e.target.value)} />
            <button type="button" className="op-botao" onClick={escolher}>Escolher…</button>
          </div>
          <label className="op-opcao">
            <input type="checkbox" checked={levarCapa} onChange={(e) => setLevarCapa(e.target.checked)} />
            {" "}Levar a capa da pasta junto (cover.jpg, folder.jpg)
          </label>
          <label className="op-opcao">
            <input type="checkbox" checked={removerVazias} onChange={(e) => setRemoverVazias(e.target.checked)} />
            {" "}Remover as pastas que ficarem vazias
          </label>
        </>
      }
      // o destino entregue é o do plano mostrado, não o que foi digitado depois
      aoConfirmar={(texto, plano) => aoConfirmar({ padrao: texto, plano, pastaDestino: plano.pasta, removerVazias })}
      aoCancelar={aoCancelar}
    />
  );
}
