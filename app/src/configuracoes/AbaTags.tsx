import { useEffect, useId, useState } from "react";
import type { PropsAba } from "./AbaAparencia";
import { Ajuda, CampoNumero, Opcao, Secao } from "./Campos";
import { LADO_CAPA } from "./tipos";
import { dividirGeneros } from "./validacao";

/** Lista de gêneros: o texto digitado fica local (uma linha por gênero) e só as linhas não vazias vão para a configuração. */
function Generos({ generos, aoMudar }: { generos: string[]; aoMudar: (g: string[]) => void }) {
  const id = useId();
  const [texto, setTexto] = useState(generos.join("\n"));
  useEffect(() => {
    // mudou por fora (Restaurar padrões, importação)
    setTexto((atual) => (dividirGeneros(atual).join("\n") === generos.join("\n") ? atual : generos.join("\n")));
  }, [generos]);
  return (
    <textarea
      id={id}
      aria-label="Gêneros sugeridos"
      rows={8}
      value={texto}
      onChange={(e) => {
        setTexto(e.target.value);
        aoMudar(dividirGeneros(e.target.value));
      }}
    />
  );
}

/** J-13 a J-18. */
export function AbaTags({ config, mudar }: PropsAba) {
  return (
    <div className="cfg-aba">
      <Secao>Versão do ID3 ao salvar (só MP3)</Secao>
      <Ajuda>FLAC, Ogg e M4A usam o formato de tags próprio deles; as opções de ID3 não mudam nada nesses arquivos.</Ajuda>
      <div role="radiogroup" aria-label="Versão do ID3" className="cfg-radios cfg-coluna">
        <label>
          <input type="radio" name="id3" checked={config.versao_id3 === 3} onChange={() => mudar({ versao_id3: 3 })} />
          {" "}ID3v2.3 — mais compatível (Windows Explorer, carros, players antigos)
        </label>
        <label>
          <input type="radio" name="id3" checked={config.versao_id3 === 4} onChange={() => mudar({ versao_id3: 4 })} />
          {" "}ID3v2.4 — mais recente
        </label>
      </div>

      <Secao>Ao salvar</Secao>
      <Opcao rotulo={'Gravar "A; B" como vários valores (artista, gênero, compositor…)'} marcado={config.multivalor}
        dica={'Players modernos mostram cada artista/gênero separado. Desligado, "A; B" é gravado como um texto só. Vale para todos os formatos.'}
        aoMudar={(v) => mudar({ multivalor: v })} />
      <Opcao rotulo="Remover a tag ID3v1 antiga (dos anos 90) dos MP3 salvos" marcado={config.remover_id3v1}
        dica="Só existe em MP3. FLAC, Ogg e M4A não são afetados." aoMudar={(v) => mudar({ remover_id3v1: v })} />

      <Secao>Capa</Secao>
      <div className="cfg-capa">
        <Opcao rotulo="Reduzir capas grandes ao inserir, para no máximo" marcado={config.otimizar_capa}
          aoMudar={(v) => mudar({ otimizar_capa: v })} />
        <CampoNumero rotulo="Lado máximo da capa" valor={config.lado_max_capa} min={LADO_CAPA.min} max={LADO_CAPA.max}
          passo={LADO_CAPA.passo} sufixo="px" desabilitado={!config.otimizar_capa}
          aoMudar={(n) => mudar({ lado_max_capa: n })} />
      </div>
      <Ajuda>Imagens maiores que isso (ou com mais de 500 KB) viram JPEG. Uma capa de 5 MB em cada faixa pesa no álbum inteiro.</Ajuda>

      <Secao>Gêneros sugeridos no autocompletar</Secao>
      <Ajuda>Um por linha. Os gêneros que já estão nos seus arquivos também aparecem.</Ajuda>
      <Generos generos={config.generos} aoMudar={(g) => mudar({ generos: g })} />
    </div>
  );
}
