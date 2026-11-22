//! Porte de tests/test_metadata.py (v2): validação, MP3 e funções gerais.
//! Cada teste leva o nome do teste pytest; a lista está em docs/paridade-testes.md.

mod comum;

use std::collections::BTreeMap;
use std::io::Write;

use comum::*;
use lofty::TextEncoding;
use lofty::id3::v2::{
    AttachedPictureFrame, CommentFrame, ExtendedTextFrame, Frame, FrameId, Id3v2Tag, PrivateFrame,
    TextInformationFrame, UnsynchronizedTextFrame,
};
use tagger_core::metadados::*;

fn ano_atual() -> i64 {
    // o mesmo cálculo não é exposto; o teste usa a validação de "atual" como referência
    validar_valor(Campo::Data, "atual").unwrap().parse().unwrap()
}

// ----------------------------------------------------------------- validação
#[test]
fn test_valores_validos() {
    let casos = [
        (Campo::Data, "2024", "2024"),
        (Campo::Data, "2024-05-17", "2024-05-17"),
        (Campo::Faixa, "3", "3"),
        (Campo::Faixa, "3/12", "3/12"),
        (Campo::Disco, " 1/2 ", "1/2"),
        (Campo::Genero, "Rock", "Rock"),
        (Campo::Titulo, "  Nome  ", "Nome"),
        (Campo::Titulo, "", ""),
        (Campo::Data, VARIOS, VARIOS),
    ];
    for (campo, valor, esperado) in casos {
        assert_eq!(validar_valor(campo, valor), Ok(esperado.to_string()), "{campo:?} {valor:?}");
    }
    let atual = validar_valor(Campo::Data, "atual").unwrap();
    assert_eq!(atual.len(), 4);
    assert!(atual.parse::<i64>().unwrap() >= 2026);
}

#[test]
fn test_valores_invalidos() {
    let futuro = (ano_atual() + 1).to_string();
    let casos = [
        (Campo::Data, "24"),
        (Campo::Data, "2024/05"),
        (Campo::Data, "0999"),
        (Campo::Data, futuro.as_str()),
        (Campo::Faixa, "0"),
        (Campo::Faixa, "3/0"),
        (Campo::Faixa, "a"),
        (Campo::Disco, "-1"),
        (Campo::Genero, "17"),
    ];
    for (campo, valor) in casos {
        let erro = validar_valor(campo, valor).unwrap_err();
        assert!(!erro.is_empty(), "{campo:?} {valor:?}");
    }
}

// ----------------------------------------------------------------- ler / salvar
#[test]
fn test_arquivo_sem_tags() {
    let mp3 = amostra("mp3");
    let faixa = carregar(&mp3).unwrap();
    assert!(faixa.tags.values().all(String::is_empty) && faixa.tags.len() == 13);
    assert!(!faixa.tem_capa && faixa.duracao > 0.0 && faixa.bitrate == 128);
    assert_eq!(Some(faixa.mtime), mtime_atual(&mp3));
}

#[test]
fn test_ler_nao_grava() {
    let mp3 = amostra("mp3");
    let antes = std::fs::read(&mp3).unwrap();
    carregar(&mp3);
    ler_capa(&mp3);
    analisar_extras(&mp3);
    assert_eq!(std::fs::read(&mp3).unwrap(), antes);
}

#[test]
fn test_salvar_e_reler() {
    let mp3 = amostra("mp3");
    let valores = [
        (Campo::Titulo, "Música"),
        (Campo::Artista, "Artista"),
        (Campo::Album, "Álbum"),
        (Campo::Faixa, "3/12"),
        (Campo::Data, "2024"),
        (Campo::Genero, "Rock"),
        (Campo::Comentario, "linha 1\nlinha 2"),
        (Campo::Letra, "lá lá\nlá"),
    ];
    salvar(&mp3, &valores, None, PADRAO).unwrap();
    let faixa = carregar(&mp3).unwrap();
    for (c, v) in valores {
        assert_eq!(faixa.tags[&c], v, "{c:?}");
    }
    assert_eq!(versao_id3(&mp3), 3);
}

