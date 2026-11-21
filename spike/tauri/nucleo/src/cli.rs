//! Linha de comando (binário spike-tags) do núcleo do spike, usada pelo script de comparação com a v2.
//! A versão do ID3 (MP3) vem da variável SPIKE_ID3 (3 ou 4; padrão 3, o da v2).
//!   spike-tags ler <arquivo>
//!   spike-tags gravar <arquivo> <titulo|artista|faixa|gravadora> <valor>
//!   spike-tags capa <arquivo> <imagem> <mime>
//!   spike-tags amostra <mp3|flac|m4a> <arquivo>

use std::path::Path;
use std::process::ExitCode;

/// Executa a linha de comando com os argumentos do processo.
pub fn executar() -> ExitCode {
    let opcoes = crate::Opcoes {
        versao_id3: if std::env::var("SPIKE_ID3").as_deref() == Ok("4") { 4 } else { 3 },
    };
    let args: Vec<String> = std::env::args().skip(1).collect();
    let resultado = match args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["ler", arq] => crate::ler(Path::new(arq)).map(|t| {
            println!("titulo={}\nartista={}\nfaixa={}\ngravadora={}\ncapa={}", t.titulo, t.artista, t.faixa,
                     t.gravadora, t.capa.map(|c| format!("{} {} bytes", c.mime, c.dados.len())).unwrap_or_default());
        }),
        ["gravar", arq, campo, valor] => match crate::Campo::de_nome(campo) {
            Some(c) => crate::gravar(Path::new(arq), c, valor, opcoes),
            None => { eprintln!("campo desconhecido: {campo}"); return ExitCode::from(2) }
        },
        ["capa", arq, img, mime] => match std::fs::read(img) {
            Ok(dados) => crate::definir_capa(Path::new(arq), &dados, mime, opcoes),
            Err(e) => Err(e.into()),
        },
        ["amostra", fmt, arq] => {
            let p = Path::new(arq);
            match *fmt { "mp3" => crate::amostras::mp3(p), "flac" => crate::amostras::flac(p),
                         "m4a" => crate::amostras::m4a(p), _ => { eprintln!("formato?"); return ExitCode::from(2) } }
                .map_err(Into::into)
        }
        _ => { eprintln!("uso: veja o comentário no topo de src/bin/spike-tags.rs"); return ExitCode::from(2) }
    };
    match resultado {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => { eprintln!("erro: {e}"); ExitCode::FAILURE }
    }
}
