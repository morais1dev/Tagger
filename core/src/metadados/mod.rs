//! Metadados: toda a leitura e escrita de tags, sem interface. Porte de `tagger/nucleo/metadata.py`.
//!
//! Princípios (iguais aos da v2):
//! - Ler NUNCA grava nada no arquivo (só [`salvar`] e [`limpar_extras`] gravam).
//! - Uma gravação aplica várias tags (e a capa) de uma vez: um único save por arquivo.
//! - Valor vazio ("") significa "remover a tag"; [`VARIOS`] significa "não mexer".
//!
//! Formatos: MP3 (ID3, `id3.rs`), FLAC e Ogg (Vorbis comments, `vorbis.rs`) e M4A/MP4 (átomos do
//! iTunes, `mp4.rs`). Cada formato é editado pelo tipo concreto da lofty (`Id3v2Tag`,
//! `VorbisComments`, `Ilst`): o `Tag` genérico perde, ao gravar, o que não sabe mapear.
//! A leitura usa sempre `implicit_conversions(false)`: as conversões automáticas da lofty mudam o
//! arquivo ao regravar (dividem `TRACKNUMBER=3/12`, convertem `gnre`, e no ID3v2.3 descartam um
//! `TDRC` com data completa).

mod id3;
mod mp4;
mod oggflac;
mod vorbis;

use std::collections::BTreeMap;
use std::fs::File;
use std::path::{Path, PathBuf};

use lofty::config::{ParseOptions, WriteOptions};
use lofty::file::AudioFile;
use lofty::flac::FlacFile;
use lofty::mp4::Mp4File;
use lofty::mpeg::MpegFile;
use lofty::ogg::{OpusFile, VorbisFile};

// ---------------------------------------------------------------- campos
/// Campos editáveis, na ordem em que aparecem na interface.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Campo {
    Titulo,
    Artista,
    Album,
    ArtistaAlbum,
    Faixa,
    Disco,
    Data,
    Genero,
    Compositor,
    Letrista,
    Comentario,
    Letra,
    Gravadora,
}

impl Campo {
    pub const TODOS: [Campo; 13] = [
        Campo::Titulo,
        Campo::Artista,
        Campo::Album,
        Campo::ArtistaAlbum,
        Campo::Faixa,
        Campo::Disco,
        Campo::Data,
        Campo::Genero,
        Campo::Compositor,
        Campo::Letrista,
        Campo::Comentario,
        Campo::Letra,
        Campo::Gravadora,
    ];

    /// Chave interna, a mesma da v2 (`metadata.CAMPOS`).
    pub fn chave(self) -> &'static str {
        match self {
            Campo::Titulo => "title",
            Campo::Artista => "artist",
            Campo::Album => "album",
            Campo::ArtistaAlbum => "albumartist",
            Campo::Faixa => "tracknumber",
            Campo::Disco => "discnumber",
            Campo::Data => "date",
            Campo::Genero => "genre",
            Campo::Compositor => "composer",
            Campo::Letrista => "lyricist",
            Campo::Comentario => "comment",
            Campo::Letra => "lyrics",
            Campo::Gravadora => "gravadora",
        }
    }

    pub fn de_chave(chave: &str) -> Option<Campo> {
        Campo::TODOS.into_iter().find(|c| c.chave() == chave)
    }

    /// Nome amigável, ex.: `ArtistaAlbum` -> "Artista do álbum".
    pub fn rotulo(self) -> &'static str {
        match self {
            Campo::Titulo => "Título",
            Campo::Artista => "Artista",
            Campo::Album => "Álbum",
            Campo::ArtistaAlbum => "Artista do álbum",
            Campo::Faixa => "Faixa",
            Campo::Disco => "Disco",
            Campo::Data => "Ano",
            Campo::Genero => "Gênero",
            Campo::Compositor => "Compositor",
            Campo::Letrista => "Letrista",
            Campo::Comentario => "Comentário",
            Campo::Letra => "Letra",
            Campo::Gravadora => "Gravadora",
        }
    }

    /// Campos em que "A; B" vira vários valores ao salvar (se [`OpcoesGravacao::multivalor`]).
    pub fn multivalor(self) -> bool {
        matches!(
            self,
            Campo::Artista | Campo::ArtistaAlbum | Campo::Genero | Campo::Compositor | Campo::Letrista
        )
    }

    /// Campos que fazem sentido aplicar igual em vários arquivos de uma vez.
    pub fn em_lote(self) -> bool {
        !matches!(self, Campo::Titulo | Campo::Faixa | Campo::Letra)
    }
}