#[test]
fn test_gravadora_mp3() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Gravadora, "Selo; Dois")], None, PADRAO).unwrap();
    let tpub = FrameId::new("TPUB").unwrap();
    assert_eq!(id3(&mp3).unwrap().get_text(&tpub), Some("Selo; Dois")); // TPUB não é multivalor
    assert_eq!(campo(&mp3, Campo::Gravadora), "Selo; Dois");
    salvar(&mp3, &[(Campo::Gravadora, "")], None, PADRAO).unwrap();
    assert!(id3(&mp3).is_none_or(|t| t.get(&tpub).is_none()));
    assert_eq!(campo(&mp3, Campo::Gravadora), "");
}

#[test]
fn test_valor_vazio_remove_e_varios_ignora() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Titulo, "A"), (Campo::Artista, "B")], None, PADRAO).unwrap();
    salvar(&mp3, &[(Campo::Titulo, ""), (Campo::Artista, VARIOS)], None, PADRAO).unwrap();
    let tags = carregar(&mp3).unwrap().tags;
    assert_eq!((tags[&Campo::Titulo].as_str(), tags[&Campo::Artista].as_str()), ("", "B"));
    assert!(id3(&mp3).unwrap().get(&FrameId::new("TIT2").unwrap()).is_none());
}

#[test]
fn test_so_remocoes_nao_cria_cabecalho_vazio() {
    let casos: [(&[(Campo, &str)], Option<AcaoCapa>); 3] = [
        (&[(Campo::Titulo, ""), (Campo::Artista, VARIOS)], None),
        (&[], Some(AcaoCapa::Remover)),
        (&[(Campo::Comentario, ""), (Campo::Letra, "")], Some(AcaoCapa::Remover)),
    ];
    for (alteracoes, capa) in casos {
        let mp3 = amostra("mp3");
        let antes = std::fs::read(&mp3).unwrap();
        salvar(&mp3, alteracoes, capa.as_ref(), PADRAO).unwrap();
        assert!(id3(&mp3).is_none());
        assert_eq!(std::fs::read(&mp3).unwrap(), antes);
    }
}

#[test]
fn test_opcoes_padrao() {
    assert_eq!(OpcoesGravacao::default(), OpcoesGravacao { versao_id3: 3, multivalor: true, remover_id3v1: false });
}

#[test]
fn test_id3v23_por_padrao() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Titulo, "A")], None, OpcoesGravacao::default()).unwrap();
    assert_eq!(versao_id3(&mp3), 3);
}

#[test]
fn test_id3v24() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Titulo, "A")], None, OpcoesGravacao { versao_id3: 4, ..PADRAO }).unwrap();
    assert_eq!(versao_id3(&mp3), 4);
}

#[test]
fn test_versao_id3_vale_em_salvar_varios_e_definir_capa() {
    let mp3 = amostra("mp3");
    let v4 = OpcoesGravacao { versao_id3: 4, ..PADRAO };
    assert!(salvar_varios(&[&mp3], &[(Campo::Titulo, "A")], v4).is_empty());
    assert_eq!(versao_id3(&mp3), 4);
    definir_capa(&mp3, JPEG, "image/jpeg", PADRAO).unwrap();
    assert_eq!(versao_id3(&mp3), 3);
    remover_capa(&mp3, v4).unwrap();
    assert_eq!(versao_id3(&mp3), 4);
}

#[test]
fn test_dividir_valores_com_e_sem_multivalor() {
    assert_eq!(dividir_valores(Campo::Artista, "A; B", true), ["A", "B"]);
    assert_eq!(dividir_valores(Campo::Artista, "A; B", false), ["A; B"]);
    assert_eq!(dividir_valores(Campo::Titulo, "A; B", true), ["A; B"]);
}

#[test]
fn test_um_unico_save_por_arquivo() {
    // A v2 conta chamadas de save(); aqui o equivalente observável é tags + capa numa chamada só.
    let mp3 = amostra("mp3");
    let capa = AcaoCapa::Definir { dados: JPEG.to_vec(), mime: "image/jpeg".into() };
    salvar(&mp3, &[(Campo::Titulo, "A")], Some(&capa), PADRAO).unwrap();
    assert_eq!(campo(&mp3, Campo::Titulo), "A");
    assert_eq!(ler_capa(&mp3), Some((JPEG.to_vec(), "image/jpeg".to_string())));
}

