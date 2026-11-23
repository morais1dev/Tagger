//! Porte de tests/test_metadata.py (v2): FLAC, Ogg Vorbis/Opus e M4A (a fixture `outro`).

mod comum;

use std::collections::BTreeMap;
use std::path::Path;

use comum::*;
use lofty::mp4::{Atom, AtomData, AtomIdent};
use lofty::ogg::OggPictureStorage;
use lofty::picture::{MimeType, Picture, PictureInformation, PictureType};
use tagger_core::metadados::*;

fn ext(caminho: &Path) -> &str {
    caminho.extension().unwrap().to_str().unwrap()
}

fn artista_no_disco(caminho: &Path) -> Vec<String> {
    if ext(caminho) == "m4a" {
        let t = ilst(caminho).unwrap();
        return t
            .get(&AtomIdent::Fourcc(*b"\xa9ART"))
            .map(|a| a.data().filter_map(|d| if let AtomData::UTF8(s) = d { Some(s.clone()) } else { None }).collect())
            .unwrap_or_default();
    }
    valores(&vorbis(caminho).unwrap(), "ARTIST")
}

/// Quantas chaves/átomos de texto o arquivo tem (o `len(tags.keys())` da v2).
fn quantas_chaves(caminho: &Path) -> usize {
    if ext(caminho) == "m4a" {
        return ilst(caminho).map(|t| (&t).into_iter().count()).unwrap_or(0);
    }
    // Diferença da v2: a lofty não grava um Vorbis comment vazio no FLAC (o bloco some); conta como 0
    let Some(t) = vorbis(caminho) else { return 0 };
    let mut chaves: Vec<String> = t.items().map(|(k, _)| k.to_uppercase()).collect();
    chaves.dedup();
    chaves.len()
}

fn com_imagens_outro(caminho: &Path, imagens: &[(u8, &[u8])]) {
    match ext(caminho) {
        "flac" => {
            let mut a = flac(caminho);
            for (tipo, dados) in imagens {
                a.insert_picture(imagem(*tipo, dados), Some(PictureInformation::default())).unwrap();
            }
            salvar_flac(caminho, &a);
        }
        "ogg" => editar_vorbis(caminho, |t| {
            for (tipo, dados) in imagens {
                t.insert_picture(imagem(*tipo, dados), Some(PictureInformation::default())).unwrap();
            }
        }),
        _ => editar_ilst(caminho, |t| {
            for (_tipo, dados) in imagens {
                t.insert_picture(Picture::unchecked(dados.to_vec()).mime_type(MimeType::Jpeg).build());
            }
        }),
    }
}

fn imagens_outro(caminho: &Path) -> Vec<(Option<u8>, Vec<u8>)> {
    match ext(caminho) {
        "flac" => flac(caminho).pictures().iter().map(|(p, _)| (Some(p.pic_type().as_u8()), p.data().to_vec())).collect(),
        "ogg" => vorbis(caminho)
            .unwrap()
            .pictures()
            .iter()
            .map(|(p, _)| (Some(p.pic_type().as_u8()), p.data().to_vec()))
            .collect(),
        _ => ilst(caminho)
            .and_then(|t| t.pictures().map(|p| p.map(|p| (None, p.data().to_vec())).collect()))
            .unwrap_or_default(),
    }
}

fn capa(dados: &[u8], mime: &str) -> AcaoCapa {
    AcaoCapa::Definir { dados: dados.to_vec(), mime: mime.to_string() }
}

#[test]
fn test_outro_sem_tags() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        let faixa = carregar(&a).unwrap();
        assert!(faixa.tags.values().all(String::is_empty), "{fmt}");
        assert!(!faixa.tem_capa && (faixa.duracao - 2.0).abs() < 0.01, "{fmt}: {}", faixa.duracao);
        assert_eq!(faixa.formato.map(Formato::nome), Some(fmt));
        assert!(ler_capa(&a).is_none());
    }
}

#[test]
fn test_outro_ler_nao_grava() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        let antes = std::fs::read(&a).unwrap();
        carregar(&a);
        ler_capa(&a);
        analisar_extras(&a);
        assert_eq!(std::fs::read(&a).unwrap(), antes, "{fmt}");
    }
}

