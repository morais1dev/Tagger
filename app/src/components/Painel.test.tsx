import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { type Faixa } from "../api";
import { CAPA_AZUL, CAPA_VERDE, type OpcoesSimuladas, faixasDeExemplo, ponteSimulada } from "../mock/ponteSimulada";
import { bytesPng } from "../testes/imagens";
import { Janela } from "./Janela";

type Usuario = ReturnType<typeof userEvent.setup>;

async function abrir(opcoes: OpcoesSimuladas = {}, faixas: Faixa[] = faixasDeExemplo(), confirmar = vi.fn(() => true)) {
  const usuario = userEvent.setup();
  const ponte = ponteSimulada(faixas, opcoes);
  render(<Janela ponte={ponte} confirmar={confirmar} />);
  await usuario.click(screen.getByRole("button", { name: "Abrir pasta" }));
  await screen.findByRole("grid", { name: "Faixas" });
  return { usuario, ponte, confirmar };
}

const linhas = () => within(screen.getByRole("grid")).getAllByRole("row").slice(1);
const celula = (linha: HTMLElement, coluna: string) => within(linha).getAllByRole("gridcell").find((c) => c.dataset.coluna === coluna)!;
const campo = (nome: string) => screen.getByLabelText(nome) as HTMLInputElement | HTMLTextAreaElement;
const painel = () => screen.getByRole("complementary", { name: "Editor de tags" });
const status = () => screen.getByRole("status");

/** Seleciona linhas pelos índices (a 1ª com clique, as outras com Ctrl). */
async function selecionar(usuario: Usuario, ...indices: number[]) {
  await usuario.click(linhas()[indices[0]]);
  for (const i of indices.slice(1)) {
    await usuario.keyboard("{Control>}");
    await usuario.click(linhas()[i]);
    await usuario.keyboard("{/Control}");
  }
}

async function menuCapa(usuario: Usuario) {
  await usuario.click(screen.getByRole("button", { name: "Mais opções da capa" }));
  return screen.getByRole("menu", { name: "Opções da capa" });
}