#[test]
fn test_arquivo_invalido() {
    let p = pasta();
    let lixo = p.join("lixo.mp3");
    std::fs::write(&lixo, b"isto nao e um mp3").unwrap();
    assert!(carregar(&lixo).is_none());
    assert!(carregar(p.join("nao-existe.mp3")).is_none());
    std::fs::write(p.join("texto.txt"), b"x").unwrap();
    assert!(carregar(p.join("texto.txt")).is_none());
}

// ----------------------------------------------------------------- formatos legados
fn tag_com(frames: Vec<Frame<'static>>) -> Id3v2Tag {
    let mut t = Id3v2Tag::new();
    for f in frames {
        t.insert(f);
    }
    t
}

fn txxx(desc: &str, texto: &str) -> Frame<'static> {
    Frame::UserText(ExtendedTextFrame::new(TextEncoding::UTF8, desc.to_string(), texto.to_string()))
}

#[test]
fn test_comentario_legado_txxx() {
    let mp3 = amostra("mp3");
    gravar_id3(&mp3, tag_com(vec![txxx("comment", "do ffmpeg")]));
    assert_eq!(campo(&mp3, Campo::Comentario), "do ffmpeg");
    salvar(&mp3, &[(Campo::Comentario, "novo")], None, PADRAO).unwrap();
    assert!(id3(&mp3).unwrap().get_user_text("comment").is_none());
    assert_eq!(campo(&mp3, Campo::Comentario), "novo");
}

#[test]
fn test_comentario_com_descricao_e_preservado() {
    let mp3 = amostra("mp3");
    gravar_id3(
        &mp3,
        tag_com(vec![
            Frame::Comment(CommentFrame::new(TextEncoding::UTF8, *b"eng", "iTunNORM", "000")),
            Frame::Comment(CommentFrame::new(TextEncoding::UTF8, *b"eng", "", "meu")),
        ]),
    );
    assert_eq!(campo(&mp3, Campo::Comentario), "meu");
    salvar(&mp3, &[(Campo::Comentario, "")], None, PADRAO).unwrap();
    let descs: Vec<String> = id3(&mp3)
        .unwrap()
        .iter()
        .filter_map(|f| if let Frame::Comment(c) = f { Some(c.description.to_string()) } else { None })
        .collect();
    assert_eq!(descs, ["iTunNORM"]);
}

#[test]
fn test_genero_id3v1_numerico() {
    let mp3 = amostra("mp3");
    gravar_id3(
        &mp3,
        tag_com(vec![Frame::Text(TextInformationFrame::new(FrameId::new("TCON").unwrap(), TextEncoding::UTF8, "(17)"))]),
    );
    assert_eq!(campo(&mp3, Campo::Genero), "Rock");
}

#[test]
fn test_letra_com_outra_descricao_e_preservada() {
    let mp3 = amostra("mp3");
    gravar_id3(
        &mp3,
        tag_com(vec![
            Frame::UnsynchronizedText(UnsynchronizedTextFrame::new(TextEncoding::UTF8, *b"eng", "", "letra")),
            Frame::UnsynchronizedText(UnsynchronizedTextFrame::new(TextEncoding::UTF8, *b"por", "traducao", "tradução")),
        ]),
    );
    assert_eq!(campo(&mp3, Campo::Letra), "letra");
    salvar(&mp3, &[(Campo::Letra, "nova")], None, PADRAO).unwrap();
    let letras: BTreeMap<String, String> = id3(&mp3)
        .unwrap()
        .iter()
        .filter_map(|f| match f {
            Frame::UnsynchronizedText(u) => Some((u.description.to_string(), u.content.to_string())),
            _ => None,
        })
        .collect();
    assert_eq!(letras, BTreeMap::from([("".into(), "nova".into()), ("traducao".into(), "tradução".into())]));
}

