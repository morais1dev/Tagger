//! Vorbis comments: FLAC (.flac) e Ogg (.ogg: Vorbis, Opus ou FLAC dentro do Ogg).
//! Porte de `tagger/nucleo/formatos/vorbis.py`; a regra completa está lá:
//! - faixa/disco "3/12" = TRACKNUMBER=3 + TRACKTOTAL=12; gravar só "4" mantém o total; apagar
//!   a faixa apaga o total;
//! - nomes alternativos (DESCRIPTION, UNSYNCEDLYRICS, "ALBUM ARTIST", LABEL) lidos só se o principal
//!   faltar; ao gravar sai a alternativa exibida ou uma cópia do mesmo valor, mas não uma com outro conteúdo;
//! - comentário e letra: só o 1º valor é do Tagger;
//! - capa: no FLAC, blocos PICTURE; no Ogg, METADATA_BLOCK_PICTURE (a lofty já decodifica). O COVERART
//!   antigo a lofty converte numa imagem do tipo "outra" (conta como capa só se não houver outra) e não
//!   o regrava, então ele sai do arquivo na primeira gravação.

use std::collections::BTreeMap;

use lofty::flac::FlacFile;
use lofty::ogg::OggPictureStorage;
use lofty::ogg::tag::VorbisComments;
use lofty::picture::{MimeType, Picture, PictureInformation, PictureType};

use super::{AcaoCapa, Campo, escolher_capa};

fn principal(campo: Campo) -> &'static str {
    match campo {
        Campo::Titulo => "TITLE",
        Campo::Artista => "ARTIST",
        Campo::Album => "ALBUM",
        Campo::ArtistaAlbum => "ALBUMARTIST",
        Campo::Faixa => "TRACKNUMBER",
        Campo::Disco => "DISCNUMBER",
        Campo::Data => "DATE",
        Campo::Genero => "GENRE",
        Campo::Compositor => "COMPOSER",
        Campo::Letrista => "LYRICIST",
        Campo::Comentario => "COMMENT",
        Campo::Letra => "LYRICS",
        Campo::Gravadora => "ORGANIZATION",
    }
}

fn alternativas(campo: Campo) -> &'static [&'static str] {
    match campo {
        Campo::ArtistaAlbum => &["ALBUM ARTIST"],
        Campo::Comentario => &["DESCRIPTION"],
        Campo::Gravadora => &["LABEL"],
        Campo::Letra => &["UNSYNCEDLYRICS"],
        _ => &[],
    }
}

/// Total de faixas/discos: o 1º nome é o que o Tagger grava.
fn totais(campo: Campo) -> &'static [&'static str] {
    match campo {
        Campo::Faixa => &["TRACKTOTAL", "TOTALTRACKS"],
        Campo::Disco => &["DISCTOTAL", "TOTALDISCS"],
        _ => &[],
    }
}

fn so_primeiro(campo: Campo) -> bool {
    matches!(campo, Campo::Comentario | Campo::Letra)
}

fn nomes(campo: Campo) -> Vec<&'static str> {
    let mut v = vec![principal(campo)];
    v.extend_from_slice(alternativas(campo));
    v
}

fn chaves_do_tagger() -> Vec<&'static str> {
    let mut v = Vec::new();
    for campo in Campo::TODOS {
        v.extend(nomes(campo));
        v.extend_from_slice(totais(campo));
    }
    v.extend(["METADATA_BLOCK_PICTURE", "COVERART", "COVERARTMIME"]);
    v
}

fn valores(tag: &VorbisComments, chave: &str) -> Vec<String> {
    tag.get_all(chave).map(str::to_string).collect()
}

/// (chave, valores) de onde o campo é lido: o nome principal, senão a 1ª alternativa com valor.
fn fonte(tag: &VorbisComments, campo: Campo) -> Option<(&'static str, Vec<String>)> {
    nomes(campo).into_iter().find_map(|chave| {
        let v = valores(tag, chave);
        if v.is_empty() { None } else { Some((chave, v)) }
    })
}

fn apagar(tag: &mut VorbisComments, chave: &str) {
    let _ = tag.remove(chave).count();
}

pub(super) fn ler(tag: &VorbisComments, campo: Campo) -> Vec<String> {
    let Some((_chave, valores)) = fonte(tag, campo) else { return Vec::new() };
    if so_primeiro(campo) {
        return valores[..1].to_vec();
    }
    if !totais(campo).is_empty() {
        let mut numero = valores[0].clone();
        if !numero.contains('/')
            && let Some(total) = totais(campo).iter().find_map(|c| tag.get(c)).filter(|t| !t.is_empty()) {
                numero = format!("{numero}/{total}");
            }
        return vec![numero];
    }
    valores
}