#[test]
fn test_outro_salvar_e_reler() {
    let valores = [
        (Campo::Titulo, "Música"),
        (Campo::Artista, "A; B"),
        (Campo::Album, "Álbum"),
        (Campo::ArtistaAlbum, "Vários"),
        (Campo::Faixa, "3/12"),
        (Campo::Disco, "1/2"),
        (Campo::Data, "2024-05-17"),
        (Campo::Genero, "Rock; Pop"),
        (Campo::Compositor, "C"),
        (Campo::Letrista, "L1; L2"),
        (Campo::Comentario, "linha 1\nlinha 2"),
        (Campo::Letra, "lá lá\nlá"),
        (Campo::Gravadora, "Selo; Dois"),
    ];
    for fmt in OUTROS {
        let a = amostra(fmt);
        salvar(&a, &valores, None, PADRAO).unwrap();
        let tags = carregar(&a).unwrap().tags;
        let esperado: Tags = valores.iter().map(|(c, v)| (*c, v.to_string())).collect();
        assert_eq!(tags, esperado, "{fmt}");
    }
}

#[test]
fn test_outro_multivalor_nativo() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        salvar(&a, &[(Campo::Artista, "A; B")], None, PADRAO).unwrap();
        assert_eq!(artista_no_disco(&a), ["A", "B"], "{fmt}");
        salvar(&a, &[(Campo::Artista, "A; B")], None, OpcoesGravacao { multivalor: false, ..PADRAO }).unwrap();
        assert_eq!(artista_no_disco(&a), ["A; B"], "{fmt}");
    }
}

#[test]
fn test_outro_faixa_sem_total() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        salvar(&a, &[(Campo::Faixa, "3/12")], None, PADRAO).unwrap();
        salvar(&a, &[(Campo::Faixa, "4")], None, PADRAO).unwrap();
        // Vorbis: o total é outra chave (TRACKTOTAL) e fica; MP4: é o mesmo par (trkn), como no ID3
        let esperado = if fmt == "m4a" { "4" } else { "4/12" };
        assert_eq!(campo(&a, Campo::Faixa), esperado, "{fmt}");
        salvar(&a, &[(Campo::Faixa, "")], None, PADRAO).unwrap(); // apagar a faixa apaga o total junto
        assert_eq!(campo(&a, Campo::Faixa), "");
        assert_eq!(quantas_chaves(&a), 0, "{fmt}");
    }
}

#[test]
fn test_vorbis_numero_sem_barra_mantem_total() {
    for (c, chave, principal, total) in [
        (Campo::Faixa, "TRACKTOTAL", "TRACKNUMBER", "TOTALTRACKS"),
        (Campo::Disco, "DISCTOTAL", "DISCNUMBER", "TOTALDISCS"),
    ] {
        let a = amostra("flac");
        editar_vorbis(&a, |t| {
            t.push(principal.into(), "3".into());
            t.push(total.into(), "12".into()); // nome alternativo do total
        });
        salvar(&a, &[(c, "5")], None, PADRAO).unwrap();
        let g = vorbis(&a).unwrap();
        assert_eq!((valores(&g, principal), valores(&g, total)), (vec!["5".into()], vec!["12".into()]));
        assert_eq!(campo(&a, c), "5/12");
        salvar(&a, &[(c, "6/7")], None, PADRAO).unwrap(); // total novo: um só, com o nome principal
        let g = vorbis(&a).unwrap();
        assert_eq!(valores(&g, chave), ["7"]);
        assert!(valores(&g, total).is_empty());
    }
}

#[test]
fn test_vorbis_alternativa_com_outro_conteudo_fica() {
    let a = amostra("flac");
    editar_vorbis(&a, |t| {
        for (k, v) in [
            ("COMMENT", "visto"),
            ("DESCRIPTION", "nunca exibido"),
            ("ALBUMARTIST", "X"),
            ("ALBUM ARTIST", "X"),
            ("LYRICS", "letra"),
            ("UNSYNCEDLYRICS", "outra letra"),
        ] {
            t.push(k.into(), v.into());
        }
    });
    salvar(&a, &[(Campo::Comentario, "novo"), (Campo::ArtistaAlbum, "Y"), (Campo::Letra, "")], None, PADRAO).unwrap();
    let g = vorbis(&a).unwrap();
    assert_eq!(valores(&g, "COMMENT"), ["novo"]);
    assert_eq!(valores(&g, "DESCRIPTION"), ["nunca exibido"]);
    assert_eq!(valores(&g, "ALBUMARTIST"), ["Y"]);
    assert!(valores(&g, "ALBUM ARTIST").is_empty());
    assert!(valores(&g, "LYRICS").is_empty());
    assert_eq!(valores(&g, "UNSYNCEDLYRICS"), ["outra letra"]);
}

