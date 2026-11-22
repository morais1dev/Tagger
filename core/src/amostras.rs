//! Arquivos de áudio mínimos, sem tags, para testes: porte dos geradores de `tests/conftest.py`
//! da v2 (`criar_mp3`, `criar_flac`, `criar_ogg`, `criar_opus`, `criar_m4a`).
//!
//! O MP3 tem frames de silêncio de verdade. FLAC, Ogg e M4A têm só a estrutura que um leitor de
//! tags precisa (cabeçalhos com duração de 2 s); o áudio em si é lixo. Nenhuma música real.

use std::io;
use std::path::Path;

/// Cabeçalho de frame MPEG-1 Layer III, 128 kbps, 44,1 kHz, sem CRC: cada frame tem 417 bytes.
pub fn mp3(caminho: &Path) -> io::Result<()> {
    let mut frame = vec![0xFF, 0xFB, 0x90, 0x64];
    frame.resize(417, 0);
    std::fs::write(caminho, frame.repeat(40))
}

/// STREAMINFO: blocos de 4096, 44,1 kHz, 2 canais, 16 bits, 2 s de amostras, MD5 zerado.
pub fn flac(caminho: &Path) -> io::Result<()> {
    let taxa: u64 = 44100;
    let mut info = Vec::new();
    info.extend_from_slice(&4096u16.to_be_bytes());
    info.extend_from_slice(&4096u16.to_be_bytes());
    info.extend_from_slice(&[0; 6]);
    let campo = (taxa << 44) | (1 << 41) | (15 << 36) | (taxa * 2);
    info.extend_from_slice(&campo.to_be_bytes());
    info.extend_from_slice(&[0; 16]);
    let mut dados = b"fLaC".to_vec();
    dados.push(0x80);
    dados.extend_from_slice(&(info.len() as u32).to_be_bytes()[1..]);
    dados.extend_from_slice(&info);
    dados.extend_from_slice(&[0; 64]);
    std::fs::write(caminho, dados)
}

/// 3 páginas: identificação; comentários (vazio) + setup; um pacote de "áudio" com a posição final.
pub fn ogg(caminho: &Path) -> io::Result<()> {
    let taxa: u32 = 44100;
    let mut identificacao = b"\x01vorbis".to_vec();
    identificacao.extend_from_slice(&0u32.to_le_bytes()); // versão
    identificacao.push(2); // canais
    identificacao.extend_from_slice(&taxa.to_le_bytes());
    identificacao.extend_from_slice(&0i32.to_le_bytes());
    identificacao.extend_from_slice(&128000i32.to_le_bytes());
    identificacao.extend_from_slice(&0i32.to_le_bytes());
    identificacao.extend_from_slice(b"\xb8\x01");
    let mut comentarios = b"\x03vorbis".to_vec();
    comentarios.extend_from_slice(&6u32.to_le_bytes());
    comentarios.extend_from_slice(b"Tagger");
    comentarios.extend_from_slice(&0u32.to_le_bytes());
    comentarios.push(1);
    let mut setup = b"\x05vorbis".to_vec();
    setup.extend_from_slice(&[0; 30]);
    let paginas = [
        (vec![identificacao], 0u64),
        (vec![comentarios, setup], 0),
        (vec![vec![0; 100]], u64::from(taxa) * 2),
    ];
    std::fs::write(caminho, gravar_ogg(&paginas))
}

/// Opus num .ogg: OpusHead; OpusTags (vazio); um pacote de "áudio" (Opus conta sempre a 48 kHz).
pub fn opus(caminho: &Path) -> io::Result<()> {
    let mut cabecalho = b"OpusHead".to_vec();
    cabecalho.push(1); // versão
    cabecalho.push(2); // canais
    cabecalho.extend_from_slice(&0u16.to_le_bytes()); // pre-skip
    cabecalho.extend_from_slice(&48000u32.to_le_bytes());
    cabecalho.extend_from_slice(&0i16.to_le_bytes());
    cabecalho.push(0);
    let mut comentarios = b"OpusTags".to_vec();
    comentarios.extend_from_slice(&6u32.to_le_bytes());
    comentarios.extend_from_slice(b"Tagger");
    comentarios.extend_from_slice(&0u32.to_le_bytes());
    let paginas = [(vec![cabecalho], 0u64), (vec![comentarios], 0), (vec![vec![0; 100]], 48000 * 2)];
    std::fs::write(caminho, gravar_ogg(&paginas))
}

