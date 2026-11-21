//! Núcleo do spike: leitura e gravação de tags com a crate lofty (MP3, FLAC e M4A).
//!
//! Cada formato é editado pelo seu tipo concreto da lofty (Id3v2Tag, VorbisComments, Ilst), e não
//! pelo `Tag` genérico: o genérico converte as tags para um modelo comum e, ao gravar, perde o que
//! não sabe mapear (TXXX, PRIV, átomos freeform...). Editando o tipo concreto, só o campo pedido muda.
//!
//! Semântica igual à da v2 (tagger/nucleo/metadata.py):
//! - valor vazio remove o campo;
//! - "A; B" vira vários valores no artista (multivalor);
//! - a capa é a imagem frontal (tipo 3); sem frontal, a 1ª do tipo "outra" (0). Trocar a capa não
//!   mexe nas outras imagens (contracapa, artista...). No M4A não há tipo de imagem: é a 1ª do covr;
//! - MP3 grava ID3v2.4 por padrão (Opcoes), ou ID3v2.3 como a v2; valores múltiplos separados por nulo.

use std::fs::File;
use std::path::Path;

use lofty::config::{ParseOptions, WriteOptions};
use lofty::file::AudioFile;
use lofty::flac::FlacFile;
use lofty::id3::v2::{AttachedPictureFrame, Frame, FrameId, Id3v2Tag, TextInformationFrame};
use lofty::mp4::{AtomData, AtomIdent, Ilst, Mp4File};
use lofty::mpeg::MpegFile;
use lofty::ogg::OggPictureStorage;
use lofty::ogg::tag::VorbisComments;
use lofty::picture::{MimeType, Picture, PictureInformation, PictureType};
use lofty::prelude::Accessor;
use lofty::TextEncoding;
use serde::Serialize;

pub const SEPARADOR: &str = "; ";

/// Campos que o spike mostra e edita.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Campo {
    Titulo,
    Artista,
    Faixa,
    Gravadora,
}

impl Campo {
    pub fn de_nome(nome: &str) -> Option<Campo> {
        match nome {
            "titulo" => Some(Campo::Titulo),
            "artista" => Some(Campo::Artista),
            "faixa" => Some(Campo::Faixa),
            "gravadora" => Some(Campo::Gravadora),
            _ => None,
        }
    }

    fn multivalor(self) -> bool {
        self == Campo::Artista
    }
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize)]
pub struct Capa {
    pub mime: String,
    pub dados: Vec<u8>,
}

#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize)]
pub struct Tags {
    pub formato: String,
    pub titulo: String,
    pub artista: String,
    pub faixa: String,
    pub gravadora: String,
    pub capa: Option<Capa>,
}

/// Uma imagem embutida, para conferir que trocar a capa não apaga as outras.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Imagem {
    pub tipo: u8,
    pub mime: String,
    pub tamanho: usize,
}

#[derive(Debug)]
pub enum Erro {
    FormatoNaoSuportado(String),
    Lofty(String),
    Io(std::io::Error),
}

