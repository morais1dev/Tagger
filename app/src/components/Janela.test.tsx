import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ponteSimulada } from "../mock/ponteSimulada";
import { Janela } from "./Janela";

async function abrir() {
  const usuario = userEvent.setup();
  render(<Janela ponte={ponteSimulada()} />);
  await usuario.click(screen.getByRole("button", { name: "Abrir pasta" }));
  await screen.findByRole("grid", { name: "Faixas" });
  return usuario;
}

const linhas = () => within(screen.getByRole("grid")).getAllByRole("row").slice(1);       // sem o cabeçalho
const titulos = () => linhas().map((l) => within(l).getAllByRole("gridcell")[1].textContent);
const cabecalhos = () => screen.getAllByRole("columnheader").map((c) => c.textContent?.replace(/[▲▼]/g, "").trim());

describe("janela principal", () => {
  it("começa vazia, com a barra do topo, Configurações e o botão de modo claro/escuro", () => {
    render(<Janela ponte={ponteSimulada()} />);
    expect(screen.getByText("Abra uma pasta para começar.")).toBeInTheDocument();
    expect(screen.getByRole("toolbar", { name: "Barra principal" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Configurações" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Alternar tema claro/escuro" })).toBeInTheDocument();
    expect(screen.getByText("Mostrando 0 de 0")).toBeInTheDocument();
  });

  it("Abrir pasta mostra as faixas com as colunas padrão na ordem da v2", async () => {
    await abrir();
    expect(cabecalhos()).toEqual(["Nº", "Título", "Artista", "Álbum", "Ano", "Gênero", "Duração", "Capa", "Estado"]);
    expect(linhas()).toHaveLength(7);
    expect(screen.getByText("Mostrando 7 de 7")).toBeInTheDocument();
    expect(titulos()[0]).toBe("Abertura");
  });

  it("título vazio mostra o nome do arquivo em itálico; campos vazios, em cor apagada com —", async () => {
    await abrir();
    const sem = linhas()[5];
    const celulas = within(sem).getAllByRole("gridcell");
    expect(celulas[1]).toHaveTextContent("sem-tags.flac");
    expect(celulas[1]).toHaveClass("sem-titulo");
    expect(celulas[2]).toHaveTextContent("—");
    expect(celulas[2]).toHaveClass("apagada");
  });
});

describe("destaque de célula pendente", () => {
  it("só as células alteradas ficam marcadas; o ponto de estado e a capa pendente aparecem", async () => {
    await abrir();
    const segunda = within(linhas()[1]).getAllByRole("gridcell");
    const genero = segunda.find((c) => c.dataset.coluna === "genre")!;
    expect(genero).toHaveTextContent("Rock");
    expect(genero).toHaveClass("pendente");
    expect(genero).toHaveAttribute("data-pendente", "true");
    expect(segunda.find((c) => c.dataset.coluna === "artist")).not.toHaveClass("pendente");
    const estado = segunda.find((c) => c.dataset.coluna === "estado")!;
    expect(estado).toHaveAttribute("title", "Alterado, não salvo");
    expect(estado.querySelector(".ponto-pendente")).not.toBeNull();
    const quarta = within(linhas()[3]).getAllByRole("gridcell").find((c) => c.dataset.coluna === "capa")!;
    expect(quarta).toHaveAttribute("title", "Sem capa");                     // o tooltip fala da capa do arquivo; o quadradinho mostra a pendente
    expect(quarta.querySelector(".capa-cheia")).not.toBeNull();
    const primeira = within(linhas()[0]).getAllByRole("gridcell").find((c) => c.dataset.coluna === "estado")!;
    expect(primeira.querySelector(".ponto-pendente")).toBeNull();
  });

  it("o valor pendente aparece no lugar do valor do arquivo", async () => {
    await abrir();
    expect(titulos()[4]).toBe("Fechamento (ao vivo)");
  });
});

