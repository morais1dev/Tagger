# Paridade de testes: v2 (pytest) → v3 (Rust)

Os testes pytest da v2 são a especificação do núcleo da v3. Esta lista diz, para cada teste, onde está o equivalente em Rust (`core/tests/`) ou por que não foi portado. Os testes Rust têm o **mesmo nome** do teste pytest; parametrizações viram laços dentro do teste.

Como rodar: `cargo test` na raiz (workspace) e `python -m pytest` para a v2.

## tests/test_metadata.py → core/tests/metadados_mp3.rs e metadados_outros.rs

| Teste pytest | Teste Rust | Observação |
|---|---|---|
| `test_valores_validos` | `metadados_mp3.rs::test_valores_validos` | parametrizado vira um laço; "atual" conferido pelo formato do ano |
| `test_valores_invalidos` | `metadados_mp3.rs::test_valores_invalidos` |  |
| `test_arquivo_sem_tags` | `metadados_mp3.rs::test_arquivo_sem_tags` |  |
| `test_ler_nao_grava` | `metadados_mp3.rs::test_ler_nao_grava` |  |
| `test_salvar_e_reler` | `metadados_mp3.rs::test_salvar_e_reler` |  |
| `test_gravadora_mp3` | `metadados_mp3.rs::test_gravadora_mp3` |  |
| `test_valor_vazio_remove_e_varios_ignora` | `metadados_mp3.rs::test_valor_vazio_remove_e_varios_ignora` |  |
| `test_so_remocoes_nao_cria_cabecalho_vazio` | `metadados_mp3.rs::test_so_remocoes_nao_cria_cabecalho_vazio` |  |
| `test_opcoes_padrao` | `metadados_mp3.rs::test_opcoes_padrao` |  |
| `test_id3v23_por_padrao` | `metadados_mp3.rs::test_id3v23_por_padrao` |  |
| `test_id3v24` | `metadados_mp3.rs::test_id3v24` |  |
| `test_versao_id3_vale_em_salvar_varios_e_definir_capa` | `metadados_mp3.rs::test_versao_id3_vale_em_salvar_varios_e_definir_capa` |  |
| `test_dividir_valores_com_e_sem_multivalor` | `metadados_mp3.rs::test_dividir_valores_com_e_sem_multivalor` |  |
| `test_um_unico_save_por_arquivo` | `metadados_mp3.rs::test_um_unico_save_por_arquivo` | a v2 conta chamadas de save() com monkeypatch; aqui confere o efeito (tags + capa numa chamada de `salvar`). O save único é estrutural: `salvar` termina num só `gravar_arquivo` |
| `test_leitura_fragil_vira_falha` | — (não portado) | troca a classe `MP3` do mutagen por uma que levanta erro (monkeypatch); não há ponto de injeção equivalente na lofty. O caminho "leitura falha → `None`" é coberto por `test_arquivo_invalido` e `test_outro_arquivo_invalido` |
| `test_arquivo_invalido` | `metadados_mp3.rs::test_arquivo_invalido` |  |
| `test_comentario_legado_txxx` | `metadados_mp3.rs::test_comentario_legado_txxx` |  |
| `test_comentario_com_descricao_e_preservado` | `metadados_mp3.rs::test_comentario_com_descricao_e_preservado` |  |
| `test_genero_id3v1_numerico` | `metadados_mp3.rs::test_genero_id3v1_numerico` |  |
| `test_letra_com_outra_descricao_e_preservada` | `metadados_mp3.rs::test_letra_com_outra_descricao_e_preservada` |  |
| `test_multivalor` | `metadados_mp3.rs::test_multivalor` |  |
| `test_multivalor_desligado` | `metadados_mp3.rs::test_multivalor_desligado` |  |
| `test_multivalor_ligado_no_id3v23_grava_valores_separados` | `metadados_mp3.rs::test_multivalor_ligado_no_id3v23_grava_valores_separados` | bytes diferem: a lofty não repete o BOM UTF-16 antes do 2º valor; o mutagen lê igual (spike) |
| `test_multivalor_sobrevive_ao_salvar_outro_campo` | `metadados_mp3.rs::test_multivalor_sobrevive_ao_salvar_outro_campo` |  |
| `test_trocar_capa_mantem_outras_imagens` | `metadados_mp3.rs::test_trocar_capa_mantem_outras_imagens` |  |
| `test_remover_capa_mantem_outras_imagens` | `metadados_mp3.rs::test_remover_capa_mantem_outras_imagens` |  |
| `test_capa_do_tipo_outra` | `metadados_mp3.rs::test_capa_do_tipo_outra` |  |
| `test_so_contracapa_nao_conta_como_capa` | `metadados_mp3.rs::test_so_contracapa_nao_conta_como_capa` |  |
| `test_remover_capa_sem_tags_nao_cria_cabecalho` | `metadados_mp3.rs::test_remover_capa_sem_tags_nao_cria_cabecalho` |  |
| `test_foi_modificado` | `metadados_mp3.rs::test_foi_modificado` | mtime ajustado com `File::set_modified` em vez de `os.utime` |
| `test_remover_id3v1_ao_salvar` | `metadados_mp3.rs::test_remover_id3v1_ao_salvar` |  |
| `test_limpar_extras_usa_as_opcoes_no_save` | `metadados_mp3.rs::test_limpar_extras_usa_as_opcoes_no_save` | a tag ganha um TIT2: a lofty não grava tag ID3v2 vazia (apaga o cabeçalho), o mutagen grava |
| `test_analisar_e_limpar_extras` | `metadados_mp3.rs::test_analisar_e_limpar_extras` |  |
| `test_valores_comuns` | `metadados_mp3.rs::test_valores_comuns` |  |
| `test_formatos_suportados` | `metadados_mp3.rs::test_formatos_suportados` |  |
| `test_outro_sem_tags` | `metadados_outros.rs::test_outro_sem_tags` |  |
| `test_outro_ler_nao_grava` | `metadados_outros.rs::test_outro_ler_nao_grava` |  |
| `test_outro_salvar_e_reler` | `metadados_outros.rs::test_outro_salvar_e_reler` |  |
| `test_outro_multivalor_nativo` | `metadados_outros.rs::test_outro_multivalor_nativo` |  |
| `test_outro_faixa_sem_total` | `metadados_outros.rs::test_outro_faixa_sem_total` | FLAC: a lofty não grava Vorbis comment vazio (o bloco some); contado como 0 chaves |
| `test_vorbis_numero_sem_barra_mantem_total` | `metadados_outros.rs::test_vorbis_numero_sem_barra_mantem_total` |  |
| `test_vorbis_alternativa_com_outro_conteudo_fica` | `metadados_outros.rs::test_vorbis_alternativa_com_outro_conteudo_fica` |  |
| `test_outro_so_o_primeiro_comentario_ou_letra_e_trocado` | `metadados_outros.rs::test_outro_so_o_primeiro_comentario_ou_letra_e_trocado` |  |
| `test_mp4_limpeza_nao_toca_atomos_tecnicos` | `metadados_outros.rs::test_mp4_limpeza_nao_toca_atomos_tecnicos` |  |
| `test_mp4_capa_que_nao_e_jpeg_nem_png_e_recusada` | `metadados_outros.rs::test_mp4_capa_que_nao_e_jpeg_nem_png_e_recusada` |  |
| `test_ogg_coverart_antigo` | `metadados_outros.rs::test_ogg_coverart_antigo` | o COVERART é posto por fora com a lofty, que já o lê como imagem |
| `test_ogg_opus` | `metadados_outros.rs::test_ogg_opus` |  |
| `test_outro_valor_vazio_remove_e_varios_ignora` | `metadados_outros.rs::test_outro_valor_vazio_remove_e_varios_ignora` |  |
| `test_outro_um_unico_save` | `metadados_outros.rs::test_outro_um_unico_save` | idem |
| `test_outro_capa_definir_trocar_remover` | `metadados_outros.rs::test_outro_capa_definir_trocar_remover` |  |
| `test_outro_outras_imagens_ficam` | `metadados_outros.rs::test_outro_outras_imagens_ficam` |  |
| `test_vorbis_so_contracapa_nao_conta_como_capa` | `metadados_outros.rs::test_vorbis_so_contracapa_nao_conta_como_capa` |  |
| `test_flac_sem_vorbis_comment_remove_capa` | `metadados_outros.rs::test_flac_sem_vorbis_comment_remove_capa` |  |
| `test_vorbis_nomes_alternativos` | `metadados_outros.rs::test_vorbis_nomes_alternativos` |  |
| `test_outro_analisar_e_limpar_extras` | `metadados_outros.rs::test_outro_analisar_e_limpar_extras` |  |
| `test_outro_id3v1_nunca_corta_o_arquivo` | `metadados_outros.rs::test_outro_id3v1_nunca_corta_o_arquivo` |  |
| `test_outro_arquivo_invalido` | `metadados_outros.rs::test_outro_arquivo_invalido` |  |
| `test_textos_de_formatos` | `metadados_mp3.rs::test_textos_de_formatos` |  |
| `test_gravadora_outro_gravar_e_apagar` | `metadados_outros.rs::test_gravadora_outro_gravar_e_apagar` | idem (Vorbis comment vazio no FLAC) |
| `test_gravadora_vorbis_le_label` | `metadados_outros.rs::test_gravadora_vorbis_le_label` |  |
| `test_gravadora_vorbis_organization_tem_prioridade` | `metadados_outros.rs::test_gravadora_vorbis_organization_tem_prioridade` |  |
| `test_bitrate_usa_o_do_mutagen` | `metadados_mp3.rs::test_bitrate_usa_o_do_mutagen` | `_bitrate(info, caminho)` vira `bitrate_kbps(bitrate, duracao, tamanho)` |
| `test_bitrate_estimado_pelo_tamanho` | `metadados_mp3.rs::test_bitrate_estimado_pelo_tamanho` | idem; os 3 casos do parametrize (None, 0, sem atributo) viram None e Some(0) |
| `test_bitrate_sem_duracao_e_zero` | `metadados_mp3.rs::test_bitrate_sem_duracao_e_zero` | idem |

