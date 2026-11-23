//! Padrões de nome de arquivo <-> tags. Porte de `tagger/nucleo/padroes.py`, sem interface.
//!
//! Um padrão mistura texto fixo com campos, em qualquer uma das duas formas:
//!     {tracknumber:02} - {artist} - {title}       %artist% - %title%
//! - `{campo:02}` completa números com zeros à esquerda ("3/12" -> "03");
//! - apelidos aceitos: track, disc, year (iguais a tracknumber, discnumber, date);
//! - só para ler tags do nome: `{*}` (ou `%*%`) ignora um trecho, e "/" separa pastas.
//!
//! Renomear usa os campos de `metadados::Campo` e: limpa caracteres que o Windows não aceita;
//! detecta conflitos (dois arquivos com o mesmo nome novo, ou nome já existente); renomeia em duas
//! etapas (via nome temporário), então trocas como A->B e B->A funcionam.

use std::collections::{BTreeMap, HashMap, HashSet};
use std::io;
use std::path::{Path, PathBuf};
use std::sync::LazyLock;
use std::sync::atomic::{AtomicU64, Ordering};

use regex::Regex;

use crate::metadados::{Campo, Tags};

/// Caracteres, sem a extensão (o caminho inteiro tem limite no Windows).
pub const TAMANHO_MAX_NOME: usize = 180;

static RE_CAMPO: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\{(\w+|\*)(?::(\d+))?\}|%(\w+|\*)(?::(\d+))?%").expect("regex válida"));
static RE_ESPACOS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\s+").expect("regex válida"));
static RE_SEPARADORES_REPETIDOS: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"(\s*-\s*){2,}").expect("regex válida"));

/// Uma parte do padrão: texto fixo ou campo (`None` = `{*}`, ignorar) com largura opcional.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Parte {
    Texto(String),
    Campo { campo: Option<Campo>, largura: Option<usize> },
}

fn campo_do_nome(nome: &str) -> Option<Campo> {
    let nome = nome.to_lowercase();
    let nome = match nome.as_str() {
        "track" => "tracknumber",
        "disc" => "discnumber",
        "year" => "date",
        outro => outro,
    };
    Campo::de_chave(nome)
}

fn numerico(campo: Campo) -> bool {
    matches!(campo, Campo::Faixa | Campo::Disco)
}

/// Quebra o padrão em partes. Err com mensagem amigável se houver campo desconhecido.
pub fn analisar(padrao: &str) -> Result<Vec<Parte>, String> {
    let mut partes = Vec::new();
    let mut inicio = 0;
    for achado in RE_CAMPO.captures_iter(padrao) {
        let todo = achado.get(0).expect("grupo 0");
        if todo.start() > inicio {
            partes.push(Parte::Texto(padrao[inicio..todo.start()].to_string()));
        }
        let nome = achado.get(1).or(achado.get(3)).map(|m| m.as_str()).unwrap_or("");
        let largura = achado.get(2).or(achado.get(4)).and_then(|m| m.as_str().parse().ok());
        let campo = if nome == "*" {
            None
        } else {
            Some(campo_do_nome(nome).ok_or_else(|| format!("Campo desconhecido: {}", todo.as_str()))?)
        };
        partes.push(Parte::Campo { campo, largura });
        inicio = todo.end();
    }
    if inicio < padrao.len() {
        partes.push(Parte::Texto(padrao[inicio..].to_string()));
    }
    Ok(partes)
}

/// Campos usados no padrão, na ordem e sem repetir (sem o `{*}`).
pub fn campos_do_padrao(padrao: &str) -> Result<Vec<Campo>, String> {
    let mut vistos = Vec::new();
    for parte in analisar(padrao)? {
        if let Parte::Campo { campo: Some(c), .. } = parte
            && !vistos.contains(&c) {
                vistos.push(c);
            }
    }
    Ok(vistos)
}

