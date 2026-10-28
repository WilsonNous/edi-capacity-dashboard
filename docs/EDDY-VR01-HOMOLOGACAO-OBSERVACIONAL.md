# VR01 — homologação por etapas

Decisão operacional solicitada em 28/10/2026: avançar com a VR01 mesmo com pendências de conectividade, **limitando o aceite imediato ao modo observacional do piloto #49227**.

A função `homologar_observacao_vr01` exige autorização explícita, escopo #49227 e retorna `HOMOLOGADA_SOMENTE_OBSERVACAO`. Registra pendências sem fingir que foram validadas. A aprovação observacional não concede permissão para envio Graph, follow-up, troca de responsável ou escrita Redmine. O gate independente `verificar_prontidao_vr01` continua necessário para execução externa.

A aprovação no código não altera dados MySQL, não comprova deploy no Azure e não executa o piloto. A entrada em produção observacional requer implantação confirmada; operação externa exige testes de integração e dados frescos do Redmine. Não habilitar flags de prontidão sem validação.
