import { describe, expect, it } from "vitest";
import {
  camposDoPadrao, caminhoRelativo, nomePelasTags, planejarOrganizacao, planejarRenomeacao, relativoA, resumoFalhas,
  resumoMovimentos, sanitizar, tagsPeloNome, validarValor,
} from "./padroesSimulados";
import { nomeExtra } from "./nomesExtras";

const faixa = (caminho: string, valores: Record<string, string> = {}) => ({ caminho, valores });

describe("padrão -> nome (padroes.py)", () => {
  it("campos do padrão, nas duas formas e com apelidos", () => {
    expect(camposDoPadrao("{tracknumber:02} - {artist} - {title}")).toEqual(["tracknumber", "artist", "title"]);
    expect(camposDoPadrao("%track% - %year% %disc% {title} {title}")).toEqual(["tracknumber", "date", "discnumber", "title"]);
    expect(camposDoPadrao("{*} - {title}")).toEqual(["title"]);
    expect(() => camposDoPadrao("{foo}")).toThrow("Campo desconhecido: {foo}");
  });

  it("nome pelas tags completa com zeros e usa só o número da faixa", () => {
    const v = { tracknumber: "3/12", artist: "Aurora Lane", title: "Afterglow" };
    expect(nomePelasTags("{tracknumber:02} - {artist} - {title}", v)).toBe("03 - Aurora Lane - Afterglow");
    expect(nomePelasTags("{discnumber}-{tracknumber:02} {title}", { ...v, discnumber: "1" })).toBe("1-03 Afterglow");
  });

  it("campos vazios não deixam separadores sobrando", () => {
    expect(nomePelasTags("{tracknumber:02} - {artist} - {title}", { tracknumber: "3", title: "Afterglow" })).toBe("03 - Afterglow");
    expect(nomePelasTags("{artist} - {title}", { artist: "A" })).toBe("A");
  });

  it("sanitiza para o Windows, trata nomes reservados e recusa barras", () => {
    expect(sanitizar('AC/DC: "Live"?')).toBe("AC-DC - 'Live'");
    expect(nomePelasTags("{title}", { title: "con" })).toBe("con_");
    expect(nomePelasTags("{title}", { title: "x".repeat(300) }).length).toBe(180);
    expect(() => nomePelasTags("{artist}/{title}", {})).toThrow("não pode ter");
  });
});

describe("prévia de renomear", () => {
  const padrao = "{tracknumber:02} - {title}";

  it("sem mudança, nome vazio e extensão em minúsculas", () => {
    const plano = planejarRenomeacao([
      faixa("D:\\m\\03 - A.mp3", { tracknumber: "3", title: "A" }),
      faixa("D:\\m\\x.mp3", {}),
      faixa("D:\\m\\y.MP3", { tracknumber: "1", title: "B" }),
    ], padrao);
    expect(plano[0]).toEqual({ origem: "D:\\m\\03 - A.mp3", destino: null, erro: "" });
    expect(plano[1].erro).toContain("ficaria vazio");
    expect(plano[2].destino).toBe("D:\\m\\01 - B.mp3");
  });

  it("conflitos: dois com o mesmo nome e nome que já existe", () => {
    const iguais = planejarRenomeacao([faixa("D:\\m\\a.mp3", { title: "X" }), faixa("D:\\m\\b.mp3", { title: "X" })], "{title}");
    expect(iguais.map((i) => i.erro)).toEqual(["Outro arquivo ficaria com o mesmo nome", "Outro arquivo ficaria com o mesmo nome"]);
    const existe = planejarRenomeacao([faixa("D:\\m\\a.mp3", { title: "X" })], "{title}", new Set(["d:\\m\\X.mp3"]));
    expect(existe[0].erro).toBe("Já existe um arquivo com esse nome na pasta");
  });

  it("trocar nomes entre dois arquivos não é conflito", () => {
    const plano = planejarRenomeacao([faixa("D:\\m\\a.mp3", { title: "b" }), faixa("D:\\m\\b.mp3", { title: "a" })], "{title}");
    expect(plano.map((i) => i.erro)).toEqual(["", ""]);
  });
});

describe("nome -> tags", () => {
  it("lê artista e título do nome", () => {
    expect(tagsPeloNome("%artist% - %title%", "D:\\m\\Aurora Lane - Afterglow.mp3")).toEqual({ artist: "Aurora Lane", title: "Afterglow" });
    expect(tagsPeloNome("%artist% - %title%", "D:\\m\\sem separador.mp3")).toBeNull();
  });

  it("número sem zeros à esquerda, e {*} ignora um trecho", () => {
    expect(tagsPeloNome("%track% - %title%", "D:\\m\\03 - A.mp3")).toEqual({ tracknumber: "3", title: "A" });
    expect(tagsPeloNome("%*% - %title%", "D:\\m\\qualquer - A.mp3")).toEqual({ title: "A" });
  });

  it("trocar _ por espaço e usar as pastas acima", () => {
    expect(tagsPeloNome("%artist% - %title%", "D:\\m\\A_B - C_D.mp3", true)).toEqual({ artist: "A B", title: "C D" });
    expect(tagsPeloNome("%artist%/%album%/%track% - %title%", "D:\\Música\\Aurora\\Daybreak\\03 - Afterglow.flac")).toEqual({
      artist: "Aurora", album: "Daybreak", tracknumber: "3", title: "Afterglow",
    });
    expect(tagsPeloNome("%artist%/%album%/%title%", "A.mp3")).toBeNull();
  });

  it("validação mínima do que foi lido", () => {
    expect(validarValor("date", "2024")).toBe("");
    expect(validarValor("date", "abcd")).toContain("Ano inválido");
    expect(validarValor("date", "3000", 2026)).toContain("entre 1000 e 2026");
    expect(validarValor("tracknumber", "0")).toContain("Número inválido");
    expect(validarValor("genre", "17")).toContain("por extenso");
    expect(validarValor("title", "qualquer")).toBe("");
  });
});