// ----------------------------------------------------------------- multivalor
fn textos(tag: &Id3v2Tag, id: &str) -> Vec<String> {
    tag.get_texts(&FrameId::new(id.to_string()).unwrap()).map(|v| v.map(str::to_string).collect()).unwrap_or_default()
}

#[test]
fn test_multivalor() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Artista, "A; B"), (Campo::Genero, "Rock;Pop"), (Campo::Titulo, "X; Y")], None, PADRAO)
        .unwrap();
    let tag = id3(&mp3).unwrap();
    assert_eq!(textos(&tag, "TPE1"), ["A", "B"]);
    assert_eq!(tag.genres().unwrap().collect::<Vec<_>>(), ["Rock", "Pop"]);
    assert_eq!(textos(&tag, "TIT2"), ["X; Y"]); // título não é multivalor
    assert_eq!(campo(&mp3, Campo::Artista), "A; B");
}

#[test]
fn test_multivalor_desligado() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Artista, "A; B")], None, OpcoesGravacao { multivalor: false, ..PADRAO }).unwrap();
    assert_eq!(textos(&id3(&mp3).unwrap(), "TPE1"), ["A; B"]);
}

#[test]
fn test_multivalor_ligado_no_id3v23_grava_valores_separados() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Artista, "A; B")], None, PADRAO).unwrap();
    let conteudo = std::fs::read(&mp3).unwrap();
    // dois textos UTF-16 separados por nulo (a v2/mutagen repete o BOM antes do 2º; a lofty não, e o
    // mutagen lê os dois do mesmo jeito: conferido no spike, docs/spike/tauri.md)
    assert!(conteudo.windows(6).any(|w| w == b"A\x00\x00\x00B\x00"));
    assert!(!conteudo.windows(3).any(|w| w == b"A/B"));
}

#[test]
fn test_multivalor_sobrevive_ao_salvar_outro_campo() {
    let mp3 = amostra("mp3");
    salvar(&mp3, &[(Campo::Artista, "AC/DC; Outro")], None, PADRAO).unwrap();
    salvar(&mp3, &[(Campo::Titulo, "T")], None, PADRAO).unwrap();
    assert_eq!(textos(&id3(&mp3).unwrap(), "TPE1"), ["AC/DC", "Outro"]);
}

// ----------------------------------------------------------------- capa
fn com_imagens(mp3: &std::path::Path, imagens: &[(u8, &str, &[u8])]) {
    let mut t = Id3v2Tag::new();
    for (tipo, desc, dados) in imagens {
        let mut p = imagem(*tipo, dados);
        p.set_description(if desc.is_empty() { None } else { Some(desc.to_string()) });
        t.insert(Frame::Picture(AttachedPictureFrame::new(TextEncoding::UTF8, p)));
    }
    gravar_id3(mp3, t);
}

fn apics(mp3: &std::path::Path) -> Vec<(u8, Vec<u8>)> {
    let mut v: Vec<(u8, Vec<u8>)> = id3(mp3)
        .map(|t| {
            t.iter()
                .filter_map(|f| match f {
                    Frame::Picture(p) => Some((p.picture.pic_type().as_u8(), p.picture.data().to_vec())),
                    _ => None,
                })
                .collect()
        })
        .unwrap_or_default();
    v.sort();
    v
}

#[test]
fn test_trocar_capa_mantem_outras_imagens() {
    let mp3 = amostra("mp3");
    com_imagens(&mp3, &[(3, "", b"frente"), (4, "Cover", b"verso"), (8, "artista", b"foto")]);
    let capa = AcaoCapa::Definir { dados: PNG.to_vec(), mime: "image/png".into() };
    salvar(&mp3, &[], Some(&capa), PADRAO).unwrap();
    assert_eq!(apics(&mp3), [(3, PNG.to_vec()), (4, b"verso".to_vec()), (8, b"foto".to_vec())]);
    assert_eq!(ler_capa(&mp3), Some((PNG.to_vec(), "image/png".into())));
}