impl std::fmt::Display for Erro {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Erro::FormatoNaoSuportado(ext) => write!(f, "formato não suportado: {ext}"),
            Erro::Lofty(e) => write!(f, "{e}"),
            Erro::Io(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for Erro {}

impl From<lofty::error::FileParseError> for Erro {
    fn from(e: lofty::error::FileParseError) -> Self {
        Erro::Lofty(e.to_string())
    }
}

impl From<lofty::error::FileEncodingError> for Erro {
    fn from(e: lofty::error::FileEncodingError) -> Self {
        Erro::Lofty(e.to_string())
    }
}

impl From<std::io::Error> for Erro {
    fn from(e: std::io::Error) -> Self {
        Erro::Io(e)
    }
}

pub type Resultado<T> = Result<T, Erro>;

#[derive(Clone, Copy, PartialEq, Eq)]
enum Formato {
    Mp3,
    Flac,
    M4a,
}

fn formato(caminho: &Path) -> Resultado<Formato> {
    let ext = caminho.extension().and_then(|e| e.to_str()).unwrap_or("").to_lowercase();
    match ext.as_str() {
        "mp3" => Ok(Formato::Mp3),
        "flac" => Ok(Formato::Flac),
        "m4a" | "mp4" => Ok(Formato::M4a),
        _ => Err(Erro::FormatoNaoSuportado(ext)),
    }
}

fn dividir(campo: Campo, valor: &str) -> Vec<String> {
    if !campo.multivalor() {
        return vec![valor.to_string()];
    }
    let partes: Vec<String> = valor.split(';').map(|p| p.trim().to_string()).filter(|p| !p.is_empty()).collect();
    if partes.is_empty() { vec![valor.to_string()] } else { partes }
}

/// Opções de gravação (como OpcoesGravacao na v2). `versao_id3`: 3 ou 4, só para MP3.
/// O padrão é 4: com a lofty, o ID3v2.3 corrompe gênero multivalor (veja docs/spike/tauri.md).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Opcoes {
    pub versao_id3: u8,
}

impl Default for Opcoes {
    fn default() -> Self {
        Opcoes { versao_id3: 4 }
    }
}

fn opcoes_gravacao(opcoes: Opcoes) -> WriteOptions {
    WriteOptions::default().use_id3v23(opcoes.versao_id3 == 3)
}

/// Leitura do MP3 sem as "conversões implícitas" da lofty. Com elas, um TDRC com data completa
/// numa tag ID3v2.3 (o que a v2/mutagen grava) é descartado na leitura (read.rs, construct_tdrc_from_v3:
/// o frame é removido e, se já tem mês, não volta) e some ao gravar.
fn opcoes_leitura_mp3() -> ParseOptions {
    ParseOptions::new().implicit_conversions(false)
}

fn abrir(caminho: &Path) -> Resultado<File> {
    Ok(File::options().read(true).write(true).open(caminho)?)
}

// ---------------------------------------------------------------- capa (regra da v2)
fn tipo_capa(imagens: &[(u8, usize)]) -> Vec<usize> {
    let frontais: Vec<usize> = imagens.iter().filter(|(t, _)| *t == 3).map(|(_, i)| *i).collect();
    if !frontais.is_empty() {
        return frontais;
    }
    imagens.iter().filter(|(t, _)| *t == 0).map(|(_, i)| *i).take(1).collect()
}

fn capa_de(picture: &Picture) -> Capa {
    Capa {
        mime: picture.mime_type().map(|m| m.as_str().to_string()).unwrap_or_default(),
        dados: picture.data().to_vec(),
    }
}

fn nova_imagem(dados: &[u8], mime: &str, tipo: PictureType) -> Picture {
    Picture::unchecked(dados.to_vec()).pic_type(tipo).mime_type(MimeType::from_str(mime)).build()
}

// ---------------------------------------------------------------- MP3 (ID3v2)
fn id_mp3(campo: Campo) -> FrameId<'static> {
    let id = match campo {
        Campo::Titulo => "TIT2",
        Campo::Artista => "TPE1",
        Campo::Faixa => "TRCK",
        Campo::Gravadora => "TPUB",
    };
    FrameId::new(id).expect("frame id válido")
}

fn ler_mp3_campo(tag: &Id3v2Tag, campo: Campo) -> String {
    tag.get_texts(&id_mp3(campo)).map(|v| v.collect::<Vec<_>>().join(SEPARADOR)).unwrap_or_default()
}

fn capas_mp3(tag: &Id3v2Tag) -> Vec<&Picture> {
    let imagens: Vec<&Picture> = tag
        .iter()
        .filter_map(|f| if let Frame::Picture(p) = f { Some(&*p.picture) } else { None })
        .collect();
    let tipos: Vec<(u8, usize)> = imagens.iter().enumerate().map(|(i, p)| (p.pic_type().as_u8(), i)).collect();
    tipo_capa(&tipos).into_iter().map(|i| imagens[i]).collect()
}

