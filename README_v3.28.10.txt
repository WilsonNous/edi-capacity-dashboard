EDNNA v3.28.10 — Resiliência de Investigação

Alterações principais:
1. Versionamento centralizado em version.py (APP_VERSION / APP_RELEASE).
2. Rodapé passa a consumir a versão central, evitando divergência visual.
3. Consultas pontuais de contexto (ex.: Investigar inclusão) podem consultar
   issues/<id>.json mesmo quando o circuit breaker da listagem massiva está ativo.
4. Falha de uma consulta pontual não abre, fecha ou interfere no circuit breaker
   global usado para proteger cargas amplas do Redmine.
5. O cache histórico SQLite continua sendo usado antes da rede e como fallback.

Objetivo do teste:
Central de Descoberta -> #48318 REDE SANTA LUCIA / VALECARD -> Investigar inclusão.
No log, com breaker global ativo, deve aparecer:
[REDMINE] Consulta pontual autorizada apesar do circuit breaker | issues/48318.json
