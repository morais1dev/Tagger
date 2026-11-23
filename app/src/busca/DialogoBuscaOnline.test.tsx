import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ReleaseSimulado } from "./analiseSimulada";
import { DialogoBuscaOnline, type PropsBusca } from "./DialogoBuscaOnline";
import { criarPonteSimulada, type OpcoesPonteBusca } from "./ponteBusca";
import { DICA_SEM_DISCOGS, type Capa, type FaixaBusca } from "./tipos";

const mb: ReleaseSimulado = {
  id: "mb1", descricao: "Aurora Lane — Daybreak  (2020, BR, 3 faixas, Selo)", titulo: "Daybreak", artista: "Aurora Lane",
  data: "2020-05-01", generos: ["Pop"], gravadora: "Selo", faixas: [
    { titulo: "Afterglow", artista: "Aurora Lane", numero: 1, disco: 1 },
    { titulo: "Sunrise", artista: "Aurora Lane", numero: 2, disco: 1 },
    { titulo: "Dusk", artista: "Aurora Lane", numero: 3, disco: 1 },
  ],
};
const mb2: ReleaseSimulado = { ...mb, id: "mb2", descricao: "Aurora Lane — Daybreak (Deluxe)  (2021)", titulo: "Daybreak Deluxe" };
const dg: ReleaseSimulado = {
  id: "dg1", descricao: "Aurora Lane — Daybreak  (1979, UK, Vinyl, LP, Selo X)", titulo: "Daybreak", artista: "Aurora Lane",
  data: "1979", generos: [], gravadora: "Selo X", url: "https://www.discogs.com/release/123-Daybreak", faixas: [
    { titulo: "Afterglow", artista: "Aurora Lane", posicao: "A1" },
    { titulo: "Sunrise", artista: "Aurora Lane", posicao: "A2" },
    { titulo: "Dusk", artista: "Aurora Lane", posicao: "B1" },
    { titulo: "Bonus", artista: "Aurora Lane", posicao: "C1" },
  ],
};
const dgSo: ReleaseSimulado = { ...dg, id: "dg2", descricao: "Só no Discogs", titulo: "Raridade", artista: "Banda Rara" };

const faixa = (n: string, valores: FaixaBusca["valores"] = {}): FaixaBusca => ({ id: n, nome: `${n}.mp3`, valores });
const tres = [
  faixa("a", { title: "Afterglow", artist: "Aurora Lane", album: "Daybreak" }),
  faixa("b", { title: "Sunrise", artist: "Aurora Lane", album: "Daybreak" }),
  faixa("c", { title: "Dusk", artist: "Aurora Lane", album: "Daybreak" }),
];
const capa: Capa = { dados: new Uint8Array([1, 2, 3]), mime: "image/jpeg" };

function abrir(opcoes: OpcoesPonteBusca = {}, extra: Partial<PropsBusca> = {}) {
  const ponte = criarPonteSimulada({ musicbrainz: [mb], discogs: [dg], capas: { mb1: capa }, ...opcoes });
  const aoAplicar = vi.fn();
  const aoCancelar = vi.fn();
  const aoAbrirSobre = vi.fn();
  const usuario = userEvent.setup();
  const props: PropsBusca = {
    faixas: tres, ponte, estados: { discogs: { disponivel: true } }, aoAplicar, aoCancelar, aoAbrirSobre, ...extra,
  };
  const r = render(<DialogoBuscaOnline {...props} />);
  return { usuario, ponte, aoAplicar, aoCancelar, aoAbrirSobre, props, rerender: (novo: Partial<PropsBusca>) => r.rerender(<DialogoBuscaOnline {...props} {...novo} />) };
}