// ---------------------------------------------------------------- tags -> nome de arquivo
/// Tira o que o Windows não aceita num nome de arquivo (e espaços sobrando).
pub fn sanitizar(texto: &str) -> String {
    let mut saida = String::with_capacity(texto.len());
    for c in texto.chars() {
        match c {
            '/' | '\\' | '|' => saida.push('-'),
            ':' => saida.push_str(" -"),
            '"' => saida.push('\''),
            '*' | '?' | '<' | '>' => {}
            c if (c as u32) < 0x20 || c as u32 == 0x7f => saida.push(' '),
            c => saida.push(c),
        }
    }
    RE_ESPACOS.replace_all(&saida, " ").trim().to_string()
}

fn valor_formatado(campo: Campo, valor: &str, largura: Option<usize>) -> String {
    let mut valor = valor.trim().to_string();
    if numerico(campo) {
        valor = valor.split('/').next().unwrap_or("").trim().to_string();
        if let Some(l) = largura
            && !valor.is_empty() && valor.chars().all(|c| c.is_ascii_digit()) && valor.len() < l {
                valor = format!("{}{valor}", "0".repeat(l - valor.len()));
            }
    }
    sanitizar(&valor)
}

fn reservado(nome: &str) -> bool {
    let n = nome.to_uppercase();
    matches!(n.as_str(), "CON" | "PRN" | "AUX" | "NUL")
        || ((n.starts_with("COM") || n.starts_with("LPT"))
            && n.len() == 4
            && matches!(n.as_bytes()[3], b'1'..=b'9'))
}

/// Nome novo (sem extensão) para um arquivo com essas tags. "" se ficar vazio.
/// Campos vazios somem e os separadores sobrando são limpos ("Artista -  - Título" vira "Artista - Título").
pub fn nome_pelas_tags(padrao: &str, valores: &Tags) -> Result<String, String> {
    if padrao.contains('/') || padrao.contains('\\') {
        return Err("O padrão de nome não pode ter / ou \\ (organizar em pastas fica para a v2.1).".into());
    }
    let mut texto = String::new();
    for parte in analisar(padrao)? {
        match parte {
            Parte::Texto(t) => texto.push_str(&t),
            Parte::Campo { campo: Some(c), largura } => {
                texto.push_str(&valor_formatado(c, valores.get(&c).map(String::as_str).unwrap_or(""), largura))
            }
            Parte::Campo { campo: None, .. } => {}
        }
    }
    let texto = sanitizar(&texto);
    let texto = RE_SEPARADORES_REPETIDOS.replace_all(&texto, " - ");
    let aparar = |s: &str| s.trim_matches(|c| matches!(c, ' ' | '-' | '_' | '.')).to_string();
    let mut texto = aparar(&texto);
    if texto.chars().count() > TAMANHO_MAX_NOME {
        let cortado: String = texto.chars().take(TAMANHO_MAX_NOME).collect();
        texto = cortado.trim_end_matches([' ', '-', '_', '.']).to_string();
    }
    if reservado(&texto) {
        texto.push('_');
    }
    Ok(texto)
}

/// Um arquivo do plano: destino `None` = o nome não muda.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ItemRenomear {
    pub origem: PathBuf,
    pub destino: Option<PathBuf>,
    pub erro: String,
}

impl ItemRenomear {
    pub fn valido(&self) -> bool {
        self.destino.is_some() && self.erro.is_empty()
    }
}

/// Para comparar caminhos como o sistema compara (no Windows, sem diferenciar maiúsculas).
pub fn chave(caminho: &Path) -> String {
    let absoluto = std::path::absolute(caminho).unwrap_or_else(|_| caminho.to_path_buf());
    let texto = absoluto.to_string_lossy().into_owned();
    if cfg!(windows) { texto.replace('/', "\\").to_lowercase() } else { texto }
}

