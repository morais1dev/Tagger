import { useId, useState } from "react";
import { TEMAS } from "../temas";
import { Ajuda, CampoNumero, Linha } from "./Campos";
import { ACENTO_DO_TEMA, ACENTOS, DENSIDADES, TAMANHO_FONTE, type Config, type Densidade } from "./tipos";
import { corValida } from "./validacao";

export interface PropsAba {
  config: Config;
  mudar: (parcial: Partial<Config>) => void;
}

const AUTOMATICA = "Automática";

function temas(escuro: boolean) {
  return Object.entries(TEMAS).filter(([, t]) => t.escuro === escuro);
}

function CorPersonalizada({ acento, mudar }: { acento: string; mudar: PropsAba["mudar"] }) {
  const id = useId();
  const [aberto, setAberto] = useState(false);
  const [texto, setTexto] = useState(corValida(acento) ? acento : "#");
  const invalido = !corValida(texto);
  const personalizada = acento !== ACENTO_DO_TEMA && !ACENTOS.some((a) => a.cor === acento.toLowerCase());
  return (
    <>
      <button
        type="button"
        className="cfg-botao"
        aria-pressed={personalizada}
        title="Escolher qualquer cor"
        onClick={() => setAberto((a) => !a)}
      >
        Personalizada…
      </button>
      {aberto && (
        <span className="cfg-cor-livre">
          <input
            id={id}
            type="text"
            aria-label="Cor personalizada (#rrggbb)"
            aria-invalid={invalido}
            value={texto}
            maxLength={7}
            onChange={(e) => {
              setTexto(e.target.value);
              if (corValida(e.target.value)) mudar({ acento: e.target.value.toLowerCase() });
            }}
          />
          {invalido && <span role="alert" className="cfg-erro">Cor inválida. Use o formato #rrggbb.</span>}
        </span>
      )}
    </>
  );
}

/** J-02 a J-07: modo, temas, cor de destaque, fontes, tamanho e altura das linhas. */
export function AbaAparencia({ config, mudar, fontes }: PropsAba & { fontes: string[] }) {
  const ids = { escuro: useId(), claro: useId(), fonte: useId(), mono: useId(), dens: useId() };
  return (
    <div className="cfg-aba">
      <Linha rotulo="Modo">
        <div role="radiogroup" aria-label="Modo" className="cfg-radios">
          <label><input type="radio" name="modo" checked={config.usar_escuro} onChange={() => mudar({ usar_escuro: true })} /> Escuro</label>
          <label><input type="radio" name="modo" checked={!config.usar_escuro} onChange={() => mudar({ usar_escuro: false })} /> Claro</label>
        </div>
      </Linha>

      <Linha rotulo="Tema escuro" para={ids.escuro}>
        <select id={ids.escuro} value={config.tema_escuro} onChange={(e) => mudar({ tema_escuro: e.target.value })}>
          {temas(true).map(([id, t]) => <option key={id} value={id}>{t.nome}</option>)}
        </select>
      </Linha>
      <Linha rotulo="Tema claro" para={ids.claro}>
        <select id={ids.claro} value={config.tema_claro} onChange={(e) => mudar({ tema_claro: e.target.value })}>
          {temas(false).map(([id, t]) => <option key={id} value={id}>{t.nome}</option>)}
        </select>
      </Linha>

      <Linha rotulo="Cor de destaque">
        <div className="cfg-acentos">
          <div className="cfg-amostras">
            {ACENTOS.map((a) => (
              <button
                key={a.cor}
                type="button"
                className="cfg-amostra"
                style={{ background: a.cor }}
                title={a.nome}
                aria-label={`Cor de destaque ${a.nome}`}
                aria-pressed={config.acento.toLowerCase() === a.cor}
                onClick={() => mudar({ acento: a.cor })}
              />
            ))}
          </div>
          <div className="cfg-botoes-cor">
            <button
              type="button"
              className="cfg-botao"
              aria-pressed={config.acento === ACENTO_DO_TEMA}
              title="Usa a cor de destaque de cada tema (ex.: roxo no Dracula)"
              onClick={() => mudar({ acento: ACENTO_DO_TEMA })}
            >
              Do tema
            </button>
            <CorPersonalizada acento={config.acento} mudar={mudar} />
          </div>
        </div>
      </Linha>

      <Linha rotulo="Fonte da interface" para={ids.fonte}>
        <select id={ids.fonte} value={config.fonte} onChange={(e) => mudar({ fonte: e.target.value })}>
          <option value="">{AUTOMATICA}</option>
          {fontes.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </Linha>
      <Linha rotulo="Fonte dos números" para={ids.mono}>
        <select id={ids.mono} value={config.fonte_mono} onChange={(e) => mudar({ fonte_mono: e.target.value })}>
          <option value="">{AUTOMATICA}</option>
          {fontes.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </Linha>

      <Linha rotulo="Tamanho da fonte">
        <CampoNumero
          rotulo="Tamanho da fonte"
          valor={config.tamanho_fonte}
          min={TAMANHO_FONTE.min}
          max={TAMANHO_FONTE.max}
          sufixo="px"
          aoMudar={(n) => mudar({ tamanho_fonte: n })}
        />
      </Linha>

      <Linha rotulo="Altura das linhas" para={ids.dens}>
        <select id={ids.dens} value={config.densidade} onChange={(e) => mudar({ densidade: e.target.value as Densidade })}>
          {Object.entries(DENSIDADES).map(([id, nome]) => <option key={id} value={id}>{nome}</option>)}
        </select>
      </Linha>
      <Ajuda>Cada mudança é aplicada na hora. Cancelar volta tudo ao que estava.</Ajuda>
    </div>
  );
}