pub const SEPARADOR: &str = "; ";

/// Marcador de "vários valores" numa edição em lote: o campo não é tocado.
pub const VARIOS: &str = "\u{0}<varios>\u{0}";

/// Tags lidas: campo -> texto ("" se vazio).
pub type Tags = BTreeMap<Campo, String>;

fn tags_vazias() -> Tags {
    Campo::TODOS.into_iter().map(|c| (c, String::new())).collect()
}

// ---------------------------------------------------------------- opções e erros
/// Como gravar as tags. Sem ela valem estes padrões (os da v2).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct OpcoesGravacao {
    /// Versão do ID3v2 (só MP3): 3 (mais compatível) ou 4.
    pub versao_id3: u8,
    /// "A; B" em artista, gênero etc. vira vários valores (todos os formatos).
    pub multivalor: bool,
    /// Remove a tag ID3v1 ao salvar (só MP3).
    pub remover_id3v1: bool,
}

impl Default for OpcoesGravacao {
    fn default() -> Self {
        OpcoesGravacao { versao_id3: 3, multivalor: true, remover_id3v1: false }
    }
}

impl OpcoesGravacao {
    fn escrita(&self) -> WriteOptions {
        WriteOptions::default().use_id3v23(self.versao_id3 == 3)
    }
}

/// O que fazer com a capa numa gravação.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum AcaoCapa {
    Definir { dados: Vec<u8>, mime: String },
    Remover,
}

#[derive(Debug)]
pub enum Erro {
    FormatoNaoSuportado(PathBuf),
    ArquivoInvalido(String),
    CapaInvalida(String),
    Io(std::io::Error),
}

impl std::fmt::Display for Erro {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Erro::FormatoNaoSuportado(c) => write!(f, "formato não suportado: {}", c.display()),
            Erro::ArquivoInvalido(m) | Erro::CapaInvalida(m) => f.write_str(m),
            Erro::Io(e) => write!(f, "{e}"),
        }
    }
}

impl std::error::Error for Erro {}

impl From<std::io::Error> for Erro {
    fn from(e: std::io::Error) -> Self {
        Erro::Io(e)
    }
}

impl From<lofty::error::FileParseError> for Erro {
    fn from(e: lofty::error::FileParseError) -> Self {
        Erro::ArquivoInvalido(e.to_string())
    }
}

impl From<lofty::error::FileEncodingError> for Erro {
    fn from(e: lofty::error::FileEncodingError) -> Self {
        Erro::ArquivoInvalido(e.to_string())
    }
}

pub type Resultado<T> = Result<T, Erro>;

// ---------------------------------------------------------------- formatos
/// Formato pela extensão (sem ponto).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Formato {
    Mp3,
    Flac,
    Ogg,
    M4a,
    Mp4,
}

impl Formato {
    pub fn nome(self) -> &'static str {
        match self {
            Formato::Mp3 => "mp3",
            Formato::Flac => "flac",
            Formato::Ogg => "ogg",
            Formato::M4a => "m4a",
            Formato::Mp4 => "mp4",
        }
    }
}

/// Extensões suportadas, em ordem alfabética.
pub const EXTENSOES_SUPORTADAS: [&str; 5] = ["flac", "m4a", "mp3", "mp4", "ogg"];

/// Formato pela extensão; None se não for suportado.
pub fn formato(arquivo: impl AsRef<Path>) -> Option<Formato> {
    let ext = arquivo.as_ref().extension()?.to_str()?.to_lowercase();
    match ext.as_str() {
        "mp3" => Some(Formato::Mp3),
        "flac" => Some(Formato::Flac),
        "ogg" => Some(Formato::Ogg),
        "m4a" => Some(Formato::M4a),
        "mp4" => Some(Formato::Mp4),
        _ => None,
    }
}

