//! Porte de tests/test_padroes.py (v2).

mod comum;

use std::path::{Path, PathBuf};

use comum::pasta;
use tagger_core::metadados::{Campo, Tags};
use tagger_core::padroes::*;

const PADRAO: &str = "{tracknumber:02} - {artist} - {title}";

fn t(pares: &[(Campo, &str)]) -> Tags {
    pares.iter().map(|(c, v)| (*c, v.to_string())).collect()
}

fn arquivo(pasta: &Path, nome: &str) -> PathBuf {
    let p = pasta.join(nome);
    tagger_core::amostras::mp3(&p).unwrap();
    p
}

fn nomes(pasta: &Path) -> Vec<String> {
    let mut v: Vec<String> =
        std::fs::read_dir(pasta).unwrap().map(|e| e.unwrap().file_name().to_string_lossy().into_owned()).collect();
    v.sort();
    v
}

// ----------------------------------------------------------------- padrão
#[test]
fn test_campos_do_padrao() {
    assert_eq!(
        campos_do_padrao("%track% - %artist% - {*} - {title}").unwrap(),
        [Campo::Faixa, Campo::Artista, Campo::Titulo]
    );
}

#[test]
fn test_campo_desconhecido() {
    assert!(campos_do_padrao("{artista}").unwrap_err().contains("desconhecido"));
}

// ----------------------------------------------------------------- tags -> nome
#[test]
fn test_nome_pelas_tags() {
    let valores = t(&[(Campo::Faixa, "3/12"), (Campo::Artista, "Artista"), (Campo::Titulo, "Música")]);
    assert_eq!(nome_pelas_tags(PADRAO, &valores).unwrap(), "03 - Artista - Música");
    assert_eq!(nome_pelas_tags("%track% %title%", &valores).unwrap(), "3 Música");
}

#[test]
fn test_campos_vazios_nao_deixam_separadores_sobrando() {
    assert_eq!(nome_pelas_tags(PADRAO, &t(&[(Campo::Titulo, "Só título")])).unwrap(), "Só título");
    assert_eq!(nome_pelas_tags(PADRAO, &t(&[(Campo::Faixa, "1"), (Campo::Titulo, "T")])).unwrap(), "01 - T");
    assert_eq!(nome_pelas_tags(PADRAO, &t(&[])).unwrap(), "");
}

#[test]
fn test_sanitizar() {
    for (entrada, saida) in [
        ("AC/DC: \"Live\"?", "AC-DC - 'Live'"),
        ("a\\b|c*d<e>f", "a-b-cdef"),
        ("  muitos    espaços  ", "muitos espaços"),
        ("tab\taqui\u{0}", "tab aqui"),
    ] {
        assert_eq!(sanitizar(entrada), saida, "{entrada:?}");
    }
}

#[test]
fn test_nomes_reservados_e_pontos_no_fim() {
    assert_eq!(nome_pelas_tags("{title}", &t(&[(Campo::Titulo, "CON")])).unwrap(), "CON_");
    assert_eq!(nome_pelas_tags("{title}", &t(&[(Campo::Titulo, "Fim...")])).unwrap(), "Fim");
}

#[test]
fn test_barra_no_padrao_e_recusada() {
    assert!(nome_pelas_tags("{artist}/{title}", &t(&[(Campo::Titulo, "x")])).is_err());
}

// ----------------------------------------------------------------- planejar / executar
fn itens(pares: &[(&PathBuf, &str)]) -> Vec<(PathBuf, Tags)> {
    pares.iter().map(|(c, titulo)| ((*c).clone(), t(&[(Campo::Titulo, titulo)]))).collect()
}

#[test]
fn test_planejar_sem_mudanca_e_conflitos() {
    let p = pasta();
    let (a, b, c) = (arquivo(&p, "a.mp3"), arquivo(&p, "b.mp3"), arquivo(&p, "c.mp3"));
    arquivo(&p, "existe.mp3");
    let d = arquivo(&p, "d.mp3");
    let plano = planejar_renomeacao(&itens(&[(&a, "a"), (&b, "igual"), (&c, "igual"), (&d, "existe")]), "{title}").unwrap();
    assert!(plano[0].destino.is_none() && plano[0].erro.is_empty()); // nome não muda
    assert!(plano[1].erro.contains("mesmo nome") && plano[2].erro.contains("mesmo nome"));
    assert!(plano[3].erro.contains("Já existe"));
    assert!(!plano.iter().any(ItemRenomear::valido));
}

#[test]
fn test_nome_vazio_e_erro() {
    let p = pasta();
    let a = arquivo(&p, "a.mp3");
    assert!(planejar_renomeacao(&[(a, Tags::new())], "{title}").unwrap()[0].erro.contains("vazio"));
}

#[test]
fn test_renomear_e_trocar_nomes() {
    let p = pasta();
    let (a, b) = (arquivo(&p, "a.mp3"), arquivo(&p, "b.mp3"));
    let mut conteudo = std::fs::read(&a).unwrap();
    conteudo.push(b'A');
    std::fs::write(&a, conteudo).unwrap();
    let plano = planejar_renomeacao(&itens(&[(&a, "b"), (&b, "a")]), "{title}").unwrap(); // troca: a->b e b->a
    assert!(plano.iter().all(ItemRenomear::valido));
    let (feitos, falhas) = executar_renomeacao(&plano);
    assert!(falhas.is_empty(), "{falhas:?}");
    assert_eq!(feitos.len(), 2);
    assert!(std::fs::read(&b).unwrap().ends_with(b"A")); // o conteúdo de "a" agora é "b"
    assert_eq!(nomes(&p), ["a.mp3", "b.mp3"]);
}

