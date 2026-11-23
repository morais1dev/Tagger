import { describe, expect, it } from "vitest";
import {
  acentoEfetivo, aplicarAparencia, alturaBotao, alturaCabecalho, altura_linha, clarear, temaDaConfig, textoSobreAcento,
  variaveisDaAparencia,
} from "./aparencia";
import { contraste } from "./contraste";
import { PADROES } from "./configuracoes/tipos";
import { TEMAS } from "./temas";

describe("tema do modo (J-02, J-03)", () => {
  it("escuro usa o tema escuro; claro, o tema claro", () => {
    expect(temaDaConfig({ ...PADROES, usar_escuro: true, tema_escuro: "dracula", tema_claro: "sepia" })).toBe("dracula");
    expect(temaDaConfig({ ...PADROES, usar_escuro: false, tema_escuro: "dracula", tema_claro: "sepia" })).toBe("sepia");
  });

  it("id desconhecido ou do modo errado cai no padrão do modo", () => {
    expect(temaDaConfig({ ...PADROES, usar_escuro: true, tema_escuro: "nao-existe" })).toBe("grafite");
    expect(temaDaConfig({ ...PADROES, usar_escuro: true, tema_escuro: "claro" })).toBe("grafite");
    expect(temaDaConfig({ ...PADROES, usar_escuro: false, tema_claro: "dracula" })).toBe("claro");
  });
});

describe("cor de destaque (M-03)", () => {
  it("'Do tema' usa a cor de cada tema; cor escolhida vale em qualquer tema; inválida volta à do tema", () => {
    expect(acentoEfetivo("dracula", "tema")).toBe(TEMAS.dracula.cores.acento);
    expect(acentoEfetivo("nord", "tema")).toBe(TEMAS.nord.cores.acento);
    expect(acentoEfetivo("nord", "#FF9A4D")).toBe("#ff9a4d");
    expect(acentoEfetivo("nord", "laranja")).toBe(TEMAS.nord.cores.acento);
    expect(acentoEfetivo("desconhecido", "tema")).toBe(TEMAS.grafite.cores.acento);
  });

  it("o texto sobre o destaque é preto ou branco, o que tiver mais contraste (e passa de 4,5 nas cores prontas)", () => {
    expect(textoSobreAcento("#3ddc97")).toBe("#0b0d0c");           // menta clara: texto escuro
    expect(textoSobreAcento("#1a237e")).toBe("#ffffff");           // azul bem escuro: texto branco
    for (const cor of ["#3ddc97", "#6b9bff", "#ff9a4d", "#c58bff", "#ff6b9d", "#f5c542"]) {
      expect(contraste(textoSobreAcento(cor), cor), cor).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("hover é a cor 10% mais clara, igual ao QColor.lighter(110) da v2 (valores conferidos no Qt)", () => {
    const qt: Record<string, string> = {
      "#808080": "#8d8d8d", "#3ddc97": "#43f2a6", "#6b9bff": "#84acff", "#ff9a4d": "#ffa866", "#c58bff": "#d2a4ff",
      "#ff6b9d": "#ff84ae", "#f5c542": "#ffd153", "#1a237e": "#1d268b", "#268bd2": "#2a99e7", "#bd93f9": "#cda9ff",
      "#ffffff": "#ffffff", "#000000": "#000000",
    };
    const canais = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
    for (const [cor, esperado] of Object.entries(qt)) {
      // o Qt arredonda o matiz de outro jeito: um canal pode diferir em 1 (invisível), então a conferência tem folga de 1
      canais(clarear(cor)).forEach((c, i) => expect(Math.abs(c - canais(esperado)[i]), `${cor} canal ${i}`).toBeLessThanOrEqual(1));
    }
  });
});

describe("tamanho e altura das linhas (M-05, B-17)", () => {
  it("altura da linha = tamanho + 21/29/37; cabeçalho +21; botão +19", () => {
    expect(altura_linha(13, "compacta")).toBe(34);
    expect(altura_linha(13, "confortavel")).toBe(42);
    expect(altura_linha(13, "espacosa")).toBe(50);
    expect(altura_linha(18, "compacta")).toBe(39);
    expect(alturaCabecalho(13)).toBe(34);
    expect(alturaBotao(13)).toBe(32);
  });
});

describe("variáveis e aplicação na raiz", () => {
  it("gera destaque, texto sobre o destaque, hover, fontes, tamanho e alturas", () => {
    const v = variaveisDaAparencia({ ...PADROES, acento: "#6b9bff", fonte: "Segoe UI", fonte_mono: "Consolas", tamanho_fonte: 15, densidade: "espacosa" });
    expect(v["--acento"]).toBe("#6b9bff");
    expect(v["--texto-sobre-acento"]).toBe("#0b0d0c");
    expect(v["--acento-hover"]).toBe(clarear("#6b9bff"));
    expect(v["--fonte-ui"]).toMatch(/^"Segoe UI", "Geist"/);
    expect(v["--fonte-mono"]).toMatch(/^"Consolas", "Geist Mono"/);
    expect(v["--tamanho-fonte"]).toBe("15px");
    expect(v["--altura-linha"]).toBe("52px");
    expect(v["--altura-cabecalho"]).toBe("36px");
  });

  it("fonte automática usa só as preferidas; aspas no nome da família não escapam do CSS", () => {
    const v = variaveisDaAparencia({ ...PADROES, fonte: "", fonte_mono: 'A"; evil: "B' });
    expect(v["--fonte-ui"]).toMatch(/^"Geist", "Segoe UI Variable Text"/);
    expect(v["--fonte-mono"]).toBe('"A; evil: B", "Geist Mono", "Cascadia Mono", "Consolas", "SF Mono", "Menlo", "DejaVu Sans Mono", monospace');
  });

  it("aplicarAparencia põe data-tema e as variáveis no elemento", () => {
    const raiz = document.createElement("html");
    aplicarAparencia({ ...PADROES, usar_escuro: false, tema_claro: "sepia", acento: "tema" }, raiz);
    expect(raiz.dataset.tema).toBe("sepia");
    expect(raiz.style.getPropertyValue("--acento")).toBe(TEMAS.sepia.cores.acento);
    expect(raiz.style.getPropertyValue("--altura-linha")).toBe("34px");
  });
});
