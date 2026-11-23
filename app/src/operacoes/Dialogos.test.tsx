import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Faixa } from "../api";
import { DialogoLimpeza } from "./DialogoLimpeza";
import { DialogoOrganizar } from "./DialogoOrganizar";
import { lembrarPadrao } from "./DialogoPadrao";
import { DialogoRenomear } from "./DialogoRenomear";
import { DialogoTagsDoNome } from "./DialogoTagsDoNome";
import { criarPonteSimulada, type OpcoesPonteSimulada } from "./ponteOperacoes";
import { ResumoOrganizar } from "./ResumoOrganizar";
import { itemValido, type AnaliseExtras } from "./tipos";

function faixa(caminho: string, tags: Faixa["tags"] = {}, pendentes: Faixa["pendentes"] = {}): Faixa {
  return { id: caminho, caminho, tags, pendentes, duracao: 200, bitrate: 320, temCapa: false };
}

const faixas = [
  faixa("D:\\m\\a.mp3", { tracknumber: "1", artist: "Aurora Lane", album: "Daybreak", albumartist: "Aurora Lane", title: "Afterglow" }),
  faixa("D:\\m\\b.mp3", { tracknumber: "2", artist: "Aurora Lane", album: "Daybreak", albumartist: "Aurora Lane", title: "Sunrise" }),
  faixa("D:\\m\\c.mp3", { tracknumber: "3", artist: "Aurora Lane", album: "Daybreak", albumartist: "Aurora Lane", title: "Dusk" }),
];

const ROTULO_PADRAO = "Padrão";
const linhasDaPrevia = () => within(screen.getByRole("table", { name: "Prévia" })).getAllByRole("row").slice(1);
const botao = (nome: string | RegExp) => screen.getByRole("button", { name: nome });

describe("lembrarPadrao (F-07)", () => {
  it("põe o padrão no topo, sem repetir, até 8", () => {
    expect(lembrarPadrao(["a", "b", "c"], "b")).toEqual(["b", "a", "c"]);
    const muitos = Array.from({ length: 12 }, (_, i) => `p${i}`);
    const r = lembrarPadrao(muitos, "novo");
    expect(r).toHaveLength(8);
    expect(r[0]).toBe("novo");
  });
});

