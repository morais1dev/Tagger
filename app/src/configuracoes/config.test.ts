import { describe, expect, it } from "vitest";
import { criarPonteSimulada } from "./ponteConfig";
import { ACENTO_DO_TEMA, ACENTOS, CHAVES_CREDENCIAL, copiarConfig, GENEROS_PADRAO, PADROES } from "./tipos";
import { corValida, dividirGeneros, limitar, normalizarConfig, validarConfig } from "./validacao";

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

  it("normalizarConfig corrige valores velhos ou estranhos", () => {
    const n = normalizarConfig({
      ...PADROES, tamanho_fonte: 99, lado_max_capa: 5, acento: "lixo", versao_id3: 2 as never, discogs_token: "  t  ",
    });
    expect([n.tamanho_fonte, n.lado_max_capa, n.acento, n.versao_id3, n.discogs_token]).toEqual([18, 300, "tema", 3, "t"]);
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

  it("importar da v2 sem registro devolve 'não encontrada' e não altera a configuração", async () => {
    const ponte = criarPonteSimulada();
    expect(await ponte.importarDaV2()).toEqual({ encontrada: false, config: {}, ignoradas: [] });
    expect(await ponte.carregar()).toEqual(PADROES);
  });
});
