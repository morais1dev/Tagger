//! FLAC dentro de Ogg (.ogg), que a lofty não suporta. Implementação própria sobre o `ogg_pager`.
//!
//! Mapeamento (xiph.org, "FLAC in Ogg"): o 1º pacote é 0x7F "FLAC", versão, nº de pacotes de
//! cabeçalho, "fLaC" e o bloco STREAMINFO; cada pacote de cabeçalho seguinte é um bloco de metadados
//! do FLAC (4 bytes de cabeçalho + corpo). O bloco VORBIS_COMMENT (tipo 4) é o das tags, sem o bit
//! de enquadramento do Vorbis. O áudio começa numa página nova.
//!
//! Gravar troca só o pacote dos comentários: os pacotes de cabeçalho são repaginados e as páginas de
//! áudio são copiadas, só com o número de sequência e o CRC refeitos.

use std::io::Cursor;
use std::path::Path;

use lofty::config::ParsingMode;
use lofty::ogg::OggPictureStorage;
use lofty::ogg::tag::VorbisComments;
use lofty::picture::Picture;
use ogg_pager::{CONTAINS_FIRST_PAGE_OF_BITSTREAM, Packets, Page, paginate};

use super::{Erro, Resultado};

const TIPO_COMENTARIO: u8 = 4;

/// Ogg cujo 1º pacote é o cabeçalho do FLAC-em-Ogg (0x7F "FLAC").
pub(super) fn e_oggflac(cabecalho: &[u8]) -> bool {
    if cabecalho.len() < 28 || &cabecalho[..4] != b"OggS" {
        return false;
    }
    let inicio = 27 + cabecalho[26] as usize;
    cabecalho.get(inicio..inicio + 5) == Some(b"\x7fFLAC".as_slice())
}

pub(super) struct OggFlac {
    pub(super) comentarios: VorbisComments,
    pub(super) duracao: f64,
    pacotes: Vec<Vec<u8>>,
    indice_comentario: Option<usize>,
    fim_cabecalho: u64,
    serial: u32,
}

fn invalido(caminho: &Path, motivo: &str) -> Erro {
    Erro::ArquivoInvalido(format!("FLAC em Ogg inválido ({motivo}): {}", caminho.display()))
}

fn ler_u32_le(b: &[u8], i: &mut usize) -> Option<u32> {
    let v = u32::from_le_bytes(b.get(*i..*i + 4)?.try_into().ok()?);
    *i += 4;
    Some(v)
}

/// Corpo de um VORBIS_COMMENT (vendor + itens). Imagens (METADATA_BLOCK_PICTURE) viram imagens.
fn ler_comentarios(corpo: &[u8]) -> Option<VorbisComments> {
    let mut i = 0;
    let mut tag = VorbisComments::default();
    let n = ler_u32_le(corpo, &mut i)? as usize;
    tag.set_vendor(String::from_utf8_lossy(corpo.get(i..i + n)?).into_owned());
    i += n;
    for _ in 0..ler_u32_le(corpo, &mut i)? {
        let n = ler_u32_le(corpo, &mut i)? as usize;
        let item = corpo.get(i..i + n)?;
        i += n;
        let Some(igual) = item.iter().position(|&b| b == b'=') else { continue };
        let (chave, valor) = (String::from_utf8_lossy(&item[..igual]), &item[igual + 1..]);
        if chave.eq_ignore_ascii_case("METADATA_BLOCK_PICTURE")
            && let Ok((p, info)) = Picture::from_flac_bytes(valor, true, ParsingMode::Relaxed) {
                let _ = tag.insert_picture(p, Some(info));
                continue;
            }
        tag.push(chave.into_owned(), String::from_utf8_lossy(valor).into_owned());
    }
    Some(tag)
}

fn gravar_comentarios(tag: &VorbisComments) -> Vec<u8> {
    let mut itens: Vec<Vec<u8>> = tag.items().map(|(k, v)| format!("{k}={v}").into_bytes()).collect();
    for (p, info) in tag.pictures() {
        let mut item = b"METADATA_BLOCK_PICTURE=".to_vec();
        item.extend(p.as_flac_bytes(*info, true));
        itens.push(item);
    }
    let mut corpo = (tag.vendor().len() as u32).to_le_bytes().to_vec();
    corpo.extend_from_slice(tag.vendor().as_bytes());
    corpo.extend_from_slice(&(itens.len() as u32).to_le_bytes());
    for item in itens {
        corpo.extend_from_slice(&(item.len() as u32).to_le_bytes());
        corpo.extend(item);
    }
    corpo
}

