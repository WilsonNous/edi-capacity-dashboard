# VR01 — piloto controlado

Pré-requisitos: esquema MySQL de snapshots existente e migração `migrations/eddy_vr01_decisoes.sql` aplicada manualmente e validada.

Com snapshot previamente importado:
```bash
python -m scripts.eddy_vr01_controlled_pilot
```

Para importar explicitamente journals do Redmine (somente GET) e auditar:
```bash
python -m scripts.eddy_vr01_controlled_pilot --importar-redmine
```

A execução está limitada a #49227 e #49289. Nenhum envio de e-mail, mudança no Redmine, liberação BAT ou operação externa é implementado.

Validar os hashes e registros no MySQL, reexecutar para conferir idempotência, verificar CI e logs Azure. **A presença deste script na main não constitui homologação nem comprova que houve execução no Azure.**