fn ler_mp3(caminho: &Path) -> Resultado<Tags> {
    let arquivo = MpegFile::read_from(&mut File::open(caminho)?, opcoes_leitura_mp3())?;
    let mut tags = Tags { formato: "mp3".into(), ..Default::default() };
    if let Some(tag) = arquivo.id3v2() {
        tags.titulo = ler_mp3_campo(tag, Campo::Titulo);
        tags.artista = ler_mp3_campo(tag, Campo::Artista);
        tags.faixa = ler_mp3_campo(tag, Campo::Faixa);
        tags.gravadora = ler_mp3_campo(tag, Campo::Gravadora);
        tags.capa = capas_mp3(tag).first().map(|p| capa_de(p));
    }
    Ok(tags)
}

fn editar_mp3(caminho: &Path, opcoes: Opcoes, editar: impl FnOnce(&mut Id3v2Tag)) -> Resultado<()> {
    let mut arquivo = MpegFile::read_from(&mut File::open(caminho)?, opcoes_leitura_mp3())?;
    if arquivo.id3v2().is_none() {
        arquivo.set_id3v2(Id3v2Tag::new());
    }
    editar(arquivo.id3v2_mut().expect("acabou de ser criado"));
    arquivo.save_to(&mut abrir(caminho)?, opcoes_gravacao(opcoes))?;
    Ok(())
}

fn gravar_mp3(caminho: &Path, opcoes: Opcoes, campo: Campo, valor: &str) -> Resultado<()> {
    editar_mp3(caminho, opcoes, |tag| {
        let id = id_mp3(campo);
        let _ = tag.remove(&id).count();
        if !valor.is_empty() {
            let texto = dividir(campo, valor).join("\0");
            tag.insert(Frame::Text(TextInformationFrame::new(id, TextEncoding::UTF16, texto)));
        }
    })
}

fn capa_mp3(caminho: &Path, opcoes: Opcoes, dados: &[u8], mime: &str) -> Resultado<()> {
    editar_mp3(caminho, opcoes, |tag| {
        let remover: Vec<Picture> = capas_mp3(tag).into_iter().cloned().collect();
        tag.retain(|f| !matches!(f, Frame::Picture(p) if remover.contains(&*p.picture)));
        let picture = nova_imagem(dados, mime, PictureType::CoverFront);
        // APIC com descrição livre: a chave do APIC é a descrição, então outra imagem com "" não é sobrescrita
        let usadas: Vec<String> = tag
            .iter()
            .filter_map(|f| if let Frame::Picture(p) = f { Some(p.picture.description().unwrap_or("").to_string()) } else { None })
            .collect();
        let descricao = ["", "Cover"].iter().map(|s| s.to_string())
            .chain((2..100).map(|n| format!("Cover {n}")))
            .find(|d| !usadas.contains(d))
            .unwrap_or_else(|| "Cover 100".into());
        let mut picture = picture;
        picture.set_description(if descricao.is_empty() { None } else { Some(descricao) });
        tag.insert(Frame::Picture(AttachedPictureFrame::new(TextEncoding::UTF16, picture)));
    })
}

fn imagens_mp3(caminho: &Path) -> Resultado<Vec<Imagem>> {
    let arquivo = MpegFile::read_from(&mut File::open(caminho)?, opcoes_leitura_mp3())?;
    Ok(arquivo
        .id3v2()
        .map(|tag| {
            tag.iter()
                .filter_map(|f| if let Frame::Picture(p) = f { Some(imagem(&p.picture)) } else { None })
                .collect()
        })
        .unwrap_or_default())
}

fn imagem(p: &Picture) -> Imagem {
    Imagem {
        tipo: p.pic_type().as_u8(),
        mime: p.mime_type().map(|m| m.as_str().to_string()).unwrap_or_default(),
        tamanho: p.data().len(),
    }
}

// ---------------------------------------------------------------- FLAC (Vorbis comments + blocos PICTURE)
fn chaves_flac(campo: Campo) -> &'static [&'static str] {
    // a 1ª chave é a gravada; as outras são lidas (e apagadas ao gravar), como na v2
    match campo {
        Campo::Titulo => &["TITLE"],
        Campo::Artista => &["ARTIST"],
        Campo::Faixa => &["TRACKNUMBER"],
        Campo::Gravadora => &["ORGANIZATION", "LABEL"],
    }
}