describe("DialogoRenomear (F-01 a F-03)", () => {
  function abrir(extra: Partial<Parameters<typeof DialogoRenomear>[0]> = {}, opcoes?: OpcoesPonteSimulada) {
    const aoConfirmar = vi.fn();
    const aoCancelar = vi.fn();
    const usuario = userEvent.setup();
    render(
      <DialogoRenomear faixas={faixas} padrao="{tracknumber:02} - {title}" recentes={["{artist} - {title}"]}
        ponte={criarPonteSimulada(opcoes)} aoConfirmar={aoConfirmar} aoCancelar={aoCancelar} {...extra} />,
    );
    return { usuario, aoConfirmar, aoCancelar };
  }

  it("mostra a prévia 'Nome atual → Novo nome' com o resumo e o botão com a contagem", async () => {
    abrir();
    expect(screen.getByRole("dialog", { name: "Renomear arquivos pelas tags" })).toBeInTheDocument();
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    expect(screen.getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Nome atual", "Novo nome"]);
    expect(within(linhasDaPrevia()[0]).getAllByRole("cell").map((c) => c.textContent)).toEqual(["a.mp3", "01 - Afterglow.mp3"]);
    expect(screen.getByText("3 serão renomeados")).toBeInTheDocument();
    expect(botao("Renomear 3 arquivos")).toBeEnabled();
  });

  it("usa os valores pendentes e avisa quando há pendências", async () => {
    abrir({ faixas: [faixa("D:\\m\\a.mp3", { title: "Velho", tracknumber: "1" }, { title: "Novo" })], temPendentes: true });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(1));
    expect(within(linhasDaPrevia()[0]).getAllByRole("cell")[1]).toHaveTextContent("01 - Novo.mp3");
    expect(screen.getByText(/inclusive alterações ainda não salvas/)).toBeInTheDocument();
    expect(botao("Renomear 1 arquivo")).toBeEnabled();
  });

  it("atualiza a prévia ao editar o padrão (com ~150 ms de espera)", async () => {
    const { usuario } = abrir();
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    const campo = screen.getByLabelText(ROTULO_PADRAO);
    await usuario.clear(campo);
    await usuario.type(campo, "{{title}");
    await waitFor(() => expect(within(linhasDaPrevia()[1]).getAllByRole("cell")[1]).toHaveTextContent("Sunrise.mp3"));
  });

  it("padrão inválido mostra o erro e desliga o botão; vazio pede um padrão", async () => {
    const { usuario } = abrir();
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    const campo = screen.getByLabelText(ROTULO_PADRAO);
    await usuario.clear(campo);
    await usuario.type(campo, "{{foo}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Campo desconhecido: {foo}");
    expect(botao("Renomear")).toBeDisabled();
    await usuario.clear(campo);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Digite um padrão."));
  });

  it("linhas sem mudança, com conflito e com nome vazio", async () => {
    abrir({
      faixas: [
        faixa("D:\\m\\01 - A.mp3", { tracknumber: "1", title: "A" }),
        faixa("D:\\m\\b.mp3", { title: "B", tracknumber: "2" }),
        faixa("D:\\m\\c.mp3", { title: "B", tracknumber: "2" }),
        faixa("D:\\m\\d.mp3"),
      ],
    });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(4));
    const textos = linhasDaPrevia().map((l) => within(l).getAllByRole("cell")[1].textContent);
    expect(textos).toEqual(["(sem mudança)", "Outro arquivo ficaria com o mesmo nome", "Outro arquivo ficaria com o mesmo nome",
      "O nome ficaria vazio (tags em branco?)"]);
    expect(screen.getByText("0 serão renomeados · 1 já estão com esse nome · 3 com problema (não serão renomeados)")).toBeInTheDocument();
    expect(botao("Renomear")).toBeDisabled();
  });

  it("'Inserir campo' põe o token no cursor", async () => {
    const { usuario } = abrir({ padrao: "{title}" });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    const campo = screen.getByLabelText(ROTULO_PADRAO) as HTMLInputElement;
    campo.setSelectionRange(0, 0);
    await usuario.click(botao("Inserir campo"));
    expect(screen.getAllByRole("menuitem")).toHaveLength(13);
    await usuario.click(screen.getByRole("menuitem", { name: /Gravadora/ }));
    expect(campo.value).toBe("{gravadora}{title}");
  });

  it("lista de padrões recentes (▾): inteira mesmo com o campo preenchido, até 8, o atual no topo", async () => {
    const { usuario } = abrir({ recentes: Array.from({ length: 10 }, (_, i) => `{title} ${i}`) });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    const campo = screen.getByLabelText(ROTULO_PADRAO) as HTMLInputElement;
    expect(campo.value).toBe("{tracknumber:02} - {title}");
    await usuario.click(botao("Padrões recentes"));
    const opcoes = screen.getAllByRole("option");
    expect(opcoes).toHaveLength(8);
    expect(opcoes[0]).toHaveTextContent("{tracknumber:02} - {title}");
    await usuario.click(screen.getByRole("option", { name: "{title} 3" }));
    expect(campo.value).toBe("{title} 3");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await waitFor(() => expect(within(linhasDaPrevia()[0]).getAllByRole("cell")[1]).toHaveTextContent("Afterglow 3.mp3"));
  });

  it("escolher um recente refaz a prévia com esse padrão", async () => {
    const { usuario } = abrir({ recentes: ["{artist} - {title}"] });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    await usuario.click(botao("Padrões recentes"));
    await usuario.click(screen.getByRole("option", { name: "{artist} - {title}" }));
    await waitFor(() => expect(within(linhasDaPrevia()[0]).getAllByRole("cell")[1]).toHaveTextContent("Aurora Lane - Afterglow.mp3"));
  });

  it("OK fica desligado enquanto o texto difere do que foi calculado e entrega o padrão do cálculo", async () => {
    const { usuario, aoConfirmar } = abrir();
    await waitFor(() => expect(botao("Renomear 3 arquivos")).toBeEnabled());
    const campo = screen.getByLabelText(ROTULO_PADRAO);
    await usuario.clear(campo);
    await usuario.type(campo, "{{title}");
    expect(botao(/^Renomear/)).toBeDisabled();             // ainda com a prévia velha na tela
    await waitFor(() => expect(botao("Renomear 3 arquivos")).toBeEnabled());
    await usuario.click(botao("Renomear 3 arquivos"));
    expect(aoConfirmar.mock.calls[0][0]).toBe("{title}");
    expect(aoConfirmar.mock.calls[0][1][0].destino).toBe("D:\\m\\Afterglow.mp3");
  });

  it("prévia limitada a 500 linhas, mas o resultado vale para todas", async () => {
    const muitas = Array.from({ length: 600 }, (_, i) => faixa(`D:\\m\\${i}.mp3`, { title: `T${i}`, tracknumber: String((i % 99) + 1) }));
    const { usuario, aoConfirmar } = abrir({ faixas: muitas, padrao: "{title}" });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(500));
    expect(screen.getByText(/600 serão renomeados · prévia das primeiras 500/)).toBeInTheDocument();
    await usuario.click(botao("Renomear 600 arquivos"));
    expect(aoConfirmar.mock.calls[0][1]).toHaveLength(600);
  });

  it("OK entrega o padrão e o plano; Cancelar e Esc cancelam", async () => {
    const { usuario, aoConfirmar, aoCancelar } = abrir();
    await waitFor(() => expect(botao("Renomear 3 arquivos")).toBeEnabled());
    await usuario.click(botao("Renomear 3 arquivos"));
    const [padrao, plano] = aoConfirmar.mock.calls[0];
    expect(padrao).toBe("{tracknumber:02} - {title}");
    expect(plano.filter(itemValido)).toHaveLength(3);
    await usuario.click(botao("Cancelar"));
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(2);
  });
});

