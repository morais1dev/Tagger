//! Comandos chamados pela interface (React). Toda a regra fica em `nucleo`; aqui só se traduz.

use std::path::{Path, PathBuf};

use base64::Engine;
use nucleo::{Campo, Opcoes};
use serde::Serialize;

/// As tags como a interface usa: a capa vira data URL.
#[derive(Serialize)]
struct TagsTela {
    formato: String,
    titulo: String,
    artista: String,
    faixa: String,
    gravadora: String,
    capa: Option<String>,
}

fn texto(e: impl std::fmt::Display) -> String {
    e.to_string()
}

#[tauri::command]
fn gerar_amostras() -> Result<Vec<String>, String> {
    let pasta: PathBuf = std::env::temp_dir().join("tagger-spike-amostras");
    std::fs::create_dir_all(&pasta).map_err(texto)?;
    let mut caminhos = Vec::new();
    for (fmt, criar) in [
        ("mp3", nucleo::amostras::mp3 as fn(&Path) -> std::io::Result<()>),
        ("flac", nucleo::amostras::flac),
        ("m4a", nucleo::amostras::m4a),
    ] {
        let caminho = pasta.join(format!("amostra.{fmt}"));
        criar(&caminho).map_err(texto)?;
        caminhos.push(caminho.to_string_lossy().into_owned());
    }
    Ok(caminhos)
}

#[tauri::command]
fn ler(caminho: String) -> Result<TagsTela, String> {
    let t = nucleo::ler(Path::new(&caminho)).map_err(texto)?;
    let capa = t.capa.map(|c| {
        let mime = if c.mime.is_empty() { "image/jpeg".to_string() } else { c.mime };
        format!("data:{mime};base64,{}", base64::engine::general_purpose::STANDARD.encode(c.dados))
    });
    Ok(TagsTela { formato: t.formato, titulo: t.titulo, artista: t.artista, faixa: t.faixa, gravadora: t.gravadora, capa })
}

#[tauri::command]
fn gravar(caminho: String, campo: String, valor: String) -> Result<(), String> {
    let campo = Campo::de_nome(&campo).ok_or_else(|| format!("campo desconhecido: {campo}"))?;
    // MP3 em ID3v2.4 no app (decisão do spike; veja docs/spike/tauri.md)
    nucleo::gravar(Path::new(&caminho), campo, &valor, Opcoes::default()).map_err(texto)
}

/// PNG 1x1 vermelho, gerado aqui mesmo (sem imagem protegida).
const PNG_TESTE: &[u8] = &[
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49,
    0x44, 0x41, 0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00, 0x03, 0x01, 0x01, 0x00, 0x18, 0xDD, 0x8D, 0xB0,
    0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
];

#[tauri::command]
fn capa_de_teste(caminho: String) -> Result<(), String> {
    nucleo::definir_capa(Path::new(&caminho), PNG_TESTE, "image/png", Opcoes::default()).map_err(texto)
}

pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![gerar_amostras, ler, gravar, capa_de_teste])
        .run(tauri::generate_context!())
        .expect("erro ao iniciar o app");
}