fn ler_flac_campo(tag: &VorbisComments, campo: Campo) -> String {
    for chave in chaves_flac(campo) {
        let valores: Vec<&str> = tag.get_all(chave).collect();
        if !valores.is_empty() {
            let texto = valores.join(SEPARADOR);
            if campo == Campo::Faixa {
                if let Some(total) = tag.get("TRACKTOTAL").or_else(|| tag.get("TOTALTRACKS")) {
                    if !texto.contains('/') {
                        return format!("{texto}/{total}");
                    }
                }
            }
            return texto;
        }
    }
    String::new()
}

fn imagens_flac_todas(arquivo: &FlacFile) -> Vec<&Picture> {
    // a lofty guarda os blocos PICTURE no FlacFile e as imagens METADATA_BLOCK_PICTURE dentro dos comentários
    let mut lista: Vec<&Picture> = arquivo.pictures().iter().map(|(p, _)| p).collect();
    if let Some(tag) = arquivo.vorbis_comments() {
        lista.extend(tag.pictures().iter().map(|(p, _)| p));
    }
    lista
}

fn ler_flac(caminho: &Path) -> Resultado<Tags> {
    let arquivo = FlacFile::read_from(&mut File::open(caminho)?, ParseOptions::new())?;
    let mut tags = Tags { formato: "flac".into(), ..Default::default() };
    if let Some(tag) = arquivo.vorbis_comments() {
        tags.titulo = ler_flac_campo(tag, Campo::Titulo);
        tags.artista = ler_flac_campo(tag, Campo::Artista);
        tags.faixa = ler_flac_campo(tag, Campo::Faixa);
        tags.gravadora = ler_flac_campo(tag, Campo::Gravadora);
    }
    let imagens = imagens_flac_todas(&arquivo);
    let tipos: Vec<(u8, usize)> = imagens.iter().enumerate().map(|(i, p)| (p.pic_type().as_u8(), i)).collect();
    tags.capa = tipo_capa(&tipos).first().map(|&i| capa_de(imagens[i]));
    Ok(tags)
}

fn editar_flac(caminho: &Path, opcoes: Opcoes, editar: impl FnOnce(&mut FlacFile)) -> Resultado<()> {
    let mut arquivo = FlacFile::read_from(&mut File::open(caminho)?, ParseOptions::new())?;
    if arquivo.vorbis_comments().is_none() {
        arquivo.set_vorbis_comments(VorbisComments::default());
    }
    editar(&mut arquivo);
    arquivo.save_to(&mut abrir(caminho)?, opcoes_gravacao(opcoes))?;
    Ok(())
}

fn gravar_flac(caminho: &Path, opcoes: Opcoes, campo: Campo, valor: &str) -> Resultado<()> {
    editar_flac(caminho, opcoes, |arquivo| {
        let tag = arquivo.vorbis_comments_mut().expect("acabou de ser criado");
        for chave in chaves_flac(campo) {
            let _ = tag.remove(chave).count();
        }
        let (valor, total) = match (campo, valor.split_once('/')) {
            (Campo::Faixa, Some((n, t))) => (n.to_string(), Some(t.to_string())),
            _ => (valor.to_string(), None),
        };
        if campo == Campo::Faixa && valor.is_empty() {
            for chave in ["TRACKTOTAL", "TOTALTRACKS"] {
                let _ = tag.remove(chave).count();
            }
        }
        if !valor.is_empty() {
            for parte in dividir(campo, &valor) {
                tag.push(chaves_flac(campo)[0].to_string(), parte);
            }
        }
        if let Some(total) = total {
            let _ = tag.remove("TOTALTRACKS").count();
            tag.insert("TRACKTOTAL".into(), total);
        }
    })
}