#[test]
fn test_outro_so_o_primeiro_comentario_ou_letra_e_trocado() {
    for fmt in OUTROS {
        for (c, chave_vorbis, fourcc) in
            [(Campo::Comentario, "COMMENT", *b"\xa9cmt"), (Campo::Letra, "LYRICS", *b"\xa9lyr")]
        {
            let a = amostra(fmt);
            if fmt == "m4a" {
                editar_ilst(&a, |t| {
                    let dados = vec![AtomData::UTF8("primeiro".into()), AtomData::UTF8("segundo".into())];
                    t.insert(Atom::from_collection(AtomIdent::Fourcc(fourcc), dados).unwrap());
                });
            } else {
                editar_vorbis(&a, |t| {
                    t.push(chave_vorbis.into(), "primeiro".into());
                    t.push(chave_vorbis.into(), "segundo".into());
                });
            }
            assert_eq!(campo(&a, c), "primeiro", "{fmt}");
            salvar(&a, &[(c, "novo")], None, PADRAO).unwrap();
            let no_disco: Vec<String> = if fmt == "m4a" {
                ilst(&a)
                    .unwrap()
                    .get(&AtomIdent::Fourcc(fourcc))
                    .unwrap()
                    .data()
                    .filter_map(|d| if let AtomData::UTF8(s) = d { Some(s.clone()) } else { None })
                    .collect()
            } else {
                valores(&vorbis(&a).unwrap(), chave_vorbis)
            };
            assert_eq!(no_disco, ["novo", "segundo"], "{fmt} {c:?}");
        }
    }
}

#[test]
fn test_mp4_limpeza_nao_toca_atomos_tecnicos() {
    let a = amostra("m4a");
    let livre = |nome: &str, dado: &[u8]| {
        Atom::new(
            AtomIdent::Freeform { mean: "com.apple.iTunes".into(), name: nome.to_string().into() },
            AtomData::UTF8(String::from_utf8(dado.to_vec()).unwrap()),
        )
    };
    editar_ilst(&a, |t| {
        t.insert(Atom::new(AtomIdent::Fourcc(*b"\xa9too"), AtomData::UTF8("Lavf".into())));
        t.insert(Atom::new(AtomIdent::Fourcc(*b"pgap"), AtomData::Bool(true)));
        t.insert(Atom::new(AtomIdent::Fourcc(*b"cpil"), AtomData::Bool(true)));
        t.insert(Atom::new(AtomIdent::Fourcc(*b"tmpo"), AtomData::SignedInteger(120)));
        t.insert(livre("iTunSMPB", b" 00000000 00000840"));
        t.insert(livre("iTunNORM", b" 0000031F"));
    });
    assert_eq!(analisar_extras(&a).extras, BTreeMap::from([("\u{a9}too".to_string(), 1)]));
    assert!(limpar_extras(&a, false, false, true, PADRAO).unwrap());
    let mut restantes: Vec<String> = (&ilst(&a).unwrap()).into_iter().map(|at| at.ident().to_string()).collect();
    restantes.sort();
    assert_eq!(restantes, ["----:com.apple.iTunes:iTunNORM", "----:com.apple.iTunes:iTunSMPB", "cpil", "pgap", "tmpo"]);
}

#[test]
fn test_mp4_capa_que_nao_e_jpeg_nem_png_e_recusada() {
    let a = amostra("m4a");
    let antes = std::fs::read(&a).unwrap();
    let r = salvar(&a, &[(Campo::Titulo, "A")], Some(&capa(b"GIF89a", "image/gif")), PADRAO);
    assert!(matches!(r, Err(Erro::CapaInvalida(_))));
    assert_eq!(std::fs::read(&a).unwrap(), antes); // nada gravado, nem o título
}