#[test]
fn test_remover_capa_mantem_outras_imagens() {
    let mp3 = amostra("mp3");
    com_imagens(&mp3, &[(3, "", b"frente"), (4, "verso", b"verso")]);
    salvar(&mp3, &[], Some(&AcaoCapa::Remover), PADRAO).unwrap();
    assert_eq!(apics(&mp3).into_iter().map(|(t, _)| t).collect::<Vec<_>>(), [4]);
    assert!(!carregar(&mp3).unwrap().tem_capa && ler_capa(&mp3).is_none());
}

#[test]
fn test_capa_do_tipo_outra() {
    let mp3 = amostra("mp3");
    com_imagens(&mp3, &[(0, "", b"outra"), (4, "verso", b"verso")]);
    assert_eq!(ler_capa(&mp3), Some((b"outra".to_vec(), "image/jpeg".into())));
    definir_capa(&mp3, JPEG, "image/jpeg", PADRAO).unwrap();
    assert_eq!(apics(&mp3), [(3, JPEG.to_vec()), (4, b"verso".to_vec())]);
}

#[test]
fn test_so_contracapa_nao_conta_como_capa() {
    let mp3 = amostra("mp3");
    com_imagens(&mp3, &[(4, "", b"verso")]);
    assert!(!carregar(&mp3).unwrap().tem_capa);
    definir_capa(&mp3, JPEG, "image/jpeg", PADRAO).unwrap();
    assert_eq!(apics(&mp3).into_iter().map(|(t, _)| t).collect::<Vec<_>>(), [3, 4]);
}

#[test]
fn test_remover_capa_sem_tags_nao_cria_cabecalho() {
    let mp3 = amostra("mp3");
    let antes = std::fs::read(&mp3).unwrap();
    remover_capa(&mp3, PADRAO).unwrap();
    assert_eq!(std::fs::read(&mp3).unwrap(), antes);
}

// ----------------------------------------------------------------- mtime
#[test]
fn test_foi_modificado() {
    let mp3 = amostra("mp3");
    let faixa = carregar(&mp3).unwrap();
    assert!(!foi_modificado(&faixa));
    salvar(&mp3, &[(Campo::Titulo, "por outro programa")], None, PADRAO).unwrap();
    let depois = std::time::UNIX_EPOCH + std::time::Duration::from_nanos((faixa.mtime + 5_000_000_000) as u64);
    std::fs::File::options().write(true).open(&mp3).unwrap().set_modified(depois).unwrap();
    assert!(foi_modificado(&faixa));
}

// ----------------------------------------------------------------- limpeza
fn com_id3v1(caminho: &std::path::Path) {
    let mut v1 = b"TAG".to_vec();
    let mut titulo = b"Titulo v1".to_vec();
    titulo.resize(30, 0);
    v1.extend(titulo);
    v1.extend([0u8; 94]);
    v1.push(0xff); // sem gênero
    std::fs::OpenOptions::new().append(true).open(caminho).unwrap().write_all(&v1).unwrap();
}

#[test]
fn test_remover_id3v1_ao_salvar() {
    let mp3 = amostra("mp3");
    com_id3v1(&mp3);
    salvar(&mp3, &[(Campo::Titulo, "A")], None, PADRAO).unwrap();
    assert!(tem_id3v1(&mp3)); // padrão: só atualiza
    salvar(&mp3, &[(Campo::Titulo, "B")], None, OpcoesGravacao { remover_id3v1: true, ..PADRAO }).unwrap();
    assert!(!tem_id3v1(&mp3));
}

#[test]
fn test_limpar_extras_usa_as_opcoes_no_save() {
    let mp3 = amostra("mp3");
    // Diferença da v2: a lofty não grava tag ID3v2 vazia (apaga o cabeçalho). Por isso fica um TIT2,
    // para a tag sobreviver e a versão poder ser conferida.
    gravar_id3(
        &mp3,
        tag_com(vec![
            txxx("REPLAYGAIN_TRACK_GAIN", "-6 dB"),
            Frame::Text(TextInformationFrame::new(FrameId::new("TIT2").unwrap(), TextEncoding::UTF8, "fica")),
        ]),
    );
    assert!(limpar_extras(&mp3, false, false, true, OpcoesGravacao { versao_id3: 4, ..PADRAO }).unwrap());
    assert_eq!(versao_id3(&mp3), 4);
}

