//! Validação dos valores dos campos: porte de `metadata.validar_valor` / `validar_alteracoes` da v2.
//! É a fonte de verdade das regras e mensagens (o `app/src/validacao.ts` espelha esta).

use std::collections::BTreeMap;

use crate::metadados::{Campo, VARIOS};

/// Ano corrente pelo relógio do sistema (UTC).
pub fn ano_atual() -> i64 {
    let segundos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0);
    // dias -> ano civil (algoritmo de Howard Hinnant)
    let z = segundos.div_euclid(86_400) + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let mes = if mp < 10 { mp + 3 } else { mp - 9 };
    yoe + era * 400 + i64::from(mes <= 2)
}

fn so_digitos(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit())
}

/// Ok(valor normalizado) ou Err(mensagem). Valor vazio é sempre válido: significa remover.
pub fn validar_valor(campo: Campo, valor: &str) -> Result<String, String> {
    validar_valor_no_ano(campo, valor, ano_atual())
}

/// Como [`validar_valor`], com o ano corrente dado (para testes e para a interface).
pub fn validar_valor_no_ano(campo: Campo, valor: &str, atual: i64) -> Result<String, String> {
    let valor = valor.trim();
    if valor.is_empty() || valor == VARIOS.trim() || valor == VARIOS {
        return Ok(if valor.is_empty() { String::new() } else { VARIOS.to_string() });
    }
    match campo {
        Campo::Data => {
            if valor.eq_ignore_ascii_case("atual") {
                return Ok(atual.to_string());
            }
            let partes: Vec<&str> = valor.split('-').collect();
            let formato_ok = partes.len() <= 3
                && partes[0].len() == 4
                && partes.iter().all(|p| so_digitos(p))
                && partes[1..].iter().all(|p| p.len() == 2);
            if !formato_ok {
                return Err("Ano inválido. Use AAAA (ex.: 2024) ou AAAA-MM-DD.".into());
            }
            let ano: i64 = partes[0].parse().unwrap_or(0);
            if !(1000..=atual).contains(&ano) {
                return Err(format!("O ano deve estar entre 1000 e {atual}."));
            }
            Ok(valor.to_string())
        }
        Campo::Faixa | Campo::Disco => {
            let partes: Vec<&str> = valor.split('/').collect();
            let ok = partes.len() <= 2
                && partes.iter().all(|p| so_digitos(p))
                && partes.iter().all(|p| p.parse::<u64>().map(|n| n > 0).unwrap_or(true));
            if !ok {
                return Err("Número inválido. Use números maiores que 0 (ex.: '3' ou '3/12').".into());
            }
            Ok(valor.to_string())
        }
        Campo::Genero if so_digitos(valor) => Err("Digite o nome do gênero por extenso (ex.: 'Rock').".into()),
        _ => Ok(valor.to_string()),
    }
}

/// Valida campo -> valor. Devolve (normalizados, erros), como a v2.
pub fn validar_alteracoes(alteracoes: &[(Campo, &str)]) -> (BTreeMap<Campo, String>, BTreeMap<Campo, String>) {
    let mut normalizado = BTreeMap::new();
    let mut erros = BTreeMap::new();
    for (campo, valor) in alteracoes {
        match validar_valor(*campo, valor) {
            Ok(v) => {
                normalizado.insert(*campo, v);
            }
            Err(m) => {
                erros.insert(*campo, m);
            }
        }
    }
    (normalizado, erros)
}
