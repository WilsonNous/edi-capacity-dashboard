# Auditoria de dependências SQLite — EDDY / EDNNA (2026-11-07)

## Decisão arquitetural

O banco `ednna.db` foi aposentado. Em produção (`EDDY_DB_ENGINE=mysql`), nenhum componente pode criar, ler ou escrever nele. O MySQL é a fonte de persistência operacional do EDDY. `painel.db` é um cache separado de apresentação e **não** constitui migração de estado operacional.

## Inventário por busca de código na main (GitHub)

| Componente | Dependência encontrada | Tratamento nesta PR | Próxima migração |
|---|---|---|---|
| `ednna/armazenamento.py` | CRUD operacional SQLite e criação implícita de arquivo | Conexão recusada no modo MySQL; import sem criação de diretório | Portar tabelas/consumidores para repositórios MySQL |
| `ednna/recovery_guard.py` | Validação do arquivo legado | Modo MySQL não aceita SQLite como prontidão | Prontidão real de cada motor via MySQL |
| `ui/operational_data.py` | `chamados_df()` lia `ednna.db` | Reutiliza carteira ativa já validada via painel/ponte MySQL | Leitura histórica exclusiva MySQL |
| `eddy_api/service.py` | Contadores locais de regras, ações, follow-ups | Não abre SQLite no modo MySQL; sinaliza métricas não migradas | Consultas MySQL com tabelas homologadas |
| `ednna/redmine_status_catalog.py` | Cache de status em SQLite legado | **Migrado nesta PR**: leitura/escrita na tabela `eddy_redmine_status_catalog` quando `EDDY_DB_ENGINE=mysql` | Validar dados reais e permissões DDL em Azure |
| `ednna/continuidade_decisoes.py` | Persistência de decisões SQLite | **Migrado nesta PR**: `eddy_continuidade_decisoes` com leitura, escrita e prazo estável | Validar MySQL real e migrar revisões correlatas |
| `ednna/acompanhamento_acoes.py` | Acompanhamento de ações SQLite | **Pendente** | Migrar filas e follow-ups |
| `ednna/orquestrador_cancelamentos.py` | SQLite operacional | **Pendente** | Migrar orquestração |
| `ednna/executor_envio_eddy.py`, `ednna/observabilidade.py`, `ednna/security.py` | Acessos SQLite identificados | **Pendente** | Classificar armazenamento e migrar |
| `app.py`, `painel_cache.py`, `ednna/mysql_panel_bridge.py` | SQLite do painel e/ou legado | **Pendente de separação completa** | Preservar somente cache de painel, eliminar caminhos operacionais legados |
| `scripts/start_eddy.sh` | Desativa workers legados no modo MySQL | Mantido intencionalmente | Reativar apenas após migração e homologação por motor |

## Evidências e limites

A busca de código cobriu `ednna.db`, `EDNNA_DB_PATH`, `sqlite3.connect` e `EDDY_DB_ENGINE`. Documentação histórica e testes legados podem continuar mencionando `ednna.db` sem serem caminhos ativos. O inventário não substitui análise de chamadas dinâmicas, dependências indiretas ou teste em Azure.

**Esta PR é a primeira fase de auditoria e contenção**, não a migração integral das tabelas e motores. Não habilitar workers SQLite legados, nem substituir valores ausentes de métricas por números fictícios. Não apagar `painel.db` sem separar os seus consumidores.

## Critérios para encerrar a migração

1. Nenhum acesso operacional a `ednna.db` no modo MySQL, incluindo imports e rotas secundárias.
2. Estados, ações, aprovações, outbox, follow-ups e catálogos em repositórios MySQL, com idempotência.
3. Testes de integração MySQL e regressão de cada motor, inclusive falhas de conexão.
4. Remoção dos bloqueios de inicialização somente depois de homologação em produção.

## Volume, desempenho e retenção (nova exigência)

- `storage_table_sizes()` consulta somente `information_schema` e retorna as maiores tabelas com dados, índices e contagem **estimada** de linhas.
- `storage_budget()` compara o tamanho estimado com `EDDY_DB_WARNING_MB` (padrão inicial: 512 MiB), apenas para alerta. Não interrompe atendimento e não apaga registros.
- `eddy_continuidade_decisoes` mantém **uma linha por chamado**, sobrescrita idempotentemente; campos textuais têm limites explícitos. Não guarda histórico repetido a cada ciclo.
- `eddy_chamados.payload_json` e `eddy_journals.detalhes_json` são os maiores candidatos a crescimento. Não eliminar journals, evidências Graph ou outbox sem uma política de retenção e reconstrução homologada.
- Priorizar consultas por PK/chamado_id e índices de estado/data; evitar carregar todos os payloads para montar dashboards. `information_schema.table_rows` em InnoDB é aproximação, não contagem exata.
- Próxima validação: registrar tamanho real por tabela, tamanho médio/p95 de payloads, latência p95 de leitura/escrita e evolução semanal. Não declarar o banco pequeno ou rápido antes dessas medições.
- Nenhuma rotina de exclusão automática foi habilitada. Definir retenção por classe (cache descartável versus evidência operacional obrigatória) antes de implementar limpeza.
