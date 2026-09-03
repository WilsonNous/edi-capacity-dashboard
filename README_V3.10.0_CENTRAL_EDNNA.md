# EDI Capacity Dashboard — v3.10.0 Central Operacional EDNNA

Esta versão foi construída sobre a v3.9.0 consolidada.

## Principais mudanças

### Catálogo automático da equipe EDI

A EDNNA não precisa mais assumir que qualquer autor humano é EDI.

Ela cria o catálogo a partir de todos os nomes encontrados em:

```text
Atribuído a
```

no snapshot completo do dashboard.

A variável `EDNNA_AUTORES_EDI` passa a ser apenas complementar para nomes históricos.

### Classificação conservadora

- `JA_ATUADO`: atuação comprovada de integrante reconhecido como EDI
- `AGUARDANDO_PRIMEIRO_COMBATE`: nenhuma atuação EDI identificada
- `REVISAO_NECESSARIA`: comentário/alteração relevante de autor desconhecido
- `NAO_ANALISADO`: ainda não passou pela EDNNA
- `ERRO_ANALISE`: erro técnico durante a análise

### Fila completa

Novo botão:

```text
🤖 Analisar fila completa
```

A EDNNA processa todos os pendentes de forma sequencial.

Não há paralelismo contra o Redmine.

Proteções:

```text
EDNNA_SYNC_INTERVAL_SECONDS=0.10
EDNNA_MAX_ERROS_CONSECUTIVOS=3
```

Se houver três erros consecutivos, a execução é interrompida.

### Análise incremental

Chamados já analisados não são consultados novamente enquanto o campo `Alterado` permanecer igual.

### Central Operacional

A aba EDNNA agora possui:

- Visão EDNNA
- Primeiro combate
- Já atuados
- Revisão
- Equipe EDI

Além de gráficos, prioridades e identidade visual da EDNNA.

## Variáveis Azure

Manter:

```text
EDNNA_DB_PATH=/home/data/ednna.db
PAINEL_DB_PATH=/home/data/painel.db
PAINEL_CACHE_TTL_SECONDS=600
```

Recomendado:

```text
EDNNA_SYNC_INTERVAL_SECONDS=0.10
EDNNA_MAX_ERROS_CONSECUTIVOS=3
```

Opcional:

```text
EDNNA_AUTORES_EDI=Nome Histórico 1,Nome Histórico 2
```

## Implantação

Suba esta versão inteira em um único commit.

Não aplique patches de versões anteriores.
