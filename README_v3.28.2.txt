EDNNA v3.28.2 — Otimização Multiusuário

Arquivos alterados:
- redmine_api.py
- ednna/contexto_relacionamentos.py
- ednna/email_sender.py

Ajustes:
1. custom_fields compartilhado via painel.db, com TTL persistente de 24h por padrão.
2. Evita repetição de custom_fields quando circuit breaker está aberto.
3. Lock compartilhado por chamado para contexto histórico; sessões simultâneas não consultam o mesmo issue.
4. Em falha do Redmine, contexto histórico usa última cópia SQLite disponível, inclusive expirada, como contingência.
5. Microsoft Graph: remove combinação $filter + $orderby que gerava InefficientFilter; filtra conversationId/data localmente em janela recente da Inbox.

Variáveis opcionais:
REDMINE_CUSTOM_FIELDS_TTL=3600
REDMINE_CUSTOM_FIELDS_PERSIST_TTL=86400

O snapshot principal continua com PAINEL_CACHE_TTL_SECONDS=600, portanto a lista de chamados segue atualizando a cada 10 minutos por padrão, coordenada por lock global.
