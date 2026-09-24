# EDNNA v3.28.59 — Operação orientada à ação

- Home passa a responder primeiro: prontos para executar, precisam do operador, aguardando resposta, follow-up e problemas de identificação.
- Nova visão explícita das regras ASSISTIDAS com os chamados relacionados e o motivo de cada estado.
- Regra homologada sem chamado compatível passa a ser apresentada como SEM_DEMANDA, evitando confusão com falha de identificação.
- Central de Regras mostra, para cada regra ativa, quantidade e links dos chamados, diagnóstico e próxima ação.
- Regra ASSISTIDA com executor disponível pode ser promovida explicitamente para AUTOMATICA após revisão do diagnóstico.
- Mantidas as barreiras de idempotência, continuidade, Redmine pendente e histórico operacional existentes.
- Diagnóstico é somente leitura: não envia e-mail, não altera Redmine e não muda autorização sozinho.