describe("painel: campos e seleção (C-01 a C-05)", () => {
  it("C-03: sem seleção mostra o painel vazio, com o rodapé porque há pendências", async () => {
    await abrir();
    expect(within(painel()).getByText("Nenhum arquivo selecionado")).toBeInTheDocument();
    expect(painel()).toHaveTextContent("Use Ctrl, Shift ou arraste o mouse para editar várias.");
    expect(within(painel()).getByRole("button", { name: "Salvar 3 arquivos" })).toBeEnabled();     // faixas 2, 4 e 5
    expect(screen.queryByLabelText("Título")).toBeNull();
  });

  it("C-01 e C-04: uma faixa mostra os 13 campos na ordem da v2 e o cabeçalho com nome, duração e bitrate", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    const rotulos = within(painel()).getAllByText((_t, el) => el?.tagName === "LABEL").map((l) => l.textContent?.trim());
    expect(rotulos).toEqual(["Título", "Artista", "Álbum", "Artista do álbum", "Faixa", "Disco", "Ano", "Gênero",
      "Compositor", "Letrista", "Gravadora", "Comentário", "Letra"]);
    expect(campo("Título").value).toBe("Abertura");
    expect(campo("Faixa").value).toBe("1/5");
    expect(campo("Ano").value).toBe("1977");
    expect(campo("Comentário").tagName).toBe("TEXTAREA");
    expect(campo("Letra").tagName).toBe("TEXTAREA");
    expect(within(painel()).getByRole("heading", { name: "Abertura" })).toBeInTheDocument();
    const sub = within(painel()).getByText(/01 - Abertura\.mp3/);
    expect(sub).toHaveTextContent("01 - Abertura.mp3 · 3:07 · 320 kbps");
    expect(sub).toHaveAttribute("title", "C:\\Musicas\\Disco Raro\\01 - Abertura.mp3");
  });

  it("C-04: título vazio usa o nome do arquivo; bitrate desconhecido vira —", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 5);
    expect(within(painel()).getByRole("heading", { name: "sem-tags.flac" })).toBeInTheDocument();
    await selecionar(usuario, 2);
    expect(painel()).toHaveTextContent("· —");
  });

  it("C-02 e C-04: várias faixas mostram o valor comum e '‹vários valores›' no que difere", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0, 2);
    expect(within(painel()).getByRole("heading", { name: "2 arquivos selecionados" })).toBeInTheDocument();
    expect(painel()).toHaveTextContent("Campos diferentes aparecem como ‹vários valores› e só mudam se você editar.");
    expect(campo("Álbum").value).toBe("Disco Raro");
    expect(campo("Título").value).toBe("");
    expect(campo("Título")).toHaveAttribute("placeholder", "‹vários valores›");
    expect(campo("Álbum")).toHaveAttribute("placeholder", "");
  });

  it("C-02: digitar numa multisseleção altera todas; apagar o que digitou volta ao estado anterior", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0, 2);
    await usuario.type(campo("Título"), "Igual");
    await waitFor(() => expect(celula(linhas()[0], "title")).toHaveTextContent("Igual"));
    expect(celula(linhas()[2], "title")).toHaveTextContent("Igual");
    expect(celula(linhas()[0], "title")).toHaveClass("pendente");
    await usuario.clear(campo("Título"));
    await waitFor(() => expect(celula(linhas()[0], "title")).toHaveTextContent("Abertura"));
    expect(celula(linhas()[2], "title")).toHaveTextContent("Terceira");
    expect(celula(linhas()[0], "title")).not.toHaveClass("pendente");
  });

  it("C-02: apagar volta ao pendente que a faixa já tinha (não ao valor do arquivo)", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 1, 2);                               // Segunda tem gênero pendente (Rock); Terceira tem MPB
    expect(campo("Gênero").value).toBe("");
    await usuario.type(campo("Gênero"), "Jazz");
    await waitFor(() => expect(celula(linhas()[2], "genre")).toHaveTextContent("Jazz"));
    await usuario.clear(campo("Gênero"));
    await waitFor(() => expect(celula(linhas()[2], "genre")).toHaveTextContent("MPB"));
    expect(celula(linhas()[1], "genre")).toHaveTextContent("Rock");
    expect(celula(linhas()[1], "genre")).toHaveClass("pendente");
  });

  it("C-05: só o campo com alteração pendente ganha a marca ao lado do rótulo", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 1);                                  // gênero pendente
    const marca = (nome: string) => campo(nome).closest(".campo")!.querySelector('[role="img"]');
    expect(marca("Gênero")).not.toBeNull();
    expect(marca("Gênero")).toHaveAttribute("aria-label", "Alterado, não salvo");
    expect(marca("Título")).toBeNull();
    await usuario.type(campo("Artista"), "!");
    await waitFor(() => expect(marca("Artista")).not.toBeNull());
  });

  it("editar um campo vira pendência na tabela, com o ponto de estado", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    await usuario.clear(campo("Artista"));
    await usuario.type(campo("Artista"), "Outro");
    await waitFor(() => expect(celula(linhas()[0], "artist")).toHaveTextContent("Outro"));
    expect(celula(linhas()[0], "estado").querySelector(".ponto-pendente")).not.toBeNull();
    await usuario.clear(campo("Artista"));
    await usuario.type(campo("Artista"), "Banda");                 // voltou ao valor do arquivo: some a pendência
    await waitFor(() => expect(celula(linhas()[0], "artist")).not.toHaveClass("pendente"));
  });
});

