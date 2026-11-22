import { type CampoTag, type Faixa, type Ponte } from "../api";

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
      ...extra,
    };
  };
  return [
    base(1, "Abertura"),
    base(2, "Segunda", { pendentes: { genre: "Rock" } }),
    base(3, "Terceira", { bitrate: null }),
    base(4, "Quarta", { temCapa: false, capaPendente: "definir" }),
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

/** Ponte em memória: não toca em disco nem na rede. */
export function ponteSimulada(inicial: Faixa[] = faixasDeExemplo()): Ponte {
  const faixas = inicial.map((f) => structuredClone(f));
  const achar = (id: string) => {
    const faixa = faixas.find((f) => f.id === id);
    if (!faixa) throw new Error(`Faixa desconhecida: ${id}`);
    return faixa;
  };
  return {
    async abrirPasta() {
      return structuredClone(faixas);
    },
    async definirPendente(id: string, campo: CampoTag, valor: string) {
      const faixa = achar(id);
      if ((faixa.tags[campo] ?? "") === valor) delete faixa.pendentes[campo];     // voltou ao original: sem pendência
      else faixa.pendentes[campo] = valor;
      return structuredClone(faixa);
    },
    async descartarPendencias(ids: string[]) {
      for (const id of ids) {
        const faixa = achar(id);
        faixa.pendentes = {};
        delete faixa.capaPendente;
      }
      return ids.map((id) => structuredClone(achar(id)));
    },
  };
}
