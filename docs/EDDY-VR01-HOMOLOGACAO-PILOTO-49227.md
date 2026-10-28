# EDDY VR01 — homologação controlada do piloto #49227

## Estado
**Ainda não homologada em produção.** O gate é uma verificação de evidências para revisão humana, não autorização de execução.

## Evidências exigidas
1. Snapshot fresco do Redmine com timestamp e identificador do chamado.
2. Snapshot MySQL e journals reconciliados.
3. Responsável original registrado no ledger MySQL.
4. Assunção confirmada por leitura posterior do Redmine.
5. Devolução confirmada por leitura posterior do Redmine.
6. Transporte MySQL testado sem envio real.
7. Destinatário validado.
8. Respostas conciliadas.
9. Auditoria MySQL validada.

Cada item precisa de `confirmado: true` e referência verificável; variáveis de ambiente não são evidência. Mesmo checklist completo resulta em `EVIDENCIAS_COMPLETAS_PARA_REVISAO`, nunca em homologação automática.

## Limites
O código existente `eddy_vr01_ownership_confirmation.py` confirma observações fornecidas pelo chamador, mas não busca por si só um snapshot fresco do Redmine. A prontidão em `eddy_vr_readiness.py` permanece bloqueada até transporte, destinatários, reconciliação e auditoria estarem homologados. Não enviar Graph, não escrever no Redmine, não alterar responsável, não ativar `EDDY_VR01_EXTERNAL_ENABLED` sem autorização operacional específica.

## Próximo passo
Validar evidências reais do piloto, incluindo ciclo de posse/devolução aprovado, em ambiente controlado; obter aceite humano documentado; publicar regra versionada no MySQL e só então avaliar habilitação de execução externa.
