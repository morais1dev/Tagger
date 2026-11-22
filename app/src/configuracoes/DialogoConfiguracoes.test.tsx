import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DialogoConfiguracoes, previaDe, restaurarPadroes } from "./DialogoConfiguracoes";
import { criarPonteSimulada } from "./ponteConfig";
import { AVISO_SOBRE } from "./Sobre";
import { ACENTO_DO_TEMA, copiarConfig, PADROES, type Config } from "./tipos";

function abrir(inicial: Partial<Config> = {}, v2?: Parameters<typeof criarPonteSimulada>[1]) {
  const config = { ...copiarConfig(PADROES), ...inicial };
  const ponte = criarPonteSimulada(config, v2);
  const aoMudar = vi.fn();
  const aoFechar = vi.fn();
  const usuario = userEvent.setup();
  render(<DialogoConfiguracoes config={config} ponte={ponte} aoMudar={aoMudar} aoFechar={aoFechar} />);
  const ultima = (): Config => aoMudar.mock.calls.at(-1)![0];
  return { usuario, ponte, aoMudar, aoFechar, ultima };
}

const aba = (nome: string) => screen.getByRole("tab", { name: nome });

describe("estrutura (J-01)", () => {
  it("tem as 4 abas da v2, com Aparência aberta", () => {
    abrir();
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Aparência", "Comportamento", "Tags", "Serviços online"]);
    expect(aba("Aparência")).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("dialog", { name: "Configurações" })).toBeInTheDocument();
  });

  it("as setas trocam de aba pelo teclado", async () => {
    const { usuario } = abrir();
    aba("Aparência").focus();
    await usuario.keyboard("{ArrowRight}");
    expect(aba("Comportamento")).toHaveAttribute("aria-selected", "true");
    await usuario.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(aba("Serviços online")).toHaveAttribute("aria-selected", "true");
  });

  it("a prévia ao vivo avisa a cada mudança, sem salvar", async () => {
    const { usuario, aoMudar, ponte, ultima } = abrir();
    const salvar = vi.spyOn(ponte, "salvar");
    await usuario.selectOptions(screen.getByLabelText("Tema escuro"), "dracula");
    expect(aoMudar).toHaveBeenCalledTimes(1);
    expect(ultima().tema_escuro).toBe("dracula");
    expect(salvar).not.toHaveBeenCalled();
  });

  it("Cancelar devolve os valores antigos e fecha sem aceitar; Esc faz o mesmo", async () => {
    const { usuario, aoMudar, aoFechar, ultima } = abrir();
    await usuario.selectOptions(screen.getByLabelText("Tema escuro"), "dracula");
    await usuario.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(ultima()).toEqual(PADROES);
    expect(aoFechar).toHaveBeenLastCalledWith(false);

    await usuario.selectOptions(screen.getByLabelText("Tema escuro"), "nord");
    await usuario.keyboard("{Escape}");
    expect(aoMudar.mock.calls.at(-1)![0]).toEqual(PADROES);
    expect(aoFechar).toHaveBeenCalledTimes(2);
  });

  it("OK salva pela ponte e fecha aceitando", async () => {
    const { usuario, ponte, aoFechar } = abrir();
    await usuario.selectOptions(screen.getByLabelText("Altura das linhas"), "espacosa");
    await usuario.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(aoFechar).toHaveBeenCalledWith(true));
    expect((await ponte.carregar()).densidade).toBe("espacosa");
  });
});