describe("painel: validação e gênero (C-06 e C-07)", () => {
  it("C-06: ano inválido mostra a mensagem sob o campo, borda de erro e tooltip; corrigir limpa", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    await usuario.clear(campo("Ano"));
    await usuario.type(campo("Ano"), "20");
    const erro = await screen.findByRole("alert");
    expect(erro).toHaveTextContent("Ano inválido. Use AAAA (ex.: 2024) ou AAAA-MM-DD.");
    expect(campo("Ano")).toHaveAttribute("aria-invalid", "true");
    expect(campo("Ano")).toHaveClass("invalido");
    expect(campo("Ano")).toHaveAttribute("title", "Ano inválido. Use AAAA (ex.: 2024) ou AAAA-MM-DD.");
    await usuario.type(campo("Ano"), "24");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(campo("Ano")).toHaveAttribute("aria-invalid", "false");
  });

  it("C-06: faixa/disco e gênero numérico inválidos; 'atual' e vazio são aceitos", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    await usuario.clear(campo("Faixa"));
    await usuario.type(campo("Faixa"), "0");
    expect(await screen.findByRole("alert")).toHaveTextContent("Número inválido");
    await usuario.clear(campo("Faixa"));
    expect(screen.queryByRole("alert")).toBeNull();                     // vazio é válido
    await usuario.clear(campo("Gênero"));
    await usuario.type(campo("Gênero"), "12");
    expect(await screen.findByRole("alert")).toHaveTextContent("Digite o nome do gênero por extenso");
    await usuario.clear(campo("Gênero"));
    await usuario.clear(campo("Ano"));
    await usuario.type(campo("Ano"), "atual");
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("C-06: o valor inválido continua pendente (a v2 só bloqueia ao salvar), mas a mensagem fica visível", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    await usuario.clear(campo("Ano"));
    await usuario.type(campo("Ano"), "9");
    await waitFor(() => expect(celula(linhas()[0], "date")).toHaveTextContent("9"));
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("C-07: o gênero sugere a lista padrão mais os gêneros dos arquivos, sem repetir", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    const lista = campo("Gênero").getAttribute("list")!;
    const opcoes = [...document.getElementById(lista)!.querySelectorAll("option")].map((o) => o.getAttribute("value"));
    expect(opcoes).toContain("Bossa Nova");
    expect(opcoes).toContain("Rock");
    expect(opcoes.filter((o) => o === "MPB")).toHaveLength(1);
    expect(opcoes).toEqual([...opcoes].sort((a, b) => a!.localeCompare(b!, "pt-BR", { sensitivity: "base" })));
  });
});

