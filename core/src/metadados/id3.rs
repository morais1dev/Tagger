//! MP3: tags ID3v2 (e o ID3v1 legado). Porte da parte ID3 de `metadata.py`.

use std::borrow::Cow;
use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;
use std::str::FromStr;

use lofty::TextEncoding;
use lofty::config::WriteOptions;
use lofty::file::AudioFile;
use lofty::id3::v1::{GENRES, Id3v1Tag};
use lofty::id3::v2::{
    AttachedPictureFrame, CommentFrame, Frame, FrameId, Id3v2Tag, TextInformationFrame, TimestampFrame,
    UnsynchronizedTextFrame,
};
use lofty::mpeg::MpegFile;
use lofty::picture::{MimeType, Picture, PictureType};
use lofty::tag::TagType;
use lofty::tag::items::Timestamp;

use super::{AcaoCapa, Campo, OpcoesGravacao, Resultado, SEPARADOR, escolher_capa};

const NULO: char = '\0';
const IDIOMA: [u8; 3] = *b"eng";

fn id_do_campo(campo: Campo) -> &'static str {
    match campo {
        Campo::Titulo => "TIT2",
        Campo::Artista => "TPE1",
        Campo::Album => "TALB",
        Campo::ArtistaAlbum => "TPE2",
        Campo::Faixa => "TRCK",
        Campo::Disco => "TPOS",
        Campo::Data => "TDRC",
        Campo::Genero => "TCON",
        Campo::Compositor => "TCOM",
        Campo::Letrista => "TEXT",
        Campo::Comentario => "COMM",
        Campo::Letra => "USLT",
        Campo::Gravadora => "TPUB",
    }
}

fn frame_id(id: &str) -> FrameId<'static> {
    FrameId::new(Cow::Owned(id.to_string())).expect("frame id válido")
}

/// Frames que o Tagger mostra/edita. TYER/TDAT/TIME são a data de uma tag ID3v2.3 (lida sem as
/// conversões da lofty); o mutagen da v2 os lê como TDRC.
const FRAMES_DO_TAGGER: [&str; 17] = [
    "TIT2", "TPE1", "TALB", "TPE2", "TRCK", "TPOS", "TDRC", "TCON", "TCOM", "TEXT", "COMM", "USLT", "TPUB", "APIC",
    "TYER", "TDAT", "TIME",
];

/// Frames que a lofty lê como binários mas não são "desconhecidos" (o mutagen os entende).
const BINARIOS_CONHECIDOS: [&str; 3] = ["GEOB", "SYLT", "ATXT"];

fn texto(tag: &Id3v2Tag, id: &str) -> Option<String> {
    let frame_id = frame_id(id);
    match tag.get(&frame_id)? {
        Frame::Text(f) => Some(f.value.split(NULO).collect::<Vec<_>>().join(SEPARADOR)),
        Frame::Timestamp(f) => Some(f.timestamp.to_string()),
        _ => None,
    }
}

fn data(tag: &Id3v2Tag) -> String {
    if let Some(tdrc) = texto(tag, "TDRC") {
        return tdrc;
    }
    // ID3v2.3 padrão: TYER (ano) + TDAT (DDMM), como o mutagen junta em TDRC
    let Some(ano) = texto(tag, "TYER") else { return String::new() };
    match texto(tag, "TDAT") {
        Some(d) if d.len() == 4 && d.bytes().all(|b| b.is_ascii_digit()) => format!("{ano}-{}-{}", &d[2..], &d[..2]),
        _ => ano,
    }
}

fn comentario_sem_descricao(tag: &Id3v2Tag) -> Option<&CommentFrame<'_>> {
    tag.iter().find_map(|f| match f {
        Frame::Comment(c) if c.description.is_empty() => Some(c),
        _ => None,
    })
}

fn letra_exibida(tag: &Id3v2Tag) -> Option<&UnsynchronizedTextFrame<'_>> {
    let letras: Vec<&UnsynchronizedTextFrame<'_>> = tag
        .iter()
        .filter_map(|f| if let Frame::UnsynchronizedText(u) = f { Some(u) } else { None })
        .collect();
    letras.iter().find(|u| u.description.is_empty()).or(letras.first()).copied()
}

pub(super) fn ler(tag: &Id3v2Tag, campo: Campo) -> String {
    match campo {
        Campo::Comentario => {
            if let Some(c) = comentario_sem_descricao(tag) {
                return c.content.to_string();
            }
            // alguns programas (ex.: ffmpeg) gravam o comentário como TXXX:comment
            tag.get_user_text("comment").map(|t| t.split(NULO).collect::<Vec<_>>().join(SEPARADOR)).unwrap_or_default()
        }
        Campo::Letra => letra_exibida(tag).map(|u| u.content.to_string()).unwrap_or_default(),
        Campo::Data => data(tag),
        // a lofty converte códigos do ID3v1 como "(17)" para "Rock", como o .genres do mutagen
        Campo::Genero => tag.genres().map(|g| g.collect::<Vec<_>>().join(SEPARADOR)).unwrap_or_default(),
        _ => texto(tag, id_do_campo(campo)).unwrap_or_default(),
    }
}

