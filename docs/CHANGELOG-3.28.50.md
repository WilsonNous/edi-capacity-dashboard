# EDNNA v3.28.50

## Executor transacional

- `enviado_em` e o estado `AGUARDANDO_RESPOSTA` deixam de ser tratados isoladamente como prova de envio.
- Nova coluna SQLite `envio_confirmado`, criada automaticamente no primeiro uso.
- `envio_confirmado=1` só é persistido depois que o Microsoft Graph aceita o envio.
- IDs reais do Graph continuam sendo aceitos como evidência para registros anteriores.
- Estados legados inconsistentes sem prova Graph são recuperados automaticamente e liberados para nova execução.
- A trava de idempotência continua ativa quando há prova positiva de envio.
- Logs informam se o bloqueio ocorreu por `ENVIO_CONFIRMADO` ou `GRAPH_ID`.

## Objetivo

Eliminar o falso `EMAIL_JA_ENVIADO` observado na operação assistida sem remover a proteção contra envio duplicado.
