//! Regressões que a v3 precisa garantir além da v2 (ADR 0001, "Em aberto → Resolvido"):
//! problemas da lofty encontrados no spike e o comportamento sem as conversões implícitas.

mod comum;

use std::path::Path;

use comum::*;
use lofty::mp4::{Atom, AtomData, AtomIdent};
use lofty::prelude::Accessor;
use tagger_core::metadados::*;

/// Tag ID3v2.3 crua (como outro programa gravaria): frames de texto latin-1 e, opcionalmente, um
/// cabeçalho estendido. `frames`: (id, texto). Coloca a tag na frente do MP3.
fn mp3_com_tag_v23(caminho: &Path, frames: &[(&str, &str)], estendido: bool) {
    mp3_com_tag_v23_crc(caminho, frames, estendido, false)
}

/// Como [`mp3_com_tag_v23`]; `crc`: o cabeçalho estendido traz a flag e o CRC (10 bytes).
fn mp3_com_tag_v23_crc(caminho: &Path, frames: &[(&str, &str)], estendido: bool, crc: bool) {
    let mut corpo = Vec::new();
    if estendido {
        let tamanho: u32 = if crc { 10 } else { 6 };
        corpo.extend_from_slice(&tamanho.to_be_bytes()); // tamanho (sem os 4 bytes do próprio tamanho)
        corpo.extend_from_slice(if crc { &[0x80, 0] } else { &[0, 0] }); // flags
        corpo.extend_from_slice(&0u32.to_be_bytes()); // tamanho do padding
        if crc {
            corpo.extend_from_slice(&[1, 2, 3, 4]);
        }
    }
    for (id, texto) in frames {
        let mut dados = vec![0u8]; // latin-1
        dados.extend(texto.chars().map(|c| c as u8)); // latin-1 (só caracteres < 256 nos testes)
        corpo.extend_from_slice(id.as_bytes());
        corpo.extend_from_slice(&(dados.len() as u32).to_be_bytes());
        corpo.extend_from_slice(&[0, 0]);
        corpo.extend_from_slice(&dados);
    }
    corpo.extend_from_slice(&[0; 32]); // padding
    let n = corpo.len() as u32;
    let sincrono = [(n >> 21) as u8 & 0x7f, (n >> 14) as u8 & 0x7f, (n >> 7) as u8 & 0x7f, n as u8 & 0x7f];
    let mut tag = b"ID3\x03\x00".to_vec();
    tag.push(if estendido { 0x40 } else { 0 });
    tag.extend_from_slice(&sincrono);
    tag.extend_from_slice(&corpo);
    let audio = std::fs::read(caminho).unwrap();
    std::fs::write(caminho, [tag, audio].concat()).unwrap();
}

fn audio_do_mp3(caminho: &Path) -> Vec<u8> {
    let b = std::fs::read(caminho).unwrap();
    let inicio = b.windows(4).position(|w| w == [0xFF, 0xFB, 0x90, 0x64]).unwrap();
    b[inicio..].to_vec()
}

// ---------------------------------------------------------------- ID3v2.3
#[test]
fn genero_multivalor_sobrevive_em_id3v23() {
    // patch do Tagger na lofty (third_party/lofty, create_items_v3): sem ele vira "(Rock)Pop"
    let a = amostra("mp3");
    salvar(&a, &[(Campo::Genero, "Rock; Pop")], None, PADRAO).unwrap();
    salvar(&a, &[(Campo::Titulo, "outro campo")], None, PADRAO).unwrap();
    assert_eq!(versao_id3(&a), 3);
    assert_eq!(campo(&a, Campo::Genero), "Rock; Pop");
    assert_eq!(id3(&a).unwrap().genres().unwrap().collect::<Vec<_>>(), ["Rock", "Pop"]);
}

