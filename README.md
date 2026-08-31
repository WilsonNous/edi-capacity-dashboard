# EDI — Painel de Capacidade e Atendimento

Painel operacional desenvolvido para acompanhamento dos chamados do EDI, consolidando informações do Redmine em uma visão simples e interativa.

A solução permite acompanhar backlog, responsáveis, prioridades, tempo em aberto, clientes, origens e demais indicadores utilizados na operação da equipe.

## Fonte de dados

O painel possui duas formas de carregamento:

### API Redmine — principal

Os chamados em aberto são consultados diretamente pela API do Redmine.

A integração utiliza variáveis de ambiente para autenticação e configuração dos projetos:

```text
REDMINE_URL
REDMINE_API_KEY
REDMINE_AUTHORIZATION
REDMINE_PROJECT_IDS
```

Os campos personalizados do Redmine também são consultados para tradução automática de informações como:

- Clientes
- Origem

Dessa forma, códigos internos do Redmine são apresentados no painel com seus respectivos nomes.

### CSV — contingência

Também é possível carregar manualmente um CSV exportado do Redmine.

O CSV funciona como alternativa caso a API esteja indisponível ou para análises específicas.

Também pode ser utilizado um arquivo:

```text
issues.csv
```

no mesmo diretório do `app.py`.

## Executar localmente

Utilizando o ambiente virtual do projeto, execute:

```bat
python -m streamlit run app.py
```

O Streamlit iniciará o painel e informará o endereço local para acesso pelo navegador.

## Funcionalidades

O painel possui filtros permanentes e diferentes visões operacionais.

Entre os principais recursos estão:

- quantidade de chamados em aberto;
- chamados em atuação do EDI;
- chamados aguardando terceiros;
- chamados com mais de 30 dias;
- chamados de prioridade Alta/Urgente;
- chamados com prazo vencido;
- filtros por responsável;
- filtros por estado;
- filtros por prioridade;
- filtros por tipo;
- filtros por projeto;
- filtros por cliente;
- análise por tempo em aberto;
- ranking de clientes;
- identificação da origem dos chamados;
- acesso direto ao chamado no Redmine pelo número do ticket.

## Gráficos interativos

Os gráficos permitem selecionar informações e visualizar os chamados que compõem aquele indicador.

A interação está disponível em análises como:

- situação dos chamados;
- responsável;
- mês de origem;
- tempo em aberto;
- tipo de demanda;
- prioridade;
- clientes.

Ao selecionar uma informação no gráfico, o painel apresenta os chamados correspondentes, mantendo o número do ticket como link para abertura direta no Redmine.

## Desempenho

A integração com o Redmine utiliza cache para reduzir consultas desnecessárias.

A versão atual também utiliza:

- reaproveitamento de conexões HTTP;
- consultas paralelas aos projetos;
- paginação paralela da API;
- cache dos campos personalizados;
- carregamento de detalhes individuais somente quando necessário.

O painel possui diagnóstico da carga da API, permitindo acompanhar tempos como:

```text
Listagem Redmine
Detalhes individuais
Catálogo Clientes/Origem
Montagem do DataFrame
Backend total
```

Isso facilita a identificação de gargalos entre Redmine, processamento e painel.

## Aparência

A interface utiliza uma paleta inspirada no Facebook/Meta:

- Azul principal: `#1877F2`
- Fundo: `#F0F2F5`
- Cartões: `#FFFFFF`
- Texto: `#1C1E21`

A navegação foi construída para manter filtros permanentemente disponíveis e facilitar o uso diário pela equipe.

## Estrutura principal

```text
app.py
redmine_api.py
requirements.txt
.streamlit/
    config.toml
```

### app.py

Responsável pela interface Streamlit, filtros, indicadores, gráficos, tabelas e interação com o usuário.

### redmine_api.py

Responsável pela comunicação com o Redmine, autenticação, paginação, campos personalizados, tradução de Clientes/Origem e otimizações das consultas.

### requirements.txt

Principais dependências:

```text
streamlit
pandas
plotly
requests
```

## Publicação

O painel está preparado para publicação no Azure App Service utilizando GitHub Actions.

Comando de inicialização utilizado no ambiente Azure:

```bash
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0
```

As credenciais e configurações do Redmine devem permanecer nas variáveis de ambiente do Azure e nunca diretamente no código-fonte.

## Versão atual

**V3.5.4 — Performance**

Principais evoluções:

- integração direta com a API Redmine;
- CSV mantido como contingência;
- tradução automática de Clientes e Origem;
- gráficos interativos com detalhamento dos chamados;
- links diretos para tickets do Redmine;
- cache de consultas;
- reutilização de conexões HTTP;
- consultas paralelas por projeto;
- paginação paralela;
- diagnóstico de desempenho da carga.

---

**Netunna — EDI**  
Painel de Capacidade e Atendimento
