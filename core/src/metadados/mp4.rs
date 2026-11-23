//! Tags MP4/iTunes: .m4a e .mp4. Porte de `tagger/nucleo/formatos/mp4.py`:
//! - texto em átomos ©nam, ©ART...; vários dados no átomo = multivalor;
//! - faixa/disco são pares (trkn/disk): "3/12" <-> (3, 12); só "3" <-> (3, 0);
//! - letrista e gravadora em átomos livres (----:com.apple.iTunes:LYRICIST / LABEL), como o Picard;
//! - capa: covr é uma lista sem tipo; "a capa" é a 1ª imagem; só JPEG e PNG;
//! - comentário e letra: só o 1º valor é do Tagger;
//! - átomos técnicos (gapless, normalização, compilação, BPM...) nunca são "extras".
//! - gênero numérico antigo (gnre): lido se não houver ©gen (lido sem as conversões da lofty);
//!   gravar o gênero apaga os dois.

use std::collections::BTreeMap;

use lofty::mp4::{Atom, AtomData, AtomIdent, Ilst};
use lofty::picture::{MimeType, Picture, PictureType};
use lofty::prelude::Accessor;

use super::{AcaoCapa, Campo, Erro, Resultado};

const LIVRE: &str = "com.apple.iTunes";

fn atomo(campo: Campo) -> AtomIdent<'static> {
    let fourcc = |b: &[u8; 4]| AtomIdent::Fourcc(*b);
    match campo {
        Campo::Titulo => fourcc(b"\xa9nam"),
        Campo::Artista => fourcc(b"\xa9ART"),
        Campo::Album => fourcc(b"\xa9alb"),
        Campo::ArtistaAlbum => fourcc(b"aART"),
        Campo::Faixa => fourcc(b"trkn"),
        Campo::Disco => fourcc(b"disk"),
        Campo::Data => fourcc(b"\xa9day"),
        Campo::Genero => fourcc(b"\xa9gen"),
        Campo::Compositor => fourcc(b"\xa9wrt"),
        Campo::Letrista => AtomIdent::Freeform { mean: LIVRE.into(), name: "LYRICIST".into() },
        Campo::Comentario => fourcc(b"\xa9cmt"),
        Campo::Letra => fourcc(b"\xa9lyr"),
        Campo::Gravadora => AtomIdent::Freeform { mean: LIVRE.into(), name: "LABEL".into() },
    }
}

const GNRE: AtomIdent<'static> = AtomIdent::Fourcc(*b"gnre");

fn so_primeiro(campo: Campo) -> bool {
    matches!(campo, Campo::Comentario | Campo::Letra)
}

fn textos(atomo: &Atom<'_>) -> Vec<String> {
    atomo
        .data()
        .filter_map(|d| match d {
            AtomData::UTF8(s) | AtomData::UTF16(s) => Some(s.clone()),
            AtomData::Unknown { data, .. } => Some(String::from_utf8_lossy(data).into_owned()),
            _ => None,
        })
        .collect()
}

fn par(tag: &Ilst, campo: Campo) -> (Option<u32>, Option<u32>) {
    if campo == Campo::Faixa { (tag.track(), tag.track_total()) } else { (tag.disk(), tag.disk_total()) }
}

pub(super) fn ler(tag: &Ilst, campo: Campo) -> Vec<String> {
    if matches!(campo, Campo::Faixa | Campo::Disco) {
        return match par(tag, campo) {
            (Some(0), _) => Vec::new(),
            (Some(n), Some(t)) if t > 0 => vec![format!("{n}/{t}")],
            (Some(n), _) => vec![n.to_string()],
            _ => Vec::new(),
        };
    }
    let Some(a) = tag.get(&atomo(campo)) else {
        if campo == Campo::Genero {
            return genero_antigo(tag).into_iter().collect();
        }
        return Vec::new();
    };
    let v = textos(a);
    if so_primeiro(campo) { v.into_iter().take(1).collect() } else { v }
}

/// gnre: índice (1 = o 1º gênero do ID3v1) em 2 bytes.
fn genero_antigo(tag: &Ilst) -> Option<String> {
    let a = tag.get(&GNRE)?;
    let indice = a.data().find_map(|d| match d {
        AtomData::Unknown { data, .. } if data.len() >= 2 => Some(u16::from_be_bytes([data[0], data[1]]) as usize),
        AtomData::UnsignedInteger(n) => Some(*n as usize),
        AtomData::SignedInteger(n) => Some(*n as usize),
        _ => None,
    })?;
    lofty::id3::v1::GENRES.get(indice.checked_sub(1)?).map(|g| g.to_string())
}

