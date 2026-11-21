# Arquitetura do Tagger

Este documento descreve como o código está organizado na v2.2 e como estendê-lo. Ele cita arquivos e funções; para ver o código, abra o arquivo indicado.

## Módulos e responsabilidades

| Pasta / arquivo | Responsabilidade |
|---|---|
| `tagger/__init__.py` | Define `__version__`, a única fonte da versão (GUI, CLI e build leem daqui). |
| `tagger/__main__.py` | Ponto de entrada de `python -m tagger`. |
| `tagger/cli.py` | Versão de linha de comando; usa as mesmas funções de `nucleo/metadata.py`. |
| `tagger/nucleo/` | Regra de negócio. **Não importa Qt** (nenhum arquivo daqui nem `cli.py` importa PySide6). |
| `tagger/nucleo/formatos/` | Um módulo por família de formato além do MP3 (`vorbis.py`, `mp4.py`). |
| `tagger/gui/` | Interface em PySide6: janela, tabela, editor, diálogos, tema e configurações. |

### `tagger/nucleo/`

- `metadata.py`: leitura e gravação de tags para todos os formatos. Define `CAMPOS` (campos editáveis), `Faixa` (retrato do arquivo lido), `carregar`, `carregar_varios`, `salvar`, `salvar_varios`, `validar_valor`, `limpar_extras` e `EXTENSOES_SUPORTADAS`. O MP3 (ID3) é tratado aqui mesmo.
- `formatos/__init__.py`: contrato comum dos formatos (docstring do módulo) e `escolher_capa`, que decide quais imagens contam como "a capa".
- `formatos/vorbis.py`: FLAC e Ogg (Vorbis, Opus, FLAC no Ogg), via Vorbis comments.
- `formatos/mp4.py`: M4A/MP4, via átomos do iTunes.
- `rascunho.py`: classe `Rascunho` (alterações pendentes) e `executar_salvamento` (veja a seção própria).
- `historico.py`: classe `Historico`, as pilhas de desfazer/refazer e as regras de qual pilha recebe o quê (gravação, falha parcial, renomear/mover, descartar); veja "O histórico de desfazer".
- `padroes.py`: padrões de nome de arquivo ⇄ tags (`nome_pelas_tags`, `executar_renomeacao`, detecção de conflitos).
- `organizar.py`: mover arquivos para pastas a partir das tags, reutilizando `padroes.py`.
- `agrupar.py`: chaves de agrupamento e ordenação por álbum (`chave_grupo`, `chave_ordem`, `ordem_faixa`).
- `busca.py`: MusicBrainz (`ClienteMusicBrainz`) e Cover Art Archive (`baixar_capa`); `analisar` e `montar_alteracoes` devolvem alterações no formato do Rascunho.
- `discogs.py`: Discogs (`ClienteDiscogs`), mesmo desenho de `busca.py`.
- `online.py`: infraestrutura comum dos serviços de rede: `LimitadorJanela`, `Cache`, `url_segura`, `abrir_sem_vazar`, `ocultar`.
- `credenciais.py`: resolve credenciais e as oculta de logs e erros (veja abaixo).
- `chaves.exemplo.json`: modelo do `chaves.json` embutido no build (o `chaves.json` real está no `.gitignore`).

### `tagger/gui/`

- `janela.py`: `JanelaPrincipal`; guarda o `Rascunho`, cria as threads de trabalho (`Carregador`, `Salvador`, `Movedor`, `Limpador`) e aplica as configurações.
- `tabela.py`, `editor.py`, `rotulo.py`, `vazio.py`, `icones.py`, `tema.py`: widgets e aparência.
- `busca_online.py`: diálogo de busca online (`DialogoBuscaOnline`), com as "fontes" (`FonteMusicBrainz`, `FonteDiscogs`) que adaptam os clientes do núcleo.
- `busca.py`: diálogo de busca só no MusicBrainz e a thread de rede `Trabalhador`.
- `padrao.py`, `organizar.py`, `limpeza.py`: diálogos de renomear, organizar e limpar extras.
- `config.py`: `PADROES` (todas as opções e seus valores padrão), `carregar_config`, `salvar_config`.
- `configuracoes.py`: janela de Configurações.
- `erros.py`, `sobre.py`: tratamento de erros e tela "Sobre".

## Decisões de arquitetura da v2.2

### 1. Regra de negócio no núcleo; a GUI chama o núcleo

Leitura, gravação, validação, padrões de nome, busca online e credenciais vivem em `tagger/nucleo/`, sem Qt. A GUI só apresenta e delega: `janela.py` importa `carregar`, `executar_salvamento`, etc. do núcleo. A CLI (`cli.py`) usa o mesmo núcleo, o que permite testar sem interface (`tests/`).

### 2. Leitura nunca grava

