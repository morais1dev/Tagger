import { describe, expect, it } from "vitest";
import { criarPonteSimulada } from "./ponteConfig";
import { ACENTO_DO_TEMA, ACENTOS, CHAVES_CREDENCIAL, copiarConfig, GENEROS_PADRAO, PADROES } from "./tipos";
import { corValida, dividirGeneros, lerConfig, limitar, normalizarConfig, validarConfig } from "./validacao";

describe("PADROES (tagger/gui/config.py)", () => {
  it("tem os mesmos valores da v2", () => {
    expect(PADROES).toMatchObject({
      usar_escuro: true, tema_escuro: "grafite", tema_claro: "claro", acento: "tema", fonte: "", fonte_mono: "",
      tamanho_fonte: 13, densidade: "compacta", subpastas: true, reabrir_ultima: false, numerar_com_total: true,
      avisar_nova_versao: true, agrupar_por_album: false, versao_id3: 3, multivalor: true, remover_id3v1: false,
      otimizar_capa: true, lado_max_capa: 1000, discogs_token: "",
      padrao_renomear: "{tracknumber:02} - {artist} - {title}", padrao_tags: "%artist% - %title%",
      padrao_organizar: "{albumartist}/{album}/{tracknumber:02} - {title}",
      recentes_renomear: [], recentes_organizar: [], recentes_tags: [],
    });
    expect(Object.keys(PADROES)).toHaveLength(26);
  });

  it("os 40 gêneros iniciais, sem repetição", () => {
    expect(GENEROS_PADRAO).toHaveLength(40);
    expect(new Set(GENEROS_PADRAO).size).toBe(40);
    expect(GENEROS_PADRAO[0]).toBe("Alternative");
    expect(GENEROS_PADRAO.at(-1)).toBe("Trap");
  });

  it("6 cores de destaque prontas, todas #rrggbb", () => {
    expect(ACENTOS.map((a) => a.nome)).toEqual(["Menta", "Azul", "Laranja", "Lilás", "Rosa", "Amarelo"]);
    for (const a of ACENTOS) expect(corValida(a.cor)).toBe(true);
  });

  it("credencial é só o token do Discogs; copiar não compartilha as listas", () => {
    expect(CHAVES_CREDENCIAL).toEqual(["discogs_token"]);
    const c = copiarConfig(PADROES);
    c.generos.push("X");
    expect(PADROES.generos).not.toContain("X");
  });
});

describe("validação", () => {
  it("limitar aceita número no intervalo e arredonda; texto vira o padrão", () => {
    expect(limitar(15, 11, 18, 13)).toBe(15);
    expect(limitar(99, 11, 18, 13)).toBe(18);
    expect(limitar(1, 11, 18, 13)).toBe(11);
    expect(limitar("abc", 11, 18, 13)).toBe(13);
    expect(limitar("", 11, 18, 13)).toBe(13);
    expect(limitar(NaN, 11, 18, 13)).toBe(13);
  });

  it("validarConfig aponta fonte, capa e cor fora do permitido", () => {
    expect(validarConfig(PADROES)).toEqual({});
    const erros = validarConfig({ ...PADROES, tamanho_fonte: 20, lado_max_capa: 100, acento: "azul" });
    expect(Object.keys(erros).sort()).toEqual(["acento", "lado_max_capa", "tamanho_fonte"]);
    expect(validarConfig({ ...PADROES, acento: ACENTO_DO_TEMA })).toEqual({});
  });

  it("dividirGeneros tira linhas vazias e espaços", () => {
    expect(dividirGeneros(" Rock \r\n\n  Pop\n")).toEqual(["Rock", "Pop"]);
    expect(dividirGeneros("")).toEqual([]);
  });
});

describe("ponte simulada", () => {
  it("guarda e devolve cópias; nada compartilha estado entre chamadas", async () => {
    const ponte = criarPonteSimulada();
    const a = await ponte.carregar();
    a.generos.push("X");
    expect((await ponte.carregar()).generos).not.toContain("X");
    await ponte.salvar({ ...a, tamanho_fonte: 99 });
    expect((await ponte.carregar()).tamanho_fonte).toBe(18);
  });
});

