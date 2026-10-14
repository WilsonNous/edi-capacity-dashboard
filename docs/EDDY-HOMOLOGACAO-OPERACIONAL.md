# Homologação operacional do EDDY — etapa 1

A aprovação do CI não confirma execução operacional no Azure.

## Antes de ativar o worker

1. Confirmar deployment da revisão da PR e validar `/api/intelligence/handshake`.
2. Confirmar que o App Service executa `scripts/start_eddy.sh` e apenas uma instância de worker (escala horizontal e slots também contam).
3. Confirmar persistência de `EDNNA_DB_PATH` e `PAINEL_DB_PATH`, Redmine e credenciais Graph válidas.
4. Auditar atribuições antigas pela capacidade `edi.staff.departure.audit` com `{"person":"Helena"}`; não reatribuir automaticamente.
5. Manter `EDNNA_MONITOR_EMAIL_ENABLED=false` até aprovar operação controlada.
6. Para observação sem disparos: `EDNNA_MONITOR_EMAIL_ENABLED=true`, `EDNNA_AUTO_EXECUTE=false`, `EDNNA_FOLLOWUP_AUTO=false`; revisar também os demais fluxos com efeitos externos que o monitor já contém, antes de ativar a rotina.
7. Homologar cada ação externa com preflight Redmine, idempotência, Graph Sent Items e outbox de evidências.
8. Só depois habilitar a execução autorizada em uma única instância, com limite por ciclo e acompanhamento.

## Evidências mínimas por chamado

- Estado inicial e última atualização Redmine
- Regra e versão homologada, responsável por autorização
- Identificador idempotente da ação
- Prova de envio Graph ou ausência explícita de envio
- Registro Redmine e próximo acompanhamento
- Estado final, erro e ação humana pendente

## Critério de aceite

Um chamado real homologado precisa completar o ciclo de decisão, autorização, execução, confirmação, registro e continuidade sem duplicidade. Contagem de regras ou de logs não substitui este aceite.
