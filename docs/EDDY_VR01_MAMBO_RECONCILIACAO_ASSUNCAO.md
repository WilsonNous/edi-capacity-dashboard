# EDDY VR01 — MAMBO #50318 — evidência e reconciliação de assunção

Identidade operacional: `eddy.ia` (Redmine ID 166); responsável original: ID 97.

## Verificação de reconciliação (somente leitura)

Na produção já atualizada:

```bash
python - <<'PY'
from pprint import pprint
from ednna.eddy_vr01_assignment_reconciliation import diagnosticar_reconciliacao_assuncao
pprint(diagnosticar_reconciliacao_assuncao())
PY
```

O diagnóstico consulta o Redmine e executa somente SELECT no MySQL; não altera atribuições, ledger, eventos ou flags.

## Critério de assunção confirmada

`ASSUNCAO_CONFIRMADA` requer simultaneamente: responsável Redmine 166, fase MySQL `ASSUMIDO_EDDY`, evento `ASSUNCAO_EDDY` com referência 166 e nenhuma operação pendente. Um PUT com timeout pode ter sido aplicado no Redmine; qualquer `operacao_pendente` impede confirmação automática e exige reconciliação humana. **Não repetir o PUT** e não limpar a reserva sem inspecionar evidências.

## Primeira execução assistida (ainda não homologada)

1. Registrar autorização explícita do operador para **uma única** assunção do chamado #50318 e versão `updated_on` vigente.
2. Confirmar em Redmine e MySQL que o responsável original ainda é 97, fase `PRONTO_PARA_ASSUMIR`, sem pendência.
3. Homologar separadamente a escrita/auditoria real, incluindo tratamento de resposta perdida; a suíte de mocks não substitui a homologação.
4. Somente com evidência real de homologação e janela controlada, habilitar gates de operação e execução. Invocar o orquestrador existente com aprovação vinculada à versão lida; não habilitar automação contínua como atalho.
5. Rodar o diagnóstico acima; se não retornar `ASSUNCAO_CONFIRMADA`, interromper as próximas etapas e reconciliar manualmente.
6. Para reversão, usar procedimento autorizado e auditado de devolução ao responsável original ID 97, com readback e MySQL reconciliados.

Não enviar e-mail ao cliente nem assumir que autorização no portal prova recebimento dos arquivos.
