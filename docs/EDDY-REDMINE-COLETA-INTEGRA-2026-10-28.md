# EDDY: janela de conectividade Redmine e coleta integral

## Alteração
A coleta por projeto de `issues.json` é sequencial (offset 0, 100, ...), usando a sessão HTTP compartilhada. Cada página mantém os retries limitados do gateway; uma falha intermediária não reinicia as páginas já coletadas. A publicação da lista depende de `total_count` consistente, quantidade exata de registros por página e IDs inteiros não duplicados. Falha de qualquer validação interrompe a publicação e preserva o último snapshot confirmado.

## Segurança
O último snapshot pode apoiar painel, MySQL e análise **observacional**, nunca autorizar e-mails, escritas Redmine ou outros efeitos externos. Circuit breaker, confirmação fresca e bloqueios de prontidão VR01 continuam intactos. Este PR **não habilita** monitor operacional nem envios. Mudanças durante a paginação podem causar falha segura; `total_count` igual sozinho não garante snapshot transacional. Não alteramos o Redmine externo.

## Validação
Testes sem rede: cobertura completa, página ausente, contagem divergente, IDs duplicados, página curta, lista vazia, sequência de offsets. Após deploy Azure, observar `[REDMINE-COLETA]`, sucesso de listagens, retries por página, ausência de publicação parcial, MySQL/VR01 observacionais e duração da coleta.

## Próximo marco para ações externas
Homologar transporte, destinatários, recebimento e auditoria, confirmar estado atual e idempotência por ação e obter aprovação explícita do piloto antes de qualquer envio real.
