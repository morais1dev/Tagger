import { Ajuda, Opcao } from "./Campos";
import type { PropsAba } from "./AbaAparencia";

/** J-08 a J-12. */
export function AbaComportamento({ config, mudar }: PropsAba) {
  return (
    <div className="cfg-aba">
      <Opcao rotulo="Incluir subpastas ao abrir uma pasta" marcado={config.subpastas}
        aoMudar={(v) => mudar({ subpastas: v })} />
      <Opcao rotulo="Reabrir a última pasta ao iniciar o Tagger" marcado={config.reabrir_ultima}
        aoMudar={(v) => mudar({ reabrir_ultima: v })} />
      <Opcao rotulo="Incluir o total ao numerar faixas (ex.: 3/12 em vez de 3)" marcado={config.numerar_com_total}
        aoMudar={(v) => mudar({ numerar_com_total: v })} />
      <Opcao rotulo="Agrupar a lista por álbum (com mais de um álbum carregado)" marcado={config.agrupar_por_album}
        aoMudar={(v) => mudar({ agrupar_por_album: v })} />
      <Opcao rotulo="Avisar quando houver uma versão nova do Tagger (consulta o GitHub, no máximo 1x por dia)"
        marcado={config.avisar_nova_versao} aoMudar={(v) => mudar({ avisar_nova_versao: v })} />
      <Ajuda>
        Alterações ficam pendentes (com o ponto verde) até você clicar em Salvar, inclusive as feitas por
        Desfazer, Numerar faixas, Colar tags e edição direto na tabela.
      </Ajuda>
    </div>
  );
}