describe("DialogoTagsDoNome (F-05, F-06)", () => {
  const arquivos = [
    faixa("D:\\m\\Aurora Lane - Afterglow.mp3", { artist: "Velho" }),
    faixa("D:\\m\\Aurora_Lane - Sunrise.mp3"),
    faixa("D:\\m\\sem-separador.mp3"),
  ];

  function abrir(extra: Partial<Parameters<typeof DialogoTagsDoNome>[0]> = {}) {
    const aoConfirmar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoTagsDoNome faixas={arquivos} padrao="%artist% - %title%" recentes={[]} ponte={criarPonteSimulada()}
      aoConfirmar={aoConfirmar} aoCancelar={vi.fn()} {...extra} />);
    return { usuario, aoConfirmar };
  }

  it("lê as tags do nome; o que não segue o padrão fica esmaecido", async () => {
    abrir();
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    expect(screen.getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Arquivo", "Artista", "Título"]);
    expect(within(linhasDaPrevia()[0]).getAllByRole("cell").map((c) => c.textContent)).toEqual(["Aurora Lane - Afterglow.mp3", "Aurora Lane", "Afterglow"]);
    expect(within(linhasDaPrevia()[2]).getAllByRole("cell")[1]).toHaveTextContent("não segue o padrão");
    expect(screen.getByText("2 arquivos com tags lidas · 1 não seguem o padrão")).toBeInTheDocument();
    expect(botao("Preencher 2 arquivos")).toBeEnabled();
  });

  it("'Trocar _ por espaço' refaz a prévia", async () => {
    const { usuario } = abrir();
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    expect(within(linhasDaPrevia()[1]).getAllByRole("cell")[1]).toHaveTextContent("Aurora_Lane");
    await usuario.click(screen.getByLabelText("Trocar _ por espaço"));
    await waitFor(() => expect(within(linhasDaPrevia()[1]).getAllByRole("cell")[1]).toHaveTextContent("Aurora Lane"));
  });

  it("'Preencher só os campos que estão vazios' mantém o que já tem valor", async () => {
    const { usuario, aoConfirmar } = abrir();
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    await usuario.click(screen.getByLabelText("Preencher só os campos que estão vazios"));
    await waitFor(() => expect(within(linhasDaPrevia()[0]).getAllByRole("cell")[1]).toHaveTextContent("Velho"));
    expect(within(linhasDaPrevia()[0]).getAllByRole("cell")[1]).toHaveAttribute("title", "Já tem valor: mantido");
    await usuario.click(botao(/^Preencher/));
    const itens = aoConfirmar.mock.calls[0][1].itens;
    expect(itens[0]).toEqual({ id: "D:\\m\\Aurora Lane - Afterglow.mp3", valores: { title: "Afterglow" } });
  });

  it("valor inválido é marcado e ignorado", async () => {
    abrir({ faixas: [faixa("D:\\m\\Aurora - abcd.mp3")], padrao: "%artist% - %year%" });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(1));
    const celulaAno = within(linhasDaPrevia()[0]).getAllByRole("cell")[2];
    expect(celulaAno).toHaveAttribute("title", expect.stringContaining("Ano inválido"));
    expect(screen.getByText(/1 valores inválidos ignorados/)).toBeInTheDocument();
  });

  it("exige pelo menos um campo e oferece 'Ignorar trecho %*%'", async () => {
    const { usuario } = abrir({ padrao: "fixo" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Use pelo menos um campo, ex.: %artist% - %title%");
    await usuario.click(botao("Inserir campo"));
    expect(screen.getByRole("menuitem", { name: /Ignorar trecho/ })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /Título/ })).toHaveTextContent("%title%");
  });
});