`metadata.py` declara no topo que só `salvar` e `limpar_extras` gravam. `carregar`, `carregar_varios`, `ler_capa` e `analisar_extras` só leem. Os módulos de `formatos/` também nunca chamam `save()`: a gravação é sempre um único save por arquivo, feito em `salvar` (e em `limpar_extras`).

### 3. Opções de gravação são parâmetro (`OpcoesGravacao`)

As opções que afetam a gravação (`versao_id3`, `multivalor`, `remover_id3v1`) formam a dataclass `OpcoesGravacao` de `metadata.py`, com os padrões na própria classe. O núcleo não guarda configuração global: `salvar`, `salvar_varios`, `definir_capa`, `remover_capa`, `limpar_extras` e `rascunho.executar_salvamento` recebem `opcoes` (o padrão `None` vale `OpcoesGravacao()`). A CLI usa os padrões. A GUI monta o objeto a partir das Configurações em `JanelaPrincipal.opcoes_gravacao` e o entrega a cada gravação (threads `Salvador` e `Limpador`). `versao_id3` e `remover_id3v1` valem só para MP3; `multivalor` vale para todos os formatos (via `dividir_valores`).

### 4. Trabalho pesado fora da thread da interface

Carregar pastas, salvar, mover arquivos e limpar extras rodam em subclasses de `QThread` definidas em `gui/janela.py`: `Carregador`, `Salvador`, `Movedor`, `Limpador`. As buscas de rede rodam em `Trabalhador` (`gui/busca.py` e `gui/busca_online.py`). A thread só chama o núcleo (por exemplo, `Salvador.run` chama `executar_salvamento`) e devolve o resultado por sinal (`concluido`, `progresso`).

### 5. Gravação segura

`executar_salvamento` recebe `mtimes` e **não grava** um arquivo que mudou no disco desde a leitura (`ArquivoModificado`), registrando-o como falha. Para cada arquivo gravado, devolve também um registro para desfazer.

### 6. Credenciais: Configurações, variável de ambiente e `chaves.json`

`credenciais.py` procura cada credencial nesta ordem (docstring do módulo): valor das Configurações, variável de ambiente (`VARIAVEIS`), `chaves.json` embutido; se nada existir, devolve `None` e a busca daquele serviço fica desativada.

- O token pessoal do Discogs nunca vem do `chaves.json`: só das Configurações ou do ambiente (`discogs_authorization`).
- `estado_servicos` e `DICAS` dão o estado e o texto de dica para a GUI desabilitar o serviço sem credencial.
- `ocultar_credenciais` e `FormatadorSemCredenciais` trocam credenciais por `***` em logs e mensagens de erro; `online.abrir_sem_vazar` e `online.url_segura` evitam enviar a credencial a outros domínios.
- O Discogs recebe a credencial só no cabeçalho `Authorization` (`discogs.py`), nunca na URL.

### 7. Limites e regras dos serviços online

- MusicBrainz: User-Agent identificado e no máximo 1 requisição por segundo (`busca.INTERVALO`, `busca.LIMITADOR`).
- Discogs: no máximo 60 requisições por minuto (`discogs.LIMITADOR`, `online.LimitadorJanela`), espera no 429 (`TENTATIVAS`, `ESPERA_MAXIMA`), cache só em memória e com teto de 6 h (`discogs.CACHE`, `TETO_CACHE`). Capas do Discogs nunca são baixadas; capas vêm só do Cover Art Archive.
- Respostas de rede inválidas viram `ErroBusca` (decorador `online.resposta_invalida`).

## O modelo Rascunho

`tagger/nucleo/rascunho.py`, classe `Rascunho`, é a **fonte única das alterações ainda não gravadas**. Cada arquivo tem o seu conjunto de alterações pendentes (campos em `Rascunho.tags`, capa em `Rascunho.capas`). Consequências:

- É possível editar uma seleção, trocar de seleção e continuar; nada é gravado até "Salvar".
- Edição no painel, edição na tabela, numerar faixas, colar tags, desfazer/refazer (`aplicar_registros`) e o resultado das buscas online (`montar_alteracoes`) entram no Rascunho pelos mesmos métodos (`definir`, `definir_por_faixa`, `definir_capa`). Tabela e painel leem os valores por `Rascunho.valor`.
- Ao salvar, `validar` aponta valores inválidos e `trabalhos` produz a lista `(caminho, {campo: valor normalizado}, ação de capa)` entregue a `executar_salvamento`.
- `descartar` joga fora as pendências; `renomear` acompanha o Rascunho quando arquivos mudam de caminho.
- Renomear/organizar arquivos **não** passa pelo Rascunho: é a exceção documentada na classe `Renomeacao` (desfazer renomeia de volta na hora). `migrar_historico` corrige os caminhos do histórico depois disso.

Regra prática: toda mudança de tag iniciada pelo usuário ou por uma busca deve virar alteração no Rascunho, nunca uma gravação direta.