/// itens: [(caminho, tags)]. Devolve um ItemRenomear por item, na mesma ordem. Nada é renomeado aqui.
pub fn planejar_renomeacao(itens: &[(PathBuf, Tags)], padrao: &str) -> Result<Vec<ItemRenomear>, String> {
    let mut plano = Vec::new();
    for (caminho, valores) in itens {
        let stem = nome_pelas_tags(padrao, valores)?;
        if stem.is_empty() {
            plano.push(ItemRenomear {
                origem: caminho.clone(),
                destino: None,
                erro: "O nome ficaria vazio (tags em branco?)".into(),
            });
            continue;
        }
        let extensao = caminho.extension().map(|e| format!(".{}", e.to_string_lossy().to_lowercase())).unwrap_or_default();
        let destino = caminho.with_file_name(format!("{stem}{extensao}"));
        let muda = destino.file_name() != caminho.file_name();
        plano.push(ItemRenomear { origem: caminho.clone(), destino: muda.then_some(destino), erro: String::new() });
    }

    let origens: HashSet<String> = plano.iter().map(|i| chave(&i.origem)).collect();
    let mut contagem: HashMap<String, usize> = HashMap::new();
    for item in &plano {
        *contagem.entry(chave(item.destino.as_ref().unwrap_or(&item.origem))).or_insert(0) += 1;
    }
    for item in &mut plano {
        let Some(destino) = &item.destino else { continue };
        if !item.erro.is_empty() {
            continue;
        }
        let k = chave(destino);
        if contagem[&k] > 1 {
            item.erro = "Outro arquivo ficaria com o mesmo nome".into();
        } else if k != chave(&item.origem) && !origens.contains(&k) && destino.exists() {
            item.erro = "Já existe um arquivo com esse nome na pasta".into();
        }
    }
    Ok(plano)
}

/// `std::fs::rename` com poucas novas tentativas se o Windows negar por instantes (antivírus, indexador).
fn renomear_com_tentativas(
    renomear: &mut impl FnMut(&Path, &Path) -> io::Result<()>,
    origem: &Path,
    destino: &Path,
) -> io::Result<()> {
    let tentativas = 3;
    for tentativa in 0..tentativas {
        match renomear(origem, destino) {
            Err(e) if e.kind() == io::ErrorKind::PermissionDenied && tentativa < tentativas - 1 => {
                std::thread::sleep(std::time::Duration::from_millis(50));
            }
            outro => return outro,
        }
    }
    unreachable!("o laço sempre retorna")
}

fn nome_temporario() -> String {
    static CONTADOR: AtomicU64 = AtomicU64::new(0);
    let agora = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).map(|d| d.as_nanos()).unwrap_or(0);
    format!(".{:x}{:x}{:x}.tagger-tmp", agora, std::process::id(), CONTADOR.fetch_add(1, Ordering::SeqCst))
}

/// Renomeia os itens válidos. Devolve (feitos [(origem, destino)], falhas {origem: erro}).
/// Etapa 1: cada arquivo vai para um nome temporário. Etapa 2: do temporário para o nome final.
/// Nunca sobrescreve um arquivo existente; se a etapa 2 falhar, o arquivo volta ao nome original.
pub fn executar_renomeacao(plano: &[ItemRenomear]) -> (Vec<(PathBuf, PathBuf)>, BTreeMap<PathBuf, String>) {
    executar_renomeacao_com(plano, |a, b| std::fs::rename(a, b))
}

