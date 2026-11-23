import { describe, expect, it } from "vitest";
import { type Capa, type Faixa } from "./api";
import { TEXTO_VARIOS, campoPendente, capaDaSelecao, capaEfetiva, temAlgumaCapa, textoCapaPendente, valorComum } from "./edicao";
import { GENEROS_PADRAO, filtrarGeneros, listaDeGeneros } from "./generos";
import { capaDeBytes, descreverCapa, extensaoAceita, lerCabecalhoImagem, nomeSugeridoDaCapa } from "./imagem";
import { CAPA_AZUL, CAPA_VERDE } from "./mock/ponteSimulada";
import { bytesJpeg, bytesPng } from "./testes/imagens";
import { validarValor } from "./validacao";

const faixa = (id: string, extra: Partial<Faixa> = {}): Faixa => ({
  id, caminho: `C:\\m\\${id}.mp3`, tags: {}, pendentes: {}, duracao: 100, bitrate: 128, temCapa: false, ...extra,
});

describe("validação dos campos (igual a metadata.validar_valor)", () => {
  const ano = 2026;
  it("vazio é sempre válido (remove a tag)", () => {
    expect(validarValor("date", "  ", ano)).toEqual({ ok: true, valor: "" });
    expect(validarValor("genre", "", ano).ok).toBe(true);
  });

  it("ano: AAAA ou AAAA-MM-DD entre 1000 e o ano atual; 'atual' vira o ano corrente", () => {
    expect(validarValor("date", "1977", ano)).toEqual({ ok: true, valor: "1977" });
    expect(validarValor("date", "2024-05-17", ano).ok).toBe(true);
    expect(validarValor("date", "2024-05", ano).ok).toBe(true);
    expect(validarValor("date", "Atual", ano)).toEqual({ ok: true, valor: "2026" });
    expect(validarValor("date", "20", ano)).toEqual({ ok: false, mensagem: "Ano inválido. Use AAAA (ex.: 2024) ou AAAA-MM-DD." });
    expect(validarValor("date", "0999", ano)).toEqual({ ok: false, mensagem: "O ano deve estar entre 1000 e 2026." });
    expect(validarValor("date", "2027", ano)).toEqual({ ok: false, mensagem: "O ano deve estar entre 1000 e 2026." });
  });

  it("faixa e disco: 3 ou 3/12, maiores que 0", () => {
    for (const campo of ["tracknumber", "discnumber"] as const) {
      expect(validarValor(campo, "3", ano).ok).toBe(true);
      expect(validarValor(campo, "3/12", ano).ok).toBe(true);
      for (const ruim of ["0", "3/0", "a", "3/", "-1"]) {
        expect(validarValor(campo, ruim, ano), ruim).toEqual({
          ok: false, mensagem: "Número inválido. Use números maiores que 0 (ex.: '3' ou '3/12').",
        });
      }
    }
  });

  it("gênero não pode ser só número; os outros campos aceitam qualquer texto", () => {
    expect(validarValor("genre", "123", ano)).toEqual({ ok: false, mensagem: "Digite o nome do gênero por extenso (ex.: 'Rock')." });
    expect(validarValor("genre", "Rock 90", ano).ok).toBe(true);
    expect(validarValor("title", "123", ano).ok).toBe(true);
    expect(validarValor("artist", "A; B", ano)).toEqual({ ok: true, valor: "A; B" });
  });
});

describe("imagens de capa", () => {
  it("lê tipo e dimensões de PNG e JPEG pelos bytes", () => {
    expect(lerCabecalhoImagem(bytesPng(300, 200))).toEqual({ mime: "image/png", largura: 300, altura: 200 });
    expect(lerCabecalhoImagem(bytesJpeg(640, 480))).toEqual({ mime: "image/jpeg", largura: 640, altura: 480 });
  });

  it("não aceita GIF, WebP, texto nem arquivo curto, mesmo com extensão .jpg", () => {
    expect(lerCabecalhoImagem(new TextEncoder().encode("GIF89a........................"))).toBeNull();
    expect(lerCabecalhoImagem(new TextEncoder().encode("RIFF....WEBPVP8 ......."))).toBeNull();
    expect(lerCabecalhoImagem(new Uint8Array([0x89, 0x50]))).toBeNull();
    expect(capaDeBytes(new Uint8Array(50))).toBeNull();
  });

  it("capaDeBytes monta a data URL e o tamanho", () => {
    const capa = capaDeBytes(bytesPng(3, 2))!;
    expect(capa).toMatchObject({ mime: "image/png", largura: 3, altura: 2, bytes: 33 });
    expect(capa.url.startsWith("data:image/png;base64,iVBORw0KGgo")).toBe(true);
  });

  it("descreve como a v2: FORMATO · LxA · N KB (mínimo 1 KB)", () => {
    expect(descreverCapa(CAPA_AZUL)).toBe("JPEG · 500×500 · 24 KB");
    expect(descreverCapa(CAPA_VERDE)).toBe("PNG · 600×600 · 80 KB");
    expect(descreverCapa({ ...CAPA_AZUL, bytes: 10 })).toContain("· 1 KB");
    expect(descreverCapa({ ...CAPA_AZUL, largura: 0, altura: 0 })).toBe("JPEG · 24 KB");
  });

  it("nome sugerido: álbum sem caracteres inválidos, .png ou .jpg conforme o tipo", () => {
    expect(nomeSugeridoDaCapa("AC/DC: Live?", "image/png")).toBe("ACDC Live.png");
    expect(nomeSugeridoDaCapa("Disco Raro", "image/jpeg")).toBe("Disco Raro.jpg");
    expect(nomeSugeridoDaCapa("", "image/jpeg")).toBe("capa.jpg");
  });

  it("extensões aceitas", () => {
    expect(["a.jpg", "a.JPEG", "a.png"].every(extensaoAceita)).toBe(true);
    expect(["a.gif", "a.webp", "a.bmp", "a"].some(extensaoAceita)).toBe(false);
  });
});