fn capa_flac(caminho: &Path, opcoes: Opcoes, dados: &[u8], mime: &str) -> Resultado<()> {
    editar_flac(caminho, opcoes, |arquivo| {
        // a capa atual pode estar em bloco PICTURE ou em METADATA_BLOCK_PICTURE; troca só ela
        let capas: Vec<Picture> = {
            let imagens = imagens_flac_todas(arquivo);
            let tipos: Vec<(u8, usize)> = imagens.iter().enumerate().map(|(i, p)| (p.pic_type().as_u8(), i)).collect();
            tipo_capa(&tipos).into_iter().map(|i| imagens[i].clone()).collect()
        };
        retirar_imagens(arquivo, &capas);
        if let Some(tag) = arquivo.vorbis_comments_mut() {
            retirar_imagens(tag, &capas);
        }
        // informação explícita: inferir (None) exige um JPEG/PNG decodificável e, se falha, a imagem não entra
        let _ = arquivo.insert_picture(nova_imagem(dados, mime, PictureType::CoverFront), Some(PictureInformation::default()));
    })
}

/// Remove só as imagens dadas. A lofty só sabe remover por tipo (`remove_picture_type`), o que apagaria
/// também outras imagens do mesmo tipo: aqui se tira tudo e se recoloca o que fica.
fn retirar_imagens<S: OggPictureStorage>(armazem: &mut S, remover: &[Picture]) {
    let manter: Vec<_> = armazem.pictures().iter().filter(|(p, _)| !remover.contains(p)).cloned().collect();
    let tipos: Vec<PictureType> = armazem.pictures().iter().map(|(p, _)| p.pic_type()).collect();
    for tipo in tipos {
        armazem.remove_picture_type(tipo);
    }
    for (p, info) in manter {
        let _ = armazem.insert_picture(p, Some(info));
    }
}

fn imagens_flac(caminho: &Path) -> Resultado<Vec<Imagem>> {
    let arquivo = FlacFile::read_from(&mut File::open(caminho)?, ParseOptions::new())?;
    Ok(imagens_flac_todas(&arquivo).into_iter().map(imagem).collect())
}

// ---------------------------------------------------------------- M4A (ilst do iTunes)
fn atomo_m4a(campo: Campo) -> AtomIdent<'static> {
    match campo {
        Campo::Titulo => AtomIdent::Fourcc(*b"\xa9nam"),
        Campo::Artista => AtomIdent::Fourcc(*b"\xa9ART"),
        Campo::Faixa => AtomIdent::Fourcc(*b"trkn"),
        Campo::Gravadora => AtomIdent::Freeform { mean: "com.apple.iTunes".into(), name: "LABEL".into() },
    }
}

fn ler_m4a_campo(tag: &Ilst, campo: Campo) -> String {
    if campo == Campo::Faixa {
        return match (tag.track(), tag.track_total()) {
            (Some(n), Some(t)) if t > 0 => format!("{n}/{t}"),
            (Some(n), _) => n.to_string(),
            _ => String::new(),
        };
    }
    let Some(atomo) = tag.get(&atomo_m4a(campo)) else { return String::new() };
    atomo
        .data()
        .filter_map(|d| match d {
            AtomData::UTF8(s) | AtomData::UTF16(s) => Some(s.as_str()),
            _ => None,
        })
        .collect::<Vec<_>>()
        .join(SEPARADOR)
}

fn ler_m4a(caminho: &Path) -> Resultado<Tags> {
    let arquivo = Mp4File::read_from(&mut File::open(caminho)?, ParseOptions::new())?;
    let mut tags = Tags { formato: "m4a".into(), ..Default::default() };
    if let Some(tag) = arquivo.ilst() {
        tags.titulo = ler_m4a_campo(tag, Campo::Titulo);
        tags.artista = ler_m4a_campo(tag, Campo::Artista);
        tags.faixa = ler_m4a_campo(tag, Campo::Faixa);
        tags.gravadora = ler_m4a_campo(tag, Campo::Gravadora);
        tags.capa = tag.pictures().and_then(|mut p| p.next()).map(capa_de);
    }
    Ok(tags)
}