describe("ordenação por cabeçalho", () => {
  it("clique ordena crescente, outro clique decrescente, e aria-sort acompanha", async () => {
    const usuario = await abrir();
    expect(screen.getByRole("columnheader", { name: /^Título/ })).toHaveAttribute("aria-sort", "none");
    await usuario.click(screen.getByRole("button", { name: "Título" }));
    expect(screen.getByRole("columnheader", { name: /^Título/ })).toHaveAttribute("aria-sort", "ascending");
    expect(titulos()[0]).toBe("Abertura");
    expect(titulos()[1]).toBe("Fechamento (ao vivo)");
    await usuario.click(screen.getByRole("button", { name: /Título/ }));
    expect(screen.getByRole("columnheader", { name: /^Título/ })).toHaveAttribute("aria-sort", "descending");
    expect(titulos()[0]).toBe("Terceira");
  });

  it("Nº ordena por valor numérico (10 depois de 5) e Duração, por segundos", async () => {
    const usuario = await abrir();
    await usuario.click(screen.getByRole("button", { name: "Nº" }));
    const numeros = linhas().map((l) => within(l).getAllByRole("gridcell")[0].textContent);
    expect(numeros).toEqual(["1", "2", "3", "4", "5", "10", "—"]);
    await usuario.click(screen.getByRole("button", { name: "Duração" }));
    expect(titulos()[0]).toBe("sem-tags.flac");                  // 1:35 é a menor
  });
});

describe("seleção de linhas", () => {
  const selecionadas = () => linhas().filter((l) => l.getAttribute("aria-selected") === "true").length;

  it("clique, Ctrl e Shift", async () => {
    const usuario = await abrir();
    await usuario.click(linhas()[1]);
    expect(selecionadas()).toBe(1);
    await usuario.keyboard("{Control>}");
    await usuario.click(linhas()[3]);
    await usuario.keyboard("{/Control}");
    expect(selecionadas()).toBe(2);
    await usuario.click(linhas()[0]);
    expect(selecionadas()).toBe(1);
    await usuario.keyboard("{Shift>}");
    await usuario.click(linhas()[4]);
    await usuario.keyboard("{/Shift}");
    expect(selecionadas()).toBe(5);
  });

  it("Ctrl+A seleciona tudo o que está visível", async () => {
    const usuario = await abrir();
    screen.getByRole("grid").focus();
    await usuario.keyboard("{Control>}a{/Control}");
    expect(selecionadas()).toBe(7);
  });

  it("o filtro tira da seleção o que sumiu e atualiza o contador", async () => {
    const usuario = await abrir();
    await usuario.click(linhas()[0]);
    await usuario.type(screen.getByLabelText("Filtrar faixas"), "singles");
    expect(screen.getByText("Mostrando 1 de 7")).toBeInTheDocument();
    expect(titulos()).toEqual(["Outra"]);
    expect(selecionadas()).toBe(0);
  });

  it("o filtro olha o nome do arquivo e os valores pendentes", async () => {
    const usuario = await abrir();
    await usuario.type(screen.getByLabelText("Filtrar faixas"), "rock");        // gênero pendente não conta (só título/artista/álbum/arquivo)
    expect(screen.getByText("Mostrando 0 de 7")).toBeInTheDocument();
    await usuario.clear(screen.getByLabelText("Filtrar faixas"));
    await usuario.type(screen.getByLabelText("Filtrar faixas"), "ao vivo");     // título pendente conta
    expect(titulos()).toEqual(["Fechamento (ao vivo)"]);
    await usuario.clear(screen.getByLabelText("Filtrar faixas"));
    await usuario.type(screen.getByLabelText("Filtrar faixas"), "sem-tags");    // nome do arquivo
    expect(screen.getByText("Mostrando 1 de 7")).toBeInTheDocument();
  });
});