describe("valor comum e capa da seleção", () => {
  it("valor igual em todas é mostrado; diferente vira 'vários' e vazio", () => {
    const l = [faixa("a", { tags: { album: "X", title: "1" } }), faixa("b", { tags: { album: "X", title: "2" } })];
    expect(valorComum(l, "album")).toEqual({ texto: "X", varios: false });
    expect(valorComum(l, "title")).toEqual({ texto: "", varios: true });
    expect(valorComum(l, "genre")).toEqual({ texto: "", varios: false });
    expect(TEXTO_VARIOS).toBe("‹vários valores›");
  });

  it("o valor pendente conta no lugar do do arquivo", () => {
    const l = [faixa("a", { tags: { album: "X" } }), faixa("b", { tags: { album: "Y" }, pendentes: { album: "X" } })];
    expect(valorComum(l, "album")).toEqual({ texto: "X", varios: false });
    expect(campoPendente(l, "album")).toBe(true);
    expect(campoPendente(l, "title")).toBe(false);
  });

  it("capa efetiva: pendente vence a do arquivo", () => {
    expect(capaEfetiva(faixa("a", { temCapa: true, capa: CAPA_AZUL }))).toBe(CAPA_AZUL);
    expect(capaEfetiva(faixa("b", { temCapa: true, capa: CAPA_AZUL, capaPendente: "remover" }))).toBeNull();
    expect(capaEfetiva(faixa("c", { capaPendente: "definir", capaNova: CAPA_VERDE }))).toBe(CAPA_VERDE);
  });

  it("quadro da seleção: mesma capa, sem capa ou várias", () => {
    const azul = (id: string) => faixa(id, { temCapa: true, capa: CAPA_AZUL });
    expect(capaDaSelecao([azul("a"), azul("b")])).toEqual({ tipo: "capa", capa: CAPA_AZUL });
    expect(capaDaSelecao([faixa("a"), faixa("b")])).toEqual({ tipo: "sem" });
    expect(capaDaSelecao([azul("a"), faixa("b")])).toEqual({ tipo: "varias" });
    expect(capaDaSelecao([azul("a"), faixa("b", { capaPendente: "definir", capaNova: CAPA_VERDE })])).toEqual({ tipo: "varias" });
    expect(capaDaSelecao([])).toEqual({ tipo: "sem" });
  });

  it("texto da capa pendente", () => {
    expect(textoCapaPendente([faixa("a")])).toBeNull();
    expect(textoCapaPendente([faixa("a", { capaPendente: "remover" })])).toBe("Capa será removida");
    expect(textoCapaPendente([faixa("a", { capaPendente: "remover" }), faixa("b", { capaPendente: "definir", capaNova: CAPA_VERDE })])).toBe("Nova capa");
  });

  it("alguma capa: do arquivo ou pendente", () => {
    const nova: Capa = CAPA_VERDE;
    expect(temAlgumaCapa([faixa("a")])).toBe(false);
    expect(temAlgumaCapa([faixa("a", { temCapa: true })])).toBe(true);
    expect(temAlgumaCapa([faixa("a", { capaPendente: "definir", capaNova: nova })])).toBe(true);
  });
});

describe("gêneros sugeridos", () => {
  it("junta a lista das Configurações e a dos arquivos como a v2 (só repetição idêntica sai; ordem sem diferenciar maiúsculas)", () => {
    const lista = listaDeGeneros(["Rock", "MPB", "Rock"], ["rock", "Shoegaze", "", "  ", "axé", "MPB"]);
    expect(lista).toEqual(["axé", "MPB", "Rock", "rock", "Shoegaze"]);
    expect(GENEROS_PADRAO).toHaveLength(40);
  });

  it("filtra por trecho, sem diferenciar maiúsculas; vazio não sugere nada", () => {
    const lista = ["Hard Rock", "Rock", "Rockabilly", "Jazz", "Pop Rock"];
    expect(filtrarGeneros(lista, "ROCK")).toEqual(["Hard Rock", "Rock", "Rockabilly", "Pop Rock"]);
    expect(filtrarGeneros(lista, "  jaz ")).toEqual(["Jazz"]);
    expect(filtrarGeneros(lista, "")).toEqual([]);
    expect(filtrarGeneros(lista, "x")).toEqual([]);
    expect(filtrarGeneros(lista, "o", 2)).toHaveLength(2);
  });
});