#[test]
fn test_ogg_coverart_antigo() {
    use base64::Engine;
    let a = amostra("ogg");
    editar_vorbis(&a, |t| {
        t.push("COVERART".into(), base64::engine::general_purpose::STANDARD.encode(PNG));
        t.push("COVERARTMIME".into(), "image/png".into());
    });
    // (a lofty de fora já converte o COVERART ao regravar acima; confere-se o resultado pelo núcleo)
    assert!(carregar(&a).unwrap().tem_capa);
    assert_eq!(ler_capa(&a), Some((PNG.to_vec(), "image/png".into())));
    definir_capa(&a, JPEG, "image/jpeg", PADRAO).unwrap();
    let g = vorbis(&a).unwrap();
    assert!(valores(&g, "COVERART").is_empty() && valores(&g, "COVERARTMIME").is_empty());
    assert_eq!(ler_capa(&a), Some((JPEG.to_vec(), "image/jpeg".into())));
}

#[test]
fn test_ogg_opus() {
    let a = amostra("opus");
    let faixa = carregar(&a).unwrap();
    assert_eq!(faixa.formato, Some(Formato::Ogg));
    assert!((faixa.duracao - 2.0).abs() < 0.01, "{}", faixa.duracao);
    salvar(&a, &[(Campo::Titulo, "Opus"), (Campo::Artista, "A; B")], Some(&capa(JPEG, "image/jpeg")), PADRAO).unwrap();
    assert_eq!(valores(&vorbis(&a).unwrap(), "ARTIST"), ["A", "B"]);
    let faixa = carregar(&a).unwrap();
    assert_eq!(faixa.tags[&Campo::Titulo], "Opus");
    assert_eq!(faixa.tags[&Campo::Artista], "A; B");
    assert!(faixa.tem_capa);
    assert_eq!(ler_capa(&a), Some((JPEG.to_vec(), "image/jpeg".into())));
}

#[test]
fn test_outro_valor_vazio_remove_e_varios_ignora() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        salvar(&a, &[(Campo::Titulo, "A"), (Campo::Artista, "B"), (Campo::Faixa, "3/12")], None, PADRAO).unwrap();
        salvar(&a, &[(Campo::Titulo, ""), (Campo::Artista, VARIOS), (Campo::Faixa, "")], None, PADRAO).unwrap();
        let t = carregar(&a).unwrap().tags;
        assert_eq!(
            (t[&Campo::Titulo].as_str(), t[&Campo::Artista].as_str(), t[&Campo::Faixa].as_str()),
            ("", "B", ""),
            "{fmt}"
        );
        assert_eq!(quantas_chaves(&a), 1, "{fmt}: nem TRACKTOTAL sobra");
    }
}

#[test]
fn test_outro_um_unico_save() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        salvar(&a, &[(Campo::Titulo, "A")], Some(&capa(JPEG, "image/jpeg")), PADRAO).unwrap();
        assert_eq!(campo(&a, Campo::Titulo), "A");
        assert_eq!(ler_capa(&a), Some((JPEG.to_vec(), "image/jpeg".into())), "{fmt}");
    }
}

#[test]
fn test_outro_capa_definir_trocar_remover() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        definir_capa(&a, JPEG, "image/jpeg", PADRAO).unwrap();
        assert!(carregar(&a).unwrap().tem_capa);
        assert_eq!(ler_capa(&a), Some((JPEG.to_vec(), "image/jpeg".into())));
        definir_capa(&a, PNG, "image/png", PADRAO).unwrap();
        assert_eq!(ler_capa(&a), Some((PNG.to_vec(), "image/png".into())), "{fmt}");
        assert_eq!(imagens_outro(&a).len(), 1, "{fmt}");
        remover_capa(&a, PADRAO).unwrap();
        assert!(ler_capa(&a).is_none() && !carregar(&a).unwrap().tem_capa, "{fmt}");
    }
}