#[test]
fn test_so_maiusculas_mudam() {
    let p = pasta();
    let a = arquivo(&p, "musica.mp3");
    let plano = planejar_renomeacao(&itens(&[(&a, "Musica")]), "{title}").unwrap();
    assert!(plano[0].valido());
    let (_feitos, falhas) = executar_renomeacao(&plano);
    assert!(falhas.is_empty(), "{falhas:?}");
    assert_eq!(nomes(&p), ["Musica.mp3"]);
}

#[test]
fn test_extensao_fica_minuscula() {
    let p = pasta();
    let a = arquivo(&p, "x.MP3");
    let destino = planejar_renomeacao(&itens(&[(&a, "y")]), "{title}").unwrap()[0].destino.clone().unwrap();
    assert_eq!(destino.file_name().unwrap(), "y.mp3");
}

#[test]
fn test_destino_criado_depois_da_previa_nao_e_sobrescrito() {
    let p = pasta();
    let a = arquivo(&p, "a.mp3");
    let plano = planejar_renomeacao(&itens(&[(&a, "novo")]), "{title}").unwrap();
    std::fs::write(p.join("novo.mp3"), b"de outro").unwrap();
    let (feitos, falhas) = executar_renomeacao(&plano);
    assert!(feitos.is_empty() && falhas.contains_key(&a));
    assert!(a.exists());
    assert_eq!(std::fs::read(p.join("novo.mp3")).unwrap(), b"de outro");
    assert!(!nomes(&p).iter().any(|n| n.ends_with(".tagger-tmp")));
}

// ----------------------------------------------------------------- nome -> tags
#[test]
fn test_tags_pelo_nome() {
    assert_eq!(
        tags_pelo_nome("%track% - %artist% - %title%", Path::new("03 - Artista - Nome - Com Hífen.mp3"), false).unwrap(),
        Some(t(&[(Campo::Faixa, "3"), (Campo::Artista, "Artista"), (Campo::Titulo, "Nome - Com Hífen")]))
    );
}

#[test]
fn test_tags_pelo_nome_nao_casa() {
    assert_eq!(tags_pelo_nome("%artist% - %title%", Path::new("sem separador.mp3"), false).unwrap(), None);
}

#[test]
fn test_tags_pelo_nome_ignorar_e_sublinhado() {
    assert_eq!(
        tags_pelo_nome("{*} {artist} - {title}", Path::new("[2020]_Banda_-_Faixa_boa.mp3"), true).unwrap(),
        Some(t(&[(Campo::Artista, "Banda"), (Campo::Titulo, "Faixa boa")]))
    );
}

#[test]
fn test_tags_pelas_pastas() {
    let caminho = Path::new("musicas").join("Artista").join("Álbum (2001)").join("07 Faixa.mp3");
    assert_eq!(
        tags_pelo_nome("%artist%/%album% (%year%)/%track% %title%", &caminho, false).unwrap(),
        Some(t(&[
            (Campo::Artista, "Artista"),
            (Campo::Album, "Álbum"),
            (Campo::Data, "2001"),
            (Campo::Faixa, "7"),
            (Campo::Titulo, "Faixa"),
        ]))
    );
}

#[test]
fn test_renomear_tenta_de_novo_se_o_windows_negar() {
    let p = pasta();
    let a = p.join("a.mp3");
    std::fs::write(&a, b"x").unwrap();
    let mut negou = false;
    let plano = planejar_renomeacao(&[(a, t(&[(Campo::Titulo, "B")]))], "{title}").unwrap();
    let (feitos, falhas) = executar_renomeacao_com(&plano, |origem, destino| {
        if !negou {
            negou = true;
            return Err(std::io::Error::new(std::io::ErrorKind::PermissionDenied, "em uso"));
        }
        std::fs::rename(origem, destino)
    });
    assert!(falhas.is_empty(), "{falhas:?}");
    assert!(!feitos.is_empty() && p.join("B.mp3").exists());
}

#[test]
fn renomear_tenta_de_novo_com_arquivo_em_uso_no_windows() {
    // 32 = ERROR_SHARING_VIOLATION, 33 = ERROR_LOCK_VIOLATION: o Rust não os chama de PermissionDenied
    for codigo in [32, 33] {
        let p = pasta();
        let a = p.join("a.mp3");
        std::fs::write(&a, b"x").unwrap();
        let mut negou = false;
        let plano = planejar_renomeacao(&[(a, t(&[(Campo::Titulo, "B")]))], "{title}").unwrap();
        let (feitos, falhas) = executar_renomeacao_com(&plano, |origem, destino| {
            if !negou {
                negou = true;
                return Err(std::io::Error::from_raw_os_error(codigo));
            }
            std::fs::rename(origem, destino)
        });
        assert!(falhas.is_empty(), "{codigo}: {falhas:?}");
        assert!(!feitos.is_empty() && p.join("B.mp3").exists());
    }
}