## O histórico de desfazer

`tagger/nucleo/historico.py`, classe `Historico`, guarda as pilhas `desfazer` e `refazer` e o `pendente` (um desfazer/refazer de tags ainda não confirmado). Não tem Qt e não toca em arquivos: a janela grava ou move e conta o resultado ao `Historico`, que decide o que fica em cada pilha. Cada item é uma lista de registros de tags (os valores anteriores, vindos de `executar_salvamento`) ou uma `Renomeacao`.

- `registrar_gravacao`: depois de gravar, só os arquivos sem falha entram. Uma gravação nova vai para `desfazer` e limpa `refazer`; a que confirma um desfazer vai para `refazer`; a que confirma um refazer volta para `desfazer`.
- `retirar` e `preparar`: desfazer/refazer de tags não gravam na hora; o registro vira alteração pendente no `Rascunho` (`Rascunho.aplicar_registros`) e só vale com "Salvar". `descartar_pendente` devolve o item à pilha de onde saiu.
- `registrar_renomeacao`, `concluir_reversao`, `registrar_movimento_interrompido`: renomear/mover não passa pelo `Rascunho`; desfazer move de volta na hora e o que falhou continua na pilha para nova tentativa. `migrar` ajusta os caminhos das pilhas quando arquivos mudam de nome.

## Como estender

### Adicionar um formato de áudio

1. Se o formato usa uma família já existente (Vorbis comments ou MP4), basta registrá-lo; senão crie `tagger/nucleo/formatos/<nome>.py` com as funções do contrato descrito em `formatos/__init__.py`: `ler`, `gravar`, `capas`, `aplicar_capa`, `extras`, `remover_extras`. Nenhuma pode chamar `save()`.
2. Em `metadata.py`: adicione a extensão a `EXTENSOES_SUPORTADAS`, importe o módulo e registre-o em `_MODULOS`, e acrescente a classe do mutagen em `_abrir`.
3. `formato`, `curingas_audio`, `nomes_formatos`, `listar_audios`, `carregar`, `salvar` e `limpar_extras` passam a funcionar sem mudança, pois consultam esses registros.
4. Atualize a docstring de `tagger/__init__.py` e o `readme.md`.
5. Teste em `tests/test_metadata.py`: leitura, gravação, remoção de tag, capa e leitura sem gravar.

### Adicionar um serviço online

1. Crie `tagger/nucleo/<servico>.py`, seguindo `busca.py` e `discogs.py`: um cliente com `buscar_releases` e `detalhar_release`, e `analisar`/`montar_alteracoes` devolvendo alterações no formato do Rascunho. Use a infraestrutura de `online.py` (limitador, cache, `url_segura`, `abrir_sem_vazar`) e respeite as regras do serviço.
2. Se exigir credencial: adicione a variável em `credenciais.VARIAVEIS`, uma função de resolução como `discogs_authorization`, a entrada em `DICAS` e em `estado_servicos`; se a chave for colada pelo usuário, inclua a chave de configuração em `CHAVES_CONFIG`, para ser ocultada nos logs. Nunca coloque a credencial em URL, código ou teste.
3. Na GUI, em `gui/busca_online.py`: crie uma classe de fonte (como `FonteDiscogs`) que adapta o cliente aos métodos `buscar`, `detalhar`, `analisar` e `atribuicao`; adicione o nome em `NOMES` e `DESCRICOES`, e trate-o em `criar_fonte`/`criar_fontes` e `credenciais_resolvidas`. Mostre a atribuição exigida pelo serviço.
4. Testes sem rede: injete respostas falsas, como em `tests/test_busca.py` e `tests/test_busca_online.py`; credenciais em `tests/test_credenciais.py`.

### Adicionar uma opção de configuração

1. Em `gui/config.py`, acrescente a chave e o valor padrão em `PADROES`. O tipo do padrão (bool, int, lista) decide a conversão em `carregar_config`; `salvar_config` grava tudo em `QSettings` sob `config/<chave>`.
2. Em `gui/configuracoes.py`, crie o controle, ligue-o a `_definir("<chave>", valor)` (que emite `mudou` para a prévia ao vivo) e preencha-o ao carregar o estado (onde `ck_multivalor` e similares são preenchidos).
3. Em `JanelaPrincipal._aplicar_config_pendente` (`gui/janela.py`), aplique o efeito; se a opção afeta a gravação de tags, ajuste também `OpcoesGravacao` e `JanelaPrincipal.opcoes_gravacao`. Se for aparência, inclua a chave em `CHAVES_APARENCIA`.
4. A regra em si fica no núcleo, recebendo o valor por parâmetro quando possível. Se a opção guarda credencial, siga o passo 2 de "Adicionar um serviço online".
5. Registre mudanças visíveis ao usuário no `CHANGELOG.md`.
