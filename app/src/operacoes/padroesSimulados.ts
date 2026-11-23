// Implementação MÍNIMA de padrões, só para a ponte simulada. A lógica real (expandir e extrair
// padrões, conflitos, Windows) é do núcleo Rust (tagger/nucleo/padroes.py e organizar.py na v2).

import { CAMPOS_TAG, type CampoTag } from "../api";
import type { ItemEntrada, ItemPlano, LinhaTagsDoNome, PlanoOrganizar } from "./tipos";

const APELIDOS: Record<string, CampoTag> = { track: "tracknumber", disc: "discnumber", year: "date" };
const NUMERICOS: ReadonlySet<string> = new Set(["tracknumber", "discnumber"]);
const RESERVADOS = new Set(["CON", "PRN", "AUX", "NUL", ...Array.from({ length: 9 }, (_, i) => `COM${i + 1}`), ...Array.from({ length: 9 }, (_, i) => `LPT${i + 1}`)]);
const TAMANHO_MAX_NOME = 180;
const SEM_ARTISTA = "Unknown Artist";
const SEM_ALBUM = "Unknown Album";
const EXTENSOES_AUDIO = [".mp3", ".flac", ".ogg", ".m4a", ".mp4"];

type Parte = { tipo: "texto"; texto: string } | { tipo: "campo"; campo: CampoTag | "*"; largura: number | null };

// --- caminhos (aceita \ e /) ---
export const partesDoCaminho = (c: string): string[] => c.split(/[\\/]/);
export const nomeDe = (c: string): string => partesDoCaminho(c).pop() ?? c;
const separador = (c: string): string => (c.includes("\\") ? "\\" : "/");
export const pastaDe = (c: string): string => {
  const p = partesDoCaminho(c);
  p.pop();
  return p.join(separador(c));
};
const extensaoDe = (nome: string): string => {
  const i = nome.lastIndexOf(".");
  return i > 0 ? nome.slice(i).toLowerCase() : "";
};
const semExtensao = (nome: string): string => {
  const i = nome.lastIndexOf(".");
  return i > 0 ? nome.slice(0, i) : nome;
};
const juntar = (base: string, ...partes: string[]): string => [base.replace(/[\\/]+$/, ""), ...partes].join(separador(base));
/** Chave para comparar caminhos como o Windows (sem diferenciar maiúsculas nem barras). */
export const chave = (c: string): string => partesDoCaminho(c).join("/").toLowerCase();

// --- padrão ---
const RE_CAMPO = /\{(\w+|\*)(?::(\d+))?\}|%(\w+|\*)(?::(\d+))?%/g;

export function analisar(padrao: string): Parte[] {
  const partes: Parte[] = [];
  let inicio = 0;
  for (const m of padrao.matchAll(RE_CAMPO)) {
    const i = m.index ?? 0;
    if (i > inicio) partes.push({ tipo: "texto", texto: padrao.slice(inicio, i) });
    let nome = (m[1] ?? m[3]).toLowerCase();
    nome = APELIDOS[nome] ?? nome;
    if (nome !== "*" && !(CAMPOS_TAG as readonly string[]).includes(nome)) throw new Error(`Campo desconhecido: ${m[0]}`);
    const largura = m[2] ?? m[4];
    partes.push({ tipo: "campo", campo: nome as CampoTag | "*", largura: largura ? Number(largura) : null });
    inicio = i + m[0].length;
  }
  if (inicio < padrao.length) partes.push({ tipo: "texto", texto: padrao.slice(inicio) });
  return partes;
}

export function camposDoPadrao(padrao: string): CampoTag[] {
  const vistos: CampoTag[] = [];
  for (const p of analisar(padrao)) if (p.tipo === "campo" && p.campo !== "*" && !vistos.includes(p.campo)) vistos.push(p.campo);
  return vistos;
}

const TROCAS: Record<string, string> = { "/": "-", "\\": "-", ":": " -", "|": "-", '"': "'", "*": "", "?": "", "<": "", ">": "" };

export function sanitizar(texto: string): string {
  const trocado = [...texto].map((c) => TROCAS[c] ?? c).join("").replace(/[\x00-\x1f\x7f]/g, " ");
  return trocado.replace(/\s+/g, " ").trim();
}

