//! Porte de tests/test_rascunho.py (v2).

mod comum;

use std::collections::{BTreeMap, HashMap};
use std::path::PathBuf;

use comum::*;
use tagger_core::metadados::{AcaoCapa, Campo, Faixa, OpcoesGravacao, VARIOS, carregar, ler_capa, salvar};
use tagger_core::rascunho::*;

fn faixas() -> Vec<Faixa> {
    let p = pasta();
    let caminhos: Vec<PathBuf> = (1..=2).map(|i| p.join(format!("{i}.mp3"))).collect();
    for c in &caminhos {
        tagger_core::amostras::mp3(c).unwrap();
    }
    salvar(&caminhos[0], &[(Campo::Titulo, "Um"), (Campo::Artista, "A")], None, PADRAO).unwrap();
    salvar(&caminhos[1], &[(Campo::Titulo, "Dois"), (Campo::Artista, "B")], None, PADRAO).unwrap();
    caminhos.iter().map(|c| carregar(c).unwrap()).collect()
}

fn refs(f: &[Faixa]) -> Vec<&Faixa> {
    f.iter().collect()
}

fn salvar_rascunho(r: &mut Rascunho, faixas: &[Faixa]) -> Salvamento {
    let mtimes: HashMap<PathBuf, u128> = faixas.iter().map(|f| (f.caminho.clone(), f.mtime)).collect();
    let resultado = executar_salvamento(&r.trabalhos(), None, &mtimes, PADRAO);
    r.descartar(None);
    resultado
}

fn por_caminho(f: &[Faixa]) -> HashMap<PathBuf, Faixa> {
    f.iter().map(|f| (f.caminho.clone(), f.clone())).collect()
}

const JPEG_R: &[u8] = b"\xff\xd8\xff\xe0jpeg-falsojpeg-falsojpeg-falso";

#[test]
fn test_salvamento_usa_as_opcoes_de_gravacao() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&refs(&f), Campo::Artista, "A; B");
    let (_r, falhas, _) =
        executar_salvamento(&r.trabalhos(), None, &HashMap::new(), OpcoesGravacao { versao_id3: 4, multivalor: false, ..PADRAO });
    assert!(falhas.is_empty());
    for faixa in &f {
        assert_eq!(versao_id3(&faixa.caminho), 4);
        let tpe1 = lofty::id3::v2::FrameId::new("TPE1").unwrap();
        assert_eq!(id3(&faixa.caminho).unwrap().get_text(&tpe1), Some("A; B"));
    }
}

#[test]
fn test_definir_e_valor() {
    let f = faixas();
    let mut r = Rascunho::new();
    let avisos = r.definir(&refs(&f), Campo::Album, "Disco");
    assert_eq!(r.valor(&f[0], Campo::Album), "Disco");
    assert_eq!(r.valor(&f[0], Campo::Titulo), "Um");
    assert_eq!((r.len(), r.quantidade_campos()), (2, 2));
    assert_eq!(avisos, f.iter().map(|x| x.caminho.clone()).collect());
}

#[test]
fn test_valor_igual_ao_do_arquivo_nao_fica_pendente() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&[&f[0]], Campo::Titulo, "Outro");
    r.definir(&[&f[0]], Campo::Titulo, "Um");
    assert!(r.vazio());
}

#[test]
fn test_varios_valores_restaurar() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&[&f[0]], Campo::Artista, "Pendente");
    let foto = r.fotografar(&[&f[0].caminho, &f[1].caminho], Campo::Artista);
    assert_eq!(foto[&f[1].caminho], None);
    r.definir(&refs(&f), Campo::Artista, "Novo");
    r.restaurar(&foto, Campo::Artista);
    assert_eq!(r.valor(&f[0], Campo::Artista), "Pendente");
    assert_eq!(r.valor(&f[1], Campo::Artista), "B");
    assert!(!r.tem(&f[1].caminho));
}

#[test]
fn test_salvar_varios_e_ignorado() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir_por_faixa(&[(&f[0], vec![(Campo::Artista, VARIOS), (Campo::Album, "X")])]);
    let (_r, falhas, relidas) = salvar_rascunho(&mut r, &f);
    assert!(falhas.is_empty());
    assert_eq!(relidas[0].tags[&Campo::Artista], "A");
    assert_eq!(relidas[0].tags[&Campo::Album], "X");
}