const botao = (n: string | RegExp) => screen.getByRole("button", { name: n });
const previa = () => within(screen.getByRole("table", { name: "Prévia" })).getAllByRole("row").slice(1).map((l) => within(l).getAllByRole("cell").map((c) => c.textContent));
const espaco = (s: string) => s.replace(/\s+/g, " ");
const opcao = (descricao: string) => screen.getByRole("option", { name: espaco(descricao) });
/** Solta as respostas da ponte manual (espera existir alguma: nada depende de tempo real). */
async function soltar(ponte: { pendentes: number; liberar(): void }) {
  await waitFor(() => expect(ponte.pendentes).toBeGreaterThan(0));
  ponte.liberar();
}
const estado = () => screen.getByRole("status");

async function buscarPrimeiro(u: ReturnType<typeof userEvent.setup>) {
  await u.click(botao("Buscar"));
  await waitFor(() => expect(botao("Aplicar ao rascunho")).toBeEnabled());
}

describe("abertura (G-01)", () => {
  it("foco no campo Artista, campos preenchidos pela seleção e Esc cancela sem clicar", async () => {
    const { usuario, aoCancelar } = abrir();
    expect(screen.getByLabelText("Artista")).toHaveFocus();
    expect(screen.getByLabelText("Artista")).toHaveValue("Aurora Lane");
    expect(screen.getByLabelText("Álbum")).toHaveValue("Daybreak");
    expect(screen.getByLabelText("Título")).toHaveValue("");           // várias faixas: sem título
    expect(estado()).toHaveTextContent("Banco de dados aberto, com capas do Cover Art Archive.");
    expect(screen.getByTestId("texto-previa")).toHaveTextContent("Prévia: escolha um resultado.");
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(1);
  });

  it("com uma faixa só, o título entra no campo; artista do álbum tem prioridade", () => {
    abrir({}, { faixas: [faixa("a", { title: "Afterglow", artist: "Solo", albumartist: "Banda" })] });
    expect(screen.getByLabelText("Título")).toHaveValue("Afterglow");
    expect(screen.getByLabelText("Artista")).toHaveValue("Banda");
  });
});

