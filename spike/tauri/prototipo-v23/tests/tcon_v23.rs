//! Com a lofty corrigida: gênero multivalor sobrevive a uma gravação em ID3v2.3.

use std::fs::File;

use lofty::TextEncoding;
use lofty::config::{ParseOptions, WriteOptions};
use lofty::file::AudioFile;
use lofty::id3::v2::{Frame, FrameId, Id3v2Tag, TextInformationFrame};
use lofty::mpeg::MpegFile;
use nucleo::{Campo, Opcoes, amostras, gravar};

#[test]
fn genero_multivalor_sobrevive_no_id3v23() {
    let caminho = std::env::temp_dir().join(format!("prototipo-v23-{}.mp3", std::process::id()));
    amostras::mp3(&caminho).unwrap();
    let mut f = MpegFile::read_from(&mut File::open(&caminho).unwrap(), ParseOptions::new()).unwrap();
    let mut tag = Id3v2Tag::new();
    tag.insert(Frame::Text(TextInformationFrame::new(FrameId::new("TCON").unwrap(), TextEncoding::UTF16, "Rock\0Pop")));
    f.set_id3v2(tag);
    f.save_to(&mut File::options().read(true).write(true).open(&caminho).unwrap(), WriteOptions::default().use_id3v23(true))
        .unwrap();

    gravar(&caminho, Campo::Titulo, "Outro campo", Opcoes { versao_id3: 3 }).unwrap();

    let bytes = std::fs::read(&caminho).unwrap();
    assert_eq!(&bytes[..4], b"ID3\x03");
    let f = MpegFile::read_from(&mut File::open(&caminho).unwrap(), ParseOptions::new()).unwrap();
    let generos: Vec<&str> = f.id3v2().unwrap().get_texts(&FrameId::new("TCON").unwrap()).unwrap().collect();
    assert_eq!(generos, ["Rock", "Pop"]);
    let _ = std::fs::remove_file(&caminho);
}