describe("lerConfig (config.carregar_config da v2)", () => {
  it("sem nada guardado, devolve os padrões; chaves a mais são ignoradas", () => {
    expect(lerConfig()).toEqual(PADROES);
    expect(lerConfig({ lastfm_api_key: "x", qualquer: 1 })).toEqual(PADROES);
    expect(lerConfig({ tema_escuro: null, subpastas: undefined })).toEqual(PADROES);
  });

  it("bool: 'true'/'1' (qualquer caixa) valem verdadeiro; o resto, falso", () => {
    for (const v of ["true", "True", "TRUE", "1", 1, true]) expect(lerConfig({ reabrir_ultima: v }).reabrir_ultima, String(v)).toBe(true);
    for (const v of ["false", "0", "", "sim", 0, 2, false]) expect(lerConfig({ subpastas: v }).subpastas, String(v)).toBe(false);
  });

  it("int: texto inteiro e número (trunca); lixo cai no padrão", () => {
    expect(lerConfig({ tamanho_fonte: "15" }).tamanho_fonte).toBe(15);
    expect(lerConfig({ tamanho_fonte: " 16 " }).tamanho_fonte).toBe(16);
    expect(lerConfig({ tamanho_fonte: 14.9 }).tamanho_fonte).toBe(14);
    expect(lerConfig({ tamanho_fonte: "abc" }).tamanho_fonte).toBe(13);
    expect(lerConfig({ tamanho_fonte: "13.5" }).tamanho_fonte).toBe(13);
    expect(lerConfig({ tamanho_fonte: NaN }).tamanho_fonte).toBe(13);
    expect(lerConfig({ tamanho_fonte: {} }).tamanho_fonte).toBe(13);
    expect(lerConfig({ lado_max_capa: "1500" }).lado_max_capa).toBe(1500);
    expect(lerConfig({ versao_id3: "4" }).versao_id3).toBe(4);
  });

  it("int fora do intervalo dos campos é limitado; versão do ID3 estranha volta ao padrão", () => {
    expect(lerConfig({ tamanho_fonte: 99 }).tamanho_fonte).toBe(18);
    expect(lerConfig({ tamanho_fonte: 1 }).tamanho_fonte).toBe(11);
    expect(lerConfig({ lado_max_capa: 5 }).lado_max_capa).toBe(300);
    expect(lerConfig({ lado_max_capa: "99999" }).lado_max_capa).toBe(3000);
    expect(lerConfig({ versao_id3: 7 }).versao_id3).toBe(3);
  });

  it("lista: texto vira lista de um item; vazio vira []; tipo errado cai no padrão", () => {
    expect(lerConfig({ generos: "Rock" }).generos).toEqual(["Rock"]);
    expect(lerConfig({ generos: ["Rock", "Pop"] }).generos).toEqual(["Rock", "Pop"]);
    expect(lerConfig({ generos: [] }).generos).toEqual([]);
    expect(lerConfig({ recentes_tags: "%title%" }).recentes_tags).toEqual(["%title%"]);
    expect(lerConfig({ recentes_renomear: 0 }).recentes_renomear).toEqual([]);
    expect(lerConfig({ generos: 5 }).generos).toEqual([...GENEROS_PADRAO]);
    expect(lerConfig({ generos: [1, "a"] }).generos).toEqual(["1", "a"]);
  });

  it("tema que não existe (ou do modo errado) volta ao padrão", () => {
    expect(lerConfig({ tema_escuro: "inexistente" }).tema_escuro).toBe("grafite");
    expect(lerConfig({ tema_escuro: "claro" }).tema_escuro).toBe("grafite");
    expect(lerConfig({ tema_claro: "dracula" }).tema_claro).toBe("claro");
    expect(lerConfig({ tema_escuro: "nord", tema_claro: "sepia" })).toMatchObject({ tema_escuro: "nord", tema_claro: "sepia" });
  });

  it("densidade inválida volta à compacta; as válidas ficam", () => {
    expect(lerConfig({ densidade: "gigante" }).densidade).toBe("compacta");
    expect(lerConfig({ densidade: 3 }).densidade).toBe("compacta");
    expect(lerConfig({ densidade: "espacosa" }).densidade).toBe("espacosa");
  });

  it("cor de destaque: 'tema' ou #rrggbb (minúsculas); o resto volta ao padrão", () => {
    expect(lerConfig({ acento: "#ABCDEF" }).acento).toBe("#abcdef");
    expect(lerConfig({ acento: "tema" }).acento).toBe("tema");
    expect(lerConfig({ acento: "vermelho" }).acento).toBe("tema");
    expect(lerConfig({ acento: "#fff" }).acento).toBe("tema");
  });

  it("texto: número vira texto, objeto cai no padrão; token perde espaços", () => {
    expect(lerConfig({ fonte: "Geist" }).fonte).toBe("Geist");
    expect(lerConfig({ fonte: 5 }).fonte).toBe("5");
    expect(lerConfig({ fonte: {} }).fonte).toBe("");
    expect(lerConfig({ padrao_tags: ["x"] }).padrao_tags).toBe(PADROES.padrao_tags);
    expect(lerConfig({ discogs_token: "  abc " }).discogs_token).toBe("abc");
  });

  it("normalizarConfig aplica as mesmas regras a uma configuração montada", () => {
    const n = normalizarConfig({ ...PADROES, tamanho_fonte: 99, tema_escuro: "x", densidade: "y" as never, acento: "lixo" });
    expect([n.tamanho_fonte, n.tema_escuro, n.densidade, n.acento]).toEqual([18, "grafite", "compacta", "tema"]);
  });
});