pub(super) fn gravar(tag: &mut VorbisComments, campo: Campo, novos: &[String]) {
    let mut restantes = Vec::new();
    if let Some((chave_fonte, antigos)) = fonte(tag, campo) {
        let exibidos: Vec<String> = if so_primeiro(campo) { antigos[..1].to_vec() } else { antigos.clone() };
        if so_primeiro(campo) {
            restantes = antigos[1..].to_vec();
        }
        apagar(tag, chave_fonte);
        for chave in nomes(campo) {
            if valores(tag, chave) == exibidos {
                apagar(tag, chave); // cópia do mesmo valor com outro nome
            }
        }
    }

    let mut novos = novos.to_vec();
    if !totais(campo).is_empty() {
        let Some(primeiro) = novos.first().cloned() else {
            for chave in totais(campo) {
                apagar(tag, chave);
            }
            return;
        };
        let (numero, total) = primeiro.split_once('/').map_or((primeiro.clone(), String::new()), |(n, t)| (n.into(), t.into()));
        novos = vec![numero];
        if !total.is_empty() {
            for chave in totais(campo) {
                apagar(tag, chave);
            }
            tag.push(totais(campo)[0].to_string(), total);
        }
    }

    for valor in novos.into_iter().chain(restantes) {
        tag.push(principal(campo).to_string(), valor);
    }
}

// ---------------------------------------------------------------- capa
fn capas_de(imagens: &[(Picture, PictureInformation)]) -> Vec<(Vec<u8>, String)> {
    let tipos: Vec<u8> = imagens.iter().map(|(p, _)| p.pic_type().as_u8()).collect();
    escolher_capa(&tipos)
        .into_iter()
        .map(|i| {
            let p = &imagens[i].0;
            (p.data().to_vec(), p.mime_type().map(|m| m.as_str().to_string()).unwrap_or_else(|| "image/jpeg".into()))
        })
        .collect()
}

pub(super) fn capas_flac(f: &FlacFile) -> Vec<(Vec<u8>, String)> {
    capas_de(f.pictures())
}

pub(super) fn capas_ogg(tag: &VorbisComments) -> Vec<(Vec<u8>, String)> {
    capas_de(tag.pictures())
}

fn nova_imagem(dados: &[u8], mime: &str) -> Picture {
    Picture::unchecked(dados.to_vec()).pic_type(PictureType::CoverFront).mime_type(MimeType::from_str(mime)).build()
}

/// Troca só a capa: a lofty remove imagens só por tipo, então tudo sai e o que fica volta, na ordem.
fn aplicar<S: OggPictureStorage>(armazem: &mut S, capa: &AcaoCapa) {
    let imagens: Vec<(Picture, PictureInformation)> = armazem.pictures().to_vec();
    let tipos: Vec<u8> = imagens.iter().map(|(p, _)| p.pic_type().as_u8()).collect();
    let capa_atual = escolher_capa(&tipos);
    for tipo in imagens.iter().map(|(p, _)| p.pic_type()).collect::<Vec<_>>() {
        armazem.remove_picture_type(tipo);
    }
    for (i, (p, info)) in imagens.into_iter().enumerate() {
        if !capa_atual.contains(&i) {
            let _ = armazem.insert_picture(p, Some(info));
        }
    }
    if let AcaoCapa::Definir { dados, mime } = capa {
        // informação explícita: inferir exige um JPEG/PNG decodificável e, se falha, a imagem não entra
        let _ = armazem.insert_picture(nova_imagem(dados, mime), Some(PictureInformation::default()));
    }
}

pub(super) fn aplicar_capa_flac(f: &mut FlacFile, capa: &AcaoCapa) {
    aplicar(f, capa);
}

pub(super) fn aplicar_capa_ogg(tag: &mut VorbisComments, capa: &AcaoCapa) {
    // a capa nova substitui a antiga (COVERART, que a lofty já leu como imagem "outra"); ao remover,
    // o COVERARTMIME só sai se não sobrar capa
    let tinha_capa = !capas_ogg(tag).is_empty();
    aplicar(tag, capa);
    if matches!(capa, AcaoCapa::Definir { .. }) || !tinha_capa || capas_ogg(tag).is_empty() {
        apagar(tag, "COVERART");
        apagar(tag, "COVERARTMIME");
    }
}

// ---------------------------------------------------------------- limpeza
fn chaves_extras(tag: &VorbisComments) -> Vec<String> {
    let do_tagger = chaves_do_tagger();
    let mut chaves: Vec<String> = Vec::new();
    for (k, _) in tag.items() {
        let k = k.to_uppercase();
        if !do_tagger.contains(&k.as_str()) && !chaves.contains(&k) {
            chaves.push(k);
        }
    }
    chaves
}

pub(super) fn extras(tag: &VorbisComments) -> BTreeMap<String, usize> {
    chaves_extras(tag).into_iter().map(|k| (k.clone(), tag.get_all(&k).count())).collect()
}

pub(super) fn remover_extras(tag: &mut VorbisComments) -> bool {
    let chaves = chaves_extras(tag);
    for chave in &chaves {
        apagar(tag, chave);
    }
    !chaves.is_empty()
}
