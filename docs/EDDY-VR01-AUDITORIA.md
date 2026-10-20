# EDDY VR01 — auditoria de decisões (fase controlada)

Esta entrega adiciona persistência idempotente de avaliações **sem enviar e-mail, modificar Redmine ou executar ações externas**.

1. Aplicar manualmente `migrations/eddy_vr01_decisoes.sql` após revisão.
2. Sincronizar snapshots e journals completos via mecanismo existente, antes de avaliar.
3. Chamar `registrar_decisao(chamado_id)` para os chamados 49227 e 49289.
4. Conferir registros em `eddy_vr_decisoes` e repetir para validar idempotência.
5. Confirmar no Azure a versão publicada e os resultados, antes de declarar homologação.

**Limite desta PR:** não implementa importação remota de journals, agendamento, UI, migração automática ou comprovação de deploy. O digest considera o snapshot completo; mudanças em campos de sincronização podem gerar nova decisão auditada. Não habilitar execução operacional.