function valorFormatado(campo: CampoTag, valor: string, largura: number | null): string {
  let v = (valor ?? "").trim();
  if (NUMERICOS.has(campo)) {
    v = v.split("/")[0].trim();
    if (largura && /^\d+$/.test(v)) v = v.padStart(largura, "0");
  }
  return sanitizar(v);
}

/** Nome novo (sem extensão); "" se ficar vazio. */
export function nomePelasTags(padrao: string, valores: Partial<Record<CampoTag, string>>): string {
  if (/[\\/]/.test(padrao)) throw new Error("O padrão de nome não pode ter / ou \\.");
  let texto = "";
  for (const p of analisar(padrao)) {
    if (p.tipo === "texto") texto += p.texto;
    else if (p.campo !== "*") texto += valorFormatado(p.campo, valores[p.campo] ?? "", p.largura);
  }
  texto = sanitizar(texto).replace(/(\s*-\s*){2,}/g, " - ").replace(/^[ \-_.]+|[ \-_.]+$/g, "");
  if (texto.length > TAMANHO_MAX_NOME) texto = texto.slice(0, TAMANHO_MAX_NOME).replace(/[ \-_.]+$/, "");
  if (RESERVADOS.has(texto.toUpperCase())) texto += "_";
  return texto;
}

/** Prévia de renomear. `existentes`: caminhos que "já existem" na pasta (a real consulta o disco). */
export function planejarRenomeacao(itens: ItemEntrada[], padrao: string, existentes: ReadonlySet<string> = new Set()): ItemPlano[] {
  const plano: ItemPlano[] = itens.map(({ caminho, valores }) => {
    const nome = nomePelasTags(padrao, valores);
    if (!nome) return { origem: caminho, destino: null, erro: "O nome ficaria vazio (tags em branco?)" };
    const destino = juntar(pastaDe(caminho), nome + extensaoDe(nomeDe(caminho)));
    return { origem: caminho, destino: nomeDe(destino) === nomeDe(caminho) ? null : destino, erro: "" };
  });
  marcarConflitos(plano, "Outro arquivo ficaria com o mesmo nome", "Já existe um arquivo com esse nome na pasta", existentes);
  return plano;
}

function marcarConflitos(plano: ItemPlano[], msgDuplicado: string, msgExistente: string, existentes: ReadonlySet<string>): void {
  const origens = new Set(plano.map((i) => chave(i.origem)));
  const contagem = new Map<string, number>();
  for (const i of plano) {
    const alvo = chave(i.destino ?? i.origem);
    contagem.set(alvo, (contagem.get(alvo) ?? 0) + 1);
  }
  const existem = new Set([...existentes].map(chave));
  for (const i of plano) {
    if (i.destino === null || i.erro) continue;
    const c = chave(i.destino);
    if ((contagem.get(c) ?? 0) > 1) i.erro = msgDuplicado;
    else if (c !== chave(i.origem) && !origens.has(c) && existem.has(c)) i.erro = msgExistente;
  }
}

// --- nome -> tags ---
function regexDoPadrao(padrao: string): { regex: RegExp; grupos: CampoTag[] } {
  const grupos: CampoTag[] = [];
  let expressao = "";
  for (const p of analisar(padrao.replace(/\\/g, "/"))) {
    if (p.tipo === "texto") expressao += p.texto.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    else if (p.campo === "*") expressao += "[^/]*?";
    else {
      grupos.push(p.campo);
      expressao += "([^/]+?)";
    }
  }
  return { regex: new RegExp(`^${expressao}$`, "i"), grupos };
}

