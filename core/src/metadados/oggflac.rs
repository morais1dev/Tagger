//! FLAC dentro de Ogg: a lofty não suporta. Implementação própria (último item da T3.2a).

use std::path::Path;

use lofty::ogg::tag::VorbisComments;

use super::{Erro, Resultado};

/// Ogg cujo 1º pacote é o cabeçalho do FLAC-em-Ogg (0x7F "FLAC").
pub(super) fn e_oggflac(cabecalho: &[u8]) -> bool {
    cabecalho.len() > 33 && &cabecalho[..4] == b"OggS" && {
        let segmentos = cabecalho[26] as usize;
        let inicio = 27 + segmentos;
        cabecalho.get(inicio..inicio + 5) == Some(b"\x7fFLAC")
    }
}

pub(super) struct OggFlac {
    pub(super) comentarios: VorbisComments,
    pub(super) duracao: f64,
}

impl OggFlac {
    pub(super) fn ler(caminho: &Path) -> Resultado<OggFlac> {
        Err(Erro::FormatoNaoSuportado(caminho.to_path_buf()))
    }

    pub(super) fn gravar(&self, caminho: &Path) -> Resultado<()> {
        Err(Erro::FormatoNaoSuportado(caminho.to_path_buf()))
    }
}