/// ("*.flac", "*.m4a", ...) para filtros de diálogos de arquivo.
pub fn curingas_audio() -> Vec<String> {
    EXTENSOES_SUPORTADAS.iter().map(|e| format!("*.{e}")).collect()
}

/// "FLAC, M4A, MP3, MP4, OGG": para textos da interface.
pub fn nomes_formatos() -> String {
    EXTENSOES_SUPORTADAS.iter().map(|e| e.to_uppercase()).collect::<Vec<_>>().join(", ")
}

/// Todos os arquivos suportados dentro de uma pasta, em ordem alfabética do caminho.
pub fn listar_audios(pasta: impl AsRef<Path>, recursivo: bool) -> Vec<PathBuf> {
    fn visitar(pasta: &Path, recursivo: bool, saida: &mut Vec<PathBuf>) {
        let Ok(entradas) = std::fs::read_dir(pasta) else { return };
        for entrada in entradas.flatten() {
            let caminho = entrada.path();
            if caminho.is_dir() {
                if recursivo {
                    visitar(&caminho, recursivo, saida);
                }
            } else if caminho.is_file() && formato(&caminho).is_some() {
                saida.push(caminho);
            }
        }
    }
    let mut lista = Vec::new();
    visitar(pasta.as_ref(), recursivo, &mut lista);
    lista.sort();
    lista
}

// ---------------------------------------------------------------- arquivo aberto
fn opcoes_leitura() -> ParseOptions {
    ParseOptions::new().implicit_conversions(false)
}

/// O arquivo aberto pela lofty, no tipo concreto do formato.
enum Arquivo {
    Mp3(MpegFile),
    Flac(FlacFile),
    Vorbis(VorbisFile),
    Opus(OpusFile),
    OggFlac(oggflac::OggFlac),
    Mp4(Mp4File),
}

fn abrir(caminho: &Path) -> Resultado<Arquivo> {
    let fmt = formato(caminho).ok_or_else(|| Erro::FormatoNaoSuportado(caminho.to_path_buf()))?;
    let mut f = File::open(caminho)?;
    Ok(match fmt {
        Formato::Mp3 => Arquivo::Mp3(MpegFile::read_from(&mut f, opcoes_leitura())?),
        Formato::Flac => Arquivo::Flac(FlacFile::read_from(&mut f, opcoes_leitura())?),
        Formato::M4a | Formato::Mp4 => Arquivo::Mp4(Mp4File::read_from(&mut f, opcoes_leitura())?),
        Formato::Ogg => {
            // .ogg pode ter Vorbis (o comum), Opus ou FLAC dentro; os três usam Vorbis comments
            let mut cabecalho = [0u8; 64];
            let n = std::io::Read::read(&mut f, &mut cabecalho)?;
            std::io::Seek::rewind(&mut f)?;
            let cabecalho = &cabecalho[..n];
            if oggflac::e_oggflac(cabecalho) {
                Arquivo::OggFlac(oggflac::OggFlac::ler(caminho)?)
            } else if cabecalho.windows(8).any(|w| w == b"OpusHead") {
                Arquivo::Opus(OpusFile::read_from(&mut f, opcoes_leitura())?)
            } else {
                Arquivo::Vorbis(VorbisFile::read_from(&mut f, opcoes_leitura())?)
            }
        }
    })
}

impl Arquivo {
    fn vorbis(&self) -> Option<&lofty::ogg::tag::VorbisComments> {
        match self {
            Arquivo::Flac(f) => f.vorbis_comments(),
            Arquivo::Vorbis(f) => Some(f.vorbis_comments()),
            Arquivo::Opus(f) => Some(f.vorbis_comments()),
            Arquivo::OggFlac(f) => Some(&f.comentarios),
            _ => None,
        }
    }

    fn tem_tags(&self) -> bool {
        match self {
            Arquivo::Mp3(f) => f.id3v2().is_some(),
            Arquivo::Mp4(f) => f.ilst().is_some(),
            _ => self.vorbis().is_some(),
        }
    }

    fn ler_campo(&self, campo: Campo) -> String {
        match self {
            Arquivo::Mp3(f) => f.id3v2().map(|t| id3::ler(t, campo)).unwrap_or_default(),
            Arquivo::Mp4(f) => f.ilst().map(|t| mp4::ler(t, campo).join(SEPARADOR)).unwrap_or_default(),
            _ => self.vorbis().map(|t| vorbis::ler(t, campo).join(SEPARADOR)).unwrap_or_default(),
        }
    }

