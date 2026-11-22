//! Apoio dos testes: amostras numa pasta temporária e leitura "por fora" (direto pela lofty).
#![allow(dead_code)]

use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU32, Ordering};

use lofty::config::{ParseOptions, WriteOptions};
use lofty::file::AudioFile;
use lofty::flac::FlacFile;
use lofty::id3::v2::Id3v2Tag;
use lofty::mp4::{Ilst, Mp4File};
use lofty::mpeg::MpegFile;
use lofty::ogg::tag::VorbisComments;
use lofty::ogg::{OpusFile, VorbisFile};
use lofty::picture::{MimeType, Picture, PictureType};
use tagger_core::amostras;
use tagger_core::metadados::{Campo, OpcoesGravacao};

pub const JPEG: &[u8] = b"\xff\xd8\xff\xe0jpeg-falsojpeg-falsojpeg-falsojpeg-falsojpeg-falsojpeg-falso";
pub const PNG: &[u8] = b"\x89PNG\r\n\x1a\npng-falsopng-falsopng-falsopng-falsopng-falsopng-falso";
pub const PADRAO: OpcoesGravacao = OpcoesGravacao { versao_id3: 3, multivalor: true, remover_id3v1: false };

/// Os formatos além do MP3 (a fixture `outro` do pytest).
pub const OUTROS: [&str; 3] = ["flac", "ogg", "m4a"];

static CONTADOR: AtomicU32 = AtomicU32::new(0);

pub fn pasta() -> PathBuf {
    let n = CONTADOR.fetch_add(1, Ordering::SeqCst);
    let p = std::env::temp_dir().join(format!("tagger-core-{}-{n}", std::process::id()));
    let _ = std::fs::remove_dir_all(&p);
    std::fs::create_dir_all(&p).unwrap();
    p
}

/// Arquivo sem tags do formato pedido ("opus" vira um .ogg com Opus dentro).
pub fn amostra(fmt: &str) -> PathBuf {
    let ext = if fmt == "opus" || fmt == "oggflac" { "ogg" } else { fmt };
    let caminho = pasta().join(format!("musica.{ext}"));
    amostras::criar(fmt, &caminho).unwrap();
    caminho
}

pub fn ler_opcoes() -> ParseOptions {
    ParseOptions::new().implicit_conversions(false)
}

fn gravar_opcoes() -> WriteOptions {
    WriteOptions::default().use_id3v23(true)
}

fn rw(caminho: &Path) -> File {
    File::options().read(true).write(true).open(caminho).unwrap()
}

// ---------------------------------------------------------------- MP3
pub fn mpeg(caminho: &Path) -> MpegFile {
    MpegFile::read_from(&mut File::open(caminho).unwrap(), ler_opcoes()).unwrap()
}

pub fn id3(caminho: &Path) -> Option<Id3v2Tag> {
    mpeg(caminho).id3v2().cloned()
}

/// Versão (3 ou 4) do ID3v2 no início do arquivo.
pub fn versao_id3(caminho: &Path) -> u8 {
    let b = std::fs::read(caminho).unwrap();
    assert_eq!(&b[..3], b"ID3");
    b[3]
}

/// Grava uma tag ID3v2 montada por fora (como `ID3().save()` nos testes da v2).
pub fn gravar_id3(caminho: &Path, tag: Id3v2Tag) {
    let mut f = mpeg(caminho);
    f.set_id3v2(tag);
    f.save_to(&mut rw(caminho), gravar_opcoes()).unwrap();
}

pub fn ids(tag: &Id3v2Tag) -> Vec<String> {
    let mut v: Vec<String> = tag.iter().map(|f| f.id_str().to_string()).collect();
    v.sort();
    v
}

// ---------------------------------------------------------------- Vorbis
pub fn vorbis(caminho: &Path) -> Option<VorbisComments> {
    let mut f = File::open(caminho).unwrap();
    match caminho.extension().unwrap().to_str().unwrap() {
        "flac" => FlacFile::read_from(&mut f, ler_opcoes()).unwrap().vorbis_comments().cloned(),
        _ => {
            let b = std::fs::read(caminho).unwrap();
            if b.windows(8).any(|w| w == b"OpusHead") {
                Some(OpusFile::read_from(&mut f, ler_opcoes()).unwrap().vorbis_comments().clone())
            } else {
                Some(VorbisFile::read_from(&mut f, ler_opcoes()).unwrap().vorbis_comments().clone())
            }
        }
    }
}

pub fn valores(tag: &VorbisComments, chave: &str) -> Vec<String> {
    tag.get_all(chave).map(str::to_string).collect()
}

/// Edita os Vorbis comments por fora (cria se o FLAC não tiver).
pub fn editar_vorbis(caminho: &Path, editar: impl FnOnce(&mut VorbisComments)) {
    let mut f = File::open(caminho).unwrap();
    match caminho.extension().unwrap().to_str().unwrap() {
        "flac" => {
            let mut a = FlacFile::read_from(&mut f, ler_opcoes()).unwrap();
            if a.vorbis_comments().is_none() {
                a.set_vorbis_comments(VorbisComments::default());
            }
            editar(a.vorbis_comments_mut().unwrap());
            a.save_to(&mut rw(caminho), gravar_opcoes()).unwrap();
        }
        _ => {
            let mut a = VorbisFile::read_from(&mut f, ler_opcoes()).unwrap();
            editar(a.vorbis_comments_mut());
            a.save_to(&mut rw(caminho), gravar_opcoes()).unwrap();
        }
    }
}

pub fn flac(caminho: &Path) -> FlacFile {
    FlacFile::read_from(&mut File::open(caminho).unwrap(), ler_opcoes()).unwrap()
}

pub fn salvar_flac(caminho: &Path, a: &FlacFile) {
    a.save_to(&mut rw(caminho), gravar_opcoes()).unwrap();
}

// ---------------------------------------------------------------- MP4
pub fn ilst(caminho: &Path) -> Option<Ilst> {
    Mp4File::read_from(&mut File::open(caminho).unwrap(), ler_opcoes()).unwrap().ilst().cloned()
}

pub fn editar_ilst(caminho: &Path, editar: impl FnOnce(&mut Ilst)) {
    let mut a = Mp4File::read_from(&mut File::open(caminho).unwrap(), ler_opcoes()).unwrap();
    if a.ilst().is_none() {
        a.set_ilst(Ilst::new());
    }
    editar(a.ilst_mut().unwrap());
    a.save_to(&mut rw(caminho), gravar_opcoes()).unwrap();
}

// ---------------------------------------------------------------- imagens
pub fn imagem(tipo: u8, dados: &[u8]) -> Picture {
    Picture::unchecked(dados.to_vec()).pic_type(PictureType::from_u8(tipo)).mime_type(MimeType::Jpeg).build()
}

/// Valor de um campo pelo núcleo.
pub fn campo(caminho: &Path, campo: Campo) -> String {
    tagger_core::metadados::carregar(caminho).unwrap().tags[&campo].clone()
}