#[test]
fn genero_com_codigo_numerico_cai_no_caminho_original_da_lofty() {
    // Limitação aceita (ADR 0001): o patch só vale quando todos os gêneros são nomes. Com um código
    // do ID3v1 no meio, a lofty grava a sintaxe de parênteses do v2.3, "(Rock)(80)", que a lofty
    // relê como dois gêneros e o mutagen como um só, literal. Este teste documenta o comportamento.
    let a = amostra("mp3");
    salvar(&a, &[(Campo::Genero, "Rock; 80")], None, PADRAO).unwrap();
    let conteudo = std::fs::read(&a).unwrap();
    let texto: Vec<u8> = "(Rock)(80)".encode_utf16().flat_map(u16::to_le_bytes).collect();
    assert!(conteudo.windows(texto.len()).any(|w| w == texto.as_slice()));
}

#[test]
fn tdrc_com_data_completa_em_id3v23_sobrevive() {
    // O que a v2 (mutagen) grava: TDRC com data completa numa tag v2.3. Com as conversões implícitas
    // da lofty ele era descartado na leitura e sumia ao gravar qualquer campo.
    let a = amostra("mp3");
    mp3_com_tag_v23(&a, &[("TIT2", "T"), ("TDRC", "2001-05-06")], false);
    assert_eq!(campo(&a, Campo::Data), "2001-05-06");
    salvar(&a, &[(Campo::Titulo, "X")], None, PADRAO).unwrap();
    assert_eq!(campo(&a, Campo::Data), "2001-05-06");
    assert_eq!(campo(&a, Campo::Titulo), "X");
}

#[test]
fn tyer_tdat_de_um_id3v23_padrao_ficam() {
    let a = amostra("mp3");
    mp3_com_tag_v23(&a, &[("TIT2", "T"), ("TYER", "1999"), ("TDAT", "0605"), ("TORY", "1998")], false);
    assert_eq!(campo(&a, Campo::Data), "1999-05-06");
    salvar(&a, &[(Campo::Titulo, "X")], None, PADRAO).unwrap();
    let tag = id3(&a).unwrap();
    assert_eq!(ids(&tag), ["TDAT", "TIT2", "TORY", "TYER"]);
    assert_eq!(campo(&a, Campo::Data), "1999-05-06");
}

#[test]
fn data_gravada_em_id3v23_e_relida() {
    let a = amostra("mp3");
    salvar(&a, &[(Campo::Data, "2024-05-17")], None, PADRAO).unwrap();
    assert_eq!(campo(&a, Campo::Data), "2024-05-17");
    salvar(&a, &[(Campo::Data, "1999")], None, OpcoesGravacao { versao_id3: 4, ..PADRAO }).unwrap();
    assert_eq!(campo(&a, Campo::Data), "1999");
}

#[test]
fn id3v23_com_cabecalho_estendido_e_lido_e_regravado() {
    // lofty-rs #761 (backport do PR #777 em third_party/lofty): na 0.25.5 nenhum frame era lido e
    // gravar deixava só o que o app definiu. Confere também que o áudio não é cortado nem duplicado
    // (tamanho da tag com o cabeçalho estendido).
    let a = amostra("mp3");
    let audio = audio_do_mp3(&a);
    mp3_com_tag_v23(&a, &[("TIT2", "Título"), ("TPE1", "Artista"), ("TALB", "Álbum")], true);
    assert_eq!(campo(&a, Campo::Titulo), "Título");
    assert_eq!(campo(&a, Campo::Artista), "Artista");
    salvar(&a, &[(Campo::Titulo, "Novo")], None, PADRAO).unwrap();
    let faixa = carregar(&a).unwrap();
    assert_eq!(faixa.tags[&Campo::Titulo], "Novo");
    assert_eq!(faixa.tags[&Campo::Artista], "Artista");
    assert_eq!(faixa.tags[&Campo::Album], "Álbum");
    let depois = audio_do_mp3(&a);
    assert!(depois == audio, "áudio mudou: {} bytes antes, {} depois", audio.len(), depois.len());
}