#[test]
fn test_desfazer_tags() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&refs(&f), Campo::Album, "Novo");
    let (registros, falhas, relidas) = salvar_rascunho(&mut r, &f);
    assert!(falhas.is_empty() && relidas.iter().all(|x| x.tags[&Campo::Album] == "Novo"));
    let esperado: Vec<Registro> = f
        .iter()
        .map(|x| Registro {
            caminho: x.caminho.clone(),
            tags: BTreeMap::from([(Campo::Album, String::new())]),
            capa: CapaAnterior::NaoMexeu,
        })
        .collect();
    assert_eq!(registros, esperado);

    // desfazer = coloca os valores antigos no rascunho; nada é gravado até salvar
    let mudou = r.aplicar_registros(&registros, &por_caminho(&relidas));
    assert_eq!(mudou, f.iter().map(|x| x.caminho.clone()).collect());
    assert!(f.iter().all(|x| carregar(&x.caminho).unwrap().tags[&Campo::Album] == "Novo"));
    salvar_rascunho(&mut r, &relidas);
    assert!(f.iter().all(|x| carregar(&x.caminho).unwrap().tags[&Campo::Album].is_empty()));
}

#[test]
fn test_desfazer_capa() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir_capa(&[&f[0].caminho], Some(AcaoCapa::Definir { dados: JPEG_R.to_vec(), mime: "image/jpeg".into() }));
    r.definir(&[&f[0]], Campo::Titulo, "Com capa");
    let (registros, falhas, relidas) = salvar_rascunho(&mut r, &f);
    assert!(falhas.is_empty());
    assert_eq!(ler_capa(&f[0].caminho), Some((JPEG_R.to_vec(), "image/jpeg".into())));
    assert_eq!(registros[0].capa, CapaAnterior::Nenhuma); // antes não havia capa

    r.aplicar_registros(&registros, &por_caminho(&relidas));
    assert_eq!(r.capa(&f[0].caminho), Some(&AcaoCapa::Remover));
    salvar_rascunho(&mut r, &relidas);
    assert!(ler_capa(&f[0].caminho).is_none());
    assert_eq!(carregar(&f[0].caminho).unwrap().tags[&Campo::Titulo], "Um");
}

#[test]
fn test_arquivo_modificado_por_fora_nao_e_sobrescrito() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&[&f[0]], Campo::Titulo, "Meu");
    salvar(&f[0].caminho, &[(Campo::Titulo, "De outro programa")], None, PADRAO).unwrap();
    let depois = std::time::UNIX_EPOCH + std::time::Duration::from_nanos((f[0].mtime + 5_000_000_000) as u64);
    std::fs::File::options().write(true).open(&f[0].caminho).unwrap().set_modified(depois).unwrap();

    let (registros, falhas, _) = salvar_rascunho(&mut r, &f);
    assert_eq!(falhas.get(&f[0].caminho).map(String::as_str), Some(ARQUIVO_MODIFICADO));
    assert!(registros.is_empty());
    assert_eq!(carregar(&f[0].caminho).unwrap().tags[&Campo::Titulo], "De outro programa");
}

#[test]
fn test_falha_de_gravacao_nao_gera_registro() {
    // a v2 troca `salvar` por uma função que falha; aqui o arquivo fica somente leitura
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&[&f[0]], Campo::Titulo, "X");
    let mut permissoes = std::fs::metadata(&f[0].caminho).unwrap().permissions();
    permissoes.set_readonly(true);
    std::fs::set_permissions(&f[0].caminho, permissoes.clone()).unwrap();
    let (registros, falhas, _) = salvar_rascunho(&mut r, &f);
    #[allow(clippy::permissions_set_readonly_false)]
    permissoes.set_readonly(false);
    std::fs::set_permissions(&f[0].caminho, permissoes).unwrap();
    assert!(registros.is_empty());
    assert!(falhas.contains_key(&f[0].caminho));
}

#[test]
fn test_validar() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&[&f[0]], Campo::Data, "24");
    let erros: Vec<(PathBuf, Campo)> = r.validar().into_iter().map(|(c, campo, _)| (c, campo)).collect();
    assert_eq!(erros, [(f[0].caminho.clone(), Campo::Data)]);
}

