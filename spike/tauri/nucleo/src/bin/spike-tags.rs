//! Linha de comando do núcleo do spike, usada pelo script de comparação com a v2.
//!   spike-tags ler <arquivo>
//!   spike-tags gravar <arquivo> <titulo|artista|faixa|gravadora> <valor>
//!   spike-tags capa <arquivo> <imagem> <mime>
//!   spike-tags amostra <mp3|flac|m4a> <arquivo>

use std::path::Path;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let resultado = match args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["ler", arq] => nucleo::ler(Path::new(arq)).map(|t| {
            println!("titulo={}\nartista={}\nfaixa={}\ngravadora={}\ncapa={}", t.titulo, t.artista, t.faixa,
                     t.gravadora, t.capa.map(|c| format!("{} {} bytes", c.mime, c.dados.len())).unwrap_or_default());
        }),
        ["gravar", arq, campo, valor] => match nucleo::Campo::de_nome(campo) {
            Some(c) => nucleo::gravar(Path::new(arq), c, valor),
            None => { eprintln!("campo desconhecido: {campo}"); return ExitCode::from(2) }
        },
        ["capa", arq, img, mime] => match std::fs::read(img) {
            Ok(dados) => nucleo::definir_capa(Path::new(arq), &dados, mime),
            Err(e) => Err(e.into()),
        },
        ["amostra", fmt, arq] => {
            let p = Path::new(arq);
            match *fmt { "mp3" => nucleo::amostras::mp3(p), "flac" => nucleo::amostras::flac(p),
                         "m4a" => nucleo::amostras::m4a(p), _ => { eprintln!("formato?"); return ExitCode::from(2) } }
                .map_err(Into::into)
        }
        _ => { eprintln!("uso: veja o comentário no topo de src/bin/spike-tags.rs"); return ExitCode::from(2) }
    };
    match resultado {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => { eprintln!("erro: {e}"); ExitCode::FAILURE }
    }
}
