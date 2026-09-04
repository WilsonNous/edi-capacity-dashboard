# EDI Capacity Dashboard — v3.12.1

Patch de estabilização baseado no ZIP efetivamente publicado.

## Ajustes

1. Validação explícita dos imports da EDNNA no GitHub Actions.
   Isso impede deploy se `app.py` importar uma função inexistente.

2. Circuit breaker para `custom_fields.json`.
   Se a carga de chamados já caiu para `painel_sqlite_contingencia`,
   o app não tenta novamente acessar o Redmine apenas para buscar catálogos.

3. Persistência dos catálogos Clientes/Origem no `painel.db`.
   Quando o Redmine estiver disponível, a cópia é atualizada.
   Em contingência, a última cópia válida é reutilizada.

## Resultado esperado em indisponibilidade

[PAINEL] Redmine indisponível | usando snapshot SQLite antigo
[REDMINE] Circuit breaker ativo | custom_fields.json não consultado
[EDNNA] Snapshot SQLite ...
[EDNNA] Classificação de demandas ...

A v3.12.1 não altera a política de execução da EDNNA:
todas as automações continuam em modo OBSERVAÇÃO.
