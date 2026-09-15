EDNNA v3.28.7.4 — Observabilidade da Reconciliação

Objetivo
- Não altera a lógica operacional da v3.28.7.3.
- Expõe no log os IDs dos chamados em cada estado da reconciliação GETNET.

Novos logs
- monitorando_ids=[...]
- processados_ids=[...]
- pendentes_redmine_ids=[...]
- presos_enviando_ids=[...]
- orfaos_reais_ids=[...]

Uso
O objetivo imediato é confirmar o estado real dos chamados #30846, #48561 e #48567 antes de qualquer nova alteração de processamento.

Deploy
Substituir ednna/monitor_respostas.py.
Os demais arquivos do pacote são mantidos para consistência com a v3.28.7.3.
