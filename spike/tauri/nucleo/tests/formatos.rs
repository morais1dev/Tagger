//! Leitura e gravação nos três formatos, com arquivos gerados na hora (nucleo::amostras).

use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};

use lofty::TextEncoding;
use lofty::config::{ParseOptions, WriteOptions};
use lofty::file::AudioFile;
use lofty::flac::FlacFile;
use lofty::id3::v2::{AttachedPictureFrame, Frame, FrameId, Id3v2Tag};
use lofty::mp4::{Ilst, Mp4File};
use lofty::mpeg::MpegFile;
use lofty::ogg::OggPictureStorage;
use lofty::picture::{MimeType, Picture, PictureInformation, PictureType};
use nucleo::{Campo, amostras, definir_capa, gravar, imagens, ler};

const JPEG: &[u8] = b"\xff\xd8\xff\xe0jpeg-falso-jpeg-falso-jpeg-falso";
const OUTRA_CAPA: &[u8] = b"\xff\xd8\xff\xe0outra-capa-jpeg";
const PNG: &[u8] = b"\x89PNG\r\n\x1a\npng-falso-png-falso-png-falso-png";

static CONTADOR: AtomicU32 = AtomicU32::new(0);

fn amostra(fmt: &str) -> PathBuf {
    let n = CONTADOR.fetch_add(1, Ordering::SeqCst);
    let pasta = std::env::temp_dir().join(format!("spike-lofty-{}-{n}", std::process::id()));
    std::fs::create_dir_all(&pasta).unwrap();
    let caminho = pasta.join(format!("musica.{fmt}"));
    match fmt {
        "mp3" => amostras::mp3(&caminho),
        "flac" => amostras::flac(&caminho),
        _ => amostras::m4a(&caminho),
    }
    .unwrap();
    caminho
}

const FORMATOS: [&str; 3] = ["mp3", "flac", "m4a"];

#[test]
fn arquivo_novo_le_vazio() {
    for fmt in FORMATOS {
        let t = ler(&amostra(fmt)).unwrap();
        assert_eq!(
            (t.titulo.as_str(), t.artista.as_str(), t.faixa.as_str(), t.gravadora.as_str()),
            ("", "", "", ""),
            "{fmt}"
        );
        assert!(t.capa.is_none(), "{fmt}");
    }
}

#[test]
fn grava_e_rele_os_quatro_campos() {
    for fmt in FORMATOS {
        let a = amostra(fmt);
        gravar(&a, Campo::Titulo, "Título ção").unwrap();
        gravar(&a, Campo::Artista, "A").unwrap();
        gravar(&a, Campo::Faixa, "3/12").unwrap();
        gravar(&a, Campo::Gravadora, "Selo").unwrap();
        let t = ler(&a).unwrap();
        assert_eq!(t.titulo, "Título ção", "{fmt}");
        assert_eq!(t.artista, "A", "{fmt}");
        assert_eq!(t.faixa, "3/12", "{fmt}");
        assert_eq!(t.gravadora, "Selo", "{fmt}");
    }
}

#[test]
fn gravar_um_campo_preserva_os_outros() {
    for fmt in FORMATOS {
        let a = amostra(fmt);
        gravar(&a, Campo::Titulo, "Fica").unwrap();
        gravar(&a, Campo::Gravadora, "Selo").unwrap();
        definir_capa(&a, JPEG, "image/jpeg").unwrap();
        gravar(&a, Campo::Artista, "Novo").unwrap();
        let t = ler(&a).unwrap();
        assert_eq!((t.titulo.as_str(), t.gravadora.as_str(), t.artista.as_str()), ("Fica", "Selo", "Novo"), "{fmt}");
        assert_eq!(t.capa.unwrap().dados, JPEG, "{fmt}");
    }
}

#[test]
fn valor_vazio_remove_o_campo() {
    for fmt in FORMATOS {
        let a = amostra(fmt);
        gravar(&a, Campo::Titulo, "X").unwrap();
        gravar(&a, Campo::Faixa, "4/9").unwrap();
        gravar(&a, Campo::Titulo, "").unwrap();
        gravar(&a, Campo::Faixa, "").unwrap();
        let t = ler(&a).unwrap();
        assert_eq!((t.titulo.as_str(), t.faixa.as_str()), ("", ""), "{fmt}");
    }
}