#[test]
fn test_outro_outras_imagens_ficam() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        com_imagens_outro(&a, &[(3, b"frente"), (4, b"verso")]);
        assert_eq!(ler_capa(&a).unwrap().0, b"frente", "{fmt}");
        definir_capa(&a, JPEG, "image/jpeg", PADRAO).unwrap();
        let imagens = imagens_outro(&a);
        assert_eq!(imagens.len(), 2, "{fmt}");
        assert!(imagens.iter().any(|(_, d)| d == b"verso"), "{fmt}");
        assert_eq!(ler_capa(&a), Some((JPEG.to_vec(), "image/jpeg".into())), "{fmt}");
        remover_capa(&a, PADRAO).unwrap();
        assert_eq!(imagens_outro(&a).into_iter().map(|(_, d)| d).collect::<Vec<_>>(), [b"verso".to_vec()], "{fmt}");
    }
}

#[test]
fn test_vorbis_so_contracapa_nao_conta_como_capa() {
    for fmt in ["flac", "ogg"] {
        let a = amostra(fmt);
        com_imagens_outro(&a, &[(4, b"verso")]);
        assert!(!carregar(&a).unwrap().tem_capa, "{fmt}");
        definir_capa(&a, JPEG, "image/jpeg", PADRAO).unwrap();
        let mut tipos: Vec<u8> = imagens_outro(&a).into_iter().map(|(t, _)| t.unwrap()).collect();
        tipos.sort();
        assert_eq!(tipos, [3, 4], "{fmt}");
    }
}

#[test]
fn test_flac_sem_vorbis_comment_remove_capa() {
    let a = amostra("flac");
    com_imagens_outro(&a, &[(3, b"frente")]);
    assert!(flac(&a).vorbis_comments().is_none());
    remover_capa(&a, PADRAO).unwrap();
    assert!(ler_capa(&a).is_none());
    assert!(flac(&a).vorbis_comments().is_none());
    assert!(flac(&a).pictures().is_empty());
}

#[test]
fn test_vorbis_nomes_alternativos() {
    let a = amostra("flac");
    editar_vorbis(&a, |t| {
        for (k, v) in
            [("DESCRIPTION", "comentário antigo"), ("UNSYNCEDLYRICS", "letra antiga"), ("TRACKNUMBER", "5"), ("TOTALTRACKS", "9")]
        {
            t.push(k.into(), v.into());
        }
    });
    let t = carregar(&a).unwrap().tags;
    assert_eq!(
        (t[&Campo::Comentario].as_str(), t[&Campo::Letra].as_str(), t[&Campo::Faixa].as_str()),
        ("comentário antigo", "letra antiga", "5/9")
    );
    salvar(&a, &[(Campo::Comentario, "novo"), (Campo::Letra, ""), (Campo::Faixa, "6/10")], None, PADRAO).unwrap();
    let mut chaves: Vec<String> = vorbis(&a).unwrap().items().map(|(k, _)| k.to_uppercase()).collect();
    chaves.sort();
    chaves.dedup();
    assert_eq!(chaves, ["COMMENT", "TRACKNUMBER", "TRACKTOTAL"]);
    assert_eq!(campo(&a, Campo::Faixa), "6/10");
}

#[test]
fn test_outro_analisar_e_limpar_extras() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        salvar(&a, &[(Campo::Titulo, "fica"), (Campo::Faixa, "1/2")], Some(&capa(JPEG, "image/jpeg")), PADRAO).unwrap();
        let chave = if fmt == "m4a" {
            editar_ilst(&a, |t| {
                t.insert(Atom::new(
                    AtomIdent::Freeform { mean: "com.apple.iTunes".into(), name: "replaygain_track_gain".into() },
                    AtomData::UTF8("-6 dB".into()),
                ))
            });
            "----:com.apple.iTunes:replaygain_track_gain"
        } else {
            editar_vorbis(&a, |t| t.push("REPLAYGAIN_TRACK_GAIN".into(), "-6 dB".into()));
            "REPLAYGAIN_TRACK_GAIN"
        };
        let analise = analisar_extras(&a);
        assert_eq!(
            analise,
            AnaliseExtras { id3v1: false, desconhecidos: 0, extras: BTreeMap::from([(chave.to_string(), 1)]) },
            "{fmt}"
        );
        assert!(!tem_id3v1(&a));
        assert!(limpar_extras(&a, true, true, true, PADRAO).unwrap());
        assert!(analisar_extras(&a).extras.is_empty());
        let faixa = carregar(&a).unwrap();
        assert_eq!(faixa.tags[&Campo::Titulo], "fica");
        assert_eq!(faixa.tags[&Campo::Faixa], "1/2");
        assert!(faixa.tem_capa);
        assert!(!limpar_extras(&a, true, true, true, PADRAO).unwrap(), "{fmt}: nada mais a fazer");
    }
}