pub(super) fn gravar(tag: &mut Id3v2Tag, campo: Campo, valor: &str, multivalor: bool) {
    match campo {
        Campo::Comentario => {
            tag.retain(|f| !matches!(f, Frame::Comment(c) if c.description.is_empty()));
            let _ = tag.remove_user_text("comment"); // formato alternativo, ver ler()
            if !valor.is_empty() {
                tag.insert(Frame::Comment(CommentFrame::new(TextEncoding::UTF8, IDIOMA, "", valor.to_string())));
            }
        }
        Campo::Letra => {
            // troca só a letra que o Tagger mostra; letras com outra descrição ficam
            let exibida = letra_exibida(tag)
                .map(|u| (u.language, u.description.to_string(), u.content.to_string()));
            if let Some((idioma, descricao, conteudo)) = exibida {
                let mut removida = false;
                tag.retain(|f| {
                    let igual = !removida
                        && matches!(f, Frame::UnsynchronizedText(u)
                            if u.language == idioma && u.description == descricao && u.content == conteudo);
                    removida |= igual;
                    !igual
                });
            }
            if !valor.is_empty() {
                tag.insert(Frame::UnsynchronizedText(UnsynchronizedTextFrame::new(
                    TextEncoding::UTF8,
                    IDIOMA,
                    "",
                    valor.to_string(),
                )));
            }
        }
        Campo::Data => {
            for id in ["TDRC", "TYER", "TDAT", "TIME"] {
                let _ = tag.remove(&frame_id(id)).count();
            }
            if !valor.is_empty() {
                // como Timestamp, a lofty grava TYER/TDAT/TIME no ID3v2.3 e TDRC no v2.4
                let frame = match Timestamp::from_str(valor) {
                    Ok(ts) => Frame::Timestamp(TimestampFrame::new(frame_id("TDRC"), TextEncoding::UTF8, ts)),
                    Err(_) => Frame::Text(TextInformationFrame::new(frame_id("TDRC"), TextEncoding::UTF8, valor.to_string())),
                };
                tag.insert(frame);
            }
        }
        _ => {
            let id = frame_id(id_do_campo(campo));
            let _ = tag.remove(&id).count();
            if !valor.is_empty() {
                let texto = super::dividir_valores(campo, valor, multivalor).join("\0");
                tag.insert(Frame::Text(TextInformationFrame::new(id, TextEncoding::UTF8, texto)));
            }
        }
    }
}

// ---------------------------------------------------------------- capa
fn imagens(tag: &Id3v2Tag) -> Vec<&AttachedPictureFrame<'_>> {
    tag.iter().filter_map(|f| if let Frame::Picture(p) = f { Some(p) } else { None }).collect()
}

fn frames_capa(tag: &Id3v2Tag) -> Vec<AttachedPictureFrame<'static>> {
    let todas = imagens(tag);
    let tipos: Vec<u8> = todas.iter().map(|p| p.picture.pic_type().as_u8()).collect();
    escolher_capa(&tipos)
        .into_iter()
        .map(|i| AttachedPictureFrame::new(todas[i].encoding, todas[i].picture.clone().into_owned()))
        .collect()
}

pub(super) fn capas(tag: &Id3v2Tag) -> Vec<(Vec<u8>, String)> {
    frames_capa(tag)
        .iter()
        .map(|p| (p.picture.data().to_vec(), p.picture.mime_type().map(|m| m.as_str().to_string()).unwrap_or_default()))
        .collect()
}

/// Descrição para a nova capa que não sobrescreva outra imagem (a chave do APIC é a descrição).
fn descricao_livre(tag: &Id3v2Tag) -> String {
    let usadas: Vec<String> =
        imagens(tag).iter().map(|p| p.picture.description().unwrap_or("").to_string()).collect();
    ["".to_string(), "Cover".to_string()]
        .into_iter()
        .chain((2..100).map(|n| format!("Cover {n}")))
        .find(|d| !usadas.contains(d))
        .unwrap_or_else(|| "Cover 100".into())
}

/// Só a capa é trocada/removida; contracapa, foto do artista etc. ficam.
pub(super) fn aplicar_capa(tag: &mut Id3v2Tag, capa: &AcaoCapa) {
    let remover: Vec<Picture> = frames_capa(tag).into_iter().map(|p| p.picture.into_owned()).collect();
    tag.retain(|f| !matches!(f, Frame::Picture(p) if remover.contains(&p.picture)));
    if let AcaoCapa::Definir { dados, mime } = capa {
        let descricao = descricao_livre(tag);
        let picture = Picture::unchecked(dados.clone())
            .pic_type(PictureType::CoverFront)
            .mime_type(MimeType::from_str(mime))
            .description(descricao)
            .build();
        tag.insert(Frame::Picture(AttachedPictureFrame::new(TextEncoding::UTF8, picture)));
    }
}

