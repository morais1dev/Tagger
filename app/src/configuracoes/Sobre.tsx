import { useEffect, useRef } from "react";

/** Aviso exigido pelo Discogs (tagger/nucleo/discogs.py AVISO_SOBRE), em inglês como no original. */
export const AVISO_SOBRE =
  "This application uses Discogs' API but is not affiliated with, sponsored or endorsed by Discogs. " +
  "'Discogs' is a trademark of Zink Media, LLC.";

export const LINKS_SOBRE = {
  musicbrainz: "https://musicbrainz.org",
  coverart: "https://coverartarchive.org",
  discogs: "https://www.discogs.com",
} as const;

function Link({ href, children }: { href: string; children: string }) {
  return <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>;
}

/** L-04: versão, fontes dos dados online e o aviso do Discogs. */
export function Sobre({ versao, aoFechar }: { versao: string; aoFechar: () => void }) {
  const fechar = useRef<HTMLButtonElement>(null);
  useEffect(() => fechar.current?.focus(), []);
  return (
    <div className="cfg-fundo" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); aoFechar(); } }}>
      <div role="dialog" aria-modal="true" aria-labelledby="sobre-titulo" className="cfg-janela cfg-sobre">
        <h2 id="sobre-titulo" className="cfg-titulo">Sobre o Tagger</h2>
        <p><b>Tagger {versao}</b><br />Editor de tags de música.</p>
        <p>
          Busca online: tags do <Link href={LINKS_SOBRE.musicbrainz}>MusicBrainz</Link>, capas do{" "}
          <Link href={LINKS_SOBRE.coverart}>Cover Art Archive</Link>, dados do{" "}
          <Link href={LINKS_SOBRE.discogs}>Discogs</Link>.
        </p>
        <p>{AVISO_SOBRE}</p>
        <div className="cfg-rodape">
          <span className="cfg-espaco" />
          <button ref={fechar} type="button" className="cfg-botao cfg-primario" onClick={aoFechar}>Fechar</button>
        </div>
      </div>
    </div>
  );
}
