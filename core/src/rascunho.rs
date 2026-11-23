//! Rascunho: tudo o que foi alterado e ainda NÃO foi gravado nos arquivos. Porte de
//! `tagger/nucleo/rascunho.py`.
//!
//! Cada arquivo tem o seu conjunto de alterações pendentes: dá para editar uma seleção, trocar de
//! seleção e continuar editando outras; desfazer, numerar faixas, colar tags e editar na tabela viram
//! alterações pendentes, iguais a uma edição normal, e só valem depois de "Salvar".
//!
//! Diferença de forma em relação à v2: em vez de um callback `ao_mudar`, os métodos que alteram o
//! rascunho devolvem o conjunto de caminhos afetados.

use std::collections::{BTreeMap, BTreeSet, HashMap};
use std::path::{Path, PathBuf};

use crate::metadados::{AcaoCapa, Campo, Faixa, OpcoesGravacao, carregar, carregar_varios, ler_capa, salvar};
use crate::validacao::validar_valor;

pub type Caminhos = BTreeSet<PathBuf>;

/// A capa num registro de desfazer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum CapaAnterior {
    /// A capa não fez parte desta alteração (o `SEM_CAPA` da v2).
    NaoMexeu,
    /// Antes não havia capa.
    Nenhuma,
    /// A capa de antes: (dados, mime).
    Imagem(Vec<u8>, String),
}

/// Registro de desfazer de um arquivo: os valores de antes e a capa de antes.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Registro {
    pub caminho: PathBuf,
    pub tags: BTreeMap<Campo, String>,
    pub capa: CapaAnterior,
}

/// Arquivos renomeados: [(caminho_antigo, caminho_novo)]. Renomear não passa pelo rascunho:
/// desfazer renomeia de volta na hora.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Renomeacao {
    pub pares: Vec<(PathBuf, PathBuf)>,
}

impl Renomeacao {
    pub fn inversa(&self) -> Renomeacao {
        Renomeacao { pares: self.pares.iter().map(|(a, n)| (n.clone(), a.clone())).collect() }
    }
}

/// Item de uma pilha de desfazer/refazer.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ItemHistorico {
    Tags(Vec<Registro>),
    Renomeacao(Renomeacao),
}

/// Atualiza os caminhos de uma pilha de desfazer/refazer depois de renomear arquivos ({antigo: novo}).
pub fn migrar_historico(pilha: &mut [ItemHistorico], mapa: &HashMap<PathBuf, PathBuf>) {
    let novo = |c: &PathBuf| mapa.get(c).cloned().unwrap_or_else(|| c.clone());
    for item in pilha {
        match item {
            ItemHistorico::Renomeacao(r) => {
                for par in &mut r.pares {
                    par.1 = novo(&par.1);
                }
            }
            ItemHistorico::Tags(registros) => {
                for r in registros {
                    r.caminho = novo(&r.caminho);
                }
            }
        }
    }
}

/// O que gravar num arquivo: (caminho, {campo: valor normalizado}, ação de capa).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Trabalho {
    pub caminho: PathBuf,
    pub tags: BTreeMap<Campo, String>,
    pub capa: Option<AcaoCapa>,
}

/// Valor de um campo numa fotografia: `None` = o campo não tinha rascunho (o `FALTA` da v2).
pub type Fotografia = BTreeMap<PathBuf, Option<String>>;

#[derive(Clone, Debug, Default)]
pub struct Rascunho {
    pub tags: BTreeMap<PathBuf, BTreeMap<Campo, String>>,
    pub capas: BTreeMap<PathBuf, AcaoCapa>,
}

fn valor_do_arquivo(faixa: &Faixa, campo: Campo) -> &str {
    faixa.tags.get(&campo).map(String::as_str).unwrap_or("")
}

impl Rascunho {
    pub fn new() -> Rascunho {
        Rascunho::default()
    }

    // ------------------------------------------------------------ consultas
    pub fn vazio(&self) -> bool {
        self.tags.is_empty() && self.capas.is_empty()
    }

    pub fn caminhos(&self) -> Caminhos {
        self.tags.keys().chain(self.capas.keys()).cloned().collect()
    }

    pub fn len(&self) -> usize {
        self.caminhos().len()
    }

    pub fn is_empty(&self) -> bool {
        self.vazio()
    }

    pub fn tem(&self, caminho: &Path) -> bool {
        self.tags.contains_key(caminho) || self.capas.contains_key(caminho)
    }

    pub fn tem_campo(&self, caminho: &Path, campo: Campo) -> bool {
        self.tags.get(caminho).is_some_and(|t| t.contains_key(&campo))
    }

    pub fn quantidade_campos(&self) -> usize {
        self.tags.values().map(BTreeMap::len).sum::<usize>() + self.capas.len()
    }