export function tagsPeloNome(padrao: string, caminho: string, sublinhado = false): Partial<Record<CampoTag, string>> | null {
  const niveis = (padrao.replace(/\\/g, "/").match(/\//g) ?? []).length;
  const pastas = partesDoCaminho(caminho).slice(0, -1);
  if (pastas.length < niveis) return null;
  let texto = [...(niveis ? pastas.slice(-niveis) : []), semExtensao(nomeDe(caminho))].join("/");
  if (sublinhado) texto = texto.replace(/_/g, " ");
  const { regex, grupos } = regexDoPadrao(padrao);
  const achado = regex.exec(texto);
  if (!achado) return null;
  const resultado: Partial<Record<CampoTag, string>> = {};
  grupos.forEach((campo, i) => {
    let valor = achado[i + 1].replace(/\s+/g, " ").trim();
    if (NUMERICOS.has(campo) && /^\d+(\/\d+)?$/.test(valor)) valor = valor.split("/").map((n) => String(Number(n))).join("/");
    if (!(campo in resultado)) resultado[campo] = valor;
  });
  return resultado;
}

/** Validação mínima (metadata.validar_valor): só o que a prévia precisa para marcar valores inválidos. */
export function validarValor(campo: CampoTag, valor: string, anoAtual = new Date().getFullYear()): string {
  const v = valor.trim();
  if (!v) return "";
  if (campo === "date") {
    if (v.toLowerCase() === "atual") return "";
    if (!/^\d{4}(-\d{2}(-\d{2})?)?$/.test(v)) return "Ano inválido. Use AAAA (ex.: 2024) ou AAAA-MM-DD.";
    const ano = Number(v.slice(0, 4));
    return ano >= 1000 && ano <= anoAtual ? "" : `O ano deve estar entre 1000 e ${anoAtual}.`;
  }
  if (campo === "tracknumber" || campo === "discnumber")
    return /^\d+(\/\d+)?$/.test(v) && v.split("/").every((p) => Number(p) > 0) ? "" : "Número inválido. Use números maiores que 0 (ex.: '3' ou '3/12').";
  if (campo === "genre" && /^\d+$/.test(v)) return "Digite o nome do gênero por extenso (ex.: 'Rock').";
  return "";
}

export function previaTagsDoNome(
  itens: Array<ItemEntrada & { id: string }>,
  padrao: string,
  { sublinhado, soVazios }: { sublinhado: boolean; soVazios: boolean },
): { campos: CampoTag[]; linhas: LinhaTagsDoNome[] } {
  const campos = camposDoPadrao(padrao);
  if (!campos.length) throw new Error("Use pelo menos um campo, ex.: %artist% - %title%");
  const linhas = itens.map<LinhaTagsDoNome>((it) => {
    const lidos = tagsPeloNome(padrao, it.caminho, sublinhado);
    if (!lidos) return { id: it.id, caminho: it.caminho, casa: false, campos: [] };
    return {
      id: it.id,
      caminho: it.caminho,
      casa: true,
      campos: campos.map((campo) => {
        const atual = it.valores[campo] ?? "";
        const novo = lidos[campo] ?? "";
        if (soVazios && atual) return { campo, novo, atual, mantido: true, erro: "" };
        return { campo, novo, atual, mantido: false, erro: validarValor(campo, novo) };
      }),
    };
  });
  return { campos, linhas };
}

// --- organizar ---
export function partesDoPadraoOrganizar(padrao: string): string[] {
  const trechos = padrao.trim().split(/[\\/]/).map((t) => t.trim()).filter(Boolean);
  if (!trechos.length) throw new Error("Digite um padrão.");
  if (/^[A-Za-z]:/.test(trechos[0])) throw new Error("O padrão é relativo à pasta de destino (sem letra de unidade).");
  for (const t of trechos) {
    analisar(t);
    if (t.replace(/^[. ]+|[. ]+$/g, "") === "") throw new Error("Trecho do padrão inválido: " + t);
  }
  if (!camposDoPadrao(padrao).length) throw new Error("Use pelo menos um campo, ex.: {artist}/{album}/{title}");
  return trechos;
}

export function caminhoRelativo(padrao: string, valores: Partial<Record<CampoTag, string>>, stemOriginal = ""): string[] {
  const trechos = partesDoPadraoOrganizar(padrao);
  const artista = (valores.artist ?? "").trim();
  const v = {
    ...valores,
    artist: artista || SEM_ARTISTA,
    albumartist: (valores.albumartist ?? "").trim() || artista || SEM_ARTISTA,
    album: (valores.album ?? "").trim() || SEM_ALBUM,
  };
  const partes = trechos.slice(0, -1).map((t) => nomePelasTags(t, v) || "Unknown");
  partes.push(nomePelasTags(trechos[trechos.length - 1], v) || stemOriginal);
  return partes;
}

export interface OpcoesSimuladas {
  /** Caminhos que já existem no disco (conflitos "já existe"). */
  existentes?: string[];
  /** Pasta de origem -> nomes de arquivo nela (para decidir se a capa vai junto). */
  conteudoDasPastas?: Record<string, string[]>;
}

/** Prévia de organizar em pastas (organizar.planejar_organizacao), com a capa indo junto só se a pasta inteira vai. */
export function planejarOrganizacao(
  itens: ItemEntrada[], padrao: string, pastaDestino: string, levarCapa: boolean, opcoes: OpcoesSimuladas = {},
): PlanoOrganizar {
  const plano: PlanoOrganizar = { pasta: pastaDestino, itens: [], capas: [] };
  for (const { caminho, valores } of itens) {
    const nome = nomeDe(caminho);
    const partes = caminhoRelativo(padrao, valores, semExtensao(nome));
    const destino = juntar(pastaDestino, ...partes.slice(0, -1), partes[partes.length - 1] + extensaoDe(nome));
    if (chave(destino) === chave(caminho)) plano.itens.push({ origem: caminho, destino: null, erro: "" });
    else if (destino.length > 255) plano.itens.push({ origem: caminho, destino: null, erro: "O caminho novo ficaria longo demais" });
    else plano.itens.push({ origem: caminho, destino, erro: "" });
  }
  marcarConflitos(plano.itens, "Outro arquivo ficaria no mesmo lugar", "Já existe um arquivo com esse nome no destino", new Set(opcoes.existentes ?? []));
  if (levarCapa) plano.capas = planejarCapas(plano.itens, opcoes.conteudoDasPastas ?? {});
  return plano;
}

function planejarCapas(itens: ItemPlano[], conteudo: Record<string, string[]>): ItemPlano[] {
  const porPasta = new Map<string, ItemPlano[]>();
  for (const i of itens) if (i.destino !== null && !i.erro) porPasta.set(pastaDe(i.origem), [...(porPasta.get(pastaDe(i.origem)) ?? []), i]);
  const movem = new Set(itens.filter((i) => i.destino !== null && !i.erro).map((i) => chave(i.origem)));
  const capas: ItemPlano[] = [];
  const alvos = new Set<string>();
  for (const [pasta, grupo] of porPasta) {
    const nomes = conteudo[pasta] ?? [];
    if (new Set(grupo.map((i) => chave(pastaDe(i.destino as string)))).size !== 1) continue;
    const restam = nomes.some((n) => EXTENSOES_AUDIO.includes(extensaoDe(n)) && !movem.has(chave(juntar(pasta, n))));
    if (restam) continue;
    const destino = pastaDe(grupo[0].destino as string);
    for (const n of nomes) {
      if (!["cover", "folder", "front"].includes(semExtensao(n).toLowerCase()) || ![".jpg", ".jpeg", ".png"].includes(extensaoDe(n))) continue;
      const alvo = juntar(destino, n);
      if (chave(alvo) !== chave(juntar(pasta, n)) && !alvos.has(chave(alvo))) {
        alvos.add(chave(alvo));
        capas.push({ origem: juntar(pasta, n), destino: alvo, erro: "" });
      }
    }
  }
  return capas;
}

// --- resumo depois de organizar (organizar.resumo_movimentos / resumo_falhas) ---
export function relativoA(caminho: string, base: string): string {
  const b = partesDoCaminho(base.replace(/[\\/]+$/, ""));
  const c = partesDoCaminho(caminho);
  const dentro = c.length > b.length && b.every((p, i) => p.toLowerCase() === c[i].toLowerCase());
  return dentro ? c.slice(b.length).join(separador(caminho)) : caminho;
}

/** [origem, destino] do que foi movido, relativos à base e ordenados pelo destino. */
export function resumoMovimentos(feitos: Array<[string, string]>, base: string): Array<[string, string]> {
  return feitos
    .map(([o, d]): [string, string] => [relativoA(o, base), relativoA(d, base)])
    .sort((a, b) => a[1].toLowerCase().localeCompare(b[1].toLowerCase()));
}

/** [arquivo, "Não movido: motivo"] do que falhou. */
export function resumoFalhas(falhas: Record<string, string>, base: string): Array<[string, string]> {
  return Object.entries(falhas).map(([o, erro]): [string, string] => [relativoA(o, base), `Não movido: ${erro}`]);
}