    /// (dados, mime) das imagens que são "a capa".
    fn capas(&self) -> Vec<(Vec<u8>, String)> {
        match self {
            Arquivo::Mp3(f) => f.id3v2().map(id3::capas).unwrap_or_default(),
            Arquivo::Mp4(f) => f.ilst().map(mp4::capas).unwrap_or_default(),
            Arquivo::Flac(f) => vorbis::capas_flac(f),
            _ => self.vorbis().map(vorbis::capas_ogg).unwrap_or_default(),
        }
    }

    fn propriedades(&self) -> (f64, u32) {
        let p = match self {
            Arquivo::Mp3(f) => (f.properties().duration(), f.properties().audio_bitrate()),
            Arquivo::Flac(f) => (f.properties().duration(), f.properties().audio_bitrate()),
            Arquivo::Vorbis(f) => (f.properties().duration(), f.properties().audio_bitrate()),
            Arquivo::Opus(f) => (f.properties().duration(), f.properties().audio_bitrate()),
            Arquivo::OggFlac(f) => (std::time::Duration::from_secs_f64(f.duracao), 0),
            Arquivo::Mp4(f) => (f.properties().duration(), f.properties().audio_bitrate().unwrap_or(0)),
        };
        (p.0.as_secs_f64(), p.1)
    }
}

// ---------------------------------------------------------------- leitura
/// Retrato de um arquivo de áudio no momento em que foi lido.
#[derive(Clone, Debug, PartialEq)]
pub struct Faixa {
    pub caminho: PathBuf,
    pub tags: Tags,
    pub tem_capa: bool,
    /// segundos
    pub duracao: f64,
    /// kbps
    pub bitrate: u32,
    /// modificação do arquivo quando foi lido (nanossegundos desde 1970)
    pub mtime: u128,
    pub formato: Option<Formato>,
}

impl Faixa {
    /// Faixa só com tags (para [`valores_comuns`] e testes), sem ler arquivo.
    pub fn com_tags(caminho: impl Into<PathBuf>, tags: Tags) -> Faixa {
        let caminho = caminho.into();
        Faixa { formato: formato(&caminho), caminho, tags, tem_capa: false, duracao: 0.0, bitrate: 0, mtime: 0 }
    }

    pub fn nome(&self) -> String {
        self.caminho.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default()
    }

    /// "m:ss".
    pub fn duracao_formatada(&self) -> String {
        let total = self.duracao.round() as u64;
        format!("{}:{:02}", total / 60, total % 60)
    }
}

/// st_mtime_ns do arquivo agora, ou None se ele não existe mais.
pub fn mtime_atual(arquivo: impl AsRef<Path>) -> Option<u128> {
    let modificado = std::fs::metadata(arquivo).ok()?.modified().ok()?;
    Some(modificado.duration_since(std::time::UNIX_EPOCH).ok()?.as_nanos())
}

/// True se o arquivo mudou no disco (outro programa) depois que a Faixa foi lida.
pub fn foi_modificado(faixa: &Faixa) -> bool {
    mtime_atual(&faixa.caminho).is_some_and(|atual| atual != faixa.mtime)
}

/// Bitrate em kbps: o do arquivo; sem ele, estimado pelo tamanho (como a v2 faz com o Opus).
pub fn bitrate_kbps(bitrate_arquivo: Option<u32>, duracao: Option<f64>, tamanho_bytes: u64) -> u32 {
    match (bitrate_arquivo, duracao) {
        (Some(b), _) if b > 0 => b,
        (_, Some(d)) if d > 0.0 => (tamanho_bytes as f64 * 8.0 / d / 1000.0) as u32,
        _ => 0,
    }
}

