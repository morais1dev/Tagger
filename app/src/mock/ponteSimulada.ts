import { type CampoTag, type Capa, type Faixa, type Ponte, caminhoDaPasta } from "../api";

/** Capa de exemplo: um quadrado de cor (SVG em data URL), com o tipo e as dimensões que o teste quiser. */
export function capaDeExemplo(cor: string, extras: Partial<Capa> = {}): Capa {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="${cor}"/></svg>`;
  return {
    url: `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
    mime: "image/jpeg", largura: 500, altura: 500, bytes: 24 * 1024,
    ...extras,
  };
}

export const CAPA_AZUL = capaDeExemplo("#3b6fd4");
export const CAPA_VERDE = capaDeExemplo("#2f9e6e", { mime: "image/png", largura: 600, altura: 600, bytes: 80 * 1024 });

/** Faixas de exemplo: dois álbuns, uma faixa sem tags e algumas com pendências. */
export function faixasDeExemplo(): Faixa[] {
  const base = (n: number, titulo: string, extra: Partial<Faixa> = {}): Faixa => {
    const caminho = `C:\\Musicas\\Disco Raro\\${String(n).padStart(2, "0")} - ${titulo}.mp3`;
    return {
      id: caminho,
      caminho,
      tags: { title: titulo, artist: "Banda", album: "Disco Raro", albumartist: "Banda", tracknumber: `${n}/5`, date: "1977", genre: "MPB" },
      pendentes: {},
      duracao: 180 + n * 7,
      bitrate: 320,
      temCapa: true,
      capa: CAPA_AZUL,
      ...extra,
    };
  };
  return [
    base(1, "Abertura"),
    base(2, "Segunda", { pendentes: { genre: "Rock" } }),
    base(3, "Terceira", { bitrate: null }),
    base(4, "Quarta", { temCapa: false, capa: undefined, capaPendente: "definir", capaNova: CAPA_VERDE }),
    base(5, "Fechamento", { pendentes: { title: "Fechamento (ao vivo)", date: "1978" } }),
    {
      id: "C:\\Musicas\\Avulsas\\sem-tags.flac", caminho: "C:\\Musicas\\Avulsas\\sem-tags.flac",
      tags: {}, pendentes: {}, duracao: 95, bitrate: 900, temCapa: false,
    },
    {
      id: "C:\\Musicas\\Avulsas\\Outra.m4a", caminho: "C:\\Musicas\\Avulsas\\Outra.m4a",
      tags: { title: "Outra", artist: "Solista", album: "Singles", tracknumber: "10", genre: "Pop", comment: "primeira linha\nsegunda linha" },
      pendentes: {}, duracao: 201, bitrate: 256, temCapa: false,
    },
  ];
}

export interface OpcoesSimuladas {
  /** O que o seletor de imagem devolve (null = cancelou). Padrão: uma capa verde. */
  imagemEscolhida?: Capa | null;
  /** O que há na área de transferência (null = nada). */
  areaDeTransferencia?: Capa | null;
  /** Pastas que já têm o arquivo cover.* (para testar a confirmação de substituir). */
  pastasComCover?: string[];
  /** Pastas onde gravar o cover falha. */
  pastasComFalha?: string[];
  /** Nome do arquivo que o diálogo de exportar "gravou"; null = cancelou. Padrão: o sugerido. */
  nomeExportado?: string | null;
}

export interface RegistrosSimulados {
  exportadas: { nome: string; capa: Capa }[];
  covers: { pastas: string[]; nome: string; capa: Capa }[];
  salvamentos: number;
}

export type PonteSimulada = Ponte & { registros: RegistrosSimulados };

