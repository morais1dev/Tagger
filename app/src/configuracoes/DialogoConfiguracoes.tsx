import { useEffect, useRef, useState } from "react";
import { AbaAparencia } from "./AbaAparencia";
import { AbaComportamento } from "./AbaComportamento";
import { AbaServicos } from "./AbaServicos";
import { AbaTags } from "./AbaTags";
import type { PonteConfig } from "./ponteConfig";
import { Sobre } from "./Sobre";
import {
  CHAVES_CREDENCIAL, CHAVES_DO_USUARIO, copiarConfig, PADROES, type Config,
} from "./tipos";
import { normalizarConfig } from "./validacao";
import "./configuracoes.css";

const ABAS = ["Aparência", "Comportamento", "Tags", "Serviços online"] as const;

/**
 * Config para a prévia ao vivo, com as credenciais ainda como estavam: a chave colada só chega
 * ao resto do app no OK, nunca fica na sessão depois de um Cancelar (v2: DialogoConfiguracoes.previa).
 */
export function previaDe(atual: Config, original: Config): Config {
  const previa = copiarConfig(atual);
  for (const chave of CHAVES_CREDENCIAL) previa[chave] = original[chave];
  return previa;
}

/** "Restaurar padrões": volta ao padrão, menos o que a janela não mostra (padrões de nome) e as credenciais. */
export function restaurarPadroes(atual: Config): Config {
  const novo = copiarConfig(PADROES);
  for (const chave of [...CHAVES_DO_USUARIO, ...CHAVES_CREDENCIAL]) {
    (novo as unknown as Record<string, unknown>)[chave] = (copiarConfig(atual) as unknown as Record<string, unknown>)[chave];
  }
  return novo;
}

export interface PropsDialogo {
  /** Configuração atual quando a janela abre. */
  config: Config;
  ponte: PonteConfig;
  /** Prévia ao vivo (sem credenciais novas); no Cancelar recebe os valores antigos. */
  aoMudar: (config: Config) => void;
  /** Fecha a janela; `aceito` = clicou em OK (a configuração já foi salva pela ponte). */
  aoFechar: (aceito: boolean) => void;
}

/** J-01 a J-25: as 4 abas das Configurações, com prévia ao vivo, Cancelar que desfaz e OK que salva. */
export function DialogoConfiguracoes({ config: inicial, ponte, aoMudar, aoFechar }: PropsDialogo) {
  const original = useRef(copiarConfig(inicial)).current;
  const [config, setConfig] = useState(() => copiarConfig(inicial));
  const [aba, setAba] = useState<number>(0);
  const [fontes, setFontes] = useState<string[]>([]);
  const [sobre, setSobre] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  // foco inicial dentro do diálogo (e de volta a ele quando o Sobre fecha): sem isso o Esc só funcionaria depois de um clique
  useEffect(() => {
    if (sobre === null) document.getElementById(`cfg-aba-${aba}`)?.focus();
  }, [sobre]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let vivo = true;
    ponte.fontesInstaladas().then((f) => vivo && setFontes(f));
    return () => { vivo = false; };
  }, [ponte]);

  function aplicar(novo: Config) {
    setConfig(novo);
    aoMudar(previaDe(novo, original));
  }

  function mudar(parcial: Partial<Config>) {
    aplicar({ ...config, ...parcial });
  }

  function cancelar() {
    aoMudar(copiarConfig(original)); // volta tudo como estava
    aoFechar(false);
  }

  async function confirmar() {
    setSalvando(true);
    const final = normalizarConfig(config);
    await ponte.salvar(final);
    aoMudar(final); // só agora as credenciais chegam ao resto do app
    aoFechar(true);
  }

  async function abrirSobre() {
    setSobre((await ponte.sobre()).versao);
  }

  const abaAtual = [
    <AbaAparencia key="a" config={config} mudar={mudar} fontes={fontes} />,
    <AbaComportamento key="c" config={config} mudar={mudar} />,
    <AbaTags key="t" config={config} mudar={mudar} />,
    <AbaServicos key="s" config={config} mudar={mudar} />,
  ][aba];

  return (
    <div className="cfg-fundo" onKeyDown={(e) => {
      if (sobre !== null) return;
      if (e.key === "Escape") cancelar();
      else if (e.key === "F1") { e.preventDefault(); void abrirSobre(); }
    }}>
      <div role="dialog" aria-modal="true" aria-labelledby="cfg-titulo" className="cfg-janela">
        <h2 id="cfg-titulo" className="cfg-titulo">Configurações</h2>

        <div role="tablist" aria-label="Seções" className="cfg-abas">
          {ABAS.map((nome, i) => (
            <button
              key={nome}
              role="tab"
              type="button"
              id={`cfg-aba-${i}`}
              aria-selected={aba === i}
              aria-controls="cfg-painel"
              tabIndex={aba === i ? 0 : -1}
              onClick={() => setAba(i)}
              onKeyDown={(e) => {
                const passo = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
                if (passo) {
                  e.preventDefault();
                  const proxima = (i + passo + ABAS.length) % ABAS.length;
                  setAba(proxima);
                  document.getElementById(`cfg-aba-${proxima}`)?.focus();
                }
              }}
            >
              {nome}
            </button>
          ))}
        </div>
        <div role="tabpanel" id="cfg-painel" aria-labelledby={`cfg-aba-${aba}`} className="cfg-painel">
          {abaAtual}
        </div>

        <div className="cfg-rodape">
          <button type="button" className="cfg-botao cfg-fantasma" onClick={() => aplicar(restaurarPadroes(config))}>
            Restaurar padrões
          </button>
          <button type="button" className="cfg-botao cfg-fantasma" onClick={abrirSobre}
            title="Versão, serviços online e avisos (F1)">
            Sobre o Tagger
          </button>
          <span className="cfg-espaco" />
          <button type="button" className="cfg-botao" onClick={cancelar}>Cancelar</button>
          <button type="button" className="cfg-botao cfg-primario" disabled={salvando} onClick={confirmar}>OK</button>
        </div>
      </div>
      {sobre !== null && <Sobre versao={sobre} aoFechar={() => setSobre(null)} />}
    </div>
  );
}
