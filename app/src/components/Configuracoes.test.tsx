import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { acentoEfetivo, clarear } from "../aparencia";
import { DialogoConfiguracoes, criarPonteSimulada } from "../configuracoes";
import { AVISO_SOBRE } from "../configuracoes/Sobre";
import { PADROES, copiarConfig } from "../configuracoes/tipos";
import { TEMAS } from "../temas";
import { faixasDeExemplo, ponteSimulada } from "../mock/ponteSimulada";
import { Janela } from "./Janela";

const html = () => document.documentElement;
const variavel = (nome: string) => html().style.getPropertyValue(nome);

async function montar(inicial: Record<string, unknown> = {}) {
  const usuario = userEvent.setup();
  const ponteCfg = criarPonteSimulada(inicial);
  render(<Janela ponte={ponteSimulada(faixasDeExemplo())} ponteConfig={ponteCfg} />);
  await waitFor(() => expect(html().dataset.tema).toBeTruthy());
  return { usuario, ponteCfg };
}

describe("botão sol/lua (I-02)", () => {
  it("mostra o sol no modo escuro e a lua no claro; troca o tema na hora e guarda a escolha", async () => {
    const { usuario, ponteCfg } = await montar({ tema_escuro: "dracula", tema_claro: "sepia" });
    const botao = screen.getByRole("button", { name: "Alternar tema claro/escuro" });
    await waitFor(() => expect(html().dataset.tema).toBe("dracula"));
    expect(botao).toHaveTextContent("☀");
    await usuario.click(botao);
    expect(html().dataset.tema).toBe("sepia");
    expect(botao).toHaveTextContent("☾");
    await waitFor(async () => expect((await ponteCfg.carregar()).usar_escuro).toBe(false));
    await usuario.click(botao);
    expect(html().dataset.tema).toBe("dracula");
    expect((await ponteCfg.carregar()).tema_claro).toBe("sepia");               // o resto da configuração não muda
  });

  it("o tema escolhido nas Configurações já vale ao abrir (a configuração guardada é carregada)", async () => {
    await montar({ usar_escuro: false, tema_claro: "catppuccin-latte" });
    await waitFor(() => expect(html().dataset.tema).toBe("catppuccin-latte"));
  });
});