describe("DialogoOrganizar (F-08 a F-10)", () => {
  const padrao = "{albumartist}/{album}/{tracknumber:02} - {title}";

  function abrir(opcoesPonte: OpcoesPonteSimulada = {}, extra: Partial<Parameters<typeof DialogoOrganizar>[0]> = {}) {
    const aoConfirmar = vi.fn();
    const ponte = criarPonteSimulada(opcoesPonte);
    const usuario = userEvent.setup();
    render(<DialogoOrganizar faixas={faixas} padrao={padrao} recentes={[]} pastaDestino={"D:\\Música"} ponte={ponte}
      aoConfirmar={aoConfirmar} aoCancelar={vi.fn()} {...extra} />);
    return { usuario, aoConfirmar, ponte };
  }

  it("prévia 'Arquivo atual → Novo local' relativa ao destino", async () => {
    abrir();
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    expect(screen.getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Arquivo atual", "Novo local"]);
    expect(within(linhasDaPrevia()[0]).getAllByRole("cell")[1]).toHaveTextContent("Aurora Lane\\Daybreak\\01 - Afterglow.mp3");
    expect(screen.getByText("3 serão movidos")).toBeInTheDocument();
    expect(botao("Organizar 3 arquivos")).toBeEnabled();
  });

  it("opções: capa junto ligada, pastas vazias desligada; destino vazio pede a pasta", async () => {
    const { usuario } = abrir();
    expect(screen.getByLabelText(/Levar a capa da pasta junto/)).toBeChecked();
    expect(screen.getByLabelText("Remover as pastas que ficarem vazias")).not.toBeChecked();
    const destino = screen.getByLabelText("Pasta de destino");
    expect(destino).toHaveValue("D:\\Música");
    await usuario.clear(destino);
    expect(await screen.findByRole("alert")).toHaveTextContent("Escolha a pasta de destino.");
    expect(botao("Organizar")).toBeDisabled();
  });

  it("'Escolher…' usa o seletor de pasta; cancelar o seletor não muda nada", async () => {
    const { usuario } = abrir({ pastaEscolhida: "E:\\Nova" });
    await usuario.click(botao("Escolher…"));
    await waitFor(() => expect(screen.getByLabelText("Pasta de destino")).toHaveValue("E:\\Nova"));
    await waitFor(() => expect(within(linhasDaPrevia()[0]).getAllByRole("cell")[1]).toHaveAttribute("title", expect.stringContaining("E:\\Nova")));
  });

  it("seletor cancelado mantém a pasta", async () => {
    const { usuario } = abrir({ pastaEscolhida: null });
    await usuario.click(botao("Escolher…"));
    expect(screen.getByLabelText("Pasta de destino")).toHaveValue("D:\\Música");
  });

  it("a capa da pasta vai junto só quando a opção está ligada (e conta no resumo)", async () => {
    const { usuario } = abrir({ conteudoDasPastas: { "D:\\m": ["a.mp3", "b.mp3", "c.mp3", "cover.jpg"] } });
    await waitFor(() => expect(screen.getByText("3 serão movidos · 1 capa(s) vão junto")).toBeInTheDocument());
    await usuario.click(screen.getByLabelText(/Levar a capa da pasta junto/));
    await waitFor(() => expect(screen.getByText("3 serão movidos")).toBeInTheDocument());
  });

  it("já no lugar e conflito aparecem na prévia", async () => {
    abrir({}, {
      faixas: [
        faixa("D:\\Música\\Aurora Lane\\Daybreak\\01 - Afterglow.mp3", faixas[0].tags),
        faixa("D:\\x\\1.mp3", faixas[1].tags),
        faixa("D:\\x\\2.mp3", faixas[1].tags),
      ],
    });
    await waitFor(() => expect(linhasDaPrevia()).toHaveLength(3));
    expect(screen.getByText("0 serão movidos · 1 já estão no lugar · 2 com problema (não serão movidos)")).toBeInTheDocument();
  });

  it("OK entrega o plano, o destino e a opção de remover pastas vazias", async () => {
    const { usuario, aoConfirmar } = abrir();
    await waitFor(() => expect(botao("Organizar 3 arquivos")).toBeEnabled());
    await usuario.click(screen.getByLabelText("Remover as pastas que ficarem vazias"));
    await usuario.click(botao("Organizar 3 arquivos"));
    const r = aoConfirmar.mock.calls[0][0];
    expect(r).toMatchObject({ padrao, pastaDestino: "D:\\Música", removerVazias: true });
    expect(r.plano.itens).toHaveLength(3);
  });
});

describe("ResumoOrganizar (F-13)", () => {
  const feitos: Array<[string, string]> = [
    ["D:\\x\\b.mp3", "D:\\d\\Z\\b.mp3"],
    ["D:\\x\\a.mp3", "D:\\d\\A\\a.mp3"],
  ];

  it("lista era → agora está em, ordenado pelo destino, e abre a pasta", async () => {
    const ponte = criarPonteSimulada();
    const aoFechar = vi.fn();
    const usuario = userEvent.setup();
    render(<ResumoOrganizar feitos={feitos} falhas={{}} pasta={"D:\\d"} ponte={ponte} aoFechar={aoFechar} />);
    expect(screen.getByText("2 arquivo(s) movido(s) para D:\\d")).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["Era", "Agora está em"]);
    const linhas = within(screen.getByRole("table", { name: "Resumo" })).getAllByRole("row").slice(1);
    expect(linhas.map((l) => within(l).getAllByRole("cell").map((c) => c.textContent))).toEqual([
      ["D:\\x\\a.mp3", "A\\a.mp3"], ["D:\\x\\b.mp3", "Z\\b.mp3"],
    ]);
    await usuario.click(botao("Abrir pasta"));
    expect(ponte.pastasAbertas).toEqual(["D:\\d"]);
    await usuario.click(botao("Fechar"));
    expect(aoFechar).toHaveBeenCalled();
  });

  it("com falhas, mostra quantas não foram movidas e o motivo", () => {
    render(<ResumoOrganizar feitos={feitos} falhas={{ "D:\\d\\c.mp3": "em uso" }} pasta={"D:\\d"} ponte={criarPonteSimulada()} aoFechar={vi.fn()} />);
    expect(screen.getByText(/2 arquivo\(s\) movido\(s\) para D:\\d · 1 não foram movidos e continuam onde estavam:/)).toBeInTheDocument();
    expect(screen.getByText("Não movido: em uso")).toBeInTheDocument();
  });

  it("nada movido: título próprio e coluna 'Motivo'", () => {
    render(<ResumoOrganizar feitos={[]} falhas={{ "D:\\d\\c.mp3": "em uso" }} pasta={"D:\\d"} ponte={criarPonteSimulada()} aoFechar={vi.fn()} />);
    expect(screen.getByText("Nenhum arquivo foi movido. 1 não foram movidos e continuam onde estavam:")).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader")[1]).toHaveTextContent("Motivo");
  });
});