    /// Valor que o usuário está vendo: o do rascunho, se houver; senão o do arquivo.
    pub fn valor(&self, faixa: &Faixa, campo: Campo) -> String {
        self.tags
            .get(&faixa.caminho)
            .and_then(|t| t.get(&campo))
            .cloned()
            .unwrap_or_else(|| valor_do_arquivo(faixa, campo).to_string())
    }

    pub fn capa(&self, caminho: &Path) -> Option<&AcaoCapa> {
        self.capas.get(caminho)
    }

    // ------------------------------------------------------------ alterações
    /// Grava no rascunho. Valor igual ao do arquivo = sem rascunho. Devolve true se mudou algo.
    fn definir_um(&mut self, faixa: &Faixa, campo: Campo, valor: &str) -> bool {
        if valor.trim() == valor_do_arquivo(faixa, campo) {
            if let Some(atual) = self.tags.get_mut(&faixa.caminho)
                && atual.remove(&campo).is_some() {
                    if atual.is_empty() {
                        self.tags.remove(&faixa.caminho);
                    }
                    return true;
                }
            return false;
        }
        let atual = self.tags.entry(faixa.caminho.clone()).or_default();
        if atual.get(&campo).map(String::as_str) == Some(valor) {
            return false;
        }
        atual.insert(campo, valor.to_string());
        true
    }

    /// Mesmo valor para várias faixas (edição no painel).
    pub fn definir(&mut self, faixas: &[&Faixa], campo: Campo, valor: &str) -> Caminhos {
        faixas.iter().filter(|f| self.definir_um(f, campo, valor)).map(|f| f.caminho.clone()).collect()
    }

    /// Valores diferentes por faixa.
    pub fn definir_por_faixa(&mut self, itens: &[(&Faixa, Vec<(Campo, &str)>)]) -> Caminhos {
        let mut mudou = Caminhos::new();
        for (faixa, valores) in itens {
            for (campo, valor) in valores {
                if self.definir_um(faixa, *campo, valor) {
                    mudou.insert(faixa.caminho.clone());
                }
            }
        }
        mudou
    }

    pub fn fotografar(&self, caminhos: &[&Path], campo: Campo) -> Fotografia {
        caminhos.iter().map(|c| (c.to_path_buf(), self.tags.get(*c).and_then(|t| t.get(&campo)).cloned())).collect()
    }

    /// Volta um campo ao estado de uma fotografia (ex.: o usuário apagou o que digitou).
    pub fn restaurar(&mut self, foto: &Fotografia, campo: Campo) -> Caminhos {
        let mut mudou = Caminhos::new();
        for (caminho, valor) in foto {
            match valor {
                None => {
                    if let Some(atual) = self.tags.get_mut(caminho) {
                        if atual.remove(&campo).is_some() {
                            mudou.insert(caminho.clone());
                        }
                        if atual.is_empty() {
                            self.tags.remove(caminho);
                        }
                    }
                }
                Some(v) => {
                    let atual = self.tags.entry(caminho.clone()).or_default();
                    if atual.get(&campo) != Some(v) {
                        atual.insert(campo, v.clone());
                        mudou.insert(caminho.clone());
                    }
                }
            }
        }
        mudou
    }

    /// `acao`: definir/remover a capa, ou `None` para tirá-la do rascunho.
    pub fn definir_capa(&mut self, caminhos: &[&Path], acao: Option<AcaoCapa>) -> Caminhos {
        let mut mudou = Caminhos::new();
        for caminho in caminhos {
            match &acao {
                None => {
                    if self.capas.remove(*caminho).is_some() {
                        mudou.insert(caminho.to_path_buf());
                    }
                }
                Some(a) => {
                    self.capas.insert(caminho.to_path_buf(), a.clone());
                    mudou.insert(caminho.to_path_buf());
                }
            }
        }
        mudou
    }

    /// Arquivos renomeados no disco: as pendências vão junto para o caminho novo. Primeiro tira tudo,
    /// depois atribui: numa troca (A->B, B->A) ou num ciclo, mover um a um misturaria as pendências.
    pub fn renomear(&mut self, mapa: &HashMap<PathBuf, PathBuf>) {
        fn mover<V>(pendencias: &mut BTreeMap<PathBuf, V>, mapa: &HashMap<PathBuf, PathBuf>) {
            let movidas: Vec<(PathBuf, V)> =
                mapa.iter().filter_map(|(antigo, novo)| pendencias.remove(antigo).map(|v| (novo.clone(), v))).collect();
            pendencias.extend(movidas);
        }
        mover(&mut self.tags, mapa);
        mover(&mut self.capas, mapa);
    }

    /// Descarta as pendências dos caminhos dados (todos, se `None`).
    pub fn descartar(&mut self, caminhos: Option<&[&Path]>) -> Caminhos {
        let alvo: Caminhos = match caminhos {
            None => self.caminhos(),
            Some(c) => c.iter().map(|p| p.to_path_buf()).filter(|p| self.tem(p)).collect(),
        };
        for caminho in &alvo {
            self.tags.remove(caminho);
            self.capas.remove(caminho);
        }
        alvo
    }

