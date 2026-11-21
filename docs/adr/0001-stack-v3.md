# ADR 0001 — Stack da v3: Tauri 2, núcleo Rust com lofty, interface React + TypeScript

- **Status:** Proposta — aguardando aprovação humana
- **Data:** 2026-11-21
- **Base:** spike T2.1, [docs/spike/tauri.md](../spike/tauri.md) (código em `spike/tauri/`)

## Contexto

A v2 é um app desktop em Python + PySide6 (Qt), com o núcleo de tags em `tagger/nucleo/` usando o mutagen. A v3 deve ser um app desktop menor e mais rápido de distribuir, com um caminho para Android depois. A condição para trocar de stack é que o novo núcleo leia e grave MP3, FLAC e M4A **sem perder nada que a v2 preserva**: os campos não editados, o multivalor (`A; B`) e as imagens que não são a capa frontal.

O spike T2.1 montou um app mínimo em Tauri 2 + React + TypeScript com o núcleo em Rust usando a crate lofty 0.25.5. Ele foi comparado com a v2 aplicando a mesma edição nos mesmos arquivos e comparando tudo o que o mutagen lê (`spike/tauri/scripts/comparar_v2.py`). Números-chave:

- **FLAC e M4A:** idênticos à v2 nas 6 edições testadas (título, artista multivalor, faixa/total, gravadora, remover campo, capa frontal).
- **MP3 em ID3v2.4:** idêntico à v2.
- **MP3 em ID3v2.3**, o padrão da v2 por compatibilidade com players antigos, som de carro e Windows Explorer. A lofty sem alterações tem dois problemas em campos **não editados**:
  1. Uma data completa em `TDRC` (o que a v2 grava) é descartada na leitura, por causa das conversões implícitas (`construct_tdrc_from_v3`). Isso tem contorno com `ParseOptions::implicit_conversions(false)`.
  2. Gênero multivalor (`Rock; Pop`) vira `(Rock)Pop` ao gravar (`create_items_v3`, ramo do `TCON`). Não tem contorno sem alterar a lofty.
- **Patch de 9 linhas** na lofty (`spike/tauri/prototipo-v23/lofty-tcon-v23.patch`): com ele, o MP3 em v2.3 fica idêntico à v2 nas 18 comparações (3 formatos × 6 edições).
- **Instalador Windows:** NSIS 1,26 MiB, MSI 1,77 MiB.
- **Tempos de build:**
  - release limpo: 298 s (~5 min);
  - release incremental: ~2 min;
  - debug incremental: 11 s.

## Decisão

1. **Desktop com Tauri 2.** A interface é em **React + TypeScript** e o núcleo em **Rust**. Toda a regra de negócio fica no núcleo, sem dependência da interface, como na v2 (`docs/ARQUITETURA.md`, decisão 1). Os comandos do Tauri só traduzem as chamadas da interface para o núcleo.
2. **Tags com a crate lofty**, editando pelo tipo concreto de cada formato: `Id3v2Tag`, `VorbisComments` e `Ilst`. O `Tag` genérico da lofty não é usado para gravar, porque descarta o que não sabe mapear.
3. **MP3 mantém ID3v2.3 como padrão**, igual à v2. A gravação usa a lofty com o patch de 9 linhas no `TCON` (`create_items_v3`), aplicado via `[patch.crates-io]` apontando para um fork. O patch é proposto à lofty como pull request. O ID3v2.4 continua disponível como opção de gravação, como na v2.
4. **O contorno do `TDRC` continua:** a leitura do MP3 usa `implicit_conversions(false)`.
5. **Android fica para depois**, na fase 4. O núcleo em Rust é o que se pretende reaproveitar lá; esta ADR não decide a interface Android.

## Consequências

- O núcleo da v3 é reescrito em Rust, e a v2 (Python) segue como referência de comportamento. A comparação com a v2 (`comparar_v2.py`, ou uma equivalente) vira o critério de aceite do núcleo.
- Instalador da ordem de 1–2 MiB, usando o WebView2 do Windows (o NSIS baixa o bootstrapper se faltar).
- Passamos a depender de um fork da lofty até o patch entrar upstream. Cada atualização da lofty exige reaplicar o patch e rodar de novo os testes de regressão.
- O núcleo precisa de código próprio onde a lofty não cobre a semântica da v2. Isso inclui o mapa de campos por formato, a regra da capa frontal e a troca só dela, e as imagens do FLAC em dois lugares. A lista está em [docs/spike/tauri.md](../spike/tauri.md), seção "O que precisou de código próprio".
- Dois toolchains, Rust (cargo) e Node (npm), no desenvolvimento e na CI.
- O build release é lento (~5 min limpo, ~2 min incremental, por causa do LTO). O ciclo de desenvolvimento usa o build de debug (11 s incremental).

## Alternativas consideradas

- **(a) ID3v2.4 como padrão do MP3, sem patch.** Rejeitada. Não exige código extra e é idêntico à v2 em v2.4, mas muda o padrão que a v2 escolheu de propósito: players antigos, som de carro e o Windows Explorer leem pior o v2.4. Além disso, quem escolhesse v2.3 como opção voltaria a ter o gênero corrompido.
- **(c) Aceitar a lofty como está, em v2.3.** Rejeitada. Corrompe um campo **não editado** (gênero multivalor) em qualquer gravação de MP3, o que viola o princípio da v2 de só mudar o que o usuário pediu.
- **Serializador próprio só para o `TCON`** em vez do patch. Descartado: a lofty descarta `TCON` que não seja frame de texto, então seria preciso reescrever o frame no arquivo depois de gravar. Pela estimativa do spike, seria mais de 100 linhas e frágil, contra 9 linhas do patch.

## Em aberto

- **Manter o fork até o upstream aceitar.** Falta decidir onde o fork fica (repositório próprio ou patch dentro deste repo, aplicado por script como no spike), fixar a versão da lofty (`=0.25.5` + o patch), e quem revisa cada atualização. Também falta definir o que fazer se o upstream recusar o patch ou resolver de outro jeito.
- **PR upstream.** Falta abrir o PR com o patch do `TCON` na lofty e registrar também o problema do `TDRC` na leitura (issue). O spike não encontrou nada aberto sobre nenhum dos dois; links relacionados estão em [docs/spike/tauri.md](../spike/tauri.md).
- **Testes de regressão no núcleo da v3.** Os testes precisam cobrir:
  - gênero multivalor que sobrevive a uma gravação em v2.3;
  - `TDRC` com data completa em tag v2.3 que sobrevive a ler e gravar;
  - `TYER`/`TDAT` de um v2.3 padrão intactos.

  Falta decidir se a comparação com a v2 roda na CI (ela depende de Python + mutagen).
- **Interação do app sem teste automático.** O spike só conferiu que a janela abre. Falta escolher como testar a interface: testes de componentes React e/ou testes ponta a ponta com o WebDriver do Tauri.
- **Tempo de build release (~5 min).** Falta avaliar se é aceitável na CI, ou se convém cache do `target/`, ou um perfil sem LTO para builds de teste.
- **Formatos e campos fora do spike.** O spike cobriu título, artista, faixa, gravadora e capa em MP3, FLAC e M4A. Faltam o Ogg/Opus e os demais campos da v2 (álbum, artista do álbum, disco, ano, gênero, compositor, letrista, comentário, letra), além da limpeza de extras.
