# EDDY — Auditoria de desativação do ednna.db

## Veredito (2026-10-28)
**NÃO APTO PARA EXCLUSÃO.** A análise estática do repositório comprova dependências legadas ativas e não comprova equivalência de dados entre SQLite e MySQL. Nenhum arquivo de produção foi acessado, removido ou migrado.

## Evidências do código
- `ednna/armazenamento.py`: define `chamados`, `journals`, `analises_primeiro_combate`, `classificacoes_demandas`, `metadados` e `coordenacao`; contém operações de leitura e escrita e inicialização do SQLite.
- `ednna/mysql_storage.py`: define `eddy_chamados`, `eddy_journals`, `eddy_schema_versions`, `eddy_external_evidence` e `eddy_storage_metrics`. Não comprova migração das análises, classificações, regras, decisões, metadados e coordenação.
- `ui/operational_data.py`: lê `ednna.db` em `chamados_df()` e `regras_df()`; esta última depende de `aprendizados_operacionais` e `revisoes_regras_operacionais`. A carteira ativa usa `painel.db` e pode usar MySQL; anteriormente havia fallback para `ednna.db` mesmo em modo MySQL.
- `ednna/recovery_guard.py`: bloqueia persistência operacional quando `EDDY_DB_ENGINE=mysql`; não declara migração operacional concluída.
- Pesquisa de código GitHub por `ednna.armazenamento`: 23 arquivos encontrados, incluindo sincronizadores, regras, primeiro combate, aprendizado e páginas. Pesquisa por `EDNNA_DB_PATH`: 16 arquivos encontrados. Estes números são índices de busca, não prova de execução em produção.
- `painel.db` é separado de `ednna.db` e não está autorizado para remoção.

## Matriz de equivalência
| Domínio | SQLite | MySQL | Conclusão |
| --- | --- | --- | --- |
| Chamados | chamados | eddy_chamados | Estruturas existem; equivalência de registros não verificada |
| Journals | journals | eddy_journals | Estruturas existem; equivalência de registros não verificada |
| Primeiro combate | analises_primeiro_combate | Sem equivalência demonstrada | Bloqueia exclusão |
| Classificações | classificacoes_demandas | Sem equivalência demonstrada | Bloqueia exclusão |
| Regras/aprendizados | aprendizados_operacionais, revisoes_regras_operacionais referenciadas na UI | Sem equivalência demonstrada | Bloqueia exclusão |
| Coordenação e metadados | coordenacao, metadados | Migração não demonstrada | Bloqueia exclusão |

## Refatoração segura nesta PR
Quando `EDDY_DB_ENGINE=mysql`, a carteira ativa deixa de apresentar silenciosamente o `ednna.db` como fallback operacional. Se a fonte atual falhar, retorna visão indisponível/vazia e registra o bloqueio. Isso **não** remove as outras dependências SQLite nem habilita efeitos externos. O comportamento de instalações em modo SQLite é mantido.

## Condições para futura retirada
1. Inventariar tabelas reais, integridade e contagens no arquivo Azure, preferencialmente a partir de cópia preservada, incluindo `-wal`/`-shm` se existentes.
2. Mapear todas as leituras e escritas em runtime, inclusive importações indiretas e páginas, e classificar cada dado como reconstruível, migrável ou histórico.
3. Migrar e reconciliar dados exclusivos para MySQL com contagens, chaves, checksums e amostragem, preservando evidência e rollback.
4. Refatorar cada consumidor para MySQL ou desativá-lo explicitamente; testar indisponibilidade e não regressão.
5. Executar homologação em Azure, confirmar ausência de acessos e **somente depois** arquivar o arquivo original; excluir definitivamente apenas sob autorização separada.

## Restrições
Sem acesso ao arquivo de produção, não se pode afirmar que o conteúdo foi recuperado, que não há dados exclusivos, ou que a migração está completa. Não executar `rm`, `mv`, `VACUUM` ou recriação do arquivo original como etapa desta PR.