// ---------------------------------------------------------------- gravação
/// O ID3v1 como o mutagen o atualiza (`v1=1`): título, artista, álbum, ano, comentário, faixa e
/// gênero a partir da v2. A lofty só regrava o v1 que leu, sem tocar no conteúdo.
fn id3v1_da_v2(tag: &Id3v2Tag, antigo: &Id3v1Tag) -> Id3v1Tag {
    let primeiro = |campo: Campo| {
        let v = ler(tag, campo);
        let p = v.split(SEPARADOR).next().unwrap_or("").to_string();
        if p.is_empty() { None } else { Some(p) }
    };
    let mut novo = antigo.clone();
    novo.title = primeiro(Campo::Titulo);
    novo.artist = primeiro(Campo::Artista);
    novo.album = primeiro(Campo::Album);
    novo.year = primeiro(Campo::Data).and_then(|d| d.get(..4).and_then(|a| a.parse().ok()));
    novo.comment = primeiro(Campo::Comentario);
    novo.track_number = primeiro(Campo::Faixa).and_then(|f| f.split('/').next().and_then(|n| n.parse().ok()));
    novo.genre = primeiro(Campo::Genero).and_then(|g| GENRES.iter().position(|x| x.eq_ignore_ascii_case(&g)).map(|i| i as u8));
    novo
}

pub(super) fn gravar_mp3(
    caminho: &Path,
    arquivo: &mut MpegFile,
    opcoes: OpcoesGravacao,
    remover_id3v1: bool,
) -> Resultado<()> {
    let escrita: WriteOptions = opcoes.escrita();
    let remover_v1 = opcoes.remover_id3v1 || remover_id3v1;
    if remover_v1 {
        arquivo.remove_id3v1();
    } else if let (Some(v2), Some(v1)) = (arquivo.id3v2(), arquivo.id3v1()) {
        let novo = id3v1_da_v2(v2, v1);
        arquivo.set_id3v1(novo);
    }
    if let Some(tag) = arquivo.id3v2_mut() {
        // O CRC/restrições de um cabeçalho estendido lido não são regravados: a lofty 0.25.5 escreve o
        // cabeçalho estendido sempre no layout do v2.4, o que corromperia uma tag v2.3.
        let mut flags = *tag.flags();
        flags.crc = false;
        flags.restrictions = None;
        tag.set_flags(flags);
    }
    if arquivo.id3v2().is_none() {
        // só havia o ID3v1 (limpeza)
        if remover_v1 {
            TagType::Id3v1.remove_from(&mut File::options().read(true).write(true).open(caminho)?, escrita)?;
        }
        return Ok(());
    }
    arquivo.save_to(&mut File::options().read(true).write(true).open(caminho)?, escrita)?;
    if remover_v1 && termina_em_id3v1(caminho) {
        TagType::Id3v1.remove_from(&mut File::options().read(true).write(true).open(caminho)?, escrita)?;
    }
    Ok(())
}

pub(super) fn termina_em_id3v1(caminho: &Path) -> bool {
    let Ok(mut f) = File::open(caminho) else { return false };
    if f.seek(SeekFrom::End(-128)).is_err() {
        return false;
    }
    let mut marca = [0u8; 3];
    f.read_exact(&mut marca).is_ok() && &marca == b"TAG"
}

// ---------------------------------------------------------------- limpeza
fn desconhecido(f: &Frame<'_>) -> bool {
    matches!(f, Frame::Binary(_)) && !BINARIOS_CONHECIDOS.contains(&f.id_str())
}

fn e_extra(f: &Frame<'_>) -> bool {
    match f {
        Frame::UserText(t) => t.description != "comment", // TXXX:comment é lido como Comentário
        _ => !FRAMES_DO_TAGGER.contains(&f.id_str()),
    }
}

/// (quantidade de frames desconhecidos, {frame_id: quantidade} dos extras).
pub(super) fn extras(tag: &Id3v2Tag) -> (usize, std::collections::BTreeMap<String, usize>) {
    let mut desconhecidos = 0;
    let mut extras = std::collections::BTreeMap::new();
    for f in tag.iter() {
        if desconhecido(f) {
            desconhecidos += 1;
        } else if e_extra(f) {
            *extras.entry(f.id_str().to_string()).or_insert(0) += 1;
        }
    }
    (desconhecidos, extras)
}

/// Remove desconhecidos e/ou extras. Devolve true se removeu algo.
pub(super) fn limpar(tag: &mut Id3v2Tag, desconhecidos: bool, extras: bool) -> bool {
    let antes = tag.len();
    tag.retain(|f| {
        if desconhecido(f) {
            !desconhecidos
        } else if e_extra(f) {
            !extras
        } else {
            true
        }
    });
    tag.len() != antes
}