pub(super) fn gravar(tag: &mut Ilst, campo: Campo, valores: &[String]) {
    if matches!(campo, Campo::Faixa | Campo::Disco) {
        if campo == Campo::Faixa { tag.remove_track() } else { tag.remove_disk() }
        let Some(primeiro) = valores.first() else { return };
        let (n, t) = primeiro.split_once('/').unwrap_or((primeiro.as_str(), ""));
        let (n, t): (u32, u32) = (n.trim().parse().unwrap_or(0), t.trim().parse().unwrap_or(0));
        if campo == Campo::Faixa {
            tag.set_track(n);
            if t > 0 {
                tag.set_track_total(t);
            }
        } else {
            tag.set_disk(n);
            if t > 0 {
                tag.set_disk_total(t);
            }
        }
        return;
    }
    let ident = atomo(campo);
    let antigos: Vec<String> = tag.get(&ident).map(textos).unwrap_or_default();
    let _ = tag.remove(&ident).count();
    if campo == Campo::Genero {
        let _ = tag.remove(&GNRE).count();
    }
    let mut novos = valores.to_vec();
    if so_primeiro(campo) {
        novos.extend(antigos.into_iter().skip(1));
    }
    if novos.is_empty() {
        return;
    }
    let dados = novos.into_iter().map(AtomData::UTF8).collect();
    if let Some(a) = Atom::from_collection(ident, dados) {
        tag.insert(a);
    }
}

// ---------------------------------------------------------------- capa
pub(super) fn verificar_mime(mime: &str) -> Resultado<()> {
    if matches!(mime, "image/jpeg" | "image/jpg" | "image/png") {
        Ok(())
    } else {
        Err(Erro::CapaInvalida(format!("A capa de um arquivo M4A/MP4 precisa ser JPEG ou PNG (veio {mime}).")))
    }
}

fn mime_de(p: &Picture) -> String {
    match p.mime_type() {
        Some(MimeType::Jpeg) => "image/jpeg".into(),
        Some(MimeType::Png) => "image/png".into(),
        _ => "application/octet-stream".into(),
    }
}

pub(super) fn capas(tag: &Ilst) -> Vec<(Vec<u8>, String)> {
    tag.pictures().and_then(|mut p| p.next()).map(|p| vec![(p.data().to_vec(), mime_de(p))]).unwrap_or_default()
}

/// Troca/remove só a 1ª imagem (a capa); as outras ficam.
pub(super) fn aplicar_capa(tag: &mut Ilst, capa: &AcaoCapa) -> Resultado<()> {
    let resto: Vec<Picture> = tag.pictures().map(|p| p.skip(1).cloned().collect()).unwrap_or_default();
    tag.remove_pictures();
    if let AcaoCapa::Definir { dados, mime } = capa {
        verificar_mime(mime)?;
        let tipo = if mime == "image/png" { MimeType::Png } else { MimeType::Jpeg };
        tag.insert_picture(Picture::unchecked(dados.clone()).pic_type(PictureType::Other).mime_type(tipo).build());
    }
    for p in resto {
        tag.insert_picture(p);
    }
    Ok(())
}

// ---------------------------------------------------------------- limpeza
const TECNICOS: [&[u8; 4]; 6] = [b"pgap", b"cpil", b"stik", b"tmpo", b"rtng", b"hdvd"];
const TECNICOS_LIVRES: [&str; 3] = ["iTunSMPB", "iTunNORM", "Encoding Params"];

/// Nome do átomo como o mutagen escreve (fourcc em latin-1, ex.: "©too"; livre: "----:mean:name").
fn nome(ident: &AtomIdent<'_>) -> String {
    match ident {
        AtomIdent::Fourcc(b) => b.iter().map(|&c| c as char).collect(),
        AtomIdent::Freeform { mean, name } => format!("----:{mean}:{name}"),
    }
}

fn do_tagger(ident: &AtomIdent<'_>) -> bool {
    Campo::TODOS.into_iter().any(|c| atomo(c) == *ident) || *ident == AtomIdent::Fourcc(*b"covr") || *ident == GNRE
}

fn tecnico(ident: &AtomIdent<'_>) -> bool {
    match ident {
        AtomIdent::Fourcc(b) => TECNICOS.contains(&b),
        AtomIdent::Freeform { name, .. } => TECNICOS_LIVRES.contains(&name.as_ref()),
    }
}

fn idents_extras(tag: &Ilst) -> Vec<AtomIdent<'static>> {
    tag.into_iter()
        .map(|a| a.ident().clone().into_owned())
        .filter(|i| !do_tagger(i) && !tecnico(i))
        .collect()
}

pub(super) fn extras(tag: &Ilst) -> BTreeMap<String, usize> {
    tag.into_iter()
        .filter(|a| !do_tagger(a.ident()) && !tecnico(a.ident()))
        .map(|a| (nome(a.ident()), a.data().count().max(1)))
        .collect()
}

pub(super) fn remover_extras(tag: &mut Ilst) -> bool {
    let idents = idents_extras(tag);
    for i in &idents {
        let _ = tag.remove(i).count();
    }
    !idents.is_empty()
}
