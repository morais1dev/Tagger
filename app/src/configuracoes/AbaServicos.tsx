import { useId, useState } from "react";
import type { PropsAba } from "./AbaAparencia";
import { Ajuda, Secao } from "./Campos";

/** J-19 e J-20: token pessoal do Discogs, oculto como senha, e o guia de como gerá-lo. */
export function AbaServicos({ config, mudar }: PropsAba) {
  const id = useId();
  const [visivel, setVisivel] = useState(false);
  const [guia, setGuia] = useState(false);
  return (
    <div className="cfg-aba">
      <Secao>Suas chaves (opcional)</Secao>
      <Ajuda>Deixe em branco para usar a chave do Tagger. Use a sua se a busca parar de funcionar ou se você usa muito.</Ajuda>
      <label className="cfg-rotulo" htmlFor={id}>Token pessoal do Discogs (opcional)</label>
      <div className="cfg-senha">
        <input
          id={id}
          type={visivel ? "text" : "password"}
          autoComplete="off"
          spellCheck={false}
          placeholder="Em branco = chave do Tagger"
          aria-label="Token pessoal do Discogs"
          value={config.discogs_token}
          onChange={(e) => mudar({ discogs_token: e.target.value.trim() })}
        />
        <button type="button" className="cfg-botao" aria-pressed={visivel} aria-label={visivel ? "Ocultar token pessoal do discogs" : "Mostrar token pessoal do discogs"}
          onClick={() => setVisivel((v) => !v)}>
          {visivel ? "Ocultar" : "Mostrar"}
        </button>
      </div>

      <button type="button" className="cfg-guia" aria-expanded={guia} onClick={() => setGuia((g) => !g)}>
        <span aria-hidden="true">{guia ? "▾" : "▸"}</span> Como gerar a minha chave?
      </button>
      {guia && (
        <div className="cfg-tutorial">
          <p><b>Discogs</b></p>
          <ol>
            <li>Entre na sua conta do Discogs.</li>
            <li>
              Vá em Configurações → Desenvolvedores (
              <a href="https://www.discogs.com/settings/developers" target="_blank" rel="noopener noreferrer">
                discogs.com/settings/developers
              </a>
              ).
            </li>
            <li>Clique em "Gerar novo token".</li>
            <li>Copie o token e cole aqui. O token é pessoal: não compartilhe com ninguém.</li>
          </ol>
        </div>
      )}
    </div>
  );
}
