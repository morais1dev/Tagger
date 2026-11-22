import { describe, expect, it } from "vitest";
import { type Faixa } from "./api";
import { COLUNAS, celulaApagada, celulaPendente, colunasPadrao, duracaoFormatada, temCapaEfetiva, textoDaCelula, tooltipDaCelula } from "./colunas";
import { faixasDeExemplo } from "./mock/ponteSimulada";
import { ordenar, proximaOrdem } from "./ordenacao";
import { SELECAO_VAZIA, clicar, manterVisiveis, selecionarTudo } from "./selecao";

const faixa = (extra: Partial<Faixa> & { id: string }): Faixa => ({
  caminho: `C:\\m\\${extra.id}.mp3`, tags: {}, pendentes: {}, duracao: 100, bitrate: 128, temCapa: false, ...extra,
});

describe("colunas (iguais às da v2)", () => {
  it("mesma ordem e títulos de tabela.COLUNAS", () => {
    expect(COLUNAS.map((c) => c.chave)).toEqual([
      "tracknumber", "title", "artist", "album", "albumartist", "discnumber", "date", "genre", "composer", "lyricist",
      "gravadora", "comment", "lyrics", "duracao", "bitrate", "arquivo", "pasta", "capa", "estado",
    ]);
    expect(COLUNAS.map((c) => c.titulo).slice(0, 5)).toEqual(["Nº", "Título", "Artista", "Álbum", "Artista do álbum"]);
  });

  it("colunas visíveis por padrão", () => {
    expect(colunasPadrao()).toEqual(["tracknumber", "title", "artist", "album", "date", "genre", "duracao", "capa", "estado"]);
  });

  it("textos: vazio vira —, nº só antes da barra, título vazio usa o nome do arquivo, só a 1ª linha", () => {
    const f = faixa({ id: "a", tags: { tracknumber: "3/12", comment: "um\ndois" }, bitrate: null, duracao: 185.4 });
    expect(textoDaCelula(f, "tracknumber")).toBe("3");
    expect(textoDaCelula(f, "title")).toBe("a.mp3");
    expect(textoDaCelula(f, "artist")).toBe("—");
    expect(textoDaCelula(f, "comment")).toBe("um");
    expect(textoDaCelula(f, "lyrics")).toBe("—");
    expect(textoDaCelula(f, "bitrate")).toBe("—");
    expect(textoDaCelula(f, "duracao")).toBe("3:05");
    expect(textoDaCelula(f, "pasta")).toBe("m");
    expect(textoDaCelula({ ...f, bitrate: 320 }, "bitrate")).toBe("320 kbps");
    expect(duracaoFormatada(59.6)).toBe("1:00");
  });

  it("célula pendente mostra o valor pendente, usa cor normal e tem tooltip de estado", () => {
    const f = faixa({ id: "b", tags: { genre: "MPB", artist: "X" }, pendentes: { genre: "Rock" } });
    expect(textoDaCelula(f, "genre")).toBe("Rock");
    expect(celulaPendente(f, "genre")).toBe(true);
    expect(celulaPendente(f, "artist")).toBe(false);
    expect(celulaApagada(f, "genre")).toBe(false);          // pendente: cor normal
    expect(celulaApagada(f, "album")).toBe(true);           // vazia: apagada
    expect(tooltipDaCelula(f, "estado")).toBe("Alterado, não salvo");
    expect(tooltipDaCelula(faixa({ id: "c" }), "estado")).toBeUndefined();
  });

  it("capa pendente vale mais que a capa do arquivo", () => {
    expect(temCapaEfetiva(faixa({ id: "d", temCapa: false, capaPendente: "definir" }))).toBe(true);
    expect(temCapaEfetiva(faixa({ id: "e", temCapa: true, capaPendente: "remover" }))).toBe(false);
    expect(tooltipDaCelula(faixa({ id: "f", temCapa: false }), "capa")).toBe("Sem capa");
  });
});