#[test]
fn test_outro_id3v1_nunca_corta_o_arquivo() {
    use std::io::Write;
    for fmt in OUTROS {
        let a = amostra(fmt);
        let mut v1 = b"TAG".to_vec();
        v1.resize(128, 0);
        std::fs::OpenOptions::new().append(true).open(&a).unwrap().write_all(&v1).unwrap();
        let antes = std::fs::read(&a).unwrap();
        assert!(!tem_id3v1(&a) && !analisar_extras(&a).id3v1);
        assert!(!limpar_extras(&a, true, false, false, PADRAO).unwrap_or(false));
        assert_eq!(std::fs::read(&a).unwrap(), antes, "{fmt}");
    }
}

#[test]
fn test_outro_arquivo_invalido() {
    let lixo = pasta().join("quebrado.flac");
    std::fs::write(&lixo, b"isto nao e audio".repeat(10)).unwrap();
    assert!(carregar(&lixo).is_none() && ler_capa(&lixo).is_none());
    assert_eq!(analisar_extras(&lixo), AnaliseExtras::default());
    assert_eq!(salvar_varios(&[&lixo], &[(Campo::Titulo, "A")], PADRAO).into_keys().collect::<Vec<_>>(), std::slice::from_ref(&lixo));
}

// ----------------------------------------------------------------- gravadora
#[test]
fn test_gravadora_outro_gravar_e_apagar() {
    for fmt in OUTROS {
        let a = amostra(fmt);
        salvar(&a, &[(Campo::Gravadora, "Selo")], None, PADRAO).unwrap();
        assert_eq!(campo(&a, Campo::Gravadora), "Selo");
        let livre = AtomIdent::Freeform { mean: "com.apple.iTunes".into(), name: "LABEL".into() };
        if fmt == "m4a" {
            assert!(ilst(&a).unwrap().get(&livre).is_some());
        } else {
            assert_eq!(valores(&vorbis(&a).unwrap(), "ORGANIZATION"), ["Selo"]);
        }
        salvar(&a, &[(Campo::Gravadora, "")], None, PADRAO).unwrap();
        assert_eq!(campo(&a, Campo::Gravadora), "");
        if fmt == "m4a" {
            assert!(ilst(&a).is_none_or(|t| t.get(&livre).is_none()));
        } else {
            assert!(vorbis(&a).is_none_or(|t| valores(&t, "ORGANIZATION").is_empty()));
        }
    }
}

#[test]
fn test_gravadora_vorbis_le_label() {
    for fmt in ["flac", "ogg"] {
        let a = amostra(fmt);
        editar_vorbis(&a, |t| t.push("LABEL".into(), "Selo Antigo".into()));
        assert_eq!(campo(&a, Campo::Gravadora), "Selo Antigo");
        salvar(&a, &[(Campo::Gravadora, "Novo")], None, PADRAO).unwrap(); // troca o exibido, sem deixar o LABEL velho
        let g = vorbis(&a).unwrap();
        assert_eq!(valores(&g, "ORGANIZATION"), ["Novo"]);
        assert!(valores(&g, "LABEL").is_empty());
        salvar(&a, &[(Campo::Gravadora, "")], None, PADRAO).unwrap();
        assert_eq!(campo(&a, Campo::Gravadora), "");
    }
}

#[test]
fn test_gravadora_vorbis_organization_tem_prioridade() {
    let a = amostra("flac");
    editar_vorbis(&a, |t| {
        t.push("ORGANIZATION".into(), "Principal".into());
        t.push("LABEL".into(), "Outro".into());
    });
    assert_eq!(campo(&a, Campo::Gravadora), "Principal");
}

#[allow(dead_code)]
fn _tipos_usados(_: PictureType) {}
