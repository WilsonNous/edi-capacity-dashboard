# EDI Capacity Dashboard — v3.11.0

## EDNNA — Classificador de Demandas e Catálogo de Regras

Esta versão consolida a v3.10 e adiciona a camada que transforma
a fila de primeiro combate em oportunidades concretas de automação.

### Correção incremental

O campo `Alterado` agora é normalizado antes de ser comparado.

Isso evita que o mesmo instante seja tratado como diferente apenas
por mudança de representação de data/hora.

A mesma normalização é utilizada para:
- snapshot da EDNNA;
- decisão de reconsultar journals;
- decisão de reclassificar a demanda.

### Classificação de demandas

Novo módulo:

```text
ednna/classificador_demandas.py
```

Intenções iniciais:

```text
RELACIONAMENTO_CREDENCIAMENTO
INCLUSAO_ESTABELECIMENTO
FALTA_ARQUIVO
REPROCESSAMENTO
ALTERACAO_CADASTRAL
DUVIDA_ORIENTACAO
NAO_CLASSIFICADO
```

A classificação usa inicialmente:
- Assunto
- Descrição
- Tipo
- Origem
- Cliente

Ela grava no SQLite:
- intenção
- confiança
- regra candidata
- ação sugerida
- evidências
- versão temporal pelo campo Alterado

### Catálogo de regras

Arquivo:

```text
ednna/catalogo_automacoes.json
```

Regras candidatas iniciais:

```text
REL-001
EST-001
FALTA-001
REP-001
CAD-001
ORI-001
```

Todas começam com:

```text
executavel = false
homologada = false
modo = OBSERVACAO
```

Portanto a v3.11 NÃO envia e-mail, NÃO altera chamado,
NÃO muda status e NÃO executa scripts.

### Nova visão no painel

A Central EDNNA ganha:

```text
Demandas e automação
```

com:
- distribuição das intenções;
- quantos padrões foram reconhecidos;
- quantos continuam não classificados;
- chamados agrupados por oportunidade;
- confiança;
- regra candidata;
- ação sugerida;
- catálogo das regras.

## Próximo passo

Depois de observar a distribuição real, escolheremos uma regra candidata,
validaremos seus pré-requisitos e só então poderemos marcar uma regra como
homologada para construir um executor controlado.