describe("seleção por arrasto e por teclado", () => {
  const selecionadas = () => linhas().map((l, i) => (l.getAttribute("aria-selected") === "true" ? i : -1)).filter((i) => i >= 0);

  it("arrastar o mouse de uma linha a outra seleciona o intervalo; soltar encerra o arrasto", async () => {
    await abrir();
    const [l0, l1, l2, l3] = linhas();
    fireEvent.mouseDown(l1, { button: 0, buttons: 1 });
    fireEvent.mouseEnter(l2, { buttons: 1 });
    fireEvent.mouseEnter(l3, { buttons: 1 });
    expect(selecionadas()).toEqual([1, 2, 3]);
    fireEvent.mouseEnter(l0, { buttons: 1 });
    expect(selecionadas()).toEqual([0, 1]);
    fireEvent.mouseUp(document);
    fireEvent.mouseEnter(l3, { buttons: 0 });
    expect(selecionadas()).toEqual([0, 1]);                          // depois de soltar, passar o mouse não muda nada
  });

  it("Ctrl+arrastar soma ao que já estava selecionado; botão direito não seleciona", async () => {
    await abrir();
    const l = linhas();
    fireEvent.mouseDown(l[0], { button: 0, buttons: 1 });
    fireEvent.mouseUp(document);
    fireEvent.mouseDown(l[3], { button: 0, buttons: 1, ctrlKey: true });
    fireEvent.mouseEnter(l[5], { buttons: 1, ctrlKey: true });
    fireEvent.mouseUp(document);
    expect(selecionadas()).toEqual([0, 3, 4, 5]);
    fireEvent.mouseDown(l[1], { button: 2, buttons: 2 });
    expect(selecionadas()).toEqual([0, 3, 4, 5]);
  });

  it("clique com Ctrl alterna só uma vez (mousedown, sem clique duplicado)", async () => {
    const usuario = await abrir();
    await usuario.click(linhas()[0]);
    await usuario.keyboard("{Control>}");
    await usuario.click(linhas()[2]);
    await usuario.keyboard("{/Control}");
    expect(selecionadas()).toEqual([0, 2]);
  });

  it("setas, Home, End, PgDn e PgUp movem a seleção; Shift estica", async () => {
    const usuario = await abrir();
    await usuario.click(linhas()[1]);
    await usuario.keyboard("{ArrowDown}");
    expect(selecionadas()).toEqual([2]);
    await usuario.keyboard("{Shift>}{ArrowDown}{ArrowDown}{/Shift}");
    expect(selecionadas()).toEqual([2, 3, 4]);
    await usuario.keyboard("{End}");
    expect(selecionadas()).toEqual([6]);
    await usuario.keyboard("{Home}");
    expect(selecionadas()).toEqual([0]);
    await usuario.keyboard("{PageDown}");                            // jsdom não tem altura: página de 10 linhas, limitada à última
    expect(selecionadas()).toEqual([6]);
    await usuario.keyboard("{PageUp}");
    expect(selecionadas()).toEqual([0]);
    await usuario.keyboard("{Shift>}{End}{/Shift}");
    expect(selecionadas()).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  it("a grade aponta a linha atual com aria-activedescendant", async () => {
    const usuario = await abrir();
    await usuario.click(linhas()[2]);
    await usuario.keyboard("{ArrowDown}");
    expect(screen.getByRole("grid")).toHaveAttribute("aria-activedescendant", linhas()[3].id);
  });

  it("depois de ordenar, as setas seguem a ordem que aparece na tela", async () => {
    const usuario = await abrir();
    await usuario.click(screen.getByRole("button", { name: "Duração" }));
    await usuario.click(linhas()[0]);                                // sem-tags.flac (1:35, a menor)
    await usuario.keyboard("{ArrowDown}");
    expect(titulos()[selecionadas()[0]]).toBe("Abertura");           // a segunda menor
  });
});

describe("colunas: mostrar/esconder e redimensionar", () => {
  async function abrirMenu(usuario: ReturnType<typeof userEvent.setup>) {
    await usuario.pointer({ keys: "[MouseRight]", target: screen.getAllByRole("columnheader")[1] });
    return screen.findByRole("menu", { name: "Colunas" });
  }

  it("clique direito no cabeçalho abre o menu, sem as colunas fixas (Título e estado)", async () => {
    const usuario = await abrir();
    const menu = await abrirMenu(usuario);
    expect(within(menu).queryByRole("menuitemcheckbox", { name: /Título/ })).toBeNull();
    expect(within(menu).queryByRole("menuitemcheckbox", { name: /Estado/ })).toBeNull();
    expect(within(menu).getAllByRole("menuitemcheckbox")).toHaveLength(17);       // 19 colunas menos as 2 fixas
    expect(within(menu).getByRole("menuitemcheckbox", { name: /Ano/ })).toHaveAttribute("aria-checked", "true");
    expect(within(menu).getByRole("menuitemcheckbox", { name: /Gravadora/ })).toHaveAttribute("aria-checked", "false");
  });

  it("mostrar uma coluna escondida e esconder uma visível; Restaurar volta ao padrão", async () => {
    const usuario = await abrir();
    let menu = await abrirMenu(usuario);
    await usuario.click(within(menu).getByRole("menuitemcheckbox", { name: /Gravadora/ }));
    await usuario.click(within(menu).getByRole("menuitemcheckbox", { name: /Ano/ }));
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(cabecalhos()).toContain("Gravadora");
    expect(cabecalhos()).not.toContain("Ano");
    menu = await abrirMenu(usuario);
    await usuario.click(within(menu).getByRole("menuitem", { name: "Restaurar colunas padrão" }));
    expect(cabecalhos()).toEqual(["Nº", "Título", "Artista", "Álbum", "Ano", "Gênero", "Duração", "Capa", "Estado"]);
  });

  it("as colunas novas entram na posição original, não no fim", async () => {
    const usuario = await abrir();
    const menu = await abrirMenu(usuario);
    await usuario.click(within(menu).getByRole("menuitemcheckbox", { name: /Artista do álbum/ }));
    const c = cabecalhos();
    expect(c.indexOf("Artista do álbum")).toBe(c.indexOf("Álbum") + 1);
  });

  it("redimensionar com o mouse (arrastar) e com o teclado, nunca abaixo do mínimo", async () => {
    await abrir();
    const cabecalho = screen.getAllByRole("row")[0];
    const alca = screen.getByRole("separator", { name: "Redimensionar Artista" });
    expect(cabecalho.style.gridTemplateColumns).toContain("170px");
    fireEvent.mouseDown(alca, { clientX: 100 });
    fireEvent.mouseMove(document, { clientX: 150 });
    fireEvent.mouseUp(document);
    expect(cabecalho.style.gridTemplateColumns).toContain("220px");
    fireEvent.keyDown(alca, { key: "ArrowLeft" });
    expect(cabecalho.style.gridTemplateColumns).toContain("210px");
    fireEvent.mouseDown(alca, { clientX: 100 });
    fireEvent.mouseMove(document, { clientX: -500 });
    fireEvent.mouseUp(document);
    expect(cabecalho.style.gridTemplateColumns).toContain("28px");
  });

  it("o Título estica (mínimo 160 px) e o redimensionar de uma coluna não mexe nas outras", async () => {
    await abrir();
    const cabecalho = screen.getAllByRole("row")[0];
    expect(cabecalho.style.gridTemplateColumns).toContain("minmax(160px, 1fr)");
    fireEvent.keyDown(screen.getByRole("separator", { name: "Redimensionar Ano" }), { key: "ArrowRight" });
    expect(cabecalho.style.gridTemplateColumns).toContain("74px");
    expect(cabecalho.style.gridTemplateColumns).toContain("170px");
  });
});
