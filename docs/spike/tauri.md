# Spike: Tauri 2 + lofty (T2.1)

Validação técnica para a v3: um app mínimo em **Tauri 2 + React + TypeScript** com o núcleo de tags em **Rust (crate lofty 0.25.5)**, comparado com a v2 (Python + mutagen) nos mesmos arquivos. Nada aqui é código de produção; tudo está em `spike/tauri/`.

## O que foi feito

| Parte | Onde | O que faz |
|---|---|---|
| Núcleo | `spike/tauri/nucleo/src/lib.rs` | `ler`, `gravar`, `definir_capa`, `imagens` para MP3, FLAC e M4A, com a semântica da v2 (vazio remove, `A; B` vira vários valores, capa = imagem frontal) |
| Amostras | `spike/tauri/nucleo/src/amostras.rs` | Porte fiel de `criar_mp3`, `criar_flac` e `criar_m4a` de `tests/conftest.py` (arquivos mínimos, sem música) |
| Testes Rust | `spike/tauri/nucleo/tests/formatos.rs` | 9 testes, nos três formatos |
| Linha de comando | `spike/tauri/nucleo/src/cli.rs` (binário `spike-tags`) | Usada pela comparação com a v2 |
| Comparação com a v2 | `spike/tauri/scripts/comparar_v2.py` | Mesma edição pela v2 e pelo spike, compara tudo o que o mutagen lê |
| App | `spike/tauri/src/App.tsx`, `spike/tauri/src-tauri/src/lib.rs` | Gera as amostras numa pasta temporária, mostra título, artista, faixa, gravadora e capa, edita um campo, grava e relê do disco. MP3 em ID3v2.4 |
| Protótipo v2.3 | `spike/tauri/prototipo-v23/` | O núcleo compilado contra a lofty com um patch de 9 linhas no TCON |

### Como reproduzir

```
cd spike/tauri/nucleo
cargo test                                   # 9 testes
cargo build
cd ../../..
python spike/tauri/scripts/comparar_v2.py               # MP3 em ID3v2.3 (padrão da v2): sai com 1
SPIKE_ID3=4 python spike/tauri/scripts/comparar_v2.py   # MP3 em ID3v2.4 nos dois lados

cd spike/tauri/prototipo-v23
python preparar.py                           # copia a lofty do cache do cargo para ../vendor e aplica o patch
cargo test                                   # teste do TCON multivalor em v2.3
cd ../../..
SPIKE_BIN=spike/tauri/prototipo-v23/target/debug/spike-tags.exe python spike/tauri/scripts/comparar_v2.py

cd spike/tauri
npm install
npx tauri dev                                # app
npx tauri build                              # instaladores NSIS e MSI
```

Nenhuma rede nos testes nem na comparação (a rede só é usada por `cargo`/`npm` para baixar dependências).

## Resultados por formato

A comparação enche o arquivo pela v2 com **todos** os campos da v2, capa frontal + contracapa (PNG) e extras que o Tagger não mostra (MP3: `TXXX:REPLAYGAIN_TRACK_GAIN`, `PRIV`; FLAC: `REPLAYGAIN_TRACK_GAIN`, `MUSICBRAINZ_TRACKID`; M4A: átomo freeform `REPLAYGAIN_TRACK_GAIN`). Depois aplica 6 edições (título, artista `Novo A; Novo B`, faixa `5/10`, gravadora, remover título, capa frontal), uma vez pela v2 e outra pelo spike, e compara tudo o que o mutagen lê das duas cópias: frames/chaves/átomos, valores, imagens (tipo, mime, tamanho) e versão do ID3.

| Formato | Leitura (título, artista, faixa, gravadora, capa) | Gravar 1 campo preserva os outros (× v2) | Multivalor `A; B` | Capa frontal sem perder as outras imagens | Resultado |
|---|---|---|---|---|---|
| FLAC | ok | **idêntico** nas 6 edições | 2 chaves `ARTIST` | ok (bloco PICTURE tipo 4 fica) | **atende** |
| M4A | ok | **idêntico** nas 6 edições | 2 valores no átomo `©ART` | ok (2ª imagem do `covr` fica; M4A não tem tipo de imagem) | **atende** |
| MP3, ID3v2.4 | ok | **idêntico** nas 6 edições (v2 também em 2.4) | `TPE1` com valores separados por nulo | ok (APIC tipo 4 fica) | **atende** |
| MP3, ID3v2.3 (padrão da v2) | ok | **difere** nas 6 edições: gênero `Rock; Pop` (não editado) vira `(Rock)Pop` | `TPE1` ok; `TCON` corrompido | ok | **não atende** sem patch |
| MP3, ID3v2.3 com o patch do protótipo | ok | **idêntico** nas 6 edições | ok | ok | atende |

