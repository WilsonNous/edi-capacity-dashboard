# EDDY — Resiliência a ConnectTimeout intermitente (28/10/2026)

## Evidência

Teste no container Azure: DNS `chamados.nteia.com` resolveu para `186.250.186.109`; Microsoft e Google conectaram em TCP/443. Em dez tentativas contra Redmine, cinco abriram TCP e receberam HTTP 401 sem autenticação, e cinco expiraram em TCP (timeout 5 s). IP de saída observado: `4.174.197.221`. Isso demonstra intermitência de conexão, não falha comprovada de DNS ou da API de aplicação. O IP de saída observado não representa necessariamente todos os IPs possíveis do App Service.

## Implementação desta PR

- As listagens completas remotas realizadas por VR01 e pelo sincronizador MySQL passam por um lock interprocesso compartilhado em `/home/data/eddy_redmine_inventory.json.listing.lock`. Assim esses dois workers não iniciam simultaneamente uma listagem completa.
- O cache confirmado de até 90 segundos continua **exclusivamente observacional** no fluxo MySQL. A VR01 continua exigindo sua própria listagem remota confirmada; nenhum snapshot antigo vira autorização.
- A biblioteca `redmine_api.py` **já possui** `requests.Session`, pool HTTP, semáforo por processo, retries 0/2/5 s, diagnósticos de ConnectTimeout e circuit breaker. Esta PR os preserva, sem introduzir tentativas adicionais que possam pressionar o servidor.
- O painel Streamlit mantém seu lock próprio: **não está coberto** pelo novo lock interprocesso dos dois workers. Não alegar serialização global de todas as consultas.
- Nenhuma alteração no Redmine externo; nenhuma liberação de email, execução operacional ou escrita Redmine.

## Validação Azure após merge e implantação

1. Confirmar a revisão efetivamente implantada no Azure; merge no GitHub não comprova deploy.
2. Observar pelo menos três ciclos VR01, incluindo recuperação após ConnectTimeout, e comparar horários das listagens MySQL/VR01.
3. Verificar `envios_realizados=0`, `redmine_escritas=0` e bloqueio quando `LISTAGEM_NAO_CONFIRMADA`.
4. Para homologação, usar `EDDY_VR01_INTERVAL_SECONDS=300` e `EDDY_MYSQL_SYNC_INTERVAL_SECONDS=900`; restaurar 900 para VR01 após os testes.
5. Aferir p95 de conexão, duração da listagem e contagem de timeouts. A correção reduz concorrência entre workers, mas não garante eliminar perda de TCP no caminho.

## Limites e evolução

O lock de arquivo só coordena processos que compartilham o mesmo volume e caminho; instâncias Azure com volumes distintos não ficam coordenadas por ele. A próxima etapa, se necessário e medida, é um mecanismo distribuído de coordenação/observabilidade para **todas** as leituras, incluindo o painel. Não remover as regras de frescor, journals, autorização explícita e fail-closed.
