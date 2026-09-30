# EDNNA 3.34.8

- Checkpoint humano aceita anexos e os vincula ao mesmo journal no Redmine.
- SAFRAPAY/TERMO exige anexo para conclusão; ao registrar, muda para Aguardando Retorno Cliente e garante datas/prazo.
- Registro de checkpoint passou a ser idempotente por marcador para evitar journals duplicados inclusive após timeout/retry.
- Primeiro follow-up passa a ser explicitamente 48 horas em todas as regras declarativas; overrides 0 são normalizados para 48h.
- Central de Regras deixa de apresentar 0 como opção/default para primeiro follow-up.
