# EDDY VR01 — descoberta dinâmica (contrato operacional)

A Regra 01 não possui allowlist de IDs de chamados. Os IDs presentes em testes são apenas cenários de regressão.

## Fluxo único

1. `ednna.eddy_vr_mysql_sync.sincronizar_carteira_vr_mysql` descobre chamados abertos pelo Redmine, usando `scripts.eddy_vr01_open_inventory._is_vr` / `ednna.eddy_vr_origin.identificar_vr`.
2. Para cada chamado elegível, busca detalhe e **todos os journals** antes de persistir com `ednna.mysql_snapshot_repository.salvar_snapshot`. Falhas são explicitadas, nunca consideradas importação bem-sucedida.
3. `ednna.eddy_vr_mysql_operation.operacao_vr_mysql` avalia os snapshots persistidos, sem fallback SQLite.
4. `scripts.eddy_vr01_mysql_cycle.executar_ciclo_vr01` bloqueia avaliação em sincronização parcial ou divergência de IDs.
5. `scripts.eddy_vr01_mysql_worker.executar_worker_vr01` é o ponto de entrada com lock MySQL para o scheduler do EDDY. **Ainda requer conexão ao scheduler em produção.**

## Limites de homologação

- `origem` pode ser código ou descrição; códigos precisam da tradução do cadastro Redmine. Assunto é fallback somente na ausência de origem.
- A sincronização geral do painel que registra `journals: não importados` não comprova histórico completo. A sincronização específica da VR exige journals.
- Nenhuma evidência de envio pode ser inferida de texto livre. Envio, resposta e anotação no Redmine exigem confirmação externa.
- Este fluxo não habilita envio de e-mail, escrita no Redmine, execução automática ou substituição do backend legado da tela Operação.
- Os antigos `ednna/eddy_vr_redmine_import.py` e `scripts/eddy_vr01_controlled_pilot.py`, restritos a IDs fixos, foram removidos.
