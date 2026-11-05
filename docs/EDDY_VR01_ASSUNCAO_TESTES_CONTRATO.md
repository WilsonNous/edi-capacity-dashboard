# VR01 #50318 — Homologação da assunção: contrato de escrita e reconciliação

## Evidência automatizada (sem efeitos externos)

`tests/test_eddy_vr01_assignment_reconciliation_contract.py` exercita o orquestrador real com fronteiras Redmine/MySQL substituídas por doubles determinísticos:

- Sucesso: aprovação específica com versão Redmine, reserva, um PUT simulado, confirmação por GET simulado, evento `ASSUNCAO_EDDY` e fase `ASSUMIDO_EDDY` sem operação pendente.
- Ausência de aprovação ou versão divergente: nenhuma reserva, nenhuma escrita.
- Falha de prontidão: nenhuma reserva, nenhuma escrita.
- Timeout de PUT: reserva permanece pendente; nova chamada não repete o PUT.
- GET sem confirmação: reserva pendente e nenhum evento de assunção falso.

**Limite da evidência:** CI não demonstra permissão real de escrita no Redmine, semântica transacional MySQL em rede, nem reconciliação de um PUT aplicado com resposta perdida. Por isso não libera as flags automaticamente.

## Homologação operacional restante

1. Separar chamado de teste autorizado e identidade EDNNA; registrar o estado original e a versão `updated_on`.
2. Em janela controlada e com autorização explícita, executar **um** teste real de atribuição no ambiente de homologação, confirmar via GET e registrar a evidência MySQL.
3. Validar caso de falha de conexão em ambiente controlado; confirmar que não há segundo PUT automático e que o responsável consegue reconciliar o estado efetivo.
4. Documentar o procedimento de retorno ao responsável original e confirmar a restauração.
5. Só após aprovação do teste real, homologar a auditoria Redmine/MySQL e liberar uma execução assistida do #50318 com aprovação vinculada à versão atual.

Não executar o teste real contra #50318 como substituto de homologação; não mudar `EDDY_VR01_EXTERNAL_ENABLED` ou `EDDY_VR01_REDMINE_MYSQL_AUDIT_READY` com base apenas nos testes simulados.