describe("DialogoLimpeza (F-14 a F-16)", () => {
  const vazia: AnaliseExtras = { id3v1: false, desconhecidos: false, extras: {} };
  const analises: AnaliseExtras[] = [
    { id3v1: true, desconhecidos: false, extras: { PRIV: 2, TXXX: 5 } },
    { id3v1: true, desconhecidos: true, extras: { TXXX: 1 } },
    vazia,
  ];

  function abrir(lista = analises) {
    const aoConfirmar = vi.fn();
    const aoCancelar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoLimpeza analises={lista} aoConfirmar={aoConfirmar} aoCancelar={aoCancelar} />);
    return { usuario, aoConfirmar, aoCancelar };
  }

  it("mostra as 3 opções com as contagens e o aviso de que não dá para desfazer", () => {
    abrir();
    expect(screen.getByText("3 arquivo(s) selecionado(s). A limpeza é gravada na hora e não pode ser desfeita.")).toBeInTheDocument();
    expect(screen.getByLabelText("Remover a tag ID3v1 antiga (só MP3) — 2 de 3 arquivo(s)")).toBeChecked();
    expect(screen.getByLabelText(/Remover frames ID3 não reconhecidos .* — 1 arquivo\(s\)/)).toBeChecked();
    expect(screen.getByLabelText("Remover tudo o que o Tagger não mostra — 2 arquivo(s)")).not.toBeChecked();
  });

  it("lista os extras do mais frequente para o menos, com nomes legíveis", () => {
    abrir();
    const itens = within(screen.getByRole("list", { name: "Extras encontrados" })).getAllByRole("listitem").map((l) => l.textContent);
    expect(itens).toEqual([
      "•  TXXX ×6  —  campos personalizados (inclui ReplayGain, MusicBrainz IDs...)",
      "•  PRIV ×2  —  dados privados de programas (Windows Media, Amazon...)",
    ]);
  });

  it("opção sem nada para limpar fica desligada; sem nenhuma, o botão Limpar também", () => {
    abrir([vazia, vazia]);
    expect(screen.getByLabelText(/Remover a tag ID3v1/)).toBeDisabled();
    expect(screen.getByLabelText(/Remover frames ID3/)).toBeDisabled();
    expect(screen.getByLabelText(/Remover tudo o que o Tagger não mostra/)).toBeDisabled();
    expect(screen.getByText("Nenhuma tag extra encontrada.")).toBeInTheDocument();
    expect(botao("Limpar")).toBeDisabled();
  });

  it("Limpar entrega as 3 opções escolhidas; Cancelar fecha", async () => {
    const { usuario, aoConfirmar, aoCancelar } = abrir();
    await usuario.click(screen.getByLabelText(/Remover tudo o que o Tagger não mostra/));
    await usuario.click(screen.getByLabelText(/Remover frames ID3/));
    await usuario.click(botao("Limpar"));
    expect(aoConfirmar).toHaveBeenCalledWith({ id3v1: true, desconhecidos: false, extras: true });
    await usuario.click(botao("Cancelar"));
    expect(aoCancelar).toHaveBeenCalled();
  });

  it("desmarcar tudo desliga o Limpar", async () => {
    const { usuario } = abrir([{ id3v1: true, desconhecidos: false, extras: {} }]);
    expect(botao("Limpar")).toBeEnabled();
    await usuario.click(screen.getByLabelText(/Remover a tag ID3v1/));
    expect(botao("Limpar")).toBeDisabled();
  });
});