/// Lê um arquivo e devolve uma Faixa, ou None se não for suportado/válido. Nunca grava.
pub fn carregar(arquivo: impl AsRef<Path>) -> Option<Faixa> {
    let caminho = arquivo.as_ref();
    let fmt = formato(caminho)?;
    let mtime = mtime_atual(caminho)?;
    let aberto = abrir(caminho).ok()?;
    let mut tags = tags_vazias();
    for campo in Campo::TODOS {
        tags.insert(campo, aberto.ler_campo(campo));
    }
    let (duracao, bitrate) = aberto.propriedades();
    let tamanho = std::fs::metadata(caminho).map(|m| m.len()).unwrap_or(0);
    Some(Faixa {
        caminho: caminho.to_path_buf(),
        tags,
        tem_capa: !aberto.capas().is_empty(),
        duracao,
        bitrate: bitrate_kbps(Some(bitrate), Some(duracao), tamanho),
        mtime,
        formato: Some(fmt),
    })
}

/// Lê vários arquivos. Devolve (faixas, os que falharam).
pub fn carregar_varios<P: AsRef<Path>>(arquivos: &[P]) -> (Vec<Faixa>, Vec<PathBuf>) {
    let mut faixas = Vec::new();
    let mut falhas = Vec::new();
    for arquivo in arquivos {
        match carregar(arquivo) {
            Some(f) => faixas.push(f),
            None => falhas.push(arquivo.as_ref().to_path_buf()),
        }
    }
    (faixas, falhas)
}

/// Para uma seleção: campo -> valor comum, ou [`VARIOS`] se diferem.
pub fn valores_comuns(faixas: &[Faixa]) -> Tags {
    let mut resultado = tags_vazias();
    let Some(primeira) = faixas.first() else { return resultado };
    for campo in Campo::TODOS {
        let valor = primeira.tags.get(&campo).cloned().unwrap_or_default();
        let igual = faixas.iter().all(|f| f.tags.get(&campo).map(String::as_str).unwrap_or("") == valor);
        resultado.insert(campo, if igual { valor } else { VARIOS.to_string() });
    }
    resultado
}

/// (bytes, mime) da capa, ou None.
pub fn ler_capa(arquivo: impl AsRef<Path>) -> Option<(Vec<u8>, String)> {
    abrir(arquivo.as_ref()).ok()?.capas().into_iter().next()
}

// ---------------------------------------------------------------- validação
pub use crate::validacao::{validar_alteracoes, validar_valor};

// ---------------------------------------------------------------- escrita
/// "A; B" -> ["A", "B"] nos campos multivalor (se `multivalor`); senão [valor].
pub fn dividir_valores(campo: Campo, valor: &str, multivalor: bool) -> Vec<String> {
    if !(multivalor && campo.multivalor()) {
        return vec![valor.to_string()];
    }
    let partes: Vec<String> =
        valor.split(';').map(|p| p.trim().to_string()).filter(|p| !p.is_empty()).collect();
    if partes.is_empty() { vec![valor.to_string()] } else { partes }
}

/// Grava várias tags (e, opcionalmente, a capa) num único save.
///
/// `alteracoes`: "" remove a tag; [`VARIOS`] é ignorado. Cria o cabeçalho de tags só se houver o
/// que gravar: só remoções num arquivo sem tags não mexem no arquivo.
pub fn salvar(
    arquivo: impl AsRef<Path>,
    alteracoes: &[(Campo, &str)],
    capa: Option<&AcaoCapa>,
    opcoes: OpcoesGravacao,
) -> Resultado<()> {
    let caminho = arquivo.as_ref();
    let fmt = formato(caminho).ok_or_else(|| Erro::FormatoNaoSuportado(caminho.to_path_buf()))?;
    if let (Formato::M4a | Formato::Mp4, Some(AcaoCapa::Definir { mime, .. })) = (fmt, capa) {
        mp4::verificar_mime(mime)?; // antes de gravar qualquer coisa
    }
    let alteracoes: Vec<(Campo, &str)> = alteracoes.iter().copied().filter(|(_, v)| *v != VARIOS).collect();
    let mut aberto = abrir(caminho)?;

    if !aberto.tem_tags() {
        let grava_algo = alteracoes.iter().any(|(_, v)| !v.is_empty())
            || matches!(capa, Some(AcaoCapa::Definir { .. }));
        if !grava_algo && (capa.is_none() || aberto.capas().is_empty()) {
            return Ok(()); // só remoções num arquivo sem tags: não cria um cabeçalho vazio
        }
        if grava_algo {
            criar_tags(&mut aberto);
        }
    }

    let multivalor = opcoes.multivalor;
    match &mut aberto {
        Arquivo::Mp3(f) => {
            if let Some(tag) = f.id3v2_mut() {
                for (campo, valor) in &alteracoes {
                    id3::gravar(tag, *campo, valor, multivalor);
                }
                if let Some(capa) = capa {
                    id3::aplicar_capa(tag, capa);
                }
            }
        }
        Arquivo::Mp4(f) => {
            let tag = f.ilst_mut().expect("criado acima");
            for (campo, valor) in &alteracoes {
                let valores = if valor.is_empty() { Vec::new() } else { dividir_valores(*campo, valor, multivalor) };
                mp4::gravar(tag, *campo, &valores);
            }
            if let Some(capa) = capa {
                mp4::aplicar_capa(tag, capa)?;
            }
        }
        _ => {
            if let Some(tag) = vorbis_mut(&mut aberto) {
                for (campo, valor) in &alteracoes {
                    let valores =
                        if valor.is_empty() { Vec::new() } else { dividir_valores(*campo, valor, multivalor) };
                    vorbis::gravar(tag, *campo, &valores);
                }
            }
            if let Some(capa) = capa {
                match &mut aberto {
                    Arquivo::Flac(f) => vorbis::aplicar_capa_flac(f, capa),
                    outro => {
                        if let Some(tag) = vorbis_mut(outro) {
                            vorbis::aplicar_capa_ogg(tag, capa);
                        }
                    }
                }
            }
        }
    }
    gravar_arquivo(caminho, &mut aberto, opcoes, false)
}