describe("organizar em pastas (organizar.py)", () => {
  const padrao = "{albumartist}/{album}/{tracknumber:02} - {title}";

  it("caminho relativo: artista do álbum cai para artista, vazios viram Unknown", () => {
    expect(caminhoRelativo(padrao, { artist: "A", album: "B", tracknumber: "3", title: "T" })).toEqual(["A", "B", "03 - T"]);
    expect(caminhoRelativo(padrao, { title: "T" })).toEqual(["Unknown Artist", "Unknown Album", "T"]);
    expect(caminhoRelativo("{artist}/{title}", {}, "original")).toEqual(["Unknown Artist", "original"]);
  });

  it("padrão inválido", () => {
    expect(() => caminhoRelativo("", {})).toThrow("Digite um padrão.");
    expect(() => caminhoRelativo("C:/{title}", {})).toThrow("sem letra de unidade");
    expect(() => caminhoRelativo("fixo/nome", {})).toThrow("pelo menos um campo");
    expect(() => caminhoRelativo("{foo}", {})).toThrow("Campo desconhecido");
  });

  it("monta o destino, mantém a extensão em minúsculas e marca o que já está no lugar", () => {
    const plano = planejarOrganizacao([
      faixa("D:\\x\\a.FLAC", { albumartist: "Aurora", album: "Daybreak", tracknumber: "3", title: "Afterglow" }),
      faixa("D:\\dest\\Aurora\\Daybreak\\01 - Já.mp3", { albumartist: "Aurora", album: "Daybreak", tracknumber: "1", title: "Já" }),
    ], padrao, "D:\\dest", true);
    expect(plano.itens[0].destino).toBe("D:\\dest\\Aurora\\Daybreak\\03 - Afterglow.flac");
    expect(plano.itens[1].destino).toBeNull();
  });

  it("conflito: dois no mesmo lugar", () => {
    const v = { albumartist: "A", album: "B", tracknumber: "1", title: "T" };
    const plano = planejarOrganizacao([faixa("D:\\x\\1.mp3", v), faixa("D:\\x\\2.mp3", v)], padrao, "D:\\d", false);
    expect(plano.itens.map((i) => i.erro)).toEqual(["Outro arquivo ficaria no mesmo lugar", "Outro arquivo ficaria no mesmo lugar"]);
  });

  it("a capa só vai junto quando a pasta inteira vai para o mesmo destino", () => {
    const v = { albumartist: "A", album: "B", title: "T" };
    const itens = [faixa("D:\\x\\1.mp3", { ...v, tracknumber: "1" }), faixa("D:\\x\\2.mp3", { ...v, tracknumber: "2" })];
    const junto = planejarOrganizacao(itens, padrao, "D:\\d", true, { conteudoDasPastas: { "D:\\x": ["1.mp3", "2.mp3", "cover.jpg", "notas.txt"] } });
    expect(junto.capas).toEqual([{ origem: "D:\\x\\cover.jpg", destino: "D:\\d\\A\\B\\cover.jpg", erro: "" }]);
    const fica = planejarOrganizacao(itens, padrao, "D:\\d", true, { conteudoDasPastas: { "D:\\x": ["1.mp3", "2.mp3", "3.mp3", "cover.jpg"] } });
    expect(fica.capas).toEqual([]);
    const desligado = planejarOrganizacao(itens, padrao, "D:\\d", false, { conteudoDasPastas: { "D:\\x": ["1.mp3", "2.mp3", "cover.jpg"] } });
    expect(desligado.capas).toEqual([]);
  });

  it("resumo: caminhos relativos à base e ordenados pelo destino; falhas com o motivo", () => {
    expect(relativoA("D:\\dest\\A\\1.mp3", "D:\\dest")).toBe("A\\1.mp3");
    expect(relativoA("E:\\fora\\1.mp3", "D:\\dest")).toBe("E:\\fora\\1.mp3");
    expect(resumoMovimentos([["D:\\x\\b.mp3", "D:\\d\\Z\\b.mp3"], ["D:\\x\\a.mp3", "D:\\d\\A\\a.mp3"]], "D:\\d")).toEqual([
      ["D:\\x\\a.mp3", "A\\a.mp3"], ["D:\\x\\b.mp3", "Z\\b.mp3"],
    ]);
    expect(resumoFalhas({ "D:\\d\\a.mp3": "em uso" }, "D:\\d")).toEqual([["a.mp3", "Não movido: em uso"]]);
  });
});

describe("nomes dos extras da limpeza", () => {
  it("frames ID3, Vorbis, MP4, famílias com prefixo, átomo livre e desconhecido", () => {
    expect(nomeExtra("PRIV")[1]).toContain("dados privados");
    expect(nomeExtra("ENCODER")).toEqual(["ENCODER", "programa/configuração do encoder"]);
    expect(nomeExtra("encoder")[1]).toContain("encoder");
    expect(nomeExtra("\u00a9too")[1]).toContain("encoder");
    expect(nomeExtra("REPLAYGAIN_TRACK_GAIN")[1]).toBe("ajuste de volume (ReplayGain)");
    expect(nomeExtra("MusicBrainz Album Id")[1]).toBe("identificadores do MusicBrainz");
    expect(nomeExtra("----:com.apple.iTunes:ISRC")).toEqual(["ISRC", "ISRC"]);
    expect(nomeExtra("ZZZZ")).toEqual(["ZZZZ", "outro"]);
  });
});
