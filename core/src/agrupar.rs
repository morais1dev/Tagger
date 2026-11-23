//! Agrupamento das faixas por álbum: chave do grupo, título do cabeçalho e ordem disco/faixa.
//! Porte de `tagger/nucleo/agrupar.py`; trabalha só com as tags, sem interface.

use crate::metadados::{Campo, Tags};

pub const SEM_ALBUM: &str = "Sem álbum";

/// Número antes da "/" ("3/12" -> 3); sem número, `ausente` (faixa sem número vai para o fim).
fn numero(texto: Option<&String>, ausente: u64) -> u64 {
    let parte = texto.map(String::as_str).unwrap_or("").split('/').next().unwrap_or("").trim();
    if !parte.is_empty() && parte.bytes().all(|b| b.is_ascii_digit()) {
        parte.parse().unwrap_or(ausente)
    } else {
        ausente
    }
}

const SEM_NUMERO: u64 = 1_000_000_000;

fn texto(tags: &Tags, campo: Campo) -> &str {
    tags.get(&campo).map(|s| s.trim()).unwrap_or("")
}

/// Identifica o álbum de uma faixa (sem diferenciar maiúsculas e espaços nas pontas).
/// Sem título de álbum, todas caem no mesmo grupo, que vai para o fim.
pub fn chave_grupo(tags: &Tags) -> (String, String) {
    let album = texto(tags, Campo::Album).to_lowercase();
    if album.is_empty() {
        return (String::new(), String::new());
    }
    (album, texto(tags, Campo::ArtistaAlbum).to_lowercase())
}

/// Ordem dentro da lista agrupada: álbum, artista do álbum, disco e faixa (sem álbum no fim).
pub fn chave_ordem(tags: &Tags) -> (bool, String, String, u64, u64) {
    let (album, artista) = chave_grupo(tags);
    let (disco, faixa) = ordem_faixa(tags);
    (album.is_empty(), album, artista, disco, faixa)
}

/// Só a parte de dentro do grupo: (disco, faixa). Sem disco vale como disco 1.
pub fn ordem_faixa(tags: &Tags) -> (u64, u64) {
    (numero(tags.get(&Campo::Disco), 1), numero(tags.get(&Campo::Faixa), SEM_NUMERO))
}

/// True quando há pelo menos dois grupos diferentes (só então vale agrupar).
pub fn mais_de_um_album<'a>(lista: impl IntoIterator<Item = &'a Tags>) -> bool {
    let mut primeiro = None;
    for tags in lista {
        let chave = chave_grupo(tags);
        match &primeiro {
            None => primeiro = Some(chave),
            Some(p) if *p != chave => return true,
            _ => {}
        }
    }
    false
}

/// "Álbum — Artista do álbum, ano" para as faixas de um grupo (partes ausentes são omitidas).
/// Sem artista do álbum usa o artista da primeira faixa; o ano é o primeiro encontrado.
pub fn titulo_cabecalho(lista: &[Tags]) -> String {
    let Some(primeira) = lista.first() else { return SEM_ALBUM.to_string() };
    let album = texto(primeira, Campo::Album);
    if album.is_empty() {
        return SEM_ALBUM.to_string();
    }
    let mut artista = lista.iter().map(|t| texto(t, Campo::ArtistaAlbum)).find(|a| !a.is_empty()).unwrap_or("");
    if artista.is_empty() {
        artista = texto(primeira, Campo::Artista);
    }
    let ano: String = lista
        .iter()
        .map(|t| texto(t, Campo::Data))
        .find(|d| !d.is_empty())
        .map(|d| d.chars().take(4).collect())
        .unwrap_or_default();
    let mut titulo = if artista.is_empty() { album.to_string() } else { format!("{album} — {artista}") };
    if !ano.is_empty() {
        titulo = format!("{titulo}, {ano}");
    }
    titulo
}