#[test]
fn test_renomear_leva_o_rascunho_junto() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&[&f[0]], Campo::Titulo, "X");
    r.definir_capa(&[&f[0].caminho], Some(AcaoCapa::Remover));
    let novo = pasta().join("novo.mp3");
    r.renomear(&HashMap::from([(f[0].caminho.clone(), novo.clone())]));
    assert_eq!(r.caminhos(), [novo].into());
}

#[test]
fn test_renomear_troca_e_ciclo_nao_mistura_pendencias() {
    for n in [2, 3] {
        // n=2: A<->B; n=3: A->B->C->A. Cada arquivo leva as suas pendências, nada se perde.
        let p = pasta();
        let caminhos: Vec<PathBuf> = (0..n).map(|i| p.join(format!("{i}.mp3"))).collect();
        let mut r = Rascunho::new();
        for (i, c) in caminhos.iter().enumerate() {
            r.definir(&[&Faixa::com_tags(c.clone(), Default::default())], Campo::Titulo, &format!("T{i}"));
            r.definir_capa(&[c], Some(AcaoCapa::Definir { dados: format!("capa{i}").into_bytes(), mime: "image/jpeg".into() }));
        }
        let mapa: HashMap<PathBuf, PathBuf> = (0..n).map(|i| (caminhos[i].clone(), caminhos[(i + 1) % n].clone())).collect();
        r.renomear(&mapa);
        for (i, antigo) in caminhos.iter().enumerate() {
            let novo = &mapa[antigo];
            assert_eq!(r.tags[novo], BTreeMap::from([(Campo::Titulo, format!("T{i}"))]));
            assert_eq!(r.capas[novo], AcaoCapa::Definir { dados: format!("capa{i}").into_bytes(), mime: "image/jpeg".into() });
        }
        assert_eq!((r.tags.len(), r.capas.len()), (n, n));
    }
}

#[test]
fn test_renomear_parcial_mantem_quem_nao_tem_pendencia() {
    let p = pasta();
    let (a, b, c) = (p.join("a.mp3"), p.join("b.mp3"), p.join("c.mp3"));
    let mut r = Rascunho::new();
    r.definir(&[&Faixa::com_tags(a.clone(), Default::default())], Campo::Titulo, "A");
    r.definir_capa(&[&b], Some(AcaoCapa::Remover));
    r.renomear(&HashMap::from([(a, b.clone()), (b.clone(), c.clone())]));
    assert_eq!(r.tags, BTreeMap::from([(b, BTreeMap::from([(Campo::Titulo, "A".to_string())]))]));
    assert_eq!(r.capas, BTreeMap::from([(c, AcaoCapa::Remover)]));
}

#[test]
fn test_migrar_historico() {
    let p = pasta();
    let (a, b, c) = (p.join("a.mp3"), p.join("b.mp3"), p.join("c.mp3"));
    let registro = |caminho: &PathBuf| Registro {
        caminho: caminho.clone(),
        tags: BTreeMap::from([(Campo::Titulo, String::new())]),
        capa: CapaAnterior::NaoMexeu,
    };
    let mut pilha = vec![
        ItemHistorico::Tags(vec![registro(&a)]),
        ItemHistorico::Renomeacao(Renomeacao { pares: vec![(c.clone(), a.clone())] }),
    ];
    migrar_historico(&mut pilha, &HashMap::from([(a, b.clone())]));
    assert_eq!(pilha[0], ItemHistorico::Tags(vec![registro(&b)]));
    let ItemHistorico::Renomeacao(ren) = &pilha[1] else { panic!() };
    assert_eq!(ren.pares, [(c.clone(), b.clone())]);
    assert_eq!(ren.inversa().pares, [(b, c)]);
}

#[test]
fn test_gravadora_no_rascunho() {
    let f = faixas();
    let mut r = Rascunho::new();
    r.definir(&refs(&f), Campo::Gravadora, "Selo");
    assert_eq!(r.valor(&f[0], Campo::Gravadora), "Selo");
    salvar_rascunho(&mut r, &f);
    assert_eq!(carregar(&f[0].caminho).unwrap().tags[&Campo::Gravadora], "Selo");
}