describe("foco inicial e Esc (os 4 diálogos)", () => {
  it("Renomear abre com o foco no campo do padrão; Esc cancela sem clicar", async () => {
    const aoCancelar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoRenomear faixas={faixas} padrao="{title}" recentes={[]} ponte={criarPonteSimulada()} aoConfirmar={vi.fn()} aoCancelar={aoCancelar} />);
    expect(screen.getByLabelText(ROTULO_PADRAO)).toHaveFocus();
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(1);
  });

  it("Tags pelo nome e Organizar também abrem com o foco no padrão", async () => {
    const aoCancelar = vi.fn();
    const usuario = userEvent.setup();
    const { unmount } = render(<DialogoTagsDoNome faixas={faixas} padrao="%title%" recentes={[]} ponte={criarPonteSimulada()} aoConfirmar={vi.fn()} aoCancelar={aoCancelar} />);
    expect(screen.getByLabelText(ROTULO_PADRAO)).toHaveFocus();
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(1);
    unmount();
    render(<DialogoOrganizar faixas={faixas} padrao="{title}" recentes={[]} pastaDestino={"D:\d"} ponte={criarPonteSimulada()} aoConfirmar={vi.fn()} aoCancelar={aoCancelar} />);
    expect(screen.getByLabelText(ROTULO_PADRAO)).toHaveFocus();
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(2);
  });

  it("Limpeza abre com o foco no primeiro controle; Esc cancela", async () => {
    const aoCancelar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoLimpeza analises={[{ id3v1: true, desconhecidos: false, extras: { PRIV: 1 } }]} aoConfirmar={vi.fn()} aoCancelar={aoCancelar} />);
    expect(screen.getByLabelText(/Remover a tag ID3v1/)).toHaveFocus();
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(1);
  });

  it("Resumo: foco em Fechar; Esc fecha", async () => {
    const aoFechar = vi.fn();
    const usuario = userEvent.setup();
    render(<ResumoOrganizar feitos={[]} falhas={{}} pasta={"D:\d"} ponte={criarPonteSimulada()} aoFechar={aoFechar} />);
    expect(botao("Fechar")).toHaveFocus();
    await usuario.keyboard("{Escape}");
    expect(aoFechar).toHaveBeenCalledTimes(1);
  });

  it("Esc com o menu 'Inserir campo' aberto fecha só o menu; o seguinte cancela", async () => {
    const aoCancelar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoRenomear faixas={faixas} padrao="{title}" recentes={[]} ponte={criarPonteSimulada()} aoConfirmar={vi.fn()} aoCancelar={aoCancelar} />);
    await usuario.click(botao("Inserir campo"));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(aoCancelar).not.toHaveBeenCalled();
    await usuario.keyboard("{Escape}");
    expect(aoCancelar).toHaveBeenCalledTimes(1);
  });

  it("Esc com a lista de recentes aberta fecha só a lista", async () => {
    const aoCancelar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoRenomear faixas={faixas} padrao="{title}" recentes={["{artist}"]} ponte={criarPonteSimulada()} aoConfirmar={vi.fn()} aoCancelar={aoCancelar} />);
    await usuario.click(botao("Padrões recentes"));
    await usuario.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(aoCancelar).not.toHaveBeenCalled();
  });
});

