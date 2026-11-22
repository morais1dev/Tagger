import { describe, expect, it } from "vitest";
import { type Faixa } from "./api";
import { COLUNAS, celulaApagada, celulaPendente, colunasPadrao, duracaoFormatada, temCapaEfetiva, textoDaCelula, tooltipDaCelula } from "./colunas";
import { faixasDeExemplo } from "./mock/ponteSimulada";
import { ordenar, proximaOrdem } from "./ordenacao";
import { SELECAO_VAZIA, arrastar, clicar, manterVisiveis, navegar, selecionarTudo } from "./selecao";

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

  it("o tooltip da capa usa a capa do arquivo, não a pendente (como na v2)", () => {
    expect(tooltipDaCelula(faixa({ id: "g", temCapa: false, capaPendente: "definir" }), "capa")).toBe("Sem capa");
    expect(tooltipDaCelula(faixa({ id: "h", temCapa: true, capaPendente: "remover" }), "capa")).toBe("Tem capa");
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

  it("Pasta ordena pelo caminho completo da pasta: X\\CD1 e Y\\CD1 não empatam", () => {
    const l = [
      faixa({ id: "y1", caminho: "C:\\Y\\CD1\\a.mp3" }),
      faixa({ id: "x2", caminho: "C:\\X\\CD2\\a.mp3" }),
      faixa({ id: "x1", caminho: "C:\\x\\CD1\\a.mp3" }),
      faixa({ id: "y0", caminho: "C:\\Y\\CD1\\b.mp3" }),
    ];
    expect(ids(ordenar(l, { chave: "pasta", direcao: "asc" }))).toEqual(["x1", "x2", "y1", "y0"]);   // caixa ignorada, empate estável
    expect(ids(ordenar(l, { chave: "pasta", direcao: "desc" }))).toEqual(["y1", "y0", "x2", "x1"]);
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

describe("seleção: arrastar e teclado", () => {
  const v = ["a", "b", "c", "d", "e", "f", "g"];
  const ids = (s: typeof SELECAO_VAZIA) => [...s.ids].sort();
  const sel = (id: string) => clicar(SELECAO_VAZIA, id, v, { ctrl: false, shift: false });

  it("arrastar seleciona da linha apertada até a linha sob o mouse, nos dois sentidos", () => {
    const base = sel("c");
    expect(ids(arrastar(base, "e", v, false))).toEqual(["c", "d", "e"]);
    expect(ids(arrastar(base, "a", v, false))).toEqual(["a", "b", "c"]);
    expect(ids(arrastar(base, "c", v, false))).toEqual(["c"]);
    expect(arrastar(base, "e", v, false).ancora).toBe("c");
  });

  it("Ctrl+arrastar soma ao que já estava selecionado", () => {
    let s = sel("a");
    s = clicar(s, "d", v, { ctrl: true, shift: false });                // a, d (âncora d)
    expect(ids(arrastar(s, "f", v, true))).toEqual(["a", "d", "e", "f"]);
  });

  it("setas movem a linha atual e selecionam só ela", () => {
    let s = sel("c");
    s = navegar(s, "ArrowDown", v, false, 3);
    expect(ids(s)).toEqual(["d"]);
    expect(s.foco).toBe("d");
    s = navegar(s, "ArrowUp", v, false, 3);
    s = navegar(s, "ArrowUp", v, false, 3);
    expect(ids(s)).toEqual(["b"]);
  });

  it("para na primeira e na última linha", () => {
    expect(ids(navegar(sel("a"), "ArrowUp", v, false, 3))).toEqual(["a"]);
    expect(ids(navegar(sel("g"), "ArrowDown", v, false, 3))).toEqual(["g"]);
  });

  it("sem linha atual, a seta começa pela primeira", () => {
    expect(ids(navegar(SELECAO_VAZIA, "ArrowDown", v, false, 3))).toEqual(["a"]);
    expect(ids(navegar(SELECAO_VAZIA, "ArrowUp", v, false, 3))).toEqual(["a"]);
  });

  it("Shift+setas esticam a seleção a partir da âncora e podem encolher", () => {
    let s = sel("c");
    s = navegar(s, "ArrowDown", v, true, 3);
    s = navegar(s, "ArrowDown", v, true, 3);
    expect(ids(s)).toEqual(["c", "d", "e"]);
    expect(s.ancora).toBe("c");
    s = navegar(s, "ArrowUp", v, true, 3);
    expect(ids(s)).toEqual(["c", "d"]);
    for (let i = 0; i < 3; i++) s = navegar(s, "ArrowUp", v, true, 3);
    expect(ids(s)).toEqual(["a", "b", "c"]);                         // passou da âncora: vai para o outro lado
  });

  it("Home e End; com Shift selecionam até a ponta", () => {
    expect(ids(navegar(sel("d"), "Home", v, false, 3))).toEqual(["a"]);
    expect(ids(navegar(sel("d"), "End", v, false, 3))).toEqual(["g"]);
    expect(ids(navegar(sel("d"), "Home", v, true, 3))).toEqual(["a", "b", "c", "d"]);
    expect(ids(navegar(sel("d"), "End", v, true, 3))).toEqual(["d", "e", "f", "g"]);
  });

  it("PgDn e PgUp andam uma página, limitados às pontas; Shift estica", () => {
    expect(ids(navegar(sel("b"), "PageDown", v, false, 3))).toEqual(["e"]);
    expect(ids(navegar(sel("e"), "PageDown", v, false, 3))).toEqual(["g"]);
    expect(ids(navegar(sel("e"), "PageUp", v, false, 3))).toEqual(["b"]);
    expect(ids(navegar(sel("b"), "PageUp", v, false, 3))).toEqual(["a"]);
    expect(ids(navegar(sel("b"), "PageDown", v, true, 3))).toEqual(["b", "c", "d", "e"]);
    expect(ids(navegar(sel("b"), "PageDown", v, false, 0))).toEqual(["c"]);        // página inválida vale 1
  });

  it("lista vazia: nada muda", () => {
    expect(navegar(SELECAO_VAZIA, "ArrowDown", [], false, 3)).toBe(SELECAO_VAZIA);
  });

  it("a linha atual que saiu da lista é esquecida", () => {
    expect(manterVisiveis(sel("c"), ["a", "b"]).foco).toBeNull();
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
