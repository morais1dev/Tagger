# lofty 0.25.5 vendorizada

Cópia da crate [lofty](https://github.com/Serial-ATA/lofty-rs) 0.25.5 (MIT OR Apache-2.0, veja
`LICENSE-MIT` e `LICENSE-APACHE`), usada pelo workspace via `[patch.crates-io]` no `Cargo.toml` da raiz.
Decisão em `docs/adr/0001-stack-v3.md`.

O 1º commit desta pasta é a crate como publicada no crates.io (sem `.cargo_vcs_info.json`,
`Cargo.toml.orig` e `Cargo.lock`; licenças copiadas do repositório, que o pacote não traz).
Alterações do Tagger, cada uma num commit próprio, marcadas no código com "Tagger:":

1. `src/id3/v2/write/frame.rs` (`create_items_v3`): gênero (`TCON`) com vários valores, todos por
   nome, é gravado em ID3v2.3 separado por nulo (como o mutagen), e não como `(Rock)Pop`.
2. `src/id3/v2/header.rs`: backport da leitura do cabeçalho estendido do ID3v2.3 do upstream
   (lofty-rs #761, PR #777, ainda não publicado em versão): na 0.25.5 ele era lido com o layout do
   v2.4 e nenhum frame era lido.

Para atualizar: trocar a pasta pela versão nova e reaplicar o que ainda não estiver no upstream.