#[test]
fn id3v23_com_cabecalho_estendido_e_crc_fica_valido() {
    let a = amostra("mp3");
    let audio = audio_do_mp3(&a);
    mp3_com_tag_v23_crc(&a, &[("TIT2", "Título"), ("TPE1", "Artista")], true, true);
    assert_eq!(campo(&a, Campo::Artista), "Artista");
    salvar(&a, &[(Campo::Titulo, "Novo")], None, PADRAO).unwrap();
    let faixa = carregar(&a).unwrap();
    assert_eq!((faixa.tags[&Campo::Titulo].as_str(), faixa.tags[&Campo::Artista].as_str()), ("Novo", "Artista"));
    assert_eq!(std::fs::read(&a).unwrap()[5] & 0x40, 0, "não regrava o cabeçalho estendido");
    assert!(audio_do_mp3(&a) == audio);
}

// ---------------------------------------------------------------- ID3v1 (como o mutagen v1=1)
#[test]
fn id3v1_existente_e_atualizado_a_partir_da_v2() {
    use std::io::Write;
    let a = amostra("mp3");
    let mut v1 = b"TAG".to_vec();
    v1.resize(127, 0);
    v1.push(0xff);
    std::fs::OpenOptions::new().append(true).open(&a).unwrap().write_all(&v1).unwrap();
    salvar(&a, &[(Campo::Titulo, "Novo título"), (Campo::Artista, "A; B"), (Campo::Genero, "Rock")], None, PADRAO)
        .unwrap();
    let f = mpeg(&a);
    let v1 = f.id3v1().expect("o ID3v1 continua");
    assert_eq!(v1.title.as_deref(), Some("Novo título"));
    assert_eq!(v1.artist.as_deref(), Some("A"));
    assert_eq!(v1.genre, Some(17));
}

#[test]
fn sem_id3v1_nao_cria_um() {
    let a = amostra("mp3");
    salvar(&a, &[(Campo::Titulo, "A")], None, PADRAO).unwrap();
    assert!(!tem_id3v1(&a));
}

// ---------------------------------------------------------------- sem conversões implícitas
#[test]
fn vorbis_tracknumber_com_barra_fica_como_esta() {
    // com as conversões implícitas, a lofty dividiria TRACKNUMBER=3/12 em TRACKNUMBER + TRACKTOTAL
    for fmt in ["flac", "ogg"] {
        let a = amostra(fmt);
        editar_vorbis(&a, |t| t.push("TRACKNUMBER".into(), "3/12".into()));
        assert_eq!(campo(&a, Campo::Faixa), "3/12");
        salvar(&a, &[(Campo::Titulo, "outro campo")], None, PADRAO).unwrap();
        let g = vorbis(&a).unwrap();
        assert_eq!(valores(&g, "TRACKNUMBER"), ["3/12"], "{fmt}");
        assert!(valores(&g, "TRACKTOTAL").is_empty(), "{fmt}");
    }
}

#[test]
fn mp4_gnre_antigo_e_lido_e_preservado() {
    let a = amostra("m4a");
    editar_ilst(&a, |t| {
        t.insert(Atom::new(
            AtomIdent::Fourcc(*b"gnre"),
            AtomData::Unknown { code: lofty::mp4::DataType::Reserved, data: vec![0, 18] }, // 18 = Rock (17 + 1)
        ));
    });
    assert_eq!(campo(&a, Campo::Genero), "Rock");
    salvar(&a, &[(Campo::Titulo, "outro campo")], None, PADRAO).unwrap();
    assert!(ilst(&a).unwrap().get(&AtomIdent::Fourcc(*b"gnre")).is_some(), "gnre não é convertido sem pedir");
    salvar(&a, &[(Campo::Genero, "Pop")], None, PADRAO).unwrap();
    let t = ilst(&a).unwrap();
    assert!(t.get(&AtomIdent::Fourcc(*b"gnre")).is_none());
    assert_eq!(t.genre().as_deref(), Some("Pop"));
}
