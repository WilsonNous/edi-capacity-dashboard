v3.28.16 — Extrator de Procedimento Operacional

- Decompõe históricos de inclusão em solicitação, destinatários/CC, assunto, ações e evidências de conclusão.
- Confirma destinatário somente quando recorrente em pelo menos dois históricos.
- Compara ações normalizadas para encontrar procedimento recorrente mesmo com dados variáveis.
- Adiciona auditoria recolhível “Ver como a EDNNA chegou a esta conclusão”.
- Mantém execução bloqueada: somente investigação/aprendizado.
- Preserva SQLite-first/stale-while-revalidate da v3.28.15.
