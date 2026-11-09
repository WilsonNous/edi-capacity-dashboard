# Varredura de dependências SQLite / MySQL — 09/11/2026

## Escopo e evidência
Busca de código no GitHub da branch main por `conectar()`, `sqlite3`, `EDDY_DB_ENGINE`, `ON CONFLICT` e `ednna.armazenamento`. Esta busca é uma triagem ampla, não substitui inventário recursivo de imports e execução em Azure. Resultados por termo: 25, 20, 26, 25 e 23 arquivos, respectivamente (conjuntos sobrepostos).

## Grupos identificados
- Escola e regras: `homologacao`, `escola_continua`, `construtor_regras`, `aprendizado_operacional`, `minerador_aberturas`, `motor_aberturas`, `motor_falta_arquivo`, `regras_ocorrencias`, `aprendizado_ocorrencias`.
- Execução e operações: `acompanhamento_acoes`, `orquestrador_cancelamentos`, `executor_envio_eddy`, `followup_engine`, `monitor_respostas`, `checkpoints_humanos`, `workflows_inclusao`, `greencard_workflow`, `status_guard`, `contexto_relacionamentos`.
- Observabilidade e API: `observabilidade`, `observabilidade_motores`, `eddy_api/service.py`, `ui/operational_data.py`, `app.py`, `painel_cache.py`, `mysql_panel_bridge.py`.
- Infraestrutura: `armazenamento`, `recovery_guard`, `security`, `sincronizador`, `sincronizador_journals`.
- `painel.db` é cache de UI, não deve ser confundido com `ednna.db` operacional.

## Mudanças nesta PR
1. Repositório MySQL para homologações versionadas, autorizações e propostas de abertura, inicialmente sem backfill.
2. Observabilidade MySQL sem leitura SQLite.
3. Motores de abertura e falta de arquivo roteados ao repositório MySQL em modo MySQL, inclusive autorização assistida de abertura.
4. Nenhuma autorização automática, envio externo ou alteração de chamados.

## Bloqueios reais restantes
- Sem migração verificada do histórico SQLite para MySQL: ausência de dados não implica ausência de regras; **não executar regras antigas sem backfill e reconciliação**.
- `aprendizado_operacional`, `homologacao`, `minerador_aberturas` ainda possuem escritas SQLite em outros caminhos.
- Demais módulos listados precisam de classificação e migração por contrato; não trocar `conectar()` globalmente, pois SQL SQLite difere de MySQL e há cache de UI legítimo.
- Necessários testes de integração MySQL real, concorrência, transações, idempotência, deduplicação de serviços por cliente/adquirente/estabelecimento/objeto e validação em Azure.
- As novas tabelas requerem privilégios DDL no usuário MySQL da observabilidade. Idealmente mover bootstrap para migração de deploy.
