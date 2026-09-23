# EDNNA 3.28.57

- SENFF passa a possuir workflow de inclusão por e-mail com executor Graph.
- Central de Regras permite autorizar regra homologada em modo ASSISTIDA ou AUTOMATICA quando o executor estiver implementado.
- Motor de inclusões reconhece ambos os modos como autorizados.
- Executor automático respeita autorização AUTOMATICA explícita; mantém compatibilidade com promoção por histórico confirmado para regras ASSISTIDAS.
- Regras sem executor implementado continuam protegidas e não podem ser autorizadas para execução.
- Mantidas as travas de atuação anterior, estado transacional, histórico, destinatário e dados obrigatórios.
