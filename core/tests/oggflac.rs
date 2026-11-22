//! FLAC dentro de Ogg (implementação própria em core/src/metadados/oggflac.rs). A v2 abre esse
//! formato pelo mutagen (OggFLAC) mas não tem teste dele; estes seguem os testes da fixture `outro`.

mod comum;

use std::collections::BTreeMap;

use comum::*;
use tagger_core::metadados::*;

fn paginas_validas(caminho: &std::path::Path) -> usize {
    // cada página com "OggS", sequência contínua e CRC conferido pelo ogg_pager
    let bytes = std::fs::read(caminho).unwrap();
    let mut cursor = std::io::Cursor::new(&bytes);
    let mut n = 0;
    while (cursor.position() as usize) < bytes.len() {
        let inicio = cursor.position() as usize;
        let pagina = ogg_pager::Page::read(&mut cursor).expect("página válida");
        assert_eq!(pagina.header().sequence_number as usize, n);
        let mut copia = pagina.clone();
        copia.gen_crc();
        assert_eq!(copia.as_bytes(), bytes[inicio..cursor.position() as usize], "CRC da página {n}");
        n += 1;
    }
    n
}

fn audio(caminho: &std::path::Path) -> Vec<u8> {
    let bytes = std::fs::read(caminho).unwrap();
    let i = bytes.windows(100).position(|w| w.iter().all(|&b| b == 0xff)).unwrap();
    bytes[i..i + 100].to_vec()
}

#[test]
fn oggflac_sem_tags() {
    let a = amostra("oggflac");
    let faixa = carregar(&a).unwrap();
    assert_eq!(faixa.formato, Some(Formato::Ogg));
    assert!(faixa.tags.values().all(String::is_empty));
    assert!(!faixa.tem_capa && (faixa.duracao - 2.0).abs() < 0.01, "{}", faixa.duracao);
    assert!(ler_capa(&a).is_none());
    assert_eq!(paginas_validas(&a), 3);
}

#[test]
fn oggflac_ler_nao_grava() {
    let a = amostra("oggflac");
    let antes = std::fs::read(&a).unwrap();
    carregar(&a);
    ler_capa(&a);
    analisar_extras(&a);
    assert_eq!(std::fs::read(&a).unwrap(), antes);
}

#[test]
fn oggflac_salvar_e_reler() {
    let a = amostra("oggflac");
    let som = audio(&a);
    let valores = [
        (Campo::Titulo, "Música"),
        (Campo::Artista, "A; B"),
        (Campo::Faixa, "3/12"),
        (Campo::Data, "2024-05-17"),
        (Campo::Genero, "Rock; Pop"),
        (Campo::Comentario, "linha 1\nlinha 2"),
        (Campo::Gravadora, "Selo"),
    ];
    salvar(&a, &valores, None, PADRAO).unwrap();
    let tags = carregar(&a).unwrap().tags;
    for (c, v) in valores {
        assert_eq!(tags[&c], v, "{c:?}");
    }
    assert_eq!(paginas_validas(&a), 3);
    assert_eq!(audio(&a), som);
    salvar(&a, &[(Campo::Titulo, ""), (Campo::Artista, VARIOS)], None, PADRAO).unwrap();
    let tags = carregar(&a).unwrap().tags;
    assert_eq!((tags[&Campo::Titulo].as_str(), tags[&Campo::Artista].as_str()), ("", "A; B"));
}

#[test]
fn oggflac_comentario_grande_ocupa_varias_paginas() {
    let a = amostra("oggflac");
    let som = audio(&a);
    let letra = "lá ".repeat(20_000); // > 1 página Ogg (~8 KB por página escrita)
    salvar(&a, &[(Campo::Letra, &letra)], None, PADRAO).unwrap();
    assert_eq!(campo(&a, Campo::Letra), letra);
    assert!(paginas_validas(&a) > 3);
    assert_eq!(audio(&a), som);
    salvar(&a, &[(Campo::Letra, "curta")], None, PADRAO).unwrap();
    assert_eq!(campo(&a, Campo::Letra), "curta");
    assert_eq!(paginas_validas(&a), 3);
}

#[test]
fn oggflac_capa_definir_trocar_remover() {
    let a = amostra("oggflac");
    definir_capa(&a, JPEG, "image/jpeg", PADRAO).unwrap();
    assert_eq!(ler_capa(&a), Some((JPEG.to_vec(), "image/jpeg".into())));
    definir_capa(&a, PNG, "image/png", PADRAO).unwrap();
    assert_eq!(ler_capa(&a), Some((PNG.to_vec(), "image/png".into())));
    remover_capa(&a, PADRAO).unwrap();
    assert!(ler_capa(&a).is_none() && !carregar(&a).unwrap().tem_capa);
}

#[test]
fn oggflac_analisar_e_limpar_extras() {
    let a = pasta().join("musica.ogg");
    tagger_core::amostras::oggflac_com(&a, &[("TITLE", "fica"), ("REPLAYGAIN_TRACK_GAIN", "-6 dB")]).unwrap();
    definir_capa(&a, JPEG, "image/jpeg", PADRAO).unwrap();
    assert_eq!(
        analisar_extras(&a),
        AnaliseExtras { extras: BTreeMap::from([("REPLAYGAIN_TRACK_GAIN".to_string(), 1)]), ..Default::default() }
    );
    assert!(limpar_extras(&a, true, true, true, PADRAO).unwrap());
    assert!(analisar_extras(&a).extras.is_empty());
    let faixa = carregar(&a).unwrap();
    assert_eq!(faixa.tags[&Campo::Titulo], "fica");
    assert!(faixa.tem_capa);
    assert!(!limpar_extras(&a, true, true, true, PADRAO).unwrap());
}