Detalhes do MP3 em ID3v2.3, os dois problemas da lofty encontrados:

1. **Data completa perdida na leitura** (contornado). A v2 (mutagen) grava `TDRC` com data completa (`2001-05-06`) mesmo em tag v2.3. Com as "conversões implícitas" ligadas (o padrão), a lofty tenta montar o `TDRC` a partir de `TYER`/`TDAT` (`src/id3/v2/read.rs`, `construct_tdrc_from_v3`): retira o `TDRC` e, quando ele já tem mês, retorna sem devolvê-lo. O frame some ao gravar qualquer campo. **Contorno:** o núcleo lê MP3 com `ParseOptions::new().implicit_conversions(false)` (`opcoes_leitura_mp3` em `nucleo/src/lib.rs`). Conferido: um v2.3 "padrão" (`TYER` + `TDAT` + `TORY`, gravado por fora) continua intacto depois de gravar o título.
2. **Gênero multivalor corrompido na gravação** (sem contorno sem mexer na lofty). Em ID3v2.3, a lofty reescreve `TCON` na sintaxe de referências do v2.3, `(Rock)Pop` (`src/id3/v2/write/frame.rs`, `create_items_v3`), e descarta `TCON` que não seja frame de texto, então nem um frame binário cru passa. O mutagen, a v2 e os players modernos leem esse texto como um gênero só. Gênero com um valor só não é afetado. Em ID3v2.4 não há conversão.

Teste do app: compilado em release e aberto (a janela "Tagger (spike Tauri)" sobe); a interação (gerar, abrir, editar, gravar, reler, capa de teste) não tem teste automático. Os comandos do app só repassam para o núcleo, que tem os testes acima.

## Tamanho e tempo de build

Máquina: AMD Ryzen 5 5500, 16 GB, Windows 11, Rust 1.100 (msvc), Node 26. Perfil release com `lto = true`, `opt-level = "s"`, `codegen-units = 1`, `strip = true`, `panic = "abort"`.

| Artefato | Tamanho |
|---|---|
| Instalador NSIS (`*-setup.exe`) | **1,26 MiB** (1 319 296 bytes) |
| Instalador MSI | 1,77 MiB (1 851 392 bytes) |
| Executável do app (`tagger-spike.exe`) | 3,45 MiB (3 622 400 bytes) |

Os instaladores não embutem o WebView2 (usam o do Windows; o NSIS baixa o bootstrapper se faltar).

| Build (`npx tauri build`, frontend + Rust + 2 instaladores) | Tempo |
|---|---|
| Limpo (sem `target/`; dependências já baixadas) | **298 s** |
| Incremental: mudança em `src-tauri/src/lib.rs` | 122 s |
| Incremental: mudança em `nucleo/src/lib.rs` | 123 s |
| Sem mudança | 112 s |

No release, o incremental fica perto de 2 min mesmo sem mudança: o `beforeBuildCommand` refaz o frontend, o que faz o crate do app recompilar e o link com LTO completo (`codegen-units = 1`) domina. Para desenvolvimento conta o build de debug (`cargo build` em `src-tauri`, o mesmo do `tauri dev`):

| Build de debug | Tempo |
|---|---|
| Limpo | 145 s |
| Incremental: mudança em `src-tauri/src/lib.rs` | 11 s |
| Incremental: mudança em `nucleo/src/lib.rs` | 11 s |

O primeiro build da máquina levou 437 s, mas inclui o download das ferramentas de instalador (NSIS e WiX) e rodou junto com outros builds; não serve de referência.

## O que precisou de código próprio (falta de suporte na lofty)