fn vorbis_mut(aberto: &mut Arquivo) -> Option<&mut lofty::ogg::tag::VorbisComments> {
    match aberto {
        Arquivo::Flac(f) => f.vorbis_comments_mut(),
        Arquivo::Vorbis(f) => Some(f.vorbis_comments_mut()),
        Arquivo::Opus(f) => Some(f.vorbis_comments_mut()),
        Arquivo::OggFlac(f) => Some(&mut f.comentarios),
        _ => None,
    }
}

fn criar_tags(aberto: &mut Arquivo) {
    match aberto {
        Arquivo::Mp3(f) => {
            f.set_id3v2(lofty::id3::v2::Id3v2Tag::new());
        }
        Arquivo::Mp4(f) => {
            f.set_ilst(lofty::mp4::Ilst::new());
        }
        Arquivo::Flac(f) => {
            f.set_vorbis_comments(lofty::ogg::tag::VorbisComments::default());
        }
        _ => {} // Ogg sempre tem o cabeçalho de comentários
    }
}

/// O único save do arquivo. `remover_id3v1`: além da opção, apaga o ID3v1 (limpeza).
fn gravar_arquivo(caminho: &Path, aberto: &mut Arquivo, opcoes: OpcoesGravacao, remover_id3v1: bool) -> Resultado<()> {
    let escrita = opcoes.escrita();
    let abrir_rw = || File::options().read(true).write(true).open(caminho);
    match aberto {
        Arquivo::Mp3(f) => id3::gravar_mp3(caminho, f, opcoes, remover_id3v1),
        Arquivo::Flac(f) => {
            if f.vorbis_comments().is_none() && f.pictures().is_empty() {
                // a lofty não grava nada nesse caso: as imagens antigas ficariam no arquivo
                lofty::tag::TagType::VorbisComments.remove_from(&mut abrir_rw()?, escrita)?;
                return Ok(());
            }
            f.save_to(&mut abrir_rw()?, escrita)?;
            Ok(())
        }
        Arquivo::Vorbis(f) => Ok(f.save_to(&mut abrir_rw()?, escrita)?),
        Arquivo::Opus(f) => Ok(f.save_to(&mut abrir_rw()?, escrita)?),
        Arquivo::OggFlac(f) => f.gravar(caminho),
        Arquivo::Mp4(f) => Ok(f.save_to(&mut abrir_rw()?, escrita)?),
    }
}

use lofty::ogg::OggPictureStorage;