describe("ordenação", () => {
  const lista = [
    faixa({ id: "1", tags: { tracknumber: "10", title: "beta", artist: "Zé" } }),
    faixa({ id: "2", tags: { tracknumber: "2", title: "Alfa", artist: "" } }),
    faixa({ id: "3", tags: { tracknumber: "", title: "", artist: "ana" } }),
  ];
  const ids = (l: Faixa[]) => l.map((f) => f.id);

  it("números por valor, vazios no fim", () => {
    expect(ids(ordenar(lista, { chave: "tracknumber", direcao: "asc" }))).toEqual(["2", "1", "3"]);
  });

  it("texto sem diferenciar maiúsculas; título vazio usa o nome do arquivo", () => {
    expect(ids(ordenar(lista, { chave: "title", direcao: "asc" }))).toEqual(["3", "2", "1"]);   // 3.mp3 (dígito vem antes), alfa, beta
  });

  it("artista vazio fica no fim ao crescer", () => {
    expect(ids(ordenar(lista, { chave: "artist", direcao: "asc" }))).toEqual(["3", "1", "2"]);
  });

  it("decrescente inverte; sem ordem mantém a de carga e não altera a lista original", () => {
    expect(ids(ordenar(lista, { chave: "tracknumber", direcao: "desc" }))).toEqual(["3", "1", "2"]);
    expect(ids(ordenar(lista, null))).toEqual(["1", "2", "3"]);
    expect(ids(lista)).toEqual(["1", "2", "3"]);
  });

  it("empates ficam na ordem de carga (ordenação estável)", () => {
    const iguais = ["a", "b", "c"].map((id) => faixa({ id, tags: { genre: "Rock" } }));
    expect(ids(ordenar(iguais, { chave: "genre", direcao: "desc" }))).toEqual(["a", "b", "c"]);
  });

  it("duração e capa ordenam por valor", () => {
    const l = [faixa({ id: "x", duracao: 300 }), faixa({ id: "y", duracao: 60, temCapa: true })];
    expect(ids(ordenar(l, { chave: "duracao", direcao: "asc" }))).toEqual(["y", "x"]);
    expect(ids(ordenar(l, { chave: "capa", direcao: "desc" }))).toEqual(["y", "x"]);
  });

  it("clique no cabeçalho: coluna nova cresce, a mesma alterna", () => {
    const a = proximaOrdem(null, "title");
    expect(a).toEqual({ chave: "title", direcao: "asc" });
    expect(proximaOrdem(a, "title")).toEqual({ chave: "title", direcao: "desc" });
    expect(proximaOrdem({ chave: "title", direcao: "desc" }, "artist")).toEqual({ chave: "artist", direcao: "asc" });
  });
});

describe("seleção", () => {
  const v = ["a", "b", "c", "d", "e"];
  const cl = (s: typeof SELECAO_VAZIA, id: string, ctrl = false, shift = false) => clicar(s, id, v, { ctrl, shift });
  const ids = (s: typeof SELECAO_VAZIA) => [...s.ids].sort();

  it("clique simples seleciona só a linha", () => {
    expect(ids(cl(cl(SELECAO_VAZIA, "a"), "c"))).toEqual(["c"]);
  });

  it("Ctrl alterna linhas", () => {
    let s = cl(SELECAO_VAZIA, "a");
    s = cl(s, "c", true);
    expect(ids(s)).toEqual(["a", "c"]);
    expect(ids(cl(s, "a", true))).toEqual(["c"]);
  });

  it("Shift seleciona o intervalo a partir da âncora, nos dois sentidos, sem mexer na âncora", () => {
    let s = cl(SELECAO_VAZIA, "b");
    s = cl(s, "d", false, true);
    expect(ids(s)).toEqual(["b", "c", "d"]);
    s = cl(s, "a", false, true);
    expect(ids(s)).toEqual(["a", "b"]);
    expect(s.ancora).toBe("b");
  });

  it("Ctrl+Shift soma o intervalo à seleção", () => {
    let s = cl(SELECAO_VAZIA, "a");
    s = cl(s, "e", true);                       // a, e (âncora e)
    s = cl(s, "c", true, true);                 // soma c..e
    expect(ids(s)).toEqual(["a", "c", "d", "e"]);
  });

  it("Shift sem âncora age como clique simples", () => {
    expect(ids(cl(SELECAO_VAZIA, "c", false, true))).toEqual(["c"]);
  });

  it("selecionar tudo e manter só o que está visível", () => {
    const todas = selecionarTudo(v, SELECAO_VAZIA);
    expect(ids(todas)).toEqual(v);
    const filtrada = manterVisiveis(todas, ["b", "c"]);
    expect(ids(filtrada)).toEqual(["b", "c"]);
    expect(manterVisiveis(filtrada, ["b", "c"])).toBe(filtrada);       // nada mudou: mesma referência
  });
});

describe("dados de exemplo", () => {
  it("têm faixa com pendência por célula, com capa pendente e sem tags", () => {
    const l = faixasDeExemplo();
    expect(l.some((f) => Object.keys(f.pendentes).length > 0)).toBe(true);
    expect(l.some((f) => f.capaPendente)).toBe(true);
    expect(l.some((f) => Object.keys(f.tags).length === 0)).toBe(true);
  });
});