describe("Organizar: OK entrega o que está na tela e a ordem das validações da v2", () => {
  const padrao = "{albumartist}/{album}/{tracknumber:02} - {title}";
  const abrir = (extra: Partial<Parameters<typeof DialogoOrganizar>[0]> = {}) => {
    const aoConfirmar = vi.fn();
    const usuario = userEvent.setup();
    render(<DialogoOrganizar faixas={faixas} padrao={padrao} recentes={[]} pastaDestino={"D:\Música"} ponte={criarPonteSimulada()}
      aoConfirmar={aoConfirmar} aoCancelar={vi.fn()} {...extra} />);
    return { usuario, aoConfirmar };
  };

  it("destino alterado: o OK espera a nova prévia e entrega o destino e o padrão do plano", async () => {
    const { usuario, aoConfirmar } = abrir();
    await waitFor(() => expect(botao("Organizar 3 arquivos")).toBeEnabled());
    const destino = screen.getByLabelText("Pasta de destino");
    await usuario.clear(destino);
    await usuario.type(destino, "E:\Novo");
    expect(botao(/^Organizar/)).toBeDisabled();
    await waitFor(() => expect(botao("Organizar 3 arquivos")).toBeEnabled());
    await usuario.click(botao("Organizar 3 arquivos"));
    const r = aoConfirmar.mock.calls[0][0];
    expect(r.pastaDestino).toBe("E:\Novo");
    expect(r.plano.pasta).toBe("E:\Novo");
    expect(r.padrao).toBe(padrao);
  });

  it("padrão vazio -> 'Digite um padrão.', mesmo sem destino", async () => {
    const { usuario } = abrir({ pastaDestino: "" });
    const campo = screen.getByLabelText(ROTULO_PADRAO);
    await usuario.clear(campo);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Digite um padrão."));
  });

  it("destino vazio + campo desconhecido mostra o erro do campo", async () => {
    abrir({ pastaDestino: "", padrao: "{foo}" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Campo desconhecido: {foo}");
  });

  it("destino vazio + padrão sem campo pede um campo; só depois pede o destino", async () => {
    const { usuario } = abrir({ pastaDestino: "", padrao: "fixo" });
    expect(await screen.findByRole("alert")).toHaveTextContent("Use pelo menos um campo, ex.: {artist}/{album}/{title}");
    const campo = screen.getByLabelText(ROTULO_PADRAO);
    await usuario.clear(campo);
    await usuario.type(campo, "{{title}");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Escolha a pasta de destino."));
    expect(botao("Organizar")).toBeDisabled();
  });
});