describe("Configurações na janela (Ctrl+, e botão)", () => {
  it("o botão abre o diálogo; Cancelar fecha e devolve o foco ao botão", async () => {
    const { usuario } = await montar();
    const botao = screen.getByRole("button", { name: "Configurações" });
    await usuario.click(botao);
    expect(screen.getByRole("dialog", { name: "Configurações" })).toBeInTheDocument();
    await usuario.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(botao).toHaveFocus();
  });

  it("Ctrl+, abre o diálogo", async () => {
    const { usuario } = await montar();
    await usuario.keyboard("{Control>},{/Control}");
    expect(await screen.findByRole("dialog", { name: "Configurações" })).toBeInTheDocument();
  });

  it("Esc fecha o diálogo sem nenhum clique (o foco inicial já está dentro) e a prévia some", async () => {
    const { usuario } = await montar();
    await usuario.keyboard("{Control>},{/Control}");
    const dialogo = await screen.findByRole("dialog", { name: "Configurações" });
    expect(dialogo.contains(document.activeElement)).toBe(true);
    expect(screen.getByRole("tab", { name: "Aparência" })).toHaveFocus();
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("os atalhos da janela ficam parados com o diálogo aberto", async () => {
    const { usuario } = await montar();
    await usuario.keyboard("{Control>},{/Control}");
    await screen.findByRole("dialog");
    await usuario.keyboard("{Control>}e{/Control}");
    expect(screen.getByRole("complementary", { name: "Editor de tags" })).toBeInTheDocument();      // o painel não fechou
  });

  it("a prévia aplica na hora e Cancelar volta ao que estava", async () => {
    const { usuario } = await montar();
    await usuario.keyboard("{Control>},{/Control}");
    await screen.findByRole("dialog");
    await usuario.click(screen.getByLabelText("Claro"));
    expect(html().dataset.tema).toBe("claro");
    await usuario.selectOptions(screen.getByLabelText("Tema escuro"), "nord");
    await usuario.click(screen.getByLabelText("Escuro"));
    expect(html().dataset.tema).toBe("nord");
    await usuario.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(html().dataset.tema).toBe("grafite");
    expect(variavel("--acento")).toBe(TEMAS.grafite.cores.acento);
  });

  it("OK guarda: a configuração vale depois de fechar e na ponte", async () => {
    const { usuario, ponteCfg } = await montar();
    await usuario.keyboard("{Control>},{/Control}");
    await screen.findByRole("dialog");
    await usuario.selectOptions(screen.getByLabelText("Tema escuro"), "tokyo-night");
    await usuario.click(screen.getByRole("button", { name: "OK" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(html().dataset.tema).toBe("tokyo-night");
    expect((await ponteCfg.carregar()).tema_escuro).toBe("tokyo-night");
  });
});

describe("aparência aplicada (M-03, M-05, B-17)", () => {
  async function abrirAparencia() {
    const r = await montar();
    await r.usuario.keyboard("{Control>},{/Control}");
    await screen.findByRole("dialog");
    return r;
  }

  it("M-03: a cor de destaque vale em tudo: variável, texto sobre ela e hover; 'Do tema' volta à do tema", async () => {
    const { usuario } = await abrirAparencia();
    expect(variavel("--acento")).toBe(TEMAS.grafite.cores.acento);
    await usuario.click(screen.getByRole("button", { name: "Cor de destaque Azul" }));
    expect(variavel("--acento")).toBe("#6b9bff");
    expect(variavel("--texto-sobre-acento")).toBe("#0b0d0c");
    expect(variavel("--acento-hover")).toBe(clarear("#6b9bff"));
    await usuario.click(screen.getByRole("button", { name: "Do tema" }));
    expect(variavel("--acento")).toBe(acentoEfetivo("grafite", "tema"));
  });

  it("M-03: o botão primário do painel usa o texto sobre o destaque (preto ou branco com contraste)", async () => {
    const usuario = userEvent.setup();
    render(<Janela ponte={ponteSimulada(faixasDeExemplo())} ponteConfig={criarPonteSimulada({ acento: "#1a237e" })} />);
    await waitFor(() => expect(variavel("--acento")).toBe("#1a237e"));
    expect(variavel("--texto-sobre-acento")).toBe("#ffffff");
    await usuario.click(screen.getByRole("button", { name: "Abrir pasta" }));
    await screen.findByRole("grid");
    expect(within(screen.getByRole("complementary", { name: "Editor de tags" })).getByRole("button", { name: /^Salvar/ })).toHaveClass("primario");
  });

  it("M-05: fonte da interface, fonte dos números e tamanho entram nas variáveis", async () => {
    const { usuario } = await abrirAparencia();
    await waitFor(() => expect(screen.getByLabelText("Fonte da interface").querySelectorAll("option").length).toBeGreaterThan(1));
    await usuario.selectOptions(screen.getByLabelText("Fonte da interface"), "Arial");
    await usuario.selectOptions(screen.getByLabelText("Fonte dos números"), "Consolas");
    expect(variavel("--fonte-ui")).toMatch(/^"Arial", "Geist"/);
    expect(variavel("--fonte-mono")).toMatch(/^"Consolas", "Geist Mono"/);
    await usuario.selectOptions(screen.getByLabelText("Fonte da interface"), "");
    expect(variavel("--fonte-ui")).toMatch(/^"Geist", "Segoe UI Variable Text"/);
    const tamanho = screen.getByRole("spinbutton", { name: "Tamanho da fonte" });
    await usuario.clear(tamanho);
    await usuario.type(tamanho, "16");
    expect(variavel("--tamanho-fonte")).toBe("16px");
  });

  it("B-17: a densidade e o tamanho mudam a altura das linhas e do cabeçalho", async () => {
    const { usuario } = await abrirAparencia();
    expect(variavel("--altura-linha")).toBe("34px");
    await usuario.selectOptions(screen.getByLabelText("Altura das linhas"), "espacosa");
    expect(variavel("--altura-linha")).toBe("50px");
    await usuario.selectOptions(screen.getByLabelText("Altura das linhas"), "confortavel");
    expect(variavel("--altura-linha")).toBe("42px");
    const tamanho = screen.getByRole("spinbutton", { name: "Tamanho da fonte" });
    await usuario.clear(tamanho);
    await usuario.type(tamanho, "15");
    expect(variavel("--altura-linha")).toBe("44px");
    expect(variavel("--altura-cabecalho")).toBe("36px");
  });

  it("a prévia não carrega credencial nova: só o OK a entrega (o token colado não vira estado da janela antes)", async () => {
    const aoMudar = vi.fn();
    const config = copiarConfig(PADROES);
    const usuario = userEvent.setup();
    render(<DialogoConfiguracoes config={config} ponte={criarPonteSimulada()} aoMudar={aoMudar} aoFechar={() => {}} />);
    await usuario.click(screen.getByRole("tab", { name: "Serviços online" }));
    await usuario.type(screen.getByLabelText("Token pessoal do Discogs"), "FAKE-TOKEN-0123456789abcdef");
    expect(aoMudar.mock.calls.every(([c]) => c.discogs_token === "")).toBe(true);
  });
});

describe("Sobre (H-09, L-04)", () => {
  it("F1 abre o Sobre com a versão e o aviso do Discogs; Esc fecha sem clicar", async () => {
    const { usuario } = await montar();
    await usuario.keyboard("{F1}");
    const sobre = await screen.findByRole("dialog", { name: "Sobre o Tagger" });
    expect(sobre).toHaveTextContent("Tagger 3.0.0-dev");
    expect(sobre).toHaveTextContent(AVISO_SOBRE);
    expect(screen.getByRole("link", { name: "Discogs" })).toHaveAttribute("href", "https://www.discogs.com");
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("o botão 'Sobre o Tagger' das Configurações abre o Sobre; Esc fecha só ele e o Esc seguinte fecha as Configurações", async () => {
    const { usuario } = await montar();
    await usuario.keyboard("{Control>},{/Control}");
    await screen.findByRole("dialog", { name: "Configurações" });
    await usuario.click(screen.getByRole("button", { name: "Sobre o Tagger" }));
    await screen.findByRole("dialog", { name: "Sobre o Tagger" });
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Sobre o Tagger" })).toBeNull();
    expect(screen.getByRole("dialog", { name: "Configurações" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Aparência" })).toHaveFocus();                // o foco voltou ao diálogo
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("F1 dentro das Configurações também abre o Sobre", async () => {
    const { usuario } = await montar();
    await usuario.keyboard("{Control>},{/Control}");
    await screen.findByRole("dialog", { name: "Configurações" });
    await usuario.keyboard("{F1}");
    expect(await screen.findByRole("dialog", { name: "Sobre o Tagger" })).toBeInTheDocument();
  });

  it("fechar o Sobre devolve o foco a quem estava com ele", async () => {
    const { usuario } = await montar();
    const abrir = screen.getByRole("button", { name: "Abrir pasta" });
    abrir.focus();
    await usuario.keyboard("{F1}");
    await screen.findByRole("dialog", { name: "Sobre o Tagger" });
    await usuario.click(screen.getByRole("button", { name: "Fechar" }));
    expect(abrir).toHaveFocus();
  });
});

describe("DialogoConfiguracoes sozinho: Esc sem clicar", () => {
  it("abre, aperta Esc e fecha como Cancelar (sem aceitar)", async () => {
    const aoFechar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoConfiguracoes config={copiarConfig(PADROES)} ponte={criarPonteSimulada()} aoMudar={() => {}} aoFechar={aoFechar} />);
    await usuario.keyboard("{Escape}");
    expect(aoFechar).toHaveBeenCalledWith(false);
  });
});
