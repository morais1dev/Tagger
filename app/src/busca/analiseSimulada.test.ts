import { describe, expect, it } from "vitest";
import { analisarSimulado, interpretarPosicao, numerar, type ReleaseSimulado } from "./analiseSimulada";
import { urlSegura, DOMINIOS_DISCOGS, primeiroValor } from "./tipos";

describe("posições do Discogs (discogs.interpretar_posicao / numerar)", () => {
  it("interpreta lado, disco-faixa, número e o que não dá para entender", () => {
    expect(interpretarPosicao("A1")).toEqual({ tipo: "lado", letra: "A", numero: 1 });
    expect(interpretarPosicao("B")).toEqual({ tipo: "lado", letra: "B", numero: 0 });
    expect(interpretarPosicao("2-05")).toEqual({ tipo: "disco", disco: 2, numero: 5 });
    expect(interpretarPosicao("CD2.5")).toEqual({ tipo: "disco", disco: 2, numero: 5 });
    expect(interpretarPosicao("7")).toEqual({ tipo: "faixa", numero: 7 });
    expect(interpretarPosicao("")).toBeNull();
    expect(interpretarPosicao("Video")).toBeNull();
    expect(interpretarPosicao("I")).toBeNull();                 // algarismo romano, não lado
  });

  it("vinil: A/B = disco 1, C/D = disco 2, a faixa conta dentro do disco (A1/B2 → faixa/disco)", () => {
    expect(numerar(["A1", "A2", "B1", "B2", "C1", "D1"])).toEqual([[1, 1], [1, 2], [1, 3], [1, 4], [2, 1], [2, 2]]);
    expect(numerar(["A", "B"])).toEqual([[1, 1], [1, 2]]);
    expect(numerar(["1-1", "1-2", "2-1"])).toEqual([[1, 1], [1, 2], [2, 1]]);
    expect(numerar(["1", "2", "Video"])).toEqual([[1, 1], [1, 2], [1, 3]]);
  });
});

describe("casamento e análise simulados", () => {
  const release: ReleaseSimulado = {
    id: "r1", descricao: "x", titulo: "Daybreak", artista: "Aurora Lane", data: "2020-05-01", generos: ["Pop", "Indie"],
    gravadora: "Selo X", faixas: [
      { titulo: "Afterglow", artista: "Aurora Lane", numero: 1, disco: 1 },
      { titulo: "Sunrise", artista: "Aurora Lane", numero: 2, disco: 1 },
    ],
  };
  const atrib = { texto: "x" };

  it("casa por título, depois por número, e só traz o que difere", () => {
    const d = analisarSimulado([
      { id: "a", nome: "a.mp3", valores: { title: "afterglow" } },
      { id: "b", nome: "b.mp3", valores: { title: "", tracknumber: "2" } },
      { id: "c", nome: "c.mp3", valores: { title: "Outra coisa" } },
    ], release, false, atrib);
    expect(d.casadas).toEqual(["a", "b"]);
    expect(d.semPar).toEqual(["c"]);
    expect(d.alteracoes[0].mudancas).toEqual({
      title: "Afterglow", album: "Daybreak", albumartist: "Aurora Lane", date: "2020-05-01", genre: "Pop; Indie",
      artist: "Aurora Lane", tracknumber: "1/2",
    });
    expect(d.alteracoes[1].mudancas.title).toBe("Sunrise");
  });

  it("não repete o que a faixa já mostra; MusicBrainz não preenche gravadora, Discogs sim", () => {
    const igual = { title: "Afterglow", album: "Daybreak", albumartist: "Aurora Lane", date: "2020-05-01", genre: "Pop; Indie", artist: "Aurora Lane", tracknumber: "1/2" };
    expect(analisarSimulado([{ id: "a", nome: "a", valores: igual }], release, false, atrib).alteracoes).toEqual([]);
    expect(analisarSimulado([{ id: "a", nome: "a", valores: igual }], release, true, atrib).alteracoes[0].mudancas).toEqual({ gravadora: "Selo X" });
  });

  it("vários discos preenchem discnumber (Discogs: pelas posições do vinil)", () => {
    const vinil: ReleaseSimulado = { ...release, faixas: [
      { titulo: "A", artista: "X", posicao: "A1" }, { titulo: "B", artista: "X", posicao: "B1" }, { titulo: "C", artista: "X", posicao: "C1" },
    ] };
    const d = analisarSimulado([{ id: "c", nome: "c", valores: { title: "C" } }], vinil, true, atrib);
    expect(d.alteracoes[0].mudancas).toMatchObject({ tracknumber: "1/1", discnumber: "2/2" });
  });

  it("título parecido casa no Discogs, e a ordem só vale com o número", () => {
    const d = analisarSimulado([{ id: "a", nome: "a", valores: { title: "Afterglo" } }], release, true, atrib);
    expect(d.casadas).toEqual(["a"]);
    expect(analisarSimulado([{ id: "a", nome: "a", valores: { title: "Afterglo" } }], release, false, atrib).casadas).toEqual([]);
  });
});

describe("utilitários", () => {
  it("links só se forem https de domínio do serviço", () => {
    expect(urlSegura("https://www.discogs.com/release/1", DOMINIOS_DISCOGS)).toBe("https://www.discogs.com/release/1");
    expect(urlSegura("http://www.discogs.com/release/1", DOMINIOS_DISCOGS)).toBe("");
    expect(urlSegura("https://discogs.com.evil.com/x", DOMINIOS_DISCOGS)).toBe("");
    expect(urlSegura("https://evil.com/discogs.com", DOMINIOS_DISCOGS)).toBe("");
    expect(urlSegura("javascript:alert(1)", DOMINIOS_DISCOGS)).toBe("");
    expect(urlSegura("https://user:senha@www.discogs.com/x", DOMINIOS_DISCOGS)).toBe("");
    expect(urlSegura(undefined, DOMINIOS_DISCOGS)).toBe("");
  });

  it("primeiro valor não vazio entre as faixas", () => {
    expect(primeiroValor([{ id: "1", nome: "1", valores: {} }, { id: "2", nome: "2", valores: { album: "X" } }], "album")).toBe("X");
    expect(primeiroValor([], "album")).toBe("");
  });
});
