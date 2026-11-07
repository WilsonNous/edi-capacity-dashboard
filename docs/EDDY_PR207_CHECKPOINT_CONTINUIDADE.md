# EDDY / EDNNA — checkpoint de continuidade da PR #207

Atualização: 2026-11-07. Este documento preserva o contexto operacional; não equivale a autorização para executar efeitos externos.

## Objetivo e princípios
Concluir a migração da persistência operacional EDDY/EDNNA do SQLite legado `ednna.db` para MySQL, mantendo os pilares NETUNNA: **Flexibilidade, Segurança, Escalabilidade e Performance**. A VR01 é a primeira regra de um motor reutilizável, não uma exceção arquitetural.

## GitHub e escopo
- Repositório: `WilsonNous/edi-capacity-dashboard`.
- PR: https://github.com/WilsonNous/edi-capacity-dashboard/pull/207
- Branch: `audit/eddy-legacy-sqlite-dependencies-20261107`.
- Todas as alterações desta migração devem permanecer na PR #207. Não alterar PR #196.
- O usuário solicitou concluir testes e homologação para merge e produção; **merge e implantação não foram executados** neste checkpoint.

## Implementações
- `ednna/armazenamento.py`: desativa acesso ao SQLite legado no modo MySQL.
- `ednna/redmine_status_catalog.py`: catálogo de status MySQL.
- `ednna/mysql_continuidade_decisoes.py` e `ednna/continuidade_decisoes.py`: decisões persistidas em MySQL, com textos limitados.
- `ednna/mysql_interpretacoes_retorno.py`: interpretações de respostas Graph com chave de deduplicação.
- `ednna/mysql_acompanhamento_acoes.py` e `ednna/acompanhamento_acoes.py`: acompanhamento operacional direcionado ao MySQL, compatibilidade SQL, lock por chamado/regra, rollback de transações abandonadas.
- `ednna/mysql_storage.py`: orçamento consultivo de armazenamento e dimensão por tabela.
- `scripts/homologate_eddy_mysql_actions.py`: homologação com registro sintético **somente em schema dedicado terminado em _homolog**, sem chamadas Graph/Redmine.
- Testes: `tests/test_mysql_acompanhamento_sql.py`, `tests/test_mysql_acompanhamento_routing.py`, `tests/test_mysql_storage_budget.py`, e testes de continuidade.

## Segurança e idempotência
- Chamado #50318 já teve e-mail enviado: **não reenviar**.
- Estado ENVIANDO incerto no modo MySQL não autoriza retry automático sem reconciliação Graph.
- O serviço `scripts/start_eddy.sh` mantém automação externa desabilitada quando MySQL está ativo. Não remover o bloqueio antes de homologação e reconciliação.
- `painel.db` é cache separado e não deve ser confundido com `ednna.db`.
- Não apagar journals, histórico Graph ou evidências para reduzir o banco.

## Evidência de testes
- No commit `52ca50285f50f6c5851e2c7d5914c2b0d7f05dc7`, quatro workflows GitHub Actions terminaram com sucesso.
- Commits posteriores exigem nova checagem de CI.
- **Não há comprovação de execução contra MySQL real**, reconciliação dos envios históricos, desempenho p95, ou validação de logs Azure. Não afirmar homologação completa sem essas evidências.

## Critérios antes de merge e produção
1. CI verde no HEAD definitivo da PR.
2. Homologação MySQL real isolada, inclusive concorrência, confirmação e leitura posterior.
3. Conferir dados/evidências históricas de envios Graph; não permitir envio duplicado.
4. Revisar o adaptador SQL e o esquema para compatibilidade real MySQL.
5. Fazer merge somente com aprovação operacional e evidências suficientes; implantação e habilitação dos workers são etapas separadas.
6. Após implantação, verificar logs Azure: conexão TLS MySQL, bootstrap, migrações, exceções, bloqueios de idempotência, filas e latências.

## Continuidade
Ao iniciar novo chat, abrir esta PR e ler este checkpoint e `docs/EDDY_AUDITORIA_SQLITE_MYSQL_20261107.md`; conferir commits/CI recentes, homologação e bloqueios antes de agir. Não recomeçar a VR01 nem repetir envios já realizados.