/// Aplica as mesmas alterações em vários arquivos. Devolve {caminho: erro} dos que falharam.
pub fn salvar_varios<P: AsRef<Path>>(
    arquivos: &[P],
    alteracoes: &[(Campo, &str)],
    opcoes: OpcoesGravacao,
) -> BTreeMap<PathBuf, String> {
    let mut falhas = BTreeMap::new();
    for arquivo in arquivos {
        if let Err(e) = salvar(arquivo, alteracoes, None, opcoes) {
            falhas.insert(arquivo.as_ref().to_path_buf(), e.to_string());
        }
    }
    falhas
}

/// Substitui a capa frontal pela imagem informada.
pub fn definir_capa(arquivo: impl AsRef<Path>, dados: &[u8], mime: &str, opcoes: OpcoesGravacao) -> Resultado<()> {
    salvar(arquivo, &[], Some(&AcaoCapa::Definir { dados: dados.to_vec(), mime: mime.to_string() }), opcoes)
}

pub fn remover_capa(arquivo: impl AsRef<Path>, opcoes: OpcoesGravacao) -> Resultado<()> {
    salvar(arquivo, &[], Some(&AcaoCapa::Remover), opcoes)
}

// ---------------------------------------------------------------- limpeza
/// O que [`limpar_extras`] removeria.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct AnaliseExtras {
    pub id3v1: bool,
    pub desconhecidos: usize,
    /// frame/chave/átomo -> quantidade
    pub extras: BTreeMap<String, usize>,
}

/// True se o MP3 termina numa tag ID3v1. Outros formatos: sempre false (não se corta o fim deles).
pub fn tem_id3v1(arquivo: impl AsRef<Path>) -> bool {
    let caminho = arquivo.as_ref();
    if formato(caminho) != Some(Formato::Mp3) {
        return false;
    }
    id3::termina_em_id3v1(caminho)
}

pub fn analisar_extras(arquivo: impl AsRef<Path>) -> AnaliseExtras {
    let caminho = arquivo.as_ref();
    let mut resultado = AnaliseExtras { id3v1: tem_id3v1(caminho), ..Default::default() };
    let Ok(aberto) = abrir(caminho) else { return resultado };
    match &aberto {
        Arquivo::Mp3(f) => {
            if let Some(tag) = f.id3v2() {
                (resultado.desconhecidos, resultado.extras) = id3::extras(tag);
            }
        }
        Arquivo::Mp4(f) => resultado.extras = f.ilst().map(mp4::extras).unwrap_or_default(),
        _ => resultado.extras = aberto.vorbis().map(vorbis::extras).unwrap_or_default(),
    }
    resultado
}

/// Remove o que foi pedido, num único save. Ok(false) se não havia nada a fazer.
pub fn limpar_extras(
    arquivo: impl AsRef<Path>,
    id3v1: bool,
    desconhecidos: bool,
    extras: bool,
    opcoes: OpcoesGravacao,
) -> Resultado<bool> {
    let caminho = arquivo.as_ref();
    let mut aberto = abrir(caminho)?;
    if let Arquivo::Mp3(f) = &mut aberto {
        let mut mudou = false;
        if let Some(tag) = f.id3v2_mut() {
            mudou = id3::limpar(tag, desconhecidos, extras);
        }
        let remover_v1 = id3v1 && tem_id3v1(caminho);
        if !mudou && !remover_v1 {
            return Ok(false);
        }
        gravar_arquivo(caminho, &mut aberto, opcoes, remover_v1)?;
        return Ok(true);
    }
    // id3v1/desconhecidos não existem fora do MP3
    let removeu = extras
        && match &mut aberto {
            Arquivo::Mp4(f) => f.ilst_mut().is_some_and(mp4::remover_extras),
            outro => vorbis_mut(outro).is_some_and(vorbis::remover_extras),
        };
    if !removeu {
        return Ok(false);
    }
    gravar_arquivo(caminho, &mut aberto, opcoes, false)?;
    Ok(true)
}

/// Escolha da capa comum a ID3 e FLAC/Ogg: as frontais (tipo 3); sem elas, a 1ª do tipo "outra" (0).
fn escolher_capa(tipos: &[u8]) -> Vec<usize> {
    let frontais: Vec<usize> = (0..tipos.len()).filter(|&i| tipos[i] == 3).collect();
    if !frontais.is_empty() {
        return frontais;
    }
    (0..tipos.len()).filter(|&i| tipos[i] == 0).take(1).collect()
}