#[test]
fn test_analisar_e_limpar_extras() {
    let mp3 = amostra("mp3");
    gravar_id3(
        &mp3,
        tag_com(vec![
            txxx("comment", "fica"),
            txxx("REPLAYGAIN_TRACK_GAIN", "-6 dB"),
            Frame::Private(PrivateFrame::new("WM/Provider", vec![b'x'])),
            Frame::Text(TextInformationFrame::new(FrameId::new("TIT2").unwrap(), TextEncoding::UTF8, "título")),
        ]),
    );
    com_id3v1(&mp3);

    let analise = analisar_extras(&mp3);
    assert!(analise.id3v1);
    assert_eq!(analise.extras, BTreeMap::from([("TXXX".to_string(), 1), ("PRIV".to_string(), 1)]));

    assert!(limpar_extras(&mp3, true, true, true, PADRAO).unwrap());
    let tag = id3(&mp3).unwrap();
    assert_eq!(ids(&tag), ["TIT2", "TXXX"]);
    assert!(tag.get_user_text("comment").is_some());
    assert!(!tem_id3v1(&mp3));
    assert!(!limpar_extras(&mp3, true, true, true, PADRAO).unwrap()); // nada mais a fazer
}

#[test]
fn test_valores_comuns() {
    let vazio: Tags = Campo::TODOS.into_iter().map(|c| (c, String::new())).collect();
    let mut ta = vazio.clone();
    ta.insert(Campo::Artista, "X".into());
    ta.insert(Campo::Album, "1".into());
    let mut tb = vazio.clone();
    tb.insert(Campo::Artista, "X".into());
    tb.insert(Campo::Album, "2".into());
    let comuns = valores_comuns(&[Faixa::com_tags("a.mp3", ta), Faixa::com_tags("b.mp3", tb)]);
    assert_eq!(comuns[&Campo::Artista], "X");
    assert_eq!(comuns[&Campo::Album], VARIOS);
    assert_eq!(comuns[&Campo::Titulo], "");
}

#[test]
fn test_formatos_suportados() {
    let nomes: Vec<Option<&str>> =
        ["MP3", "flac", "ogg", "m4a", "mp4"].iter().map(|e| formato(format!("a.{e}")).map(Formato::nome)).collect();
    assert_eq!(nomes, [Some("mp3"), Some("flac"), Some("ogg"), Some("m4a"), Some("mp4")]);
    assert!(formato("a.wav").is_none());
    let p = pasta();
    for nome in ["a.mp3", "b.FLAC", "c.ogg", "d.m4a", "e.mp4", "f.wav", "g.jpg"] {
        std::fs::write(p.join(nome), b"").unwrap();
    }
    let achados: Vec<String> =
        listar_audios(&p, true).iter().map(|c| c.file_name().unwrap().to_string_lossy().into_owned()).collect();
    assert_eq!(achados, ["a.mp3", "b.FLAC", "c.ogg", "d.m4a", "e.mp4"]);
}

#[test]
fn test_textos_de_formatos() {
    assert_eq!(curingas_audio(), ["*.flac", "*.m4a", "*.mp3", "*.mp4", "*.ogg"]);
    assert_eq!(nomes_formatos(), "FLAC, M4A, MP3, MP4, OGG");
}

// ----------------------------------------------------------------- bitrate
#[test]
fn test_bitrate_usa_o_do_mutagen() {
    assert_eq!(bitrate_kbps(Some(128), Some(2.0), 100), 128);
}

#[test]
fn test_bitrate_estimado_pelo_tamanho() {
    // 32000 bytes em 2 s = 128 kbps
    assert_eq!(bitrate_kbps(None, Some(2.0), 32000), 128);
    assert_eq!(bitrate_kbps(Some(0), Some(2.0), 32000), 128);
}

#[test]
fn test_bitrate_sem_duracao_e_zero() {
    assert_eq!(bitrate_kbps(None, Some(0.0), 1000), 0);
    assert_eq!(bitrate_kbps(None, None, 1000), 0);
}