Total: 64 testes pytest, 63 portados, 1 não portado.

## Só na v3: core/tests/regressoes.rs

Casos que a v2 não precisava testar (o mutagen não tem esses problemas), mas a lofty sim. Veja `docs/adr/0001-stack-v3.md`, "Resolvido".

| Teste Rust | O que garante |
|---|---|
| `genero_multivalor_sobrevive_em_id3v23` | patch do `TCON` em ID3v2.3 (`third_party/lofty`) |
| `genero_com_codigo_numerico_cai_no_caminho_original_da_lofty` | documenta a limitação aceita do patch: `Rock; 80` vira `(Rock)(80)` |
| `tdrc_com_data_completa_em_id3v23_sobrevive` | contorno do `TDRC` (leitura sem conversões implícitas) |
| `tyer_tdat_de_um_id3v23_padrao_ficam` | v2.3 padrão (`TYER`/`TDAT`/`TORY`) intacto e lido como data |
| `data_gravada_em_id3v23_e_relida` | a data gravada em v2.3 (vira `TYER`+`TDAT`) e em v2.4 volta igual |
| `id3v23_com_cabecalho_estendido_e_lido_e_regravado` | lofty-rs #761 (backport do #777) e o áudio intacto ao regravar (correção própria do tamanho da tag) |
| `id3v23_com_cabecalho_estendido_e_crc_fica_valido` | cabeçalho estendido com CRC não é regravado no layout do v2.4 |
| `id3v1_existente_e_atualizado_a_partir_da_v2` | ID3v1 atualizado como o mutagen faz com `v1=1` |
| `sem_id3v1_nao_cria_um` | não cria ID3v1 |
| `vorbis_tracknumber_com_barra_fica_como_esta` | sem conversões implícitas: `TRACKNUMBER=3/12` não é dividido |
| `mp4_gnre_antigo_e_lido_e_preservado` | sem conversões implícitas: `gnre` lido como gênero e só trocado quando o gênero é gravado |