describe("busca no MusicBrainz e prévia (G-01, G-02, G-07)", () => {
  it("lista o resultado, baixa os dados e mostra a prévia antes/depois", async () => {
    const { usuario, ponte } = abrir({ manual: true });
    await usuario.click(botao("Buscar"));
    expect(estado()).toHaveTextContent("Buscando no MusicBrainz...");
    expect(botao("Buscar")).toBeDisabled();
    await soltar(ponte);
    expect(await screen.findByRole("option", { name: espaco(mb.descricao) })).toHaveAttribute("aria-selected", "true");
    await waitFor(() => expect(estado()).toHaveTextContent("Baixando dados do álbum..."));
    expect(screen.getByTestId("texto-previa")).toHaveTextContent("Carregando a prévia...");
    expect(botao("Aplicar ao rascunho")).toBeDisabled();
    await soltar(ponte);
    await waitFor(() => expect(botao("Aplicar ao rascunho")).toBeEnabled());
    expect(estado()).toHaveTextContent("Confira a prévia e clique em Aplicar ao rascunho. Nada é gravado até você salvar.");
    expect(screen.getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Arquivo", "Campo", "Antes", "Depois"]);
    const linhas = previa();
    expect(linhas).toContainEqual(["a.mp3", "Ano", "", "2020-05-01"]);
    expect(linhas).toContainEqual(["a.mp3", "Faixa", "", "1/3"]);
    expect(screen.getByTestId("texto-previa")).toHaveTextContent(/^Prévia: 3 arquivo\(s\), \d+ alteração\(ões\)\.$/);
  });

  it("Enter em qualquer campo busca", async () => {
    const { usuario } = abrir();
    await usuario.click(screen.getByLabelText("Álbum"));
    await usuario.keyboard("{Enter}");
    expect(await screen.findByRole("option")).toBeInTheDocument();
  });

  it("nada encontrado e erro de rede mostram a mensagem", async () => {
    const { usuario } = abrir({ musicbrainz: [], discogs: [] });
    await usuario.click(screen.getByLabelText("Álbum"));
    await usuario.keyboard("{Enter}");
    await waitFor(() => expect(estado()).toHaveTextContent("Nada encontrado."));
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("erro de rede na busca mostra a mensagem legível", async () => {
    const { usuario } = abrir({ erroBuscar: { musicbrainz: "Sem conexão com o MusicBrainz." } });
    await usuario.click(botao("Buscar"));
    await waitFor(() => expect(estado()).toHaveTextContent("Sem conexão com o MusicBrainz."));
    expect(botao("Buscar")).toBeEnabled();
  });

  it("erro ao baixar o release: 'Prévia indisponível.' e Aplicar desligado, sem repetir a consulta", async () => {
    const { usuario, ponte } = abrir({ erroDetalhar: "O MusicBrainz não respondeu." });
    await usuario.click(botao("Buscar"));
    await waitFor(() => expect(screen.getByTestId("texto-previa")).toHaveTextContent("Prévia indisponível."));
    expect(estado()).toHaveTextContent("O MusicBrainz não respondeu.");
    expect(botao("Aplicar ao rascunho")).toBeDisabled();
    await new Promise((r) => setTimeout(r, 50));
    expect(ponte.chamadas.filter((c) => c.operacao === "detalhar")).toHaveLength(1);
  });

  it("faixas sem par e nenhuma faixa que casa", async () => {
    const { usuario } = abrir({}, { faixas: [...tres, faixa("d", { title: "Estranha" })] });
    await buscarPrimeiro(usuario);
    expect(screen.getByTestId("texto-previa")).toHaveTextContent("1 faixa(s) sem par não mudam: d.mp3");
  });

  it("nenhuma casa: aviso próprio e Aplicar desligado", async () => {
    const { usuario } = abrir({}, { faixas: [faixa("z", { title: "Nada a ver", artist: "Aurora Lane", album: "Daybreak" })] });
    await usuario.click(botao("Buscar"));
    await waitFor(() => expect(screen.getByTestId("texto-previa")).toHaveTextContent("Nenhuma das faixas casa com esse álbum"));
    expect(botao("Aplicar ao rascunho")).toBeDisabled();
  });

  it("faixas que já têm tudo: 'Nada a alterar' e não aplica sem capa", async () => {
    const completo = { title: "Afterglow", artist: "Aurora Lane", album: "Daybreak", albumartist: "Aurora Lane", date: "2020-05-01", genre: "Pop", tracknumber: "1/3" };
    const { usuario, aoAplicar } = abrir({ capas: {} }, { faixas: [faixa("a", completo)] });
    await buscarPrimeiro(usuario);
    expect(screen.getByTestId("texto-previa")).toHaveTextContent("Nada a alterar nas tags: as faixas já têm esses dados.");
    await usuario.click(botao("Aplicar ao rascunho"));
    await waitFor(() => expect(estado()).toHaveTextContent("Nada a alterar: as faixas já têm esses dados."));
    expect(aoAplicar).not.toHaveBeenCalled();
  });
});

describe("aplicar ao rascunho e capa (G-06, G-07)", () => {
  it("entrega alterações, faixas casadas e a capa do Cover Art Archive", async () => {
    const { usuario, aoAplicar } = abrir();
    await buscarPrimeiro(usuario);
    expect(screen.getByLabelText("Baixar a capa")).toBeChecked();
    await usuario.click(botao("Aplicar ao rascunho"));
    await waitFor(() => expect(aoAplicar).toHaveBeenCalledTimes(1));
    const r = aoAplicar.mock.calls[0][0];
    expect(r.capa).toEqual(capa);
    expect(r.casadas).toEqual(["a", "b", "c"]);
    expect(r.semPar).toEqual([]);
    expect(r.alteracoes).toHaveLength(3);
    expect(r.alteracoes[0].mudancas).toMatchObject({ date: "2020-05-01", tracknumber: "1/3" });
  });

  it("'Baixar a capa' desligado não pede a capa", async () => {
    const { usuario, aoAplicar, ponte } = abrir();
    await buscarPrimeiro(usuario);
    await usuario.click(screen.getByLabelText("Baixar a capa"));
    await usuario.click(botao("Aplicar ao rascunho"));
    await waitFor(() => expect(aoAplicar).toHaveBeenCalled());
    expect(aoAplicar.mock.calls[0][0].capa).toBeNull();
    expect(ponte.chamadas.some((c) => c.operacao === "capa")).toBe(false);
  });

  it("erro na capa não cancela as tags", async () => {
    const { usuario, aoAplicar } = abrir({ erroCapa: "Cover Art Archive fora do ar." });
    await buscarPrimeiro(usuario);
    await usuario.click(botao("Aplicar ao rascunho"));
    await waitFor(() => expect(aoAplicar).toHaveBeenCalled());
    expect(aoAplicar.mock.calls[0][0].capa).toBeNull();
    expect(aoAplicar.mock.calls[0][0].alteracoes.length).toBeGreaterThan(0);
  });

  it("release sem capa e sem alterações: nada a aplicar", async () => {
    const completo = { title: "Afterglow", artist: "Aurora Lane", album: "Daybreak", albumartist: "Aurora Lane", date: "2020-05-01", genre: "Pop", tracknumber: "1/3" };
    const { usuario, aoAplicar } = abrir({ capas: { mb1: null } }, { faixas: [faixa("a", completo)] });
    await buscarPrimeiro(usuario);
    await usuario.click(botao("Aplicar ao rascunho"));
    await waitFor(() => expect(estado()).toHaveTextContent("Nada a alterar: as faixas já têm esses dados."));
    expect(aoAplicar).not.toHaveBeenCalled();
  });

  it("duplo clique no resultado aplica", async () => {
    const { usuario, aoAplicar } = abrir();
    await buscarPrimeiro(usuario);
    await usuario.dblClick(screen.getByRole("option"));
    await waitFor(() => expect(aoAplicar).toHaveBeenCalledTimes(1));
  });

  it("a capa só existe para o MusicBrainz", async () => {
    const { usuario } = abrir();
    expect(screen.getByLabelText("Baixar a capa")).toBeInTheDocument();
    await usuario.click(screen.getByRole("radio", { name: "Discogs" }));
    expect(screen.queryByLabelText("Baixar a capa")).not.toBeInTheDocument();
  });
});

describe("só aplica o resultado do estado atual (G-08)", () => {
  it("escolher outro release desliga o Aplicar até a prévia dele chegar e entrega os dados dele", async () => {
    const { usuario, aoAplicar, ponte } = abrir({ musicbrainz: [mb, mb2], manual: true, capas: {} });
    await usuario.click(botao("Buscar"));
    await soltar(ponte);                                       // a busca
    await screen.findByRole("option", { name: espaco(mb2.descricao) });
    await soltar(ponte);                                       // a prévia do 1º
    await waitFor(() => expect(botao("Aplicar ao rascunho")).toBeEnabled());
    await usuario.click(opcao(mb2.descricao));
    await waitFor(() => expect(estado()).toHaveTextContent("Baixando dados do álbum..."));
    expect(botao("Aplicar ao rascunho")).toBeDisabled();       // a prévia do 2º ainda não chegou
    await soltar(ponte);
    await waitFor(() => expect(botao("Aplicar ao rascunho")).toBeEnabled());
    await usuario.click(botao("Aplicar ao rascunho"));
    await soltar(ponte);                                       // a capa (sem capa neste release)
    await waitFor(() => expect(aoAplicar).toHaveBeenCalled());
    expect(aoAplicar.mock.calls[0][0].alteracoes[0].mudancas.album).toBe("Daybreak Deluxe");
  });

  it("as setas escolhem o resultado seguinte e o anterior", async () => {
    const { usuario } = abrir({ musicbrainz: [mb, mb2] });
    await buscarPrimeiro(usuario);
    screen.getByRole("listbox", { name: "Resultados" }).focus();
    await usuario.keyboard("{ArrowDown}");
    expect(opcao(mb2.descricao)).toHaveAttribute("aria-selected", "true");
    await usuario.keyboard("{ArrowUp}");
    expect(opcao(mb.descricao)).toHaveAttribute("aria-selected", "true");
  });

  it("trocar de fonte limpa a lista e a prévia e mostra a descrição da fonte", async () => {
    const { usuario } = abrir();
    await buscarPrimeiro(usuario);
    await usuario.click(screen.getByRole("radio", { name: "Discogs" }));
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
    expect(previa()).toEqual([]);
    expect(screen.getByTestId("texto-previa")).toHaveTextContent("Prévia: escolha um resultado.");
    expect(estado()).toHaveTextContent("Bom para prensagens privadas, vinis e edições raras.");
  });
});

describe("cancelar sem esperar a rede (G-08)", () => {
  it("Cancelar fecha na hora mesmo com a busca pendurada", async () => {
    const { usuario, aoCancelar, aoAplicar } = abrir({ pendurar: true });
    await usuario.click(botao("Buscar"));
    expect(estado()).toHaveTextContent("Buscando no MusicBrainz...");
    await usuario.click(botao("Cancelar"));
    expect(aoCancelar).toHaveBeenCalledTimes(1);
    expect(aoAplicar).not.toHaveBeenCalled();
  });

  it("Esc também cancela durante a consulta, e a resposta tardia é ignorada sem erro", async () => {
    const erros = vi.spyOn(console, "error").mockImplementation(() => {});
    const { usuario, aoCancelar, ponte } = abrir({ manual: true });
    await usuario.click(botao("Buscar"));
    await waitFor(() => expect(ponte.pendentes).toBeGreaterThan(0));
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(1);
    ponte.liberar();                                           // a resposta tardia chega com o diálogo já fechado
    await new Promise((r) => setTimeout(r, 0));
    expect(erros).not.toHaveBeenCalled();
    erros.mockRestore();
  });
});

describe("Discogs (G-03, G-09, G-12)", () => {
  it("sem credencial o Discogs fica desligado com a dica, e a alternativa também", () => {
    abrir({}, { estados: { discogs: { disponivel: false } } });
    const radio = screen.getByRole("radio", { name: "Discogs" });
    expect(radio).toBeDisabled();
    expect(radio.closest("label")).toHaveAttribute("title", DICA_SEM_DISCOGS);
    expect(screen.getByLabelText("Se o MusicBrainz não achar, buscar no Discogs")).toBeDisabled();
    expect(screen.getByLabelText("Se o MusicBrainz não achar, buscar no Discogs")).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "MusicBrainz" })).toBeEnabled();
  });

  it("usa a dica vinda do estado, quando há", () => {
    abrir({}, { estados: { discogs: { disponivel: false, dica: "Token recusado." } } });
    expect(screen.getByRole("radio", { name: "Discogs" }).closest("label")).toHaveAttribute("title", "Token recusado.");
  });

  it("atribuição do Discogs antes de escolher: texto e link 'discogs.com' para o site, sem o aviso (que fica no Sobre)", async () => {
    const { usuario } = abrir();
    expect(screen.getByTestId("atribuicao")).toHaveTextContent("Dados do MusicBrainz · capas do Cover Art Archive.");
    await usuario.click(screen.getByRole("radio", { name: "Discogs" }));
    const atrib = screen.getByTestId("atribuicao");
    expect(atrib).toHaveTextContent("Data provided by Discogs.");
    expect(atrib).not.toHaveTextContent("not affiliated");
    const link = within(atrib).getByRole("link", { name: "discogs.com" });
    expect(link).toHaveAttribute("href", "https://www.discogs.com/");
  });

  it("vinil: A1/B1/C1 viram faixa e disco, com a gravadora e o link do release", async () => {
    const base = { artist: "Aurora Lane", album: "Daybreak" };
    const quatro = [faixa("a", { ...base, title: "Afterglow" }), faixa("c", { ...base, title: "Dusk" }), faixa("d", { ...base, title: "Bonus" })];
    const { usuario } = abrir({}, { faixas: quatro });
    await usuario.click(screen.getByRole("radio", { name: "Discogs" }));
    await buscarPrimeiro(usuario);
    expect(screen.queryByLabelText("Baixar a capa")).not.toBeInTheDocument();
    const linhas = previa();
    expect(linhas).toContainEqual(["a.mp3", "Faixa", "", "1/3"]);
    expect(linhas).toContainEqual(["c.mp3", "Faixa", "", "3/3"]);
    expect(linhas).toContainEqual(["d.mp3", "Faixa", "", "1/1"]);
    expect(linhas).toContainEqual(["d.mp3", "Disco", "", "2/2"]);
    expect(linhas).toContainEqual(["a.mp3", "Gravadora", "", "Selo X"]);
    const link = within(screen.getByTestId("atribuicao")).getByRole("link", { name: "Ver o release no Discogs" });
    expect(link).toHaveAttribute("href", "https://www.discogs.com/release/123-Daybreak");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noopener"));
  });

  it("link do release fora do Discogs vira só texto", async () => {
    const { usuario } = abrir({ discogs: [{ ...dg, url: "https://evil.example/discogs.com" }] });
    await usuario.click(screen.getByRole("radio", { name: "Discogs" }));
    await buscarPrimeiro(usuario);
    expect(within(screen.getByTestId("atribuicao")).queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByTestId("atribuicao")).toHaveTextContent("Data provided by Discogs.");
  });

  it("alternativa: MusicBrainz sem resultado usa o Discogs e avisa", async () => {
    const { usuario } = abrir({ musicbrainz: [], discogs: [dgSo] }, { faixas: [faixa("a", { title: "Afterglow", artist: "Banda Rara", album: "Raridade" })] });
    expect(screen.getByLabelText("Se o MusicBrainz não achar, buscar no Discogs")).toBeChecked();
    await usuario.click(botao("Buscar"));
    await waitFor(() => expect(estado()).toHaveTextContent("O MusicBrainz não achou nada; resultados do Discogs. 1 resultado(s)."));
    expect(opcao(dgSo.descricao)).toBeInTheDocument();
    await waitFor(() => expect(botao("Aplicar ao rascunho")).toBeEnabled());
    expect(estado()).toHaveTextContent("O MusicBrainz não achou nada; resultados do Discogs. Confira a prévia");
    expect(screen.queryByLabelText("Baixar a capa")).not.toBeInTheDocument();     // quem trouxe foi o Discogs
  });

  it("alternativa desligada: fica a mensagem 'Nada encontrado.'", async () => {
    const { usuario, ponte } = abrir({ musicbrainz: [], discogs: [dgSo] }, { faixas: [faixa("a", { artist: "Banda Rara", album: "Raridade" })] });
    await usuario.click(screen.getByLabelText("Se o MusicBrainz não achar, buscar no Discogs"));
    await usuario.click(botao("Buscar"));
    await waitFor(() => expect(estado()).toHaveTextContent("Nada encontrado."));
    expect(ponte.chamadas.filter((c) => c.operacao === "buscar" && c.fonte === "discogs")).toHaveLength(0);
  });

  it("credenciais do Discogs removidas com a janela aberta: descarta os resultados dele", async () => {
    const { usuario, rerender } = abrir();
    await usuario.click(screen.getByRole("radio", { name: "Discogs" }));
    await buscarPrimeiro(usuario);
    rerender({ estados: { discogs: { disponivel: false } } });
    await waitFor(() => expect(estado()).toHaveTextContent("As credenciais do Discogs mudaram: busque de novo."));
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "MusicBrainz" })).toBeChecked();
    expect(botao("Aplicar ao rascunho")).toBeDisabled();
  });
});

describe("Sobre", () => {
  it("o link Sobre chama o callback", async () => {
    const { usuario, aoAbrirSobre } = abrir();
    await usuario.click(botao("Sobre"));
    expect(aoAbrirSobre).toHaveBeenCalledTimes(1);
  });
});