/** Ponte em memória: não toca em disco nem na rede. */
export function ponteSimulada(inicial: Faixa[] = faixasDeExemplo(), opcoes: OpcoesSimuladas = {}): PonteSimulada {
  const faixas = inicial.map((f) => structuredClone(f));
  const registros: RegistrosSimulados = { exportadas: [], covers: [], salvamentos: 0 };
  const achar = (id: string) => {
    const faixa = faixas.find((f) => f.id === id);
    if (!faixa) throw new Error(`Faixa desconhecida: ${id}`);
    return faixa;
  };
  const copia = (ids: string[]) => ids.map((id) => structuredClone(achar(id)));
  const pastasDe = (ids: string[]) => [...new Set(ids.map((id) => caminhoDaPasta(achar(id))))];

  function pendente(faixa: Faixa, campo: CampoTag, valor: string) {
    if ((faixa.tags[campo] ?? "") === valor) delete faixa.pendentes[campo];     // voltou ao original: sem pendência
    else faixa.pendentes[campo] = valor;
  }

  return {
    registros,
    async abrirPasta() {
      return structuredClone(faixas);
    },
    async definirPendente(id, campo, valor) {
      const faixa = achar(id);
      pendente(faixa, campo, valor);
      return structuredClone(faixa);
    },
    async definirCampo(ids, campo, valor) {
      for (const id of ids) pendente(achar(id), campo, valor);
      return copia(ids);
    },
    async restaurarCampo(campo, foto) {
      const ids = Object.keys(foto);
      for (const id of ids) {
        const faixa = achar(id);
        const antes = foto[id];
        if (antes === undefined) delete faixa.pendentes[campo];
        else faixa.pendentes[campo] = antes;
      }
      return copia(ids);
    },
    async definirCapa(ids, acao) {
      for (const id of ids) {
        const faixa = achar(id);
        delete faixa.capaNova;
        if (acao === null) delete faixa.capaPendente;
        else if (acao.tipo === "remover") faixa.capaPendente = "remover";
        else {
          faixa.capaPendente = "definir";
          faixa.capaNova = acao.capa;
        }
      }
      return copia(ids);
    },
    async descartarPendencias(ids) {
      for (const id of ids) {
        const faixa = achar(id);
        faixa.pendentes = {};
        delete faixa.capaPendente;
        delete faixa.capaNova;
      }
      return copia(ids);
    },
    async salvar() {
      registros.salvamentos += 1;
      for (const faixa of faixas) {
        for (const [campo, valor] of Object.entries(faixa.pendentes) as [CampoTag, string][]) {
          if (valor === "") delete faixa.tags[campo];
          else faixa.tags[campo] = valor;
        }
        faixa.pendentes = {};
        if (faixa.capaPendente === "definir" && faixa.capaNova) {
          faixa.temCapa = true;
          faixa.capa = faixa.capaNova;
        } else if (faixa.capaPendente === "remover") {
          faixa.temCapa = false;
          delete faixa.capa;
        }
        delete faixa.capaPendente;
        delete faixa.capaNova;
      }
      return structuredClone(faixas);
    },
    async escolherImagem() {
      return opcoes.imagemEscolhida === undefined ? CAPA_VERDE : opcoes.imagemEscolhida;
    },
    async lerImagemDaAreaDeTransferencia() {
      return opcoes.areaDeTransferencia ?? null;
    },
    async exportarCapa(capa, nomeSugerido) {
      const nome = opcoes.nomeExportado === undefined ? nomeSugerido : opcoes.nomeExportado;
      if (nome !== null) registros.exportadas.push({ nome, capa });
      return nome;
    },
    async pastasComCover(ids) {
      return pastasDe(ids).filter((p) => (opcoes.pastasComCover ?? []).includes(p));
    },
    async salvarCoverNaPasta(ids, capa, nome) {
      const pastas = pastasDe(ids);
      const falhas = pastas.filter((p) => (opcoes.pastasComFalha ?? []).includes(p));
      registros.covers.push({ pastas: pastas.filter((p) => !falhas.includes(p)), nome, capa });
      return { gravadas: pastas.length - falhas.length, falhas: falhas.length };
    },
  };
}