/// Como [`executar_renomeacao`], com a função de renomear dada (os testes simulam o Windows negando).
pub fn executar_renomeacao_com(
    plano: &[ItemRenomear],
    mut renomear: impl FnMut(&Path, &Path) -> io::Result<()>,
) -> (Vec<(PathBuf, PathBuf)>, BTreeMap<PathBuf, String>) {
    let mut feitos = Vec::new();
    let mut falhas = BTreeMap::new();
    let mut temporarios = Vec::new();
    for item in plano.iter().filter(|i| i.valido()) {
        let temporario = item.origem.with_file_name(nome_temporario());
        match renomear_com_tentativas(&mut renomear, &item.origem, &temporario) {
            Ok(()) => temporarios.push((item, temporario)),
            Err(e) => {
                falhas.insert(item.origem.clone(), e.to_string());
            }
        }
    }
    for (item, temporario) in temporarios {
        let destino = item.destino.as_ref().expect("item válido");
        let resultado = if destino.exists() {
            Err(io::Error::new(io::ErrorKind::AlreadyExists, "Já existe um arquivo com esse nome na pasta"))
        } else {
            renomear_com_tentativas(&mut renomear, &temporario, destino)
        };
        match resultado {
            Ok(()) => feitos.push((item.origem.clone(), destino.clone())),
            Err(e) => {
                let mut mensagem = e.to_string();
                if renomear_com_tentativas(&mut renomear, &temporario, &item.origem).is_err() {
                    mensagem += &format!(" (o arquivo ficou como {})", temporario.file_name().unwrap_or_default().to_string_lossy());
                }
                falhas.insert(item.origem.clone(), mensagem);
            }
        }
    }
    (feitos, falhas)
}

// ---------------------------------------------------------------- nome de arquivo -> tags
fn regex_do_padrao(padrao: &str) -> Result<(Regex, Vec<Campo>), String> {
    let padrao = padrao.replace('\\', "/");
    let mut expressao = String::new();
    let mut grupos = Vec::new();
    for parte in analisar(&padrao)? {
        match parte {
            Parte::Texto(t) => expressao.push_str(&regex::escape(&t)),
            Parte::Campo { campo: None, .. } => expressao.push_str(r"[^/]*?"),
            Parte::Campo { campo: Some(c), .. } => {
                expressao.push_str(&format!("(?P<g{}>[^/]+?)", grupos.len()));
                grupos.push(c);
            }
        }
    }
    let regex = Regex::new(&format!("(?i)^{expressao}$")).map_err(|e| e.to_string())?;
    Ok((regex, grupos))
}

/// Lê tags do nome do arquivo (sem extensão) seguindo o padrão. None se o nome não segue o padrão.
/// Com "/" no padrão, usa também as pastas acima do arquivo.
pub fn tags_pelo_nome(padrao: &str, caminho: &Path, sublinhado_vira_espaco: bool) -> Result<Option<Tags>, String> {
    let (regex, grupos) = regex_do_padrao(padrao)?;
    let niveis = padrao.replace('\\', "/").matches('/').count();
    let stem = caminho.file_stem().map(|s| s.to_string_lossy().into_owned()).unwrap_or_default();
    let pastas: Vec<String> = caminho
        .parent()
        .map(|p| p.components().map(|c| c.as_os_str().to_string_lossy().into_owned()).collect())
        .unwrap_or_default();
    if pastas.len() < niveis {
        return Ok(None);
    }
    let mut partes: Vec<String> = pastas[pastas.len() - niveis..].to_vec();
    partes.push(stem);
    let mut texto = partes.join("/");
    if sublinhado_vira_espaco {
        texto = texto.replace('_', " ");
    }
    let Some(achado) = regex.captures(&texto) else { return Ok(None) };
    let mut resultado = Tags::new();
    for (i, campo) in grupos.iter().enumerate() {
        let bruto = achado.name(&format!("g{i}")).map(|m| m.as_str()).unwrap_or("");
        let mut valor = RE_ESPACOS.replace_all(bruto, " ").trim().to_string();
        let so_numeros = |s: &str| !s.is_empty() && s.chars().all(|c| c.is_ascii_digit());
        let partes: Vec<&str> = valor.split('/').collect();
        if numerico(*campo) && partes.len() <= 2 && partes.iter().all(|p| so_numeros(p)) {
            // "03" -> "3"
            valor = partes
                .iter()
                .map(|n| {
                    let sem_zeros = n.trim_start_matches('0');
                    if sem_zeros.is_empty() { "0" } else { sem_zeros }
                })
                .collect::<Vec<_>>()
                .join("/");
        }
        resultado.entry(*campo).or_insert(valor);
    }
    Ok(Some(resultado))
}