describe("painel: rodapé, teclado e layout (C-09 a C-13)", () => {
  it("C-11: o texto do Salvar acompanha o número de arquivos pendentes; Descartar limpa tudo", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    expect(within(painel()).getByRole("button", { name: "Salvar 3 arquivos" })).toBeEnabled();
    await usuario.type(campo("Artista"), "!");
    await within(painel()).findByRole("button", { name: "Salvar 4 arquivos" });
    await usuario.click(within(painel()).getByRole("button", { name: "Descartar" }));
    expect(await within(painel()).findByRole("button", { name: "Salvar" })).toBeDisabled();
    expect(within(painel()).getByRole("button", { name: "Descartar" })).toBeDisabled();
    expect(status()).toHaveTextContent("Alterações descartadas.");
    expect(celula(linhas()[1], "genre")).toHaveTextContent("MPB");               // o pendente (Rock) sumiu
    expect(campo("Artista").value).toBe("Banda");                                 // o painel recarregou
  });

  it("C-11: Salvar grava tudo de uma vez e zera as pendências", async () => {
    const { usuario, ponte } = await abrir();
    await selecionar(usuario, 1);
    await usuario.click(within(painel()).getByRole("button", { name: "Salvar 3 arquivos" }));
    await waitFor(() => expect(status()).toHaveTextContent("3 arquivos salvos."));
    expect(ponte.registros.salvamentos).toBe(1);
    expect(celula(linhas()[1], "genre")).toHaveTextContent("Rock");
    expect(celula(linhas()[1], "genre")).not.toHaveClass("pendente");
    expect(within(painel()).getByRole("button", { name: "Salvar" })).toBeDisabled();
  });

  it("C-11: com 1 arquivo pendente o botão diz 'Salvar 1 arquivo'", async () => {
    const um = faixasDeExemplo().slice(0, 3);
    um[1].pendentes = { genre: "Rock" };
    await abrir({}, um);
    expect(within(painel()).getByRole("button", { name: "Salvar 1 arquivo" })).toBeInTheDocument();
  });

  it("C-09: Enter num campo de texto salva; sem pendências não faz nada", async () => {
    const { usuario, ponte } = await abrir();
    await selecionar(usuario, 0);
    await usuario.click(campo("Título"));
    await usuario.keyboard("{Enter}");
    await waitFor(() => expect(ponte.registros.salvamentos).toBe(1));
    await usuario.keyboard("{Enter}");                                       // agora não há nada pendente
    expect(ponte.registros.salvamentos).toBe(1);
  });

  it("C-09: Enter numa caixa de várias linhas não salva (quebra a linha)", async () => {
    const { usuario, ponte } = await abrir();
    await selecionar(usuario, 0);
    await usuario.type(campo("Comentário"), "a{Enter}b");
    expect(ponte.registros.salvamentos).toBe(0);
    await waitFor(() => expect(campo("Comentário").value).toBe("a\nb"));
  });

  it("C-10: Esc no painel devolve o foco à tabela; Tab sai da caixa de várias linhas", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    campo("Título").focus();
    await usuario.keyboard("{Escape}");
    expect(screen.getByRole("grid")).toHaveFocus();
    campo("Comentário").focus();
    await usuario.tab();
    expect(campo("Comentário")).not.toHaveFocus();
    expect(campo("Comentário").value).toBe("");                              // não inseriu tabulação
  });

  it("C-12: o botão e o Ctrl+E mostram/escondem o painel e a escolha é lembrada", async () => {
    const { usuario } = await abrir();
    const botao = screen.getByRole("button", { name: "Editor" });
    expect(botao).toHaveAttribute("aria-pressed", "true");
    await usuario.click(botao);
    expect(screen.queryByRole("complementary", { name: "Editor de tags" })).toBeNull();
    expect(localStorage.getItem("tagger.painel_visivel")).toBe("0");
    await usuario.keyboard("{Control>}e{/Control}");
    expect(painel()).toBeInTheDocument();
    expect(localStorage.getItem("tagger.painel_visivel")).toBe("1");
  });

  it("C-12: começa escondido se foi assim que ficou da última vez", () => {
    localStorage.setItem("tagger.painel_visivel", "0");
    render(<Janela ponte={ponteSimulada()} />);
    expect(screen.queryByRole("complementary", { name: "Editor de tags" })).toBeNull();
    expect(screen.getByRole("button", { name: "Editor" })).toHaveAttribute("aria-pressed", "false");
  });

  it("C-13: o divisor mexe entre 240 e 560 px, por teclado e por arrasto, e lembra a largura", async () => {
    await abrir();
    const divisor = screen.getByRole("separator", { name: "Redimensionar o painel" });
    const coluna = () => painel().parentElement as HTMLElement;
    expect(divisor).toHaveAttribute("aria-valuenow", "380");
    expect(coluna().style.width).toBe("380px");
    fireEvent.keyDown(divisor, { key: "ArrowRight" });
    expect(coluna().style.width).toBe("396px");
    fireEvent.keyDown(divisor, { key: "End" });
    expect(coluna().style.width).toBe("560px");
    fireEvent.keyDown(divisor, { key: "ArrowRight" });
    expect(coluna().style.width).toBe("560px");
    fireEvent.keyDown(divisor, { key: "Home" });
    expect(coluna().style.width).toBe("240px");
    fireEvent.mouseDown(divisor, { clientX: 100 });
    fireEvent.mouseMove(document, { clientX: 250 });
    expect(coluna().style.width).toBe("390px");
    fireEvent.mouseMove(document, { clientX: 5000 });
    expect(coluna().style.width).toBe("560px");
    fireEvent.mouseMove(document, { clientX: -5000 });
    fireEvent.mouseUp(document);
    expect(coluna().style.width).toBe("240px");
    expect(localStorage.getItem("tagger.painel_largura")).toBe("240");
  });

  it("C-13: a largura salva é reaplicada (e limitada) ao abrir", () => {
    localStorage.setItem("tagger.painel_largura", "9999");
    render(<Janela ponte={ponteSimulada()} />);
    expect(screen.getByRole("separator", { name: "Redimensionar o painel" })).toHaveAttribute("aria-valuenow", "560");
  });
});

