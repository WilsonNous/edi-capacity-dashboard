# EDI Capacity Dashboard — v3.9.0 CONSOLIDADA

Este pacote foi gerado sobre o ZIP atual do repositório enviado pelo usuário.

## IMPORTANTE

Não aplique os pacotes antigos v3.8 ou v3.9 por cima deste.

Esta pasta já contém a versão consolidada.

## O que entra nesta versão

### Painel
- SQLite persistente próprio: `painel.db`
- TTL padrão: 10 minutos
- filtros, abas, gráficos e pesquisas trabalham sobre dados já carregados
- Redmine é consultado somente quando o snapshot vence
- se o Redmine falhar, o último snapshot válido continua atendendo o painel

### EDNNA
- SQLite persistente próprio: `ednna.db`
- snapshot dos chamados
- journals persistidos
- análise de primeiro combate
- botão `Analisar próximos 5`
- reanálise somente quando o campo `Alterado` do chamado mudou
- nenhuma escrita automática no Redmine

### Identidade
- `assets/ednna_avatar.png`

## Arquitetura

```text
REDMINE
   |
   v
/home/data/painel.db
   |
   +--> Dashboard / filtros / gráficos
   |
   v
/home/data/ednna.db
   |
   +--> Journals / Primeiro Combate / memória EDNNA
```

## Variáveis Azure

Manter:

```text
EDNNA_DB_PATH=/home/data/ednna.db
```

Adicionar:

```text
PAINEL_DB_PATH=/home/data/painel.db
PAINEL_CACHE_TTL_SECONDS=600
EDNNA_SYNC_BATCH_SIZE=5
```

Recomendado cadastrar os analistas EDI exatamente como aparecem no Redmine:

```text
EDNNA_AUTORES_EDI=Wilson Martins,Nome 2,Nome 3
```

## Upload pelo GitHub Web

1. Extraia o ZIP no HD.
2. Abra o repositório no GitHub.
3. Use `Add file` -> `Upload files`.
4. Suba os arquivos/pastas desta versão de uma vez.
5. Faça UM ÚNICO commit.
6. Aguarde o deploy terminar completamente antes de testar.

## Logs esperados

Primeira carga:

```text
[PAINEL] SQLite inicializado | arquivo=/home/data/painel.db
[PAINEL] Sem snapshot SQLite | carga inicial pelo Redmine
[PAINEL] Snapshot SQLite atualizado | chamados=...
```

Durante navegação:

```text
[PAINEL] Snapshot SQLite HIT | chamados=... | idade=...s | ttl=600s
```

Após 10 minutos:

```text
[PAINEL] Snapshot expirado | ... | atualizando pelo Redmine
```

Contingência:

```text
[PAINEL] Redmine indisponível | usando snapshot SQLite antigo
```

EDNNA:

```text
[EDNNA] Journals | chamado=... | consultando Redmine
[EDNNA] Journals OK | chamado=... | journals=... | situacao=...
```

## Validação realizada no pacote

Todos os arquivos `.py` foram compilados com `py_compile`.
Também foi validado que os imports locais existem no pacote.