fn editar_m4a(caminho: &Path, opcoes: Opcoes, editar: impl FnOnce(&mut Ilst)) -> Resultado<()> {
    let mut arquivo = Mp4File::read_from(&mut File::open(caminho)?, ParseOptions::new())?;
    if arquivo.ilst().is_none() {
        arquivo.set_ilst(Ilst::new());
    }
    editar(arquivo.ilst_mut().expect("acabou de ser criado"));
    arquivo.save_to(&mut abrir(caminho)?, opcoes_gravacao(opcoes))?;
    Ok(())
}

fn gravar_m4a(caminho: &Path, opcoes: Opcoes, campo: Campo, valor: &str) -> Resultado<()> {
    editar_m4a(caminho, opcoes, |tag| {
        if campo == Campo::Faixa {
            // trkn é um par (faixa, total), como no ID3: apagar a faixa apaga o total junto
            tag.remove_track();
            tag.remove_track_total();
            let (n, t) = valor.split_once('/').unwrap_or((valor, ""));
            if let Ok(n) = n.trim().parse() {
                tag.set_track(n);
                if let Ok(t) = t.trim().parse() {
                    tag.set_track_total(t);
                }
            }
            return;
        }
        let ident = atomo_m4a(campo);
        let _ = tag.remove(&ident).count();
        if !valor.is_empty() {
            let dados = dividir(campo, valor).into_iter().map(AtomData::UTF8).collect();
            if let Some(atomo) = lofty::mp4::Atom::from_collection(ident, dados) {
                tag.insert(atomo);
            }
        }
    })
}

fn capa_m4a(caminho: &Path, opcoes: Opcoes, dados: &[u8], mime: &str) -> Resultado<()> {
    editar_m4a(caminho, opcoes, |tag| {
        // M4A não tem tipo de imagem: "a capa" é a 1ª do covr; as demais ficam
        let resto: Vec<Picture> = tag.pictures().map(|p| p.skip(1).cloned().collect()).unwrap_or_default();
        tag.remove_pictures();
        tag.insert_picture(nova_imagem(dados, mime, PictureType::Other));
        for p in resto {
            tag.insert_picture(p);
        }
    })
}

fn imagens_m4a(caminho: &Path) -> Resultado<Vec<Imagem>> {
    let arquivo = Mp4File::read_from(&mut File::open(caminho)?, ParseOptions::new())?;
    Ok(arquivo
        .ilst()
        .and_then(|t| t.pictures().map(|p| p.map(imagem).collect()))
        .unwrap_or_default())
}

// ---------------------------------------------------------------- API pública
/// Lê os campos do spike e a capa. Nunca grava nada.
pub fn ler(caminho: &Path) -> Resultado<Tags> {
    match formato(caminho)? {
        Formato::Mp3 => ler_mp3(caminho),
        Formato::Flac => ler_flac(caminho),
        Formato::M4a => ler_m4a(caminho),
    }
}

/// Grava um campo (vazio = remove), num único save; o resto do arquivo não é tocado.
pub fn gravar(caminho: &Path, campo: Campo, valor: &str, opcoes: Opcoes) -> Resultado<()> {
    match formato(caminho)? {
        Formato::Mp3 => gravar_mp3(caminho, opcoes, campo, valor),
        Formato::Flac => gravar_flac(caminho, opcoes, campo, valor),
        Formato::M4a => gravar_m4a(caminho, opcoes, campo, valor),
    }
}

/// Troca só a capa frontal; contracapa e outras imagens ficam.
pub fn definir_capa(caminho: &Path, dados: &[u8], mime: &str, opcoes: Opcoes) -> Resultado<()> {
    match formato(caminho)? {
        Formato::Mp3 => capa_mp3(caminho, opcoes, dados, mime),
        Formato::Flac => capa_flac(caminho, opcoes, dados, mime),
        Formato::M4a => capa_m4a(caminho, opcoes, dados, mime),
    }
}

/// Todas as imagens embutidas (tipo, mime, tamanho), na ordem do arquivo.
pub fn imagens(caminho: &Path) -> Resultado<Vec<Imagem>> {
    match formato(caminho)? {
        Formato::Mp3 => imagens_mp3(caminho),
        Formato::Flac => imagens_flac(caminho),
        Formato::M4a => imagens_m4a(caminho),
    }
}

pub mod amostras;
pub mod cli;