## Diferenças conhecidas em relação à v2

- **Tag vazia:** a lofty não grava uma tag ID3v2 nem um Vorbis comment de FLAC sem itens; o cabeçalho/bloco some. O mutagen mantém o cabeçalho vazio.
- **UTF-16 multivalor no ID3v2.3:** a lofty não repete o BOM antes do 2º valor; o mutagen lê igual.
- **Data no ID3v2.3:** a v2 grava `TDRC` (fora do padrão v2.3); a v3 grava `TYER`+`TDAT`, como o padrão manda. As duas são lidas como a mesma data.
- **COVERART no Ogg:** a lofty converte o `COVERART` antigo numa imagem `METADATA_BLOCK_PICTURE` do tipo "outra" já ao ler; qualquer gravação o regrava nesse formato (a v2 só o tirava ao definir uma capa nova).
- **Frames "desconhecidos" do ID3:** a v2 conta os que o mutagen não entende; a v3 conta os que a lofty lê como binários, menos GEOB, SYLT e ATXT.

## Outros arquivos de teste da v2

Fora do escopo da T3.2a (metadados); entram nas próximas partes da T3.2: `test_agrupar.py`, `test_atribuicao.py`, `test_atualizacao.py`, `test_busca.py`, `test_busca_online.py`, `test_configuracoes_servicos.py`, `test_credenciais.py`, `test_historico.py`, `test_interface.py`, `test_interface_atualizacao.py`, `test_janela_opcoes.py`, `test_online.py`, `test_organizar.py`, `test_padroes.py`, `test_qsettings.py`, `test_rascunho.py`, `test_rede.py`, `test_seguranca.py`.