impl OggFlac {
    pub(super) fn ler(caminho: &Path) -> Resultado<OggFlac> {
        let bytes = std::fs::read(caminho)?;
        let mut cursor = Cursor::new(&bytes);
        let primeira = Page::read(&mut cursor).map_err(|_| invalido(caminho, "página"))?;
        let serial = primeira.header().stream_serial;
        let p0 = primeira.content();
        if p0.len() < 51 || &p0[..5] != b"\x7fFLAC" || &p0[9..13] != b"fLaC" {
            return Err(invalido(caminho, "cabeçalho"));
        }
        let n_cabecalhos = u16::from_be_bytes([p0[7], p0[8]]) as isize;
        // STREAMINFO: taxa (20 bits) e total de amostras (36 bits)
        let info = &p0[17..];
        let taxa = (u32::from(info[10]) << 12) | (u32::from(info[11]) << 4) | (u32::from(info[12]) >> 4);
        let amostras = (u64::from(info[13] & 0x0f) << 32) | u64::from(u32::from_be_bytes([info[14], info[15], info[16], info[17]]));
        let duracao = if taxa > 0 { amostras as f64 / f64::from(taxa) } else { 0.0 };

        cursor.set_position(0);
        let (pacotes, resto) =
            Packets::read_count(&mut cursor, 1 + n_cabecalhos).map_err(|_| invalido(caminho, "pacotes"))?;
        if resto.is_some() {
            return Err(invalido(caminho, "áudio na mesma página do cabeçalho"));
        }
        let pacotes: Vec<Vec<u8>> = pacotes.iter().map(<[u8]>::to_vec).collect();
        let indice_comentario = pacotes.iter().position(|p| p.first().is_some_and(|b| b & 0x7f == TIPO_COMENTARIO));
        let comentarios = match indice_comentario {
            Some(i) => ler_comentarios(&pacotes[i][4..]).ok_or_else(|| invalido(caminho, "comentários"))?,
            None => VorbisComments::default(),
        };
        Ok(OggFlac { comentarios, duracao, pacotes, indice_comentario, fim_cabecalho: cursor.position(), serial })
    }

    pub(super) fn gravar(&mut self, caminho: &Path) -> Resultado<()> {
        let corpo = gravar_comentarios(&self.comentarios);
        if corpo.len() >= 1 << 24 {
            return Err(Erro::ArquivoInvalido("comentários grandes demais para um bloco FLAC".into()));
        }
        let tamanho = (corpo.len() as u32).to_be_bytes();
        let mut pacotes = self.pacotes.clone();
        match self.indice_comentario {
            Some(i) => {
                let mut novo = vec![pacotes[i][0], tamanho[1], tamanho[2], tamanho[3]];
                novo.extend(corpo);
                pacotes[i] = novo;
            }
            None => {
                // sem bloco de comentários: entra logo depois do STREAMINFO, sem ser o último bloco
                let mut novo = vec![TIPO_COMENTARIO, tamanho[1], tamanho[2], tamanho[3]];
                novo.extend(corpo);
                pacotes.insert(1, novo);
                let n = u16::from_be_bytes([pacotes[0][7], pacotes[0][8]]) + 1;
                pacotes[0][7..9].copy_from_slice(&n.to_be_bytes());
                if pacotes.len() == 2 {
                    pacotes[1][0] |= 0x80; // único bloco depois do STREAMINFO: é o último
                }
            }
        }

        let erro_pagina = |_| Erro::ArquivoInvalido("falha ao paginar o FLAC em Ogg".into());
        let mut paginas = paginate([pacotes[0].as_slice()], self.serial, 0, CONTAINS_FIRST_PAGE_OF_BITSTREAM)
            .map_err(erro_pagina)?;
        paginas.extend(paginate(pacotes[1..].iter().map(Vec::as_slice), self.serial, 0, 0).map_err(erro_pagina)?);

        let original = std::fs::read(caminho)?;
        let mut cursor = Cursor::new(&original);
        cursor.set_position(self.fim_cabecalho);
        while let Ok(pagina) = Page::read(&mut cursor) {
            paginas.push(pagina);
        }
        let mut saida = Vec::with_capacity(original.len());
        for (sequencia, mut pagina) in paginas.into_iter().enumerate() {
            pagina.header_mut().sequence_number = sequencia as u32;
            pagina.gen_crc();
            saida.extend(pagina.as_bytes());
        }
        std::fs::write(caminho, saida)?;
        self.pacotes = pacotes;
        Ok(())
    }
}