describe("capa (D-01, D-03, D-09, D-12)", () => {
  it("D-01: mostra a capa da seleção com formato, dimensões e tamanho; 'Sem capa' e 'várias capas'", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    expect(screen.getByRole("img", { name: "Capa do álbum" })).toHaveAttribute("src", CAPA_AZUL.url);
    expect(painel()).toHaveTextContent("JPEG · 500×500 · 24 KB");
    expect(screen.getByTestId("quadro-capa").className).toContain("quadro-capa");
    await selecionar(usuario, 5);
    expect(within(screen.getByTestId("quadro-capa")).getByText("Sem capa")).toBeInTheDocument();
    expect(painel()).toHaveTextContent("Nenhuma imagem");
    await selecionar(usuario, 0, 5);
    expect(within(screen.getByTestId("quadro-capa")).getByText("‹várias capas›")).toBeInTheDocument();
    expect(painel()).toHaveTextContent("Capas diferentes");
  });

  it("D-01: o quadro tem 112 px (CSS) e a imagem não tem arrastar nativo", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    expect(screen.getByRole("img", { name: "Capa do álbum" })).toHaveAttribute("draggable", "false");
  });

  it("D-03 e D-12: Trocar capa vira pendência: 'Nova capa ●' no painel e quadradinho cheio na tabela", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 5);
    expect(celula(linhas()[5], "capa").querySelector(".capa-vazia")).not.toBeNull();
    await usuario.click(screen.getByRole("button", { name: "Trocar capa" }));
    await waitFor(() => expect(painel()).toHaveTextContent("Nova capa"));
    expect(painel()).toHaveTextContent("PNG · 600×600 · 80 KB");
    expect(screen.getByRole("img", { name: "Capa do álbum" })).toHaveAttribute("src", CAPA_VERDE.url);
    expect(celula(linhas()[5], "capa").querySelector(".capa-cheia")).not.toBeNull();
    expect(celula(linhas()[5], "estado").querySelector(".ponto-pendente")).not.toBeNull();
    expect(within(painel()).getByRole("button", { name: "Salvar 4 arquivos" })).toBeEnabled();
  });

  it("D-03: cancelar o seletor não muda nada", async () => {
    const { usuario } = await abrir({ imagemEscolhida: null });
    await selecionar(usuario, 5);
    await usuario.click(screen.getByRole("button", { name: "Trocar capa" }));
    await waitFor(() => expect(painel()).toHaveTextContent("Nenhuma imagem"));
    expect(painel()).not.toHaveTextContent("Nova capa");
  });

  it("D-12: uma capa pendente já existente (faixa 4) aparece no painel", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 3);
    expect(painel()).toHaveTextContent("Nova capa");
    expect(screen.getByRole("img", { name: "Capa do álbum" })).toHaveAttribute("src", CAPA_VERDE.url);
  });

  it("D-09: Remover capa vira 'Capa será removida' (tabela sem capa); Manter capa original desfaz", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Remover capa" }));
    await waitFor(() => expect(painel()).toHaveTextContent("Capa será removida"));
    expect(within(screen.getByTestId("quadro-capa")).getByText("Sem capa")).toBeInTheDocument();
    expect(celula(linhas()[0], "capa").querySelector(".capa-vazia")).not.toBeNull();
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Manter capa original" }));
    await waitFor(() => expect(painel()).not.toHaveTextContent("Capa será removida"));
    expect(screen.getByRole("img", { name: "Capa do álbum" })).toHaveAttribute("src", CAPA_AZUL.url);
    expect(celula(linhas()[0], "capa").querySelector(".capa-cheia")).not.toBeNull();
  });

  it("D-09: numa multisseleção a capa vale para todas", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0, 2);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Remover capa" }));
    await waitFor(() => expect(celula(linhas()[2], "capa").querySelector(".capa-vazia")).not.toBeNull());
    expect(celula(linhas()[0], "capa").querySelector(".capa-vazia")).not.toBeNull();
  });

  it("Salvar grava a capa pendente: a tabela passa a ter capa de verdade", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 3);
    await usuario.click(within(painel()).getByRole("button", { name: "Salvar 3 arquivos" }));
    await waitFor(() => expect(status()).toHaveTextContent("3 arquivos salvos."));
    expect(celula(linhas()[3], "capa")).toHaveAttribute("title", "Tem capa");
    expect(painel()).not.toHaveTextContent("Nova capa");
  });
});

