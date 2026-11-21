//! Arquivos de áudio mínimos, sem tags: porte fiel dos geradores de tests/conftest.py da v2
//! (criar_mp3, criar_flac, criar_m4a). Nenhuma música real; o "áudio" é silêncio ou lixo.

use std::path::Path;

/// Cabeçalho de frame MPEG-1 Layer III, 128 kbps, 44,1 kHz, sem CRC: cada frame tem 417 bytes.
pub fn mp3(caminho: &Path) -> std::io::Result<()> {
    let mut frame = vec![0xFF, 0xFB, 0x90, 0x64];
    frame.resize(417, 0);
    std::fs::write(caminho, frame.repeat(40))
}

/// STREAMINFO: blocos de 4096, 44,1 kHz, 2 canais, 16 bits, 2 s de amostras, MD5 zerado.
pub fn flac(caminho: &Path) -> std::io::Result<()> {
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

fn atomo(nome: &[u8; 4], conteudo: &[u8]) -> Vec<u8> {
    let mut a = ((8 + conteudo.len()) as u32).to_be_bytes().to_vec();
    a.extend_from_slice(nome);
    a.extend_from_slice(conteudo);
    a
}

/// ftyp + moov (mvhd + uma trilha de som com mdhd/hdlr) + mdat.
pub fn m4a(caminho: &Path) -> std::io::Result<()> {
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
