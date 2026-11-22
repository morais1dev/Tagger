/** Validação dos campos, igual a `metadata.validar_valor` da v2 (mesmas regras e mensagens). */
import { type CampoTag } from "./api";

export type Validacao = { ok: true; valor: string } | { ok: false; mensagem: string };

const RE_DATA = /^\d{4}(-\d{2}(-\d{2})?)?$/;      // 2024, 2024-05, 2024-05-17
const RE_NUMERO = /^\d+(\/\d+)?$/;                // 3 ou 3/12

/** Valor vazio é sempre válido: significa remover a tag. `atual` vira o ano corrente. */
export function validarValor(campo: CampoTag, bruto: string, anoAtual = new Date().getFullYear()): Validacao {
  const valor = bruto.trim();
  if (valor === "") return { ok: true, valor };

  if (campo === "date") {
    if (valor.toLowerCase() === "atual") return { ok: true, valor: String(anoAtual) };
    if (!RE_DATA.test(valor)) return { ok: false, mensagem: "Ano inválido. Use AAAA (ex.: 2024) ou AAAA-MM-DD." };
    const ano = Number(valor.slice(0, 4));
    if (ano < 1000 || ano > anoAtual) return { ok: false, mensagem: `O ano deve estar entre 1000 e ${anoAtual}.` };
    return { ok: true, valor };
  }

  if (campo === "tracknumber" || campo === "discnumber") {
    if (!RE_NUMERO.test(valor) || valor.split("/").some((p) => Number(p) === 0)) {
      return { ok: false, mensagem: "Número inválido. Use números maiores que 0 (ex.: '3' ou '3/12')." };
    }
    return { ok: true, valor };
  }

  if (campo === "genre" && /^\d+$/.test(valor)) {
    return { ok: false, mensagem: "Digite o nome do gênero por extenso (ex.: 'Rock')." };
  }
  return { ok: true, valor };
}