describe("menu da capa (D-04 a D-08)", () => {
  it("D-06: o menu tem as seis opções e liga/desliga como na v2", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 5);                                   // sem capa, sem pendência
    const menu = await menuCapa(usuario);
    const itens = within(menu).getAllByRole("menuitem");
    expect(itens.map((i) => i.textContent)).toEqual([
      "Escolher imagem…", "Colar imagem", "Exportar capa…", "Salvar como cover.jpg na pasta", "Remover capa", "Manter capa original"]);
    const ativo = (nome: string) => !(within(menu).getByRole("menuitem", { name: nome }) as HTMLButtonElement).disabled;
    expect([ativo("Escolher imagem…"), ativo("Colar imagem")]).toEqual([true, true]);
    expect([ativo("Exportar capa…"), ativo("Salvar como cover.jpg na pasta"), ativo("Remover capa"), ativo("Manter capa original")])
      .toEqual([false, false, false, false]);
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).toBeNull();
    await selecionar(usuario, 3);                                   // capa pendente
    const menu2 = await menuCapa(usuario);
    expect(within(menu2).getByRole("menuitem", { name: "Manter capa original" })).toBeEnabled();
    expect(within(menu2).getByRole("menuitem", { name: "Exportar capa…" })).toBeEnabled();
  });

  it("D-06: o clique direito no quadro abre o mesmo menu", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 0);
    fireEvent.contextMenu(screen.getByTestId("quadro-capa"));
    expect(await screen.findByRole("menu", { name: "Opções da capa" })).toBeInTheDocument();
    await usuario.click(screen.getByRole("menuitem", { name: "Escolher imagem…" }));
    await waitFor(() => expect(painel()).toHaveTextContent("Nova capa"));
  });

  it("D-04: arrastar uma imagem PNG sobre o quadro (borda de destaque) define a capa", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 5);
    const quadro = screen.getByTestId("quadro-capa");
    fireEvent.dragOver(quadro);
    expect(quadro).toHaveClass("arrastando");
    fireEvent.dragLeave(quadro);
    expect(quadro).not.toHaveClass("arrastando");
    const arquivo = new File([bytesPng(300, 200)], "foto.png", { type: "image/png" });
    fireEvent.drop(quadro, { dataTransfer: { files: [arquivo] } });
    await waitFor(() => expect(painel()).toHaveTextContent("PNG · 300×200 · 1 KB"));
    expect(painel()).toHaveTextContent("Nova capa");
    expect(quadro).not.toHaveClass("arrastando");
  });

  it("D-04: GIF, texto e arquivo que finge ser .png são recusados com aviso", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 5);
    const quadro = screen.getByTestId("quadro-capa");
    const gif = new File([new TextEncoder().encode("GIF89a................................")], "a.gif", { type: "image/gif" });
    fireEvent.drop(quadro, { dataTransfer: { files: [gif] } });
    await waitFor(() => expect(status()).toHaveTextContent("Só imagens JPEG ou PNG (.jpg, .jpeg, .png) servem de capa."));
    fireEvent.drop(quadro, { dataTransfer: { files: [new File(["texto"], "a.txt", { type: "text/plain" })] } });
    await waitFor(() => expect(status()).toHaveTextContent("Só imagens JPEG ou PNG"));
    fireEvent.drop(quadro, { dataTransfer: { files: [new File(["não sou imagem de verdade........"], "x.png", { type: "image/png" })] } });
    await waitFor(() => expect(status()).toHaveTextContent("Não consegui abrir essa imagem."));
    expect(painel()).not.toHaveTextContent("Nova capa");
  });

  it("D-05: Colar imagem sem nada na área de transferência avisa; com imagem define a capa", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 5);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Colar imagem" }));
    await waitFor(() => expect(status()).toHaveTextContent("Não há imagem na área de transferência."));
    expect(painel()).not.toHaveTextContent("Nova capa");
  });

  it("D-05: Colar imagem do menu usa a imagem da área de transferência", async () => {
    const { usuario } = await abrir({ areaDeTransferencia: CAPA_VERDE });
    await selecionar(usuario, 5);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Colar imagem" }));
    await waitFor(() => expect(painel()).toHaveTextContent("PNG · 600×600 · 80 KB"));
  });

  it("D-05: Ctrl+V com o quadro em foco (imagem no evento de colar) também define a capa; texto colado é ignorado", async () => {
    const { usuario } = await abrir();
    await selecionar(usuario, 5);
    const quadro = screen.getByTestId("quadro-capa");
    fireEvent.paste(quadro, { clipboardData: { files: [] } });
    expect(painel()).not.toHaveTextContent("Nova capa");
    fireEvent.paste(quadro, { clipboardData: { files: [new File([bytesPng(40, 40)], "colada.png", { type: "image/png" })] } });
    await waitFor(() => expect(painel()).toHaveTextContent("PNG · 40×40"));
  });

  it("D-07: Exportar capa sugere o nome pelo álbum, sem caracteres inválidos, e avisa", async () => {
    const lista = faixasDeExemplo();
    lista[0].tags.album = "AC/DC: Live?";
    const { usuario, ponte } = await abrir({}, lista);
    await selecionar(usuario, 0);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Exportar capa…" }));
    await waitFor(() => expect(status()).toHaveTextContent("Capa exportada para ACDC Live.jpg"));
    expect(ponte.registros.exportadas).toHaveLength(1);
    expect(ponte.registros.exportadas[0].capa).toEqual(CAPA_AZUL);
  });

  it("D-07: cancelar o diálogo de salvar não avisa nada", async () => {
    const { usuario, ponte } = await abrir({ nomeExportado: null });
    await selecionar(usuario, 0);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Exportar capa…" }));
    await waitFor(() => expect(ponte.registros.exportadas).toHaveLength(0));
    expect(status()).toBeEmptyDOMElement();
  });

  it("D-08: Salvar como cover.jpg grava na pasta e avisa o nome da pasta", async () => {
    const { usuario, ponte, confirmar } = await abrir();
    await selecionar(usuario, 0);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Salvar como cover.jpg na pasta" }));
    await waitFor(() => expect(status()).toHaveTextContent("cover.jpg salvo em Disco Raro"));
    expect(ponte.registros.covers).toEqual([{ pastas: ["C:\\Musicas\\Disco Raro"], nome: "cover.jpg", capa: CAPA_AZUL }]);
    expect(confirmar).not.toHaveBeenCalled();
  });

  it("D-08: pergunta antes de substituir; 'não' não grava, 'sim' grava", async () => {
    const existente = { pastasComCover: ["C:\\Musicas\\Disco Raro"] };
    const nao = await abrir(existente, faixasDeExemplo(), vi.fn(() => false));
    await selecionar(nao.usuario, 0);
    await nao.usuario.click(within(await menuCapa(nao.usuario)).getByRole("menuitem", { name: "Salvar como cover.jpg na pasta" }));
    await waitFor(() => expect(nao.confirmar).toHaveBeenCalledWith("Já existe um cover.jpg em 1 pasta(s). Substituir?"));
    expect(nao.ponte.registros.covers).toHaveLength(0);
    expect(status()).toBeEmptyDOMElement();
  });

  it("D-08: confirmando, substitui", async () => {
    const sim = await abrir({ pastasComCover: ["C:\\Musicas\\Disco Raro"] }, faixasDeExemplo(), vi.fn(() => true));
    await selecionar(sim.usuario, 0);
    await sim.usuario.click(within(await menuCapa(sim.usuario)).getByRole("menuitem", { name: "Salvar como cover.jpg na pasta" }));
    await waitFor(() => expect(sim.ponte.registros.covers).toHaveLength(1));
  });

  it("D-08: com várias pastas grava em cada uma e avisa quantas; falha por pasta é avisada", async () => {
    const a = faixasDeExemplo()[0];
    const b: Faixa = { ...structuredClone(a), id: "D:\\Outra\\x.mp3", caminho: "D:\\Outra\\x.mp3" };
    const ok = await abrir({}, [a, b]);
    await ok.usuario.keyboard("{Control>}a{/Control}");
    await ok.usuario.click(screen.getByRole("grid"));
    await ok.usuario.keyboard("{Control>}a{/Control}");
    await ok.usuario.click(within(await menuCapa(ok.usuario)).getByRole("menuitem", { name: "Salvar como cover.jpg na pasta" }));
    await waitFor(() => expect(status()).toHaveTextContent("cover.jpg salvo em 2 pastas"));
    expect(ok.ponte.registros.covers[0].pastas).toHaveLength(2);
  });

  it("D-08: falha ao gravar numa pasta mostra aviso de falha", async () => {
    const { usuario } = await abrir({ pastasComFalha: ["C:\\Musicas\\Disco Raro"] });
    await selecionar(usuario, 0);
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Salvar como cover.jpg na pasta" }));
    await waitFor(() => expect(status()).toHaveTextContent("Não consegui gravar cover.jpg em 1 pasta(s)."));
  });

  it("D-08: capa PNG grava cover.png", async () => {
    const { usuario, ponte } = await abrir();
    await selecionar(usuario, 3);                                   // capa pendente PNG (verde)
    await usuario.click(within(await menuCapa(usuario)).getByRole("menuitem", { name: "Salvar como cover.jpg na pasta" }));
    await waitFor(() => expect(ponte.registros.covers[0]?.nome).toBe("cover.png"));
  });
});
