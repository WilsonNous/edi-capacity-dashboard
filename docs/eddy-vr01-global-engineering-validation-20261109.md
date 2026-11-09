# EDDY VR01 — engenharia global e critérios de aceite (09/11/2026)

## Evidência operacional
- 9 chamados avaliados por ciclo; 0 envios e 0 escritas Redmine.
- #48786 e #49119: GET Redmine OK, mas falha RuntimeError em EXECUTOR_VR01; em outros ciclos falha PREFLIGHT_REDMINE.
- 6 chamados: SEM_BP_MYSQL.
- #50318: AGUARDA_CONFIRMACAO_CLIENTE, nenhuma resposta correlacionada.
- Sincronização de 285 chamados ocorreu às 12:09; posteriormente circuit breaker e snapshot preservado.
- Scheduler em VR01_ANALISE_LOCAL_COM_PROPOSTAS / modo_offline=true.

## Alterações de engenharia exigidas antes de marcar esta PR como pronta
1. Unificar o preflight Redmine por chamado e ciclo, passar snapshot validado ao executor, verificar versão e responsável antes de cada mutação.
2. Propagar tipo, etapa e causa sanitizada das exceções; separar falha de rede, prontidão, aprovação, dados e inconsistência de estado.
3. Resolver cliente, CNPJ e contatos Blueprint em MySQL; usar recuperação direcionada e não bloquear toda a carteira por falha de um cliente.
4. Garantir que decisões de execução sejam explícitas e observáveis: fila observacional != execução autorizada.
5. Revisar reservas duráveis, idempotência e reconciliação após falhas em Redmine e Graph; impedir duplicidade de e-mails.
6. Validar a sequência completa: ler journals, assumir, contatar cliente, reconciliar retorno, registrar evidências, devolver ao responsável original.
7. Cobrir #48786, #49119, #50318 e os seis SEM_BP_MYSQL em testes com mocks, além de falhas de rede e recuperação.
8. Não ativar execução externa nem fazer merge sem testes e revisão das permissões de produção.

## Critérios objetivos de aceite
- Testes unitários e integração em CI verdes.
- Sem preflight redundante em caminho normal.
- Nenhum RuntimeError genérico sem causa operacional identificável.
- Nenhuma ação duplicada sob retry/circuit breaker.
- Cada chamado possui resultado conclusivo: executado, aguardando evento externo ou bloqueado com motivo acionável.
- Evidência de pelo menos um fluxo completo em ambiente controlado, sem efeitos colaterais em produção.

**Status:** especificação de validação; não representa implementação ou homologação.
