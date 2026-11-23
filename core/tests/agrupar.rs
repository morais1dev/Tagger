//! Porte de tests/test_agrupar.py (v2).

use tagger_core::agrupar::*;
use tagger_core::metadados::{Campo, Tags};

fn t(pares: &[(Campo, &str)]) -> Tags {
    pares.iter().map(|(c, v)| (*c, v.to_string())).collect()
}

#[test]
fn test_chave_grupo_ignora_caixa_e_espacos() {
    assert_eq!(
        chave_grupo(&t(&[(Campo::Album, " Abbey Road "), (Campo::ArtistaAlbum, "The Beatles")])),
        chave_grupo(&t(&[(Campo::Album, "abbey road"), (Campo::ArtistaAlbum, "the beatles")]))
    );
    assert_ne!(chave_grupo(&t(&[(Campo::Album, "A")])), chave_grupo(&t(&[(Campo::Album, "A"), (Campo::ArtistaAlbum, "X")])));
    assert_eq!(chave_grupo(&t(&[])), chave_grupo(&t(&[(Campo::Album, "  ")])));
}

#[test]
fn test_mais_de_um_album() {
    let a = t(&[(Campo::Album, "A")]);
    assert!(!mais_de_um_album(&[]));
    assert!(!mais_de_um_album(&[a.clone(), a.clone()]));
    assert!(mais_de_um_album(&[a.clone(), t(&[(Campo::Album, "B")])]));
    assert!(mais_de_um_album(&[a, t(&[])]));
}

#[test]
fn test_ordem_por_album_disco_faixa_e_sem_album_no_fim() {
    let faixas = [
        t(&[(Campo::Album, "B"), (Campo::Faixa, "1")]),
        t(&[]),
        t(&[(Campo::Album, "A"), (Campo::Disco, "2/2"), (Campo::Faixa, "1")]),
        t(&[(Campo::Album, "A"), (Campo::Disco, "1"), (Campo::Faixa, "10/12")]),
        t(&[(Campo::Album, "A"), (Campo::Disco, "1"), (Campo::Faixa, "2")]),
        t(&[(Campo::Album, "A"), (Campo::Faixa, "")]),
    ];
    let mut ordenadas: Vec<&Tags> = faixas.iter().collect();
    ordenadas.sort_by_key(|f| chave_ordem(f));
    let resumo: Vec<(Option<&str>, Option<&str>, Option<&str>)> = ordenadas
        .iter()
        .map(|f| {
            let g = |c| f.get(&c).map(String::as_str);
            (g(Campo::Album), g(Campo::Disco), g(Campo::Faixa))
        })
        .collect();
    assert_eq!(
        resumo,
        [
            (Some("A"), Some("1"), Some("2")),
            (Some("A"), Some("1"), Some("10/12")),
            (Some("A"), None, Some("")),
            (Some("A"), Some("2/2"), Some("1")),
            (Some("B"), None, Some("1")),
            (None, None, None),
        ]
    );
}

#[test]
fn test_ordem_faixa() {
    assert_eq!(ordem_faixa(&t(&[(Campo::Disco, "1/2"), (Campo::Faixa, "3/9")])), (1, 3));
    assert!(ordem_faixa(&t(&[])) > ordem_faixa(&t(&[(Campo::Faixa, "99")])));
}

#[test]
fn test_titulo_cabecalho() {
    let disco = (Campo::Album, "Disco");
    assert_eq!(titulo_cabecalho(&[t(&[disco, (Campo::ArtistaAlbum, "Banda"), (Campo::Data, "2019-05-01")])]), "Disco — Banda, 2019");
    assert_eq!(titulo_cabecalho(&[t(&[disco, (Campo::Artista, "Fulano")])]), "Disco — Fulano");
    assert_eq!(titulo_cabecalho(&[t(&[disco, (Campo::Data, "1999")])]), "Disco, 1999");
    assert_eq!(titulo_cabecalho(&[t(&[disco]), t(&[disco, (Campo::Data, "2001")])]), "Disco, 2001");
    assert_eq!(titulo_cabecalho(&[t(&[(Campo::Artista, "X")])]), SEM_ALBUM);
}

#[test]
fn chave_grupo_usa_a_dobra_de_caixa_completa() {
    // como o casefold() da v2: "ß" dobra para "ss"
    assert_eq!(
        chave_grupo(&t(&[(Campo::Album, "Straße"), (Campo::ArtistaAlbum, "Weiß")])),
        chave_grupo(&t(&[(Campo::Album, "STRASSE"), (Campo::ArtistaAlbum, "WEISS")]))
    );
    assert!(!mais_de_um_album(&[t(&[(Campo::Album, "Straße")]), t(&[(Campo::Album, "strasse")])]));
}