describe("aba Aparência (J-02 a J-07)", () => {
  it("modo escuro/claro", async () => {
    const { usuario, ultima } = abrir();
    expect(screen.getByLabelText("Escuro")).toBeChecked();
    await usuario.click(screen.getByLabelText("Claro"));
    expect(ultima().usar_escuro).toBe(false);
  });

  it("lista os 13 temas escuros e os 7 claros da v2", () => {
    abrir();
    expect(screen.getByLabelText("Tema escuro").querySelectorAll("option")).toHaveLength(13);
    expect(screen.getByLabelText("Tema claro").querySelectorAll("option")).toHaveLength(7);
    expect(screen.getByLabelText("Tema escuro")).toHaveValue("grafite");
    expect(screen.getByLabelText("Tema claro")).toHaveValue("claro");
  });

  it("cor de destaque: 6 prontas, Do tema e Personalizada", async () => {
    const { usuario, ultima } = abrir();
    expect(screen.getByRole("button", { name: "Do tema" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getAllByRole("button", { name: /^Cor de destaque / })).toHaveLength(6);
    await usuario.click(screen.getByRole("button", { name: "Cor de destaque Lilás" }));
    expect(ultima().acento).toBe("#c58bff");
    expect(screen.getByRole("button", { name: "Cor de destaque Lilás" })).toHaveAttribute("aria-pressed", "true");
    await usuario.click(screen.getByRole("button", { name: "Do tema" }));
    expect(ultima().acento).toBe(ACENTO_DO_TEMA);

    await usuario.click(screen.getByRole("button", { name: "Personalizada…" }));
    await usuario.type(screen.getByLabelText("Cor personalizada (#rrggbb)"), "12ab34");
    expect(ultima().acento).toBe("#12ab34");
  });

  it("cor personalizada inválida mostra o erro e não chega à configuração", async () => {
    const { usuario, aoMudar } = abrir();
    await usuario.click(screen.getByRole("button", { name: "Personalizada…" }));
    await usuario.type(screen.getByLabelText("Cor personalizada (#rrggbb)"), "12zz");
    expect(screen.getByRole("alert")).toHaveTextContent("Cor inválida");
    expect(aoMudar).not.toHaveBeenCalled();
  });

  it("fontes: Automática mais as instaladas", async () => {
    const { usuario, ultima } = abrir();
    const fonte = screen.getByLabelText("Fonte da interface");
    await waitFor(() => expect(fonte.querySelectorAll("option").length).toBeGreaterThan(1));
    expect(fonte.querySelector("option")).toHaveTextContent("Automática");
    await usuario.selectOptions(fonte, "Geist");
    await usuario.selectOptions(screen.getByLabelText("Fonte dos números"), "Consolas");
    expect(ultima().fonte).toBe("Geist");
    expect(ultima().fonte_mono).toBe("Consolas");
  });

  it("tamanho da fonte de 11 a 18 px: fora disso mostra o erro e não aplica", async () => {
    const { usuario, aoMudar, ultima } = abrir();
    const campo = screen.getByLabelText("Tamanho da fonte");
    expect(campo).toHaveValue(13);
    await usuario.clear(campo);
    await usuario.type(campo, "16");
    expect(ultima().tamanho_fonte).toBe(16);
    const chamadas = aoMudar.mock.calls.length;
    await usuario.clear(campo);
    await usuario.type(campo, "30");
    expect(screen.getByRole("alert")).toHaveTextContent("11 a 18");
    expect(campo).toBeInvalid();
    expect(aoMudar.mock.calls.length).toBe(chamadas + 0); // 3 e 30 nunca valem; 16 continua o último valor aceito
    expect(ultima().tamanho_fonte).toBe(16);
  });

  it("altura das linhas: Compacta, Confortável e Espaçosa", async () => {
    const { usuario, ultima } = abrir();
    const campo = screen.getByLabelText("Altura das linhas");
    expect([...campo.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["Compacta", "Confortável", "Espaçosa"]);
    await usuario.selectOptions(campo, "confortavel");
    expect(ultima().densidade).toBe("confortavel");
  });
});

describe("aba Comportamento (J-08 a J-12)", () => {
  it("tem as 5 opções com os padrões da v2 e cada uma muda a sua chave", async () => {
    const { usuario, ultima } = abrir();
    await usuario.click(aba("Comportamento"));
    const casos: Array<[RegExp, keyof Config, boolean]> = [
      [/^Incluir subpastas/, "subpastas", true],
      [/^Reabrir a última pasta/, "reabrir_ultima", false],
      [/^Incluir o total ao numerar/, "numerar_com_total", true],
      [/^Agrupar a lista por álbum/, "agrupar_por_album", false],
      [/^Avisar quando houver uma versão nova/, "avisar_nova_versao", true],
    ];
    for (const [nome, chave, padrao] of casos) {
      const caixa = screen.getByRole("checkbox", { name: nome });
      expect(caixa.hasAttribute("checked") || (caixa as HTMLInputElement).checked, String(chave)).toBe(padrao);
      await usuario.click(caixa);
      expect(ultima()[chave], String(chave)).toBe(!padrao);
    }
  });
});

describe("aba Tags (J-13 a J-18)", () => {
  async function abaTags() {
    const r = abrir();
    await r.usuario.click(aba("Tags"));
    return r;
  }

  it("versão do ID3: v2.3 por padrão, v2.4 opcional", async () => {
    const { usuario, ultima } = await abaTags();
    expect(screen.getByRole("radio", { name: /ID3v2\.3/ })).toBeChecked();
    await usuario.click(screen.getByRole("radio", { name: /ID3v2\.4/ }));
    expect(ultima().versao_id3).toBe(4);
  });

  it("multivalor e ID3v1", async () => {
    const { usuario, ultima } = await abaTags();
    expect(screen.getByRole("checkbox", { name: /vários valores/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /Remover a tag ID3v1/ })).not.toBeChecked();
    await usuario.click(screen.getByRole("checkbox", { name: /vários valores/ }));
    await usuario.click(screen.getByRole("checkbox", { name: /Remover a tag ID3v1/ }));
    expect(ultima().multivalor).toBe(false);
    expect(ultima().remover_id3v1).toBe(true);
  });

  it("capa: o limite só vale ligado e fica entre 300 e 3000 px", async () => {
    const { usuario, ultima } = await abaTags();
    const lado = screen.getByLabelText("Lado máximo da capa");
    expect(lado).toHaveValue(1000);
    await usuario.clear(lado);
    await usuario.type(lado, "1600");
    expect(ultima().lado_max_capa).toBe(1600);
    await usuario.clear(lado);
    await usuario.type(lado, "200");
    expect(screen.getByRole("alert")).toHaveTextContent("300 a 3000");
    expect(ultima().lado_max_capa).toBe(1600);
    await usuario.click(screen.getByRole("checkbox", { name: /Reduzir capas grandes/ }));
    expect(ultima().otimizar_capa).toBe(false);
    expect(lado).toBeDisabled();
  });

  it("gêneros: 40 de padrão, um por linha, linhas vazias ignoradas", async () => {
    const { usuario, ultima } = await abaTags();
    const campo = screen.getByLabelText("Gêneros sugeridos") as HTMLTextAreaElement;
    expect(campo.value.split("\n")).toHaveLength(40);
    await usuario.clear(campo);
    await usuario.type(campo, "Rock{Enter}{Enter}  Forró  {Enter}Jazz");
    expect(ultima().generos).toEqual(["Rock", "Forró", "Jazz"]);
  });
});

describe("aba Serviços online (J-19, J-20)", () => {
  async function abaServicos() {
    const r = abrir();
    await r.usuario.click(aba("Serviços online"));
    return r;
  }

  it("token do Discogs fica oculto e o botão mostra/oculta", async () => {
    const { usuario } = await abaServicos();
    const campo = screen.getByLabelText("Token pessoal do Discogs");
    expect(campo).toHaveAttribute("type", "password");
    expect(campo).toHaveAttribute("placeholder", "Em branco = chave do Tagger");
    await usuario.click(screen.getByRole("button", { name: "Mostrar token pessoal do discogs" }));
    expect(campo).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: /Ocultar/ })).toBeInTheDocument();
  });

  it("o token digitado nunca vai na prévia ao vivo; só no OK", async () => {
    const { usuario, aoMudar, ponte, ultima } = await abaServicos();
    await usuario.type(screen.getByLabelText("Token pessoal do Discogs"), "  token-de-teste ");
    expect(ultima().discogs_token).toBe("");
    for (const [c] of aoMudar.mock.calls) expect(JSON.stringify(c)).not.toContain("token-de-teste");

    await usuario.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(ultima().discogs_token).toBe("token-de-teste"));
    expect((await ponte.carregar()).discogs_token).toBe("token-de-teste");
  });

  it("Cancelar não deixa o token na sessão", async () => {
    const { usuario, ponte, ultima } = await abaServicos();
    await usuario.type(screen.getByLabelText("Token pessoal do Discogs"), "outro-token");
    await usuario.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(ultima().discogs_token).toBe("");
    expect((await ponte.carregar()).discogs_token).toBe("");
  });

  it("guia 'Como gerar a minha chave?' abre e fecha, com o link do Discogs", async () => {
    const { usuario } = await abaServicos();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: /Como gerar a minha chave/ }));
    const link = screen.getByRole("link", { name: "discogs.com/settings/developers" });
    expect(link).toHaveAttribute("href", "https://www.discogs.com/settings/developers");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
    await usuario.click(screen.getByRole("button", { name: /Como gerar a minha chave/ }));
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("não existe campo nem guia do Last.fm", () => {
    abrir();
    expect(document.body.textContent).not.toMatch(/last\.?fm/i);
  });
});

