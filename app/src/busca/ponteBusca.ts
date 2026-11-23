// Ponte simulada da busca online: nada sai pela rede. Os "serviços" são releases de mentira e o núcleo
// Rust (tagger-core) entra no lugar com a mesma interface (PonteBusca).

import { analisarSimulado, type ReleaseSimulado } from "./analiseSimulada";
import {
  ATRIBUICAO_DISCOGS, ATRIBUICAO_MUSICBRAINZ, DISCOGS, ErroBusca, MUSICBRAINZ, NAO_ENCONTRADO, type Capa, type Fonte,
  type PonteBusca,
} from "./tipos";

export interface OpcoesPonteBusca {
  musicbrainz?: ReleaseSimulado[];
  discogs?: ReleaseSimulado[];
  /** Capa devolvida por candidato do MusicBrainz (ausente = o release não tem capa). */
  capas?: Record<string, Capa | null>;
  /** Atraso de cada resposta, em ms (0 = só uma microtarefa). */
  atrasoMs?: number;
  /** Erro de rede por operação (mensagem já legível). */
  erroBuscar?: Partial<Record<Fonte, string>>;
  erroDetalhar?: string;
  erroCapa?: string;
  /** Nunca responde: só a interrupção (AbortSignal) encerra. Para testar "cancelar sem esperar a rede". */
  pendurar?: boolean;
}

export interface PonteBuscaSimulada extends PonteBusca {
  /** Chamadas feitas, para os testes. */
  readonly chamadas: Array<{ operacao: "buscar" | "detalhar" | "capa"; fonte?: Fonte; candidato?: string }>;
}

const abortou = (): Error => Object.assign(new Error("Interrompido."), { name: "AbortError" });

const normalizar = (t: string): string => t.toLowerCase().replace(/[\W_]+/gu, " ").trim();

export function criarPonteSimulada(o: OpcoesPonteBusca = {}): PonteBuscaSimulada {
  const chamadas: PonteBuscaSimulada["chamadas"] = [];
  const base: Record<Fonte, ReleaseSimulado[]> = { musicbrainz: o.musicbrainz ?? [], discogs: o.discogs ?? [] };

  /** Espera o atraso configurado; interrompe se o sinal disparar. */
  function esperar(sinal: AbortSignal): Promise<void> {
    return new Promise((resolver, rejeitar) => {
      if (sinal.aborted) return rejeitar(abortou());
      const timer = o.pendurar ? undefined : setTimeout(resolver, o.atrasoMs ?? 0);
      sinal.addEventListener("abort", () => { clearTimeout(timer); rejeitar(abortou()); }, { once: true });
    });
  }

  const achar = (fonte: Fonte, id: string): ReleaseSimulado => {
    const r = base[fonte].find((x) => x.id === id);
    if (!r) throw new ErroBusca("Release não encontrado.");
    return r;
  };

  return {
    chamadas,
    async buscar(fonte, termos, sinal) {
      chamadas.push({ operacao: "buscar", fonte });
      await esperar(sinal);
      const erro = o.erroBuscar?.[fonte];
      if (erro) throw new ErroBusca(erro);
      const { artista, album, titulo } = termos;
      if (!artista.trim() && !album.trim() && !titulo.trim()) throw new ErroBusca("Digite o artista, o álbum ou o título.");
      const acha = (texto: string, alvo: string) => !texto.trim() || normalizar(alvo).includes(normalizar(texto));
      const achados = base[fonte].filter((r) =>
        acha(artista, r.artista) && acha(album, r.titulo) && (album.trim() || acha(titulo, r.faixas.map((f) => f.titulo).join(" "))));
      if (!achados.length) throw new ErroBusca(NAO_ENCONTRADO);
      return achados.map((r) => ({ id: r.id, descricao: r.descricao }));
    },
    async detalhar(fonte, candidato, faixas, sinal) {
      chamadas.push({ operacao: "detalhar", fonte, candidato });
      await esperar(sinal);
      if (o.erroDetalhar) throw new ErroBusca(o.erroDetalhar);
      const r = achar(fonte, candidato);
      const discogs = fonte === DISCOGS;
      return analisarSimulado(faixas, r, discogs,
        discogs ? { texto: ATRIBUICAO_DISCOGS, url: r.url } : { texto: ATRIBUICAO_MUSICBRAINZ });
    },
    async baixarCapa(candidato, sinal) {
      chamadas.push({ operacao: "capa", fonte: MUSICBRAINZ, candidato });
      await esperar(sinal);
      if (o.erroCapa) throw new ErroBusca(o.erroCapa);
      return o.capas?.[candidato] ?? null;
    },
  };
}