    // ------------------------------------------------------------ salvar
    /// [(caminho, campo, mensagem)] dos valores inválidos.
    pub fn validar(&self) -> Vec<(PathBuf, Campo, String)> {
        let mut erros = Vec::new();
        for (caminho, valores) in &self.tags {
            for (campo, valor) in valores {
                if let Err(m) = validar_valor(*campo, valor) {
                    erros.push((caminho.clone(), *campo, m));
                }
            }
        }
        erros
    }

    /// O que gravar, em ordem de caminho, com os valores normalizados pela validação.
    pub fn trabalhos(&self) -> Vec<Trabalho> {
        self.caminhos()
            .into_iter()
            .map(|caminho| {
                let tags = self
                    .tags
                    .get(&caminho)
                    .map(|t| t.iter().map(|(c, v)| (*c, validar_valor(*c, v).unwrap_or_else(|_| v.clone()))).collect())
                    .unwrap_or_default();
                let capa = self.capas.get(&caminho).cloned();
                Trabalho { caminho, tags, capa }
            })
            .collect()
    }

    /// Coloca no rascunho os valores de um registro de desfazer/refazer. Nada é gravado.
    pub fn aplicar_registros(&mut self, registros: &[Registro], faixas: &HashMap<PathBuf, Faixa>) -> Caminhos {
        let mut mudou = Caminhos::new();
        for r in registros {
            let Some(faixa) = faixas.get(&r.caminho) else { continue };
            for (campo, valor) in &r.tags {
                if self.definir_um(faixa, *campo, valor) {
                    mudou.insert(r.caminho.clone());
                }
            }
            let acao = match &r.capa {
                CapaAnterior::NaoMexeu => None,
                CapaAnterior::Nenhuma => Some(AcaoCapa::Remover),
                CapaAnterior::Imagem(dados, mime) => Some(AcaoCapa::Definir { dados: dados.clone(), mime: mime.clone() }),
            };
            if let Some(acao) = acao {
                self.capas.insert(r.caminho.clone(), acao);
                mudou.insert(r.caminho.clone());
            }
        }
        mudou
    }
}

/// Resultado de [`executar_salvamento`]: registros para desfazer, falhas {caminho: erro} e as faixas relidas.
pub type Salvamento = (Vec<Registro>, BTreeMap<PathBuf, String>, Vec<Faixa>);

/// Grava os trabalhos nos arquivos (em segundo plano, ou direto ao fechar o app).
///
/// `mtimes`: {caminho: mtime esperado}. Se o arquivo mudou no disco desde então, ele NÃO é gravado
/// (vira falha "o arquivo foi alterado por outro programa", o `ArquivoModificado` da v2).
pub fn executar_salvamento(
    trabalhos: &[Trabalho],
    mut progresso: Option<&mut dyn FnMut(usize, usize)>,
    mtimes: &HashMap<PathBuf, u128>,
    opcoes: OpcoesGravacao,
) -> Salvamento {
    let mut registros = Vec::new();
    let mut falhas = BTreeMap::new();
    let total = trabalhos.len();
    for (i, t) in trabalhos.iter().enumerate() {
        match salvar_um(t, mtimes, opcoes) {
            Ok(r) => registros.push(r),
            Err(e) => {
                falhas.insert(t.caminho.clone(), e);
            }
        }
        if let Some(p) = progresso.as_mut() {
            p(i + 1, total);
        }
    }
    let caminhos: Vec<&Path> = trabalhos.iter().map(|t| t.caminho.as_path()).collect();
    let (faixas, _) = carregar_varios(&caminhos);
    (registros, falhas, faixas)
}

pub const ARQUIVO_MODIFICADO: &str = "o arquivo foi alterado por outro programa";

fn salvar_um(t: &Trabalho, mtimes: &HashMap<PathBuf, u128>, opcoes: OpcoesGravacao) -> Result<Registro, String> {
    let faixa = carregar(&t.caminho).ok_or("arquivo inválido ou não suportado")?;
    if mtimes.get(&t.caminho).is_some_and(|esperado| *esperado != faixa.mtime) {
        return Err(ARQUIVO_MODIFICADO.into());
    }
    let capa = match &t.capa {
        None => CapaAnterior::NaoMexeu,
        Some(_) => match ler_capa(&t.caminho) {
            Some((dados, mime)) => CapaAnterior::Imagem(dados, mime),
            None => CapaAnterior::Nenhuma,
        },
    };
    let registro = Registro {
        caminho: t.caminho.clone(),
        tags: t.tags.keys().map(|c| (*c, valor_do_arquivo(&faixa, *c).to_string())).collect(),
        capa,
    };
    let alteracoes: Vec<(Campo, &str)> = t.tags.iter().map(|(c, v)| (*c, v.as_str())).collect();
    salvar(&t.caminho, &alteracoes, t.capa.as_ref(), opcoes).map_err(|e| e.to_string())?; // tags + capa num único save
    Ok(registro)
}
