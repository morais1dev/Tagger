import { describe, expect, it } from "vitest";
import { contraste } from "./contraste";
import { TEMAS } from "./temas";

const MINIMO = 4.5;
const TOKENS = ["bg", "surface", "surface2", "field", "line", "line2", "text", "muted", "faint", "hover", "erro", "acento"];

describe("temas", () => {
  it("são os 20 temas da v2, cada um com todos os tokens em #rrggbb", () => {
    expect(Object.keys(TEMAS)).toHaveLength(20);
    for (const [id, tema] of Object.entries(TEMAS)) {
      expect(Object.keys(tema.cores).sort(), id).toEqual([...TOKENS].sort());
      for (const [token, valor] of Object.entries(tema.cores)) expect(valor, `${id}.${token}`).toMatch(/^#[0-9a-f]{6}$/);
    }
  });

  it("contraste de referência do WCAG", () => {
    expect(contraste("#000000", "#ffffff")).toBeCloseTo(21, 5);
    expect(contraste("#777777", "#777777")).toBeCloseTo(1, 5);
  });

  describe.each(Object.entries(TEMAS))("%s", (id, tema) => {
    it.each(["text", "muted"])(`${id}: %s sobre o fundo tem contraste ≥ ${MINIMO}:1`, (token) => {
      expect(contraste(tema.cores[token], tema.cores.bg)).toBeGreaterThanOrEqual(MINIMO);
    });
  });
});