fn atomo(nome: &[u8; 4], conteudo: &[u8]) -> Vec<u8> {
    let mut a = ((8 + conteudo.len()) as u32).to_be_bytes().to_vec();
    a.extend_from_slice(nome);
    a.extend_from_slice(conteudo);
    a
}

/// ftyp + moov (mvhd + uma trilha de som com mdhd/hdlr) + mdat.
pub fn m4a(caminho: &Path) -> io::Result<()> {
    let quatro = |vals: [u32; 4]| vals.iter().flat_map(|v| v.to_be_bytes()).collect::<Vec<u8>>();
    let mut mvhd = vec![0; 4];
    mvhd.extend(quatro([0, 0, 1000, 2000]));
    mvhd.extend_from_slice(&[0; 80]);
    let mut mdhd = vec![0; 4];
    mdhd.extend(quatro([0, 0, 44100, 88200]));
    mdhd.extend_from_slice(&[0; 4]);
    let mut hdlr = vec![0; 8];
    hdlr.extend_from_slice(b"soun");
    hdlr.extend_from_slice(&[0; 13]);
    let mdia = [atomo(b"mdhd", &mdhd), atomo(b"hdlr", &hdlr)].concat();
    let moov = [atomo(b"mvhd", &mvhd), atomo(b"trak", &atomo(b"mdia", &mdia))].concat();
    let mut ftyp = b"M4A ".to_vec();
    ftyp.extend_from_slice(&[0; 4]);
    ftyp.extend_from_slice(b"M4A mp42isom");
    let dados = [atomo(b"ftyp", &ftyp), atomo(b"moov", &moov), atomo(b"mdat", &[0; 64])].concat();
    std::fs::write(caminho, dados)
}

/// Cria o arquivo do formato pedido ("mp3", "flac", "ogg", "opus" ou "m4a").
pub fn criar(formato: &str, caminho: &Path) -> io::Result<()> {
    match formato {
        "mp3" => mp3(caminho),
        "flac" => flac(caminho),
        "ogg" => ogg(caminho),
        "opus" => opus(caminho),
        "m4a" | "mp4" => m4a(caminho),
        _ => Err(io::Error::new(io::ErrorKind::InvalidInput, format!("formato desconhecido: {formato}"))),
    }
}

// ---------------------------------------------------------------- páginas Ogg
/// Páginas de um único fluxo lógico (serial 1), como `_gravar_ogg` do conftest.
fn gravar_ogg(paginas: &[(Vec<Vec<u8>>, u64)]) -> Vec<u8> {
    let mut dados = Vec::new();
    for (numero, (pacotes, posicao)) in paginas.iter().enumerate() {
        let mut segmentos = Vec::new();
        let mut corpo = Vec::new();
        for pacote in pacotes {
            let mut resto = pacote.len();
            loop {
                let n = resto.min(255);
                segmentos.push(n as u8);
                resto -= n;
                if n < 255 {
                    break;
                }
            }
            corpo.extend_from_slice(pacote);
        }
        let mut tipo = 0u8;
        if numero == 0 {
            tipo |= 0x02;
        }
        if numero == paginas.len() - 1 {
            tipo |= 0x04;
        }
        let mut pagina = b"OggS".to_vec();
        pagina.push(0);
        pagina.push(tipo);
        pagina.extend_from_slice(&posicao.to_le_bytes());
        pagina.extend_from_slice(&1u32.to_le_bytes());
        pagina.extend_from_slice(&(numero as u32).to_le_bytes());
        pagina.extend_from_slice(&[0; 4]); // CRC, calculado abaixo
        pagina.push(segmentos.len() as u8);
        pagina.extend_from_slice(&segmentos);
        pagina.extend_from_slice(&corpo);
        let crc = crc_ogg(&pagina);
        pagina[22..26].copy_from_slice(&crc.to_le_bytes());
        dados.extend_from_slice(&pagina);
    }
    dados
}

/// CRC-32 do Ogg (polinômio 0x04C11DB7, sem reflexão, valor inicial 0).
fn crc_ogg(dados: &[u8]) -> u32 {
    let mut crc = 0u32;
    for &byte in dados {
        crc ^= u32::from(byte) << 24;
        for _ in 0..8 {
            crc = if crc & 0x8000_0000 != 0 { (crc << 1) ^ 0x04C1_1DB7 } else { crc << 1 };
        }
    }
    crc
}