#[test]
fn multivalor_vira_valores_separados() {
    for fmt in FORMATOS {
        let a = amostra(fmt);
        gravar(&a, Campo::Artista, "A; B").unwrap();
        assert_eq!(ler(&a).unwrap().artista, "A; B", "{fmt}");
    }
    // e no disco são dois valores de verdade (não o texto "A; B")
    let mp3 = amostra("mp3");
    gravar(&mp3, Campo::Artista, "A; B").unwrap();
    let f = MpegFile::read_from(&mut File::open(&mp3).unwrap(), ParseOptions::new()).unwrap();
    let tpe1: Vec<&str> = f.id3v2().unwrap().get_texts(&FrameId::new("TPE1").unwrap()).unwrap().collect();
    assert_eq!(tpe1, ["A", "B"]);
    let flac = amostra("flac");
    gravar(&flac, Campo::Artista, "A; B").unwrap();
    let f = FlacFile::read_from(&mut File::open(&flac).unwrap(), ParseOptions::new()).unwrap();
    assert_eq!(f.vorbis_comments().unwrap().get_all("ARTIST").collect::<Vec<_>>(), ["A", "B"]);
}

#[test]
fn mp3_grava_id3v23() {
    let a = amostra("mp3");
    gravar(&a, Campo::Titulo, "A").unwrap();
    let bytes = std::fs::read(&a).unwrap();
    assert_eq!(&bytes[..4], b"ID3\x03");
}

fn imagem(dados: &[u8], mime: &str, tipo: PictureType) -> Picture {
    Picture::unchecked(dados.to_vec()).pic_type(tipo).mime_type(MimeType::from_str(mime)).build()
}

/// Coloca uma contracapa (tipo 4; no M4A, uma 2ª imagem) por fora do núcleo.
fn por_contracapa(caminho: &Path) {
    let opcoes = WriteOptions::default().use_id3v23(true);
    let mut arq = File::options().read(true).write(true).open(caminho).unwrap();
    match caminho.extension().unwrap().to_str().unwrap() {
        "mp3" => {
            let mut f = MpegFile::read_from(&mut File::open(caminho).unwrap(), ParseOptions::new()).unwrap();
            if f.id3v2().is_none() {
                f.set_id3v2(Id3v2Tag::new());
            }
            let mut pic = imagem(PNG, "image/png", PictureType::CoverBack);
            pic.set_description(Some("contracapa".into()));
            f.id3v2_mut().unwrap().insert(Frame::Picture(AttachedPictureFrame::new(TextEncoding::UTF16, pic)));
            f.save_to(&mut arq, opcoes).unwrap();
        }
        "flac" => {
            let mut f = FlacFile::read_from(&mut File::open(caminho).unwrap(), ParseOptions::new()).unwrap();
            f.insert_picture(imagem(PNG, "image/png", PictureType::CoverBack), Some(PictureInformation::default()))
                .unwrap();
            f.save_to(&mut arq, opcoes).unwrap();
        }
        _ => {
            let mut f = Mp4File::read_from(&mut File::open(caminho).unwrap(), ParseOptions::new()).unwrap();
            if f.ilst().is_none() {
                f.set_ilst(Ilst::new());
            }
            f.ilst_mut().unwrap().insert_picture(imagem(PNG, "image/png", PictureType::Other));
            f.save_to(&mut arq, opcoes).unwrap();
        }
    }
}

#[test]
fn trocar_a_capa_mantem_as_outras_imagens() {
    for fmt in FORMATOS {
        let a = amostra(fmt);
        if fmt == "m4a" {
            definir_capa(&a, JPEG, "image/jpeg").unwrap(); // M4A: a capa é a 1ª imagem; a 2ª é "outra"
        }
        por_contracapa(&a);
        definir_capa(&a, JPEG, "image/jpeg").unwrap();
        definir_capa(&a, OUTRA_CAPA, "image/jpeg").unwrap(); // trocar de novo
        let lista = imagens(&a).unwrap();
        assert_eq!(lista.len(), 2, "{fmt}: {lista:?}");
        assert!(lista.iter().any(|i| i.mime == "image/png" && i.tamanho == PNG.len()), "{fmt}: a contracapa sumiu");
        let capa = ler(&a).unwrap().capa.unwrap();
        assert_eq!(capa.dados, OUTRA_CAPA, "{fmt}");
        if fmt != "m4a" {
            assert!(lista.iter().any(|i| i.tipo == 4), "{fmt}");
            assert!(lista.iter().any(|i| i.tipo == 3), "{fmt}");
        }
    }
}

#[test]
fn ler_nunca_grava() {
    for fmt in FORMATOS {
        let a = amostra(fmt);
        gravar(&a, Campo::Titulo, "X").unwrap();
        let antes = std::fs::read(&a).unwrap();
        ler(&a).unwrap();
        imagens(&a).unwrap();
        assert_eq!(std::fs::read(&a).unwrap(), antes, "{fmt}");
    }
}