- **Editar pelo tipo concreto, não pelo `Tag` genérico.** O `Tag` genérico converte para um modelo comum e, ao gravar, descarta o que não sabe mapear (TXXX, PRIV, átomos freeform...). O núcleo edita `Id3v2Tag`, `VorbisComments` e `Ilst` diretamente, um caso por formato (cerca de 120 linhas por formato).
- **Mapa de campos por formato** (como `CAMPOS` e `formatos/` da v2): `TIT2`/`TPE1`/`TRCK`/`TPUB`; `TITLE`/`ARTIST`/`TRACKNUMBER`+`TRACKTOTAL`/`ORGANIZATION` (lendo também `LABEL`); `©nam`/`©ART`/`trkn`/`----:com.apple.iTunes:LABEL`.
- **Regra da capa** (frontal, senão a 1ª "outra"; no M4A a 1ª do `covr`) e troca só dela: a lofty remove imagens só por tipo (`remove_picture_type`), o que apagaria as outras do mesmo tipo; o núcleo tira tudo e recoloca o que fica. No MP3, a descrição do APIC novo é escolhida para não sobrescrever outra imagem (a chave do APIC é a descrição), como na v2.
- **FLAC:** a lofty guarda as imagens em dois lugares (blocos `PICTURE` no `FlacFile` e `METADATA_BLOCK_PICTURE` nos comentários); o núcleo olha os dois. Inserir imagem sem `PictureInformation` explícita falha em silêncio se o JPEG/PNG não for decodificável; o núcleo passa a informação.
- **Contorno do `TDRC`** (acima): `implicit_conversions(false)` na leitura do MP3.
- **TCON em v2.3:** só com patch na lofty (protótipo abaixo).

Total do núcleo: ~550 linhas (`nucleo/src/lib.rs`), sem contar testes.

## Custo de corrigir o ID3v2.3 (protótipo)

`spike/tauri/prototipo-v23/lofty-tcon-v23.patch`: **9 linhas** em `create_items_v3`. Quando o `TCON` tem vários valores e nenhum é código numérico do ID3v1 (nem `RX`/`CR`), o frame é gravado como está, com os valores separados por nulo (o que o mutagen e a v2 fazem). Aplicado via `[patch.crates-io]` sobre uma cópia local da lofty 0.25.5 (gerada por `prototipo-v23/preparar.py`, fora do git). Resultado: teste `tcon_v23.rs` passa e a comparação com a v2 em v2.3 fica **idêntica nas 18 edições** (3 formatos × 6).

Serializador próprio só para o `TCON` não é menor: a lofty descarta `TCON` que não seja texto, então seria preciso reescrever o frame no arquivo depois do save (localizar o frame, recalcular tamanhos do frame e da tag), na minha estimativa mais de 100 linhas, e frágil com padding/unsynchronization.

**Upstream:** não encontrei issue nem PR na lofty sobre o `TCON` em v2.3 nem sobre o `TDRC` perdido na leitura. Relacionados:
- [lofty-rs #761](https://github.com/Serial-ATA/lofty-rs/issues/761): cabeçalho estendido do ID3v2.3 lido com o layout do v2.4, nenhum frame é lido (outra perda de dados em v2.3, na 0.25.5); correção em [lofty-rs PR #777](https://github.com/Serial-ATA/lofty-rs/pull/777) (milestone 0.26.0).
- Projetos que usam a lofty contornando o mesmo `(Pop)Rock`: [DroppedNeedle PR #773](https://github.com/DroppedNeedle/DroppedNeedle/pull/773) (grava como v2.4 quando há vários gêneros) e [TagRex #671](https://github.com/tagrex/tagrex/issues/671) (testes "canário" para comportamentos da lofty, incluindo o `TYER` com data completa).

Não verifiquei esses links além do resultado da busca; nada foi aberto upstream.

## Pendências para a ADR (T2.2)

Os três formatos atendem com a lofty, **exceto o MP3 em ID3v2.3 com gênero multivalor**. Opções:

| Opção | O que é | Custo | Risco |
|---|---|---|---|
| **(a) ID3v2.4 como padrão** | O app grava MP3 em v2.4 (como no app do spike); v2.3 vira opção ou some | Zero código extra; idêntico à v2 em v2.4 | Players antigos, som de carro e o Windows Explorer leem pior o v2.4 (motivo do padrão 2.3 da v2). Se o v2.3 continuar como opção, o problema volta para quem escolher |
| **(b) v2.3 com código próprio/patch** | Manter o padrão da v2 com o patch de 9 linhas (fork/`[patch.crates-io]`) e propor o patch upstream | 9 linhas + manter o patch a cada versão da lofty até entrar upstream | Divergir da lofty; o patch toca só o caminho do `TCON` multivalor |
| **(c) Aceitar** | v2.3 com a lofty como está | Zero | Corrompe um campo **não editado** em qualquer gravação de MP3 com mais de um gênero. Não recomendado |

Também para a ADR: manter o contorno do `TDRC` (`implicit_conversions(false)`) em qualquer opção, e ter na v3 um teste de comparação com a v2 como o `comparar_v2.py` para pegar regressões da lofty.