describe("Restaurar padrões (J-21)", () => {
  it("volta ao padrão, mas mantém padrões de nome, recentes e o token colado", async () => {
    const mexido: Partial<Config> = {
      tema_escuro: "nord", tamanho_fonte: 16, densidade: "espacosa", multivalor: false, subpastas: false,
      generos: ["Rock"], padrao_renomear: "{title}", recentes_tags: ["%title%"], discogs_token: "segredo-x",
    };
    const { usuario, ultima } = abrir(mexido);
    await usuario.click(screen.getByRole("button", { name: "Restaurar padrões" }));
    const c = ultima();
    expect(c).toEqual({
      ...PADROES, padrao_renomear: "{title}", recentes_tags: ["%title%"], discogs_token: "segredo-x",
    }); // o token e os padrões de nome sobrevivem ao Restaurar
    expect(screen.getByLabelText("Tema escuro")).toHaveValue("grafite");
    expect(screen.getByLabelText("Tamanho da fonte")).toHaveValue(13);
    await usuario.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(ultima().discogs_token).toBe("segredo-x"));
    expect(ultima().padrao_renomear).toBe("{title}");
  });

  it("restaurarPadroes e previaDe são funções puras", () => {
    const atual = { ...copiarConfig(PADROES), tema_escuro: "nord", discogs_token: "t", padrao_tags: "%title%" };
    const novo = restaurarPadroes(atual);
    expect(novo.tema_escuro).toBe("grafite");
    expect(novo.discogs_token).toBe("t");
    expect(novo.padrao_tags).toBe("%title%");
    expect(previaDe(atual, PADROES).discogs_token).toBe("");
  });
});

