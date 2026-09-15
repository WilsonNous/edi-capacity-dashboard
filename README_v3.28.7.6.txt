EDNNA v3.28.7.6 — Evidência documental de retorno

- Preserva a resposta útil da adquirente na nota do Redmine.
- Baixa a mensagem original via Microsoft Graph /messages/{id}/$value.
- Anexa o e-mail original em formato .eml ao chamado Redmine.
- Persiste evidencia_anexada_em, evidencia_filename e evidencia_erro no SQLite.
- Faz reconciliação retroativa dos retornos GETNET já processados (ex.: #30846 e #48567).
- Não altera a lógica multipayer: GETNET concluída não encerra o chamado enquanto existirem outras etapas externas.
- Logs: [EDNNA] Evidência Redmine | ... e [EDNNA] Evidência auditoria | ...
