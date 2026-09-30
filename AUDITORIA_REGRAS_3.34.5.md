# Auditoria técnica de regras — EDNNA 3.34.5

A auditoria separa conhecimento configurado de executor efetivamente disponível.

## Workflows declarativos

- 19 workflows conhecidos.
- 15 possuem todos os componentes de executor declarados como implementados.
- 4 aguardam executor específico:
  - BANRISUL — `ASSISTIDO_BANCO`.
  - CIELO — `CIELO_API`.
  - REDECARD — `REDECARD_OPTIN_API` (o componente `EMAIL_GRAPH` existe).
  - TICKETLOG — `TICKETLOG_CHAMADO`.

Os demais 15 têm infraestrutura de executor disponível, mas isso **não significa execução automática**: homologação e autorização do motor continuam sendo barreiras independentes.

## Catálogo operacional clássico

Há regras de Falta de Arquivo/Cancelamento no `catalogo_operacional.json`. A capacidade automática continua condicionada aos campos `executavel`/`auto_executar` e ao pre-flight Redmine.

## Follow-up

- Regra em modo AUTOMÁTICO + prazo vencido: responsabilidade da EDNNA; entra como execução automática atrasada e é tentada pelo worker.
- Regra em modo ASSISTIDO + prazo vencido: passa para `Preciso de você`, com revisão e botão explícito para envio.
- Estados terminais e indisponibilidade do pre-flight continuam bloqueando qualquer envio.

## Segurança

Chamados já registrados na quarentena terminal deixam de provocar novo GET/pre-flight em cada ciclo operacional. O histórico/auditoria é preservado.

## v3.34.7 — Checkpoints humanos estruturados
- `Preciso de você` passa a registrar resultado + relato operacional do humano.
- O relato é persistido localmente e gravado no journal do Redmine após pre-flight fresco.
- O workflow só avança quando o checkpoint está concluído e o Redmine foi atualizado.
- SAFRAPAY: `TERMO_SAFRAPAY` concluído libera a próxima etapa do workflow.
- Falha/pre-flight indisponível mantém o checkpoint pendente (fail-safe).
- Estrutura genérica preparada para API/portal/planilha/validação de arquivos em CIELO, REDE e demais workflows.
