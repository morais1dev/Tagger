//! Núcleo do Tagger v3: regra de negócio, sem nenhuma dependência de interface (nem Tauri).
//!
//! Espelha o `tagger/nucleo/` da v2 (Python); os testes pytest da v2 são a especificação
//! (veja `docs/paridade-testes.md`).

pub mod amostras;
pub mod metadados;
pub mod validacao;
