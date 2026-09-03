# EDNNA no Dashboard EDI

Arquivos desta primeira etapa:

- `app.py`: dashboard atualizado com a aba **🤖 EDNNA**
- `ednna/__init__.py`: pacote Python
- `ednna/primeiro_combate.py`: filtro inicial da fila de chamados em estado `Aberto`

## Estrutura

```text
seu_projeto/
├── app.py
├── redmine_api.py
└── ednna/
    ├── __init__.py
    └── primeiro_combate.py
```

O `redmine_api.py` atual permanece sem alterações.

## Execução

```bash
python -m streamlit run app.py
```

## Escopo desta versão

A EDNNA está em modo de observação.

Ela:
- usa o DataFrame já carregado pelo dashboard;
- identifica apenas chamados cujo Estado real é `Aberto`;
- apresenta KPIs e uma fila de primeiro combate;
- não consulta journals;
- não envia e-mails;
- não altera chamados no Redmine.

A próxima etapa é analisar journals para distinguir chamados realmente sem primeira atuação.