describe("Sobre (L-04) e rodapé", () => {
  it("o botão abre o Sobre com versão, fontes dos dados e o aviso do Discogs; Fechar volta às Configurações", async () => {
    const { usuario } = abrir();
    await usuario.click(screen.getByRole("button", { name: "Sobre o Tagger" }));
    const sobre = await screen.findByRole("dialog", { name: "Sobre o Tagger" });
    expect(sobre).toHaveTextContent("Tagger 3.0.0-dev");
    expect(sobre).toHaveTextContent(AVISO_SOBRE);
    expect(screen.getByRole("link", { name: "MusicBrainz" })).toHaveAttribute("href", "https://musicbrainz.org");
    expect(screen.getByRole("link", { name: "Cover Art Archive" })).toHaveAttribute("href", "https://coverartarchive.org");
    expect(screen.getByRole("link", { name: "Discogs" })).toHaveAttribute("href", "https://www.discogs.com");
    await usuario.click(screen.getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("dialog", { name: "Sobre o Tagger" })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Configurações" })).toBeInTheDocument();
  });

  it("Esc no Sobre fecha só o Sobre", async () => {
    const { usuario, aoFechar } = abrir();
    await usuario.click(screen.getByRole("button", { name: "Sobre o Tagger" }));
    await screen.findByRole("dialog", { name: "Sobre o Tagger" });
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Sobre o Tagger" })).not.toBeInTheDocument();
    expect(aoFechar).not.toHaveBeenCalled();
  });
});

describe("Importar da v2 (J-25, só interface)", () => {
  it("sem configuração da v2, avisa e não muda nada", async () => {
    const { usuario, aoMudar } = abrir();
    await usuario.click(screen.getByRole("button", { name: "Importar da v2" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Nenhuma configuração da v2");
    expect(aoMudar).not.toHaveBeenCalled();
  });

  it("com configuração da v2, aplica, conta e lista o que foi ignorado, sem apagar nada", async () => {
    const v2 = { encontrada: true, config: { tema_escuro: "dracula", tamanho_fonte: 15, subpastas: false }, ignoradas: ["lastfm_api_key"] };
    const { usuario, ultima } = abrir({}, v2);
    await usuario.click(screen.getByRole("button", { name: "Importar da v2" }));
    expect(await screen.findByRole("status")).toHaveTextContent("3 configuração(ões) da v2 importadas. Nada foi apagado da v2. 1 opção(ões)");
    expect(ultima().tema_escuro).toBe("dracula");
    expect(ultima().tamanho_fonte).toBe(15);
    expect(ultima().subpastas).toBe(false);
    expect(screen.getByLabelText("Tema escuro")).toHaveValue("dracula");
  });
});
