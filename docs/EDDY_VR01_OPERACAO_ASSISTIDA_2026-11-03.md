# EDDY VR01 — Marco de transição para operação assistida

**Data:** 2026-11-03  
**Piloto:** MAMBO, Redmine #50318  
**Decisão:** encerrar homologação funcional do motor de decisões e iniciar fase de operação assistida, **sem liberação de ações externas**.

## Evidências já observadas

- PR #176: migração do preflight de auditoria para MySQL, integrado à main.
- PR #177: homologação sintética do ciclo de vida, integrado à main e observado no Azure.
- Execução `python -m scripts.eddy_vr01_final_homologation` no Azure: `resultado=APROVADO`, nove decisões verificadas, oito guardas verificadas, zero escritas Redmine, zero envios de e-mail, zero escritas MySQL.
- Scheduler observacional: oito snapshots VR no MySQL, quatro propostas observacionais persistidas, sem efeitos externos.
- Verificação `verificar_prontidao_vr01()`: `pronto=False`, sem credenciais ausentes.
- Verificação `_load()` para #50318: `None` (ciclo operacional ainda não inicializado).

## Pendências de liberação identificadas pelo sistema

1. `TRANSPORTE_MYSQL_NAO_HOMOLOGADO`
2. `DESTINATARIOS_NAO_HOMOLOGADOS`
3. `RECEPCAO_RESPOSTAS_NAO_HOMOLOGADA`
4. `AUDITORIA_REDMINE_NAO_HOMOLOGADA`
5. `EXECUCAO_EXTERNA_DESABILITADA`

## Regras da operação assistida

- Redmine permanece fonte de verdade para estado atual, responsável e operações externas.
- Snapshots MySQL não substituem preflight Redmine fresco para escritas.
- Não habilitar flags de prontidão sem evidência correspondente.
- Não assumir, devolver ou atualizar chamado, nem enviar mensagens Graph, sem autorização humana específica e verificações de produção.
- Manter scheduler observacional e rastreabilidade; registrar separadamente homologação sintética e execução real.
- Falha de conectividade não autoriza contornar bloqueios.
- Este documento é **registro de decisão**, não certificação de integrações nem liberação de produção.

## Critério para ativação externa futura

Homologar cada uma das cinco condições acima, demonstrar ciclo persistido e reconciliado no MySQL e obter autorização específica antes de cada operação externa. Até lá, operação assistida significa observação, preparação e acompanhamento humano, sem execução automática externa.
