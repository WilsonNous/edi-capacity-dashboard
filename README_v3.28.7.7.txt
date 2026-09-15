EDNNA v3.28.7.7 — Upload resiliente de evidências
- POST /uploads.json: 3 tentativas, backoff 0/2/5s.
- PUT de vínculo do anexo: 3 tentativas reutilizando o mesmo token no ciclo.
- Retry para ConnectTimeout, ReadTimeout, ConnectionError e HTTP 5xx.
- evidencia_anexada só é marcada após upload + vínculo concluídos.
