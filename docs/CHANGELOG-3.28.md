
## 3.28.25 — Aprendizado sincronizado com enriquecimento
- Fontes locais vencidas passam a gerar estado transitório `AGUARDANDO_ENRIQUECIMENTO`.
- O worker reprocessa automaticamente regras aguardando enriquecimento após atualizar o contexto.
- Lote de enriquecimento ampliado de 3 para 12 chamados por ciclo para acelerar a convergência.
- O teste em lote apresenta regras aguardando enriquecimento dentro de “Em aprendizado”.
- Nenhuma regra é homologada ou executada enquanto houver fontes parciais.

## 3.28.23 — Fila Acionável de Revisão e Homologação

- A fila persistente de regras deixa de ser apenas informativa e passa a oferecer revisão operacional diretamente no ponto de trabalho.
- Regras `PRONTA_PARA_REVISAO` e `REVISADA` ganham painel individual com completude, destinatários aprendidos, constantes, variáveis e fontes.
- Novo botão **Revisar e homologar** executa em sequência a confirmação humana e a homologação da regra.
- O operador pode corrigir/completar o destinatário antes da homologação, permitindo fechar regras cujo único bloqueio seja informação objetiva ausente.
- Regras homologadas saem automaticamente da fila de revisão e permanecem no patrimônio operacional.
- A homologação continua segura: não envia e-mail, não altera Redmine e não libera execução externa automaticamente.
- Mantida a tela detalhada de investigação como camada técnica para aprofundamento e auditoria.

Objetivo: fechar o ciclo descobrir → aprender → revisar → homologar com uma ação operacional simples, preparando a futura camada de UX executivo da EDNNA.



## 3.28.22 — Patrimônio de Regras e Homologação em Lote

- Testar todos passa a preservar players que já possuem regra homologada, sem reaprender do zero.
- Nova fila operacional persistente de regras de inclusão: HOMOLOGADA, PRONTA_PARA_REVISAO e APRENDIZADO_INCOMPLETO.
- Métrica A homologar desconta players já homologados.
- Regras homologadas tornam-se patrimônio operacional consultável da EDNNA.
- Mantida a separação de segurança: homologar não envia e-mail e não altera o Redmine.
- A execução externa das regras de inclusão permanece bloqueada nesta versão.

Objetivo: permitir homologação progressiva durante a operação, deixando a EDNNA testar em lote apenas o que ainda precisa aprender/revisar.
# EDNNA / EDI Capacity Dashboard — Histórico da linha 3.28

## 3.28.21 — Memória Local e Revisão Assistida

- Contexto histórico passa a operar em estratégia **local-first**: cache persistido válido é usado imediatamente e cache vencido também pode atender a interface sem bloquear a navegação.
- Quando a cópia local está vencida, a EDNNA agenda enriquecimento assíncrono em `contexto_enriquecimento_pendente`; o Redmine deixa de ser dependência síncrona quando já existe memória local.
- A consulta direta ao Redmine permanece para primeiro carregamento sem memória e para atualização explícita (`force=True`).
- Mantido o reprocessamento automático de aprendizados incompletos depois que o worker enriquece as fontes pendentes.
- Nova persistência `revisoes_regras_operacionais` separa aprendizado, revisão humana e homologação.
- Central de Descoberta ganha **Revisão assistida**, permitindo confirmar destinatário e registrar observações do operador.
- Nova ação **Homologar regra** só é habilitada depois da revisão humana registrada.
- Homologação não envia e-mail, não altera Redmine e não torna a nova regra executável automaticamente nesta versão.
- Fluxo formal da inclusão passa a ser: descobrir → aprender → revisar → homologar → futura liberação de execução.

## 3.28.20 — Investigação e Aprendizado em Um Clique

- `Investigar inclusão` agora executa o ciclo completo de descoberta técnica: reconstrução de contexto, montagem do corpus, aprendizado e diagnóstico da regra candidata.
- Removido o botão separado `Aprender procedimento` da Central de Descoberta.
- Novo botão `Testar todos` avalia um caso representativo de cada player descoberto e usa o histórico elegível para aprender sua regra.
- Resultado em lote apresenta players testados, regras prontas para revisão, aprendizados incompletos e erros, com detalhamento por player.
- O teste em lote não homologa regras, não envia e-mails e não altera o Redmine.
- O antigo laboratório manual de inclusão passa a orientar o operador para a Central de Descoberta, evitando dois fluxos concorrentes de aprendizado.
- Mantida a barreira humana: `PRONTA_PARA_REVISAO` continua sendo apenas candidata; homologação e execução permanecem bloqueadas nesta versão.
- Documentação da v3.28.7.1 consolidada neste changelog; removido o README de versão isolado do diretório `ednna/`.

## 3.28.19 — Corpus Operacional Unificado

- Unifica a leitura de threads do caso atual, históricos e fontes complementares em um corpus operacional auditável.
- Marca explicitamente o chamado atual como `CASO_ANCORA`, preservando históricos como `HISTORICO` e demais fontes como `CONTEXTO_COMPLEMENTAR`.
- Classifica participantes de e-mail entre `INTERNO_NETUNNA` e `EXTERNO_PLAYER`.
- Separa destinatários externos confirmados do player dos participantes internos, evitando tratar `@netunna.com.br` como canal do player.
- Mantém métricas distintas para evidência histórica e evidência do caso-âncora.
- O caso-âncora pode completar a compreensão operacional, mas continua sem substituir a recorrência histórica exigida para homologação.
- Central de Descoberta passa a exibir evidência histórica, caso-âncora, participantes e destinatários do corpus.
- Novos logs `Corpus operacional` e `Evidência separada` facilitam validação de players como VALECARD e SENFF.
- Nenhuma nova regra é automaticamente homologada ou executada por esta versão.

Este documento consolida as notas de versão que antes ficavam espalhadas no diretório raiz. A partir da v3.28.18, novas notas da família 3.28 devem ser adicionadas aqui.

## 3.28.18 — Thread Operacional e Caso-Âncora

- Extrator de threads encadeadas de e-mail em descrição e journals do Redmine.
- Estados operacionais: `SOLICITADO`, `EM_TRATATIVA` e `CONCLUIDO`.
- Extração de protocolo e prazo em horas.
- Confirmação operacional do destinatário quando o mesmo endereço externo recebe a solicitação e responde na thread.
- Caso atual pode servir como caso-âncora completo sem, sozinho, homologar recorrência histórica.
- Homologação continua exigindo evidência recorrente em inclusões históricas.
- Documentação de versões consolidada em `docs/`.


---

## Documento legado: `README_v3.28.txt`


EDNNA v3.28 — GETNET + Responsabilidade Operacional + Retornos Inteligentes

Arquivos alterados: 8
- ednna/planejador_cancelamentos.py
- ednna/motor_acoes.py
- ednna/acompanhamento_acoes.py
- ednna/redmine_writer.py
- ednna/email_sender.py
- ednna/monitor_respostas.py
- ednna/executor_automatico.py
- ui/ednna_workspace.py

Azure App Settings:
REDMINE_EDNNA_USER_ID=166
REDMINE_EDNNA_USERNAME=ednna.ia

Principais mudanças:
1. GETNET: texto contaminante descartado, CNPJ separado de EC, ECs deduplicados.
2. Cancelamento TOTAL GETNET aceita múltiplos ECs e inclui todos no rascunho.
3. Segunda barreira impede rascunho/envio GETNET sem EC.
4. Chamados conduzidos pela EDNNA são atribuídos ao usuário Redmine configurado.
5. Responsável anterior é preservado no ednna.db para governança futura.
6. Monitor de respostas tem fallback por #chamado, tolerando RE:/[EXT].
7. Retorno GETNET pedindo CNPJ/EC é registrado e a EDNNA busca dados no chamado/histórico.
8. Complementação permanece sujeita a revisão humana; não há resposta automática de cancelamento.



---

## Documento legado: `README_v3.28.9.txt`


EDNNA v3.28.9 — Central de Descoberta de Inclusões

- A Central passa a inventariar TODOS os chamados de inclusão presentes no snapshot aberto, mesmo sem regra homologada e sem atribuição à EDNNA.
- Agrupa candidatos por player e mantém links de chamados para o Redmine.
- Investigação sob demanda reconstrói BP, Abertura de Relacionamento, inclusões anteriores e evidências.
- Amplia aliases: CIELO, ONECARD, WIZEO, SODEXO/PLUXEE, ALELO, TICKET e VR BENEFICIOS, além dos players já existentes.
- Descoberta e homologação ficam separadas. Nenhuma nova regra de inclusão é executável automaticamente.
- Evita consultas em massa ao histórico: Redmine detalhado só é consultado quando o operador clica em Investigar inclusão.



---

## Documento legado: `README_v3.28.8.txt`


EDNNA v3.28.8 — Laboratório de Inclusões

- Novo planejador de inclusões em modo SOMENTE LEITURA.
- Reconstrói BP/Novo Cliente, Abertura de Relacionamento e inclusões anteriores relacionadas.
- Gera regra candidata por player, sem homologar ou executar automaticamente.
- Extrai evidências de procedimento: e-mails, CNPJs e ECs explicitamente rotulados.
- Adicionados aliases iniciais: VALECARD, TRUCKPAG, POLICARD, GREENCARD, TICKETLOG e VEROCHEQUE.
- Central de Atuação ganha botão “Aprender procedimento de inclusão”.
- Chamados e fontes permanecem clicáveis para o Redmine.
- Segurança: nenhuma ação externa é liberada pela regra candidata.



---

## Documento legado: `README_v3.28.7.txt`


EDNNA v3.28.7 — Memória Operacional e Reconciliação de Retornos

Objetivos
1. Reduzir a pressão sobre o Redmine durante a reconstrução de contexto histórico.
2. Recuperar automaticamente cancelamentos GETNET cujo e-mail foi enviado, mas que ficaram fora de acoes_operacionais/monitoramento.
3. Permitir que respostas já existentes na Inbox, como o retorno do #48567 MAIS CAMPUS, voltem ao fluxo normal da EDNNA e atualizem o Redmine.

Alterações
- contexto_relacionamentos.py
  * cache de chamados abertos: 120 minutos
  * cache de histórico concluído: 7 dias
  * mantém fallback stale e circuit breaker já existentes
- orquestrador_cancelamentos.py
  * nova listagem global de etapas GETNET enviadas/aguardando retorno
- email_sender.py
  * nova busca de mensagem enviada pelo #ID do chamado na pasta Sent Items
- monitor_respostas.py
  * reconciliação antes de cada ciclo normal
  * se uma etapa GETNET está aguardando e não existe acompanhamento local, localiza o envio e reconstrói a ação
  * em seguida o mesmo ciclo localiza a resposta, interpreta GETNET e registra no Redmine
  * confirmação GETNET encerra somente a etapa GETNET; demais players mantêm o chamado com a EDNNA
- app.py
  * identificação da versão atualizada

Validação esperada para #48567
No primeiro ciclo após o deploy, caso a etapa GETNET esteja AGUARDANDO_RESPOSTA no orquestrador, espera-se log semelhante a:
[EDNNA] Monitor e-mail | reconciliação | chamado=48567 | acompanhamento reconstruído
[EDNNA] Monitor e-mail | reconciliação | chamado=48567 | resposta já localizada
[EDNNA] Monitor e-mail | resposta recebida | chamado=48567 | regra=CANCELAMENTO-GETNET-001 | de=...

O Redmine deve receber somente o conteúdo novo da resposta da GETNET, manter Estado=Em andamento e manter a EDNNA como responsável enquanto houver outras etapas externas pendentes.



---

## Documento legado: `README_v3.28.7.7.txt`


EDNNA v3.28.7.7 — Upload resiliente de evidências
- POST /uploads.json: 3 tentativas, backoff 0/2/5s.
- PUT de vínculo do anexo: 3 tentativas reutilizando o mesmo token no ciclo.
- Retry para ConnectTimeout, ReadTimeout, ConnectionError e HTTP 5xx.
- evidencia_anexada só é marcada após upload + vínculo concluídos.



---

## Documento legado: `README_v3.28.7.6.txt`


EDNNA v3.28.7.6 — Evidência documental de retorno

- Preserva a resposta útil da adquirente na nota do Redmine.
- Baixa a mensagem original via Microsoft Graph /messages/{id}/$value.
- Anexa o e-mail original em formato .eml ao chamado Redmine.
- Persiste evidencia_anexada_em, evidencia_filename e evidencia_erro no SQLite.
- Faz reconciliação retroativa dos retornos GETNET já processados (ex.: #30846 e #48567).
- Não altera a lógica multipayer: GETNET concluída não encerra o chamado enquanto existirem outras etapas externas.
- Logs: [EDNNA] Evidência Redmine | ... e [EDNNA] Evidência auditoria | ...



---

## Documento legado: `README_v3.28.7.5.txt`


EDNNA v3.28.7.5 — Auditoria de Conclusão / Autorreparo

- Audita ações GETNET marcadas RESPOSTA_RECEBIDA contra o histórico real do Redmine.
- Se a nota EDNNA de retorno não existir, converte somente a sincronização para RESPOSTA_PENDENTE_REDMINE.
- Reutiliza resposta já persistida; não reenvia e-mail e não reinterpreta a mensagem.
- Em seguida, a fila normal de pendências tenta reparar o Redmine no mesmo ciclo.
- Se o Redmine estiver indisponível, não altera o estado confirmado localmente por hipótese.
- Logs: confirmados_ids, reparo_pendente_ids, indisponiveis_ids.



---

## Documento legado: `README_v3.28.7.4.txt`


EDNNA v3.28.7.4 — Observabilidade da Reconciliação

Objetivo
- Não altera a lógica operacional da v3.28.7.3.
- Expõe no log os IDs dos chamados em cada estado da reconciliação GETNET.

Novos logs
- monitorando_ids=[...]
- processados_ids=[...]
- pendentes_redmine_ids=[...]
- presos_enviando_ids=[...]
- orfaos_reais_ids=[...]

Uso
O objetivo imediato é confirmar o estado real dos chamados #30846, #48561 e #48567 antes de qualquer nova alteração de processamento.

Deploy
Substituir ednna/monitor_respostas.py.
Os demais arquivos do pacote são mantidos para consistência com a v3.28.7.3.



---

## Documento legado: `README_v3.28.7.3.txt`


EDNNA v3.28.7.3 — Reconciliação Idempotente + Diagnóstico

Objetivo
- Fechar o ciclo de retorno de cancelamentos GETNET, especialmente #48567 MAIS CAMPUS.

Ajustes
1. RESPOSTA_RECEBIDA e RESPOSTA_PENDENTE_REDMINE não são mais contados como órfãos.
2. Registros presos em ENVIANDO são recuperados quando o envio real existe em Sent Items.
3. Sent Items é tratado como evidência de envio e fonte de reconstrução.
4. Logs detalhados mostram cada estágio: Sent Items, reconstrução, busca Inbox e resposta.
5. Busca direta de resposta por #chamado amplia a janela da Inbox para 500 mensagens.
6. Mantida fila resiliente de sincronização Redmine da v3.28.7.2.

Arquivos
- ednna/monitor_respostas.py
- ednna/email_sender.py
- ednna/acompanhamento_acoes.py

Validação
- py_compile executado com sucesso.

Log esperado para #48567
[EDNNA] Reconciliação | avaliando chamado=48567 | estado_sqlite=...
[EDNNA] Reconciliação | Sent Items HIT | chamado=48567 | ...
[EDNNA] Reconciliação | enviado localizado | chamado=48567
[EDNNA] Reconciliação | ENVIANDO recuperado ... (se estava preso em ENVIANDO)
[EDNNA] Reconciliação | buscando Inbox | chamado=48567 | ...
[EDNNA] Reconciliação | resposta localizada | chamado=48567 | ...



---

## Documento legado: `README_v3.28.7.2.txt`


EDNNA v3.28.7.2 — Reconciliação por E-mail + Fila Resiliente Redmine
Data: 15/09/2026

OBJETIVO
- Recuperar atuações GETNET a partir de Sent Items mesmo quando o snapshot Redmine estiver antigo/indisponível.
- Evitar que chamados já processados, como #30846, sejam processados novamente.
- Recuperar o legado #48567 MAIS CAMPUS pelo #ID presente no assunto do e-mail.
- Persistir a resposta da adquirente no SQLite antes de tentar atualizar o Redmine.
- Repetir a sincronização com o Redmine em ciclos posteriores sem reler/processar a mesma resposta.

ALTERAÇÕES
1. email_sender.py
   - listar_envios_cancelamento_getnet(): descobre envios GETNET/cancelamento em Sent Items e extrai #chamado.
   - Busca local, sem filtros complexos do Graph/InefficientFilter.

2. acompanhamento_acoes.py
   - confirmar_envio_real() aceita enviado_em_real para preservar a data real do envio reconstruído.
   - novo estado RESPOSTA_PENDENTE_REDMINE.
   - persistência e fila de respostas aguardando sincronização Redmine.

3. monitor_respostas.py
   - candidatos = orquestrador + snapshot + Sent Items.
   - idempotência por estado local.
   - resposta é salva antes do PUT/nota Redmine.
   - se Redmine falhar, a resposta permanece em fila e é sincronizada posteriormente.

LOGS ESPERADOS PARA #48567
[EDNNA] Reconciliação | enviados_descobertos=N | candidatos=N | ...
[EDNNA] Reconciliação | avaliando chamado=48567
[EDNNA] Reconciliação | enviado localizado | chamado=48567
[EDNNA] Reconciliação | acompanhamento reconstruído | chamado=48567
[EDNNA] Reconciliação | resposta localizada | chamado=48567
[EDNNA] Monitor e-mail | resposta recebida | chamado=48567 | regra=CANCELAMENTO-GETNET-001

SE REDMINE ESTIVER FORA
[EDNNA] Monitor e-mail | resposta preservada | chamado=48567 | Redmine pendente: ...
Em ciclo posterior:
[EDNNA] Redmine pendente | sincronizado | chamado=48567

DEPLOY
Substituir preservando os caminhos:
- ednna/monitor_respostas.py
- ednna/acompanhamento_acoes.py
- ednna/email_sender.py
- README_v3.28.7.2.txt



---

## Documento legado: `README_v3.28.6.txt`


EDNNA v3.28.6 — CENTRAL DE ATUAÇÃO E CONTEXTO OPERACIONAL

Objetivo
- Generalizar a antiga Central de Cancelamentos para Central de Atuação EDNNA.
- Manter chamados já assumidos pela EDNNA disponíveis para análise mesmo após saírem do primeiro combate.
- Usar BP/Novo Cliente como raiz histórica para reconstruir o contexto operacional.
- Reaproveitar a mesma inteligência para abertura, inclusão, alteração, falta de arquivo, cancelamento e futuras regras homologadas.

Arquitetura
Chamado atual -> relações diretas -> BP/Novo Cliente -> relações do BP -> linha do tempo por player.

Princípios
- BP é raiz histórica, não verdade absoluta atual.
- Eventos posteriores podem alterar o estado conhecido.
- Cada informação mantém a proveniência no chamado Redmine.
- Contexto é somente leitura; execução continua dependendo do catálogo homologado.
- Cancelamento mantém o orquestrador por player da v3.28.5.

Central de Atuação
A carteira é formada pela união de:
1. chamados atribuídos formalmente à EDNNA no snapshot global;
2. chamados presentes na inteligência/classificação EDNNA.

Isso mantém casos como MAIS CAMPUS #48567 acessíveis para contexto mesmo depois de a EDNNA assumir o chamado e alterar seu estado.

Arquivos alterados
- app.py
- ednna/contexto_relacionamentos.py
- ui/ednna_workspace.py
- README_v3.28.6.txt

Deploy
Substituir somente estes arquivos no repositório e realizar um único commit/deploy.



---

## Documento legado: `README_v3.28.5.txt`


EDNNA v3.28.5 — Orquestrador de Cancelamentos por Player

Objetivo
- Tratar cancelamentos totais como um conjunto de etapas independentes por player/adquirente.
- Manter a EDNNA responsável enquanto houver etapas externas pendentes.
- Devolver ao responsável humano original somente quando todas as etapas externas conhecidas estiverem concluídas.

Principais mudanças
1. Nova tabela SQLite cancelamento_etapas em ednna.db, uma linha por chamado + player.
2. O planejador sincroniza as etapas com o catálogo operacional. Uma nova regra de cancelamento homologada passa a ser reconhecida na próxima reconstrução do plano, sem regra fixa de sequência no orquestrador.
3. GETNET é a primeira etapa executável real. Após envio, a etapa fica AGUARDANDO_RESPOSTA.
4. Retorno GETNET com confirmação de desativação/cancelamento marca somente GETNET como CANCELAMENTO_CONFIRMADO.
5. Em cancelamento com outros players pendentes, o chamado continua atribuído à EDNNA e em Em andamento.
6. Se todas as etapas externas estiverem concluídas, o chamado volta ao responsável humano original preservado e permanece Em andamento para ações internas/físicas.
7. A Central de Cancelamentos mostra o progresso por player.

Segurança
- PROCEDIMENTO_NAO_HOMOLOGADO nunca é tratado como concluído.
- Não há fechamento automático do chamado.
- Novas adquirentes só se tornam executáveis quando houver regra homologada no catálogo e preparação operacional correspondente.
- O handoff usa somente o responsável original previamente preservado pela EDNNA.

Arquivos alterados
- app.py
- ednna/acompanhamento_acoes.py
- ednna/monitor_respostas.py
- ednna/planejador_cancelamentos.py
- ednna/redmine_writer.py
- ui/ednna_workspace.py

Arquivo novo
- ednna/orquestrador_cancelamentos.py



---

## Documento legado: `README_v3.28.4.txt`


EDNNA v3.28.4 — Navegação Redmine

Objetivo
- Padronizar a navegação para o Redmine: sempre que a interface exibir um número de chamado operacional, oferecer acesso clicável ao chamado.
- Atualizar a identificação visual da versão no rodapé.

Arquivos alterados
- app.py
- ui/ednna_workspace.py

Principais ajustes
1. Carteira "Chamados com a EDNNA": coluna de chamado agora é LinkColumn e abre o Redmine.
2. Central de Cancelamentos: carteira usa a mesma função central de links.
3. Contexto histórico: chamado atual e Blueprint são links clicáveis.
4. Fontes históricas e cancelamento anterior: IDs passam a ser exibidos como links na área expandida, evitando IDs não clicáveis dentro da tabela-resumo.
5. Linha do tempo histórica: coluna de chamado usa LinkColumn.
6. Rodapé atualizado para v3.28.4.

Regra de UX consolidada
Todo número de chamado Redmine exibido como referência operacional deve ser navegável para /issues/{id}. Novas tabelas com a coluna # devem reutilizar preparar_tabela_com_link_redmine().

Validação
- app.py: py_compile OK
- ui/ednna_workspace.py: py_compile OK



---

## Documento legado: `README_v3.28.3.txt`


EDNNA v3.28.3 — Carteira EDNNA

Correção:
- "Chamados com a EDNNA" agora usa o snapshot GLOBAL de chamados abertos do Redmine.
- Antes a carteira recebia apenas o subconjunto Estado == Aberto (primeiro combate). Assim, chamados já assumidos pela EDNNA e movidos para "Em andamento" ou "Aguardando Retorno" desapareciam da carteira.
- O snapshot passa a expor também "_Atribuído a ID".
- Critério principal: assigned_to.id == REDMINE_EDNNA_USER_ID (padrão 166).
- Fallback por nome contendo "ednna" mantém compatibilidade com snapshots antigos.

Arquivos alterados:
- app.py
- redmine_api.py
- ui/ednna_workspace.py

Validação:
- python -m py_compile app.py redmine_api.py ui/ednna_workspace.py

Teste esperado:
- Após refresh do snapshot, #30846 (se ainda aberto e atribuído à EDNNA/166) deve aparecer em "Chamados com a EDNNA", mesmo estando Em andamento.



---

## Documento legado: `README_v3.28.3.1.txt`


EDNNA v3.28.3.1 — Hotfix Carteira EDNNA

Correção:
- adiciona `import os` em ui/ednna_workspace.py;
- corrige NameError ao ler REDMINE_EDNNA_USER_ID na carteira "Chamados com a EDNNA".

Não altera regras de negócio, cache, banco, Redmine ou Microsoft Graph.

Arquivos alterados:
- ui/ednna_workspace.py



---

## Documento legado: `README_v3.28.2.txt`


EDNNA v3.28.2 — Otimização Multiusuário

Arquivos alterados:
- redmine_api.py
- ednna/contexto_relacionamentos.py
- ednna/email_sender.py

Ajustes:
1. custom_fields compartilhado via painel.db, com TTL persistente de 24h por padrão.
2. Evita repetição de custom_fields quando circuit breaker está aberto.
3. Lock compartilhado por chamado para contexto histórico; sessões simultâneas não consultam o mesmo issue.
4. Em falha do Redmine, contexto histórico usa última cópia SQLite disponível, inclusive expirada, como contingência.
5. Microsoft Graph: remove combinação $filter + $orderby que gerava InefficientFilter; filtra conversationId/data localmente em janela recente da Inbox.

Variáveis opcionais:
REDMINE_CUSTOM_FIELDS_TTL=3600
REDMINE_CUSTOM_FIELDS_PERSIST_TTL=86400

O snapshot principal continua com PAINEL_CACHE_TTL_SECONDS=600, portanto a lista de chamados segue atualizando a cada 10 minutos por padrão, coordenada por lock global.



---

## Documento legado: `README_v3.28.17.txt`


EDNNA v3.28.17 — Corpus por Intenção e Linha do Tempo Operacional

- Inclusão usa somente Abertura Relacionamento, Inclusão de EC/Domc, Falta de Arquivo e Falta de registros.
- Abertura e Inclusão são fontes principais; faltas são complementares.
- Outros tipos são ignorados no aprendizado de inclusão.
- Somente inclusões históricas votam na recorrência; chamado atual fornece variáveis.
- Linha do tempo separa SOLICITACAO_EXTERNA, RETORNO_PLAYER e ACAO_INTERNA.
- Mantém travas de homologação e SQLite-first.



---

## Documento legado: `README_v3.28.16.txt`


v3.28.16 — Extrator de Procedimento Operacional

- Decompõe históricos de inclusão em solicitação, destinatários/CC, assunto, ações e evidências de conclusão.
- Confirma destinatário somente quando recorrente em pelo menos dois históricos.
- Compara ações normalizadas para encontrar procedimento recorrente mesmo com dados variáveis.
- Adiciona auditoria recolhível “Ver como a EDNNA chegou a esta conclusão”.
- Mantém execução bloqueada: somente investigação/aprendizado.
- Preserva SQLite-first/stale-while-revalidate da v3.28.15.



---

## Documento legado: `README_v3.28.15.txt`


EDI Capacity Dashboard v3.28.15
SQLite First + Aprendizado Semântico

1. Painel stale-while-revalidate
- Se existe snapshot SQLite, ele é servido imediatamente mesmo vencido.
- Snapshot vencido agenda atualização Redmine em thread de background.
- Apenas a ausência total de snapshot exige carga síncrona inicial.
- force_refresh=True preserva atualização síncrona explícita.

2. Aprendizado semântico EDNNA
- Completude deixa de medir apenas fontes/campos e passa a medir sinais operacionais.
- constantes=0 nunca produz PRONTA_PARA_REVISAO.
- Novo estado APRENDIZADO_INCOMPLETO.
- Bloqueios explícitos: histórico insuficiente, procedimento recorrente ausente,
  fontes pendentes, destinatário não confirmado e evidência de conclusão ausente.
- Fontes stale/parciais impedem homologação.

3. Enriquecimento e reaprendizado
- Fontes indisponíveis continuam entrando na fila já existente.
- Após o worker enriquecer uma fonte, regras incompletas relacionadas são
  reprocessadas automaticamente.

4. UX
- A Central informa fontes aguardando enriquecimento e recolhe pendências
  técnicas em expander.
- Nenhuma execução automática de inclusão foi habilitada nesta versão.



---

## Documento legado: `README_v3.28.13.txt`


EDI Capacity Dashboard / EDNNA — v3.28.13

Objetivo: fixar o PLAYER_ALVO do chamado de inclusão e impedir concorrência indevida de players históricos.

Principais ajustes:
- PLAYER_ALVO é extraído prioritariamente do assunto do chamado atual;
- aliases genéricos do histórico não podem substituir um player explícito;
- proteção específica contra falso positivo REDE SANTA LUCIA -> REDECARD;
- BP confirma o contexto, mas não escolhe o player quando o chamado já o informa;
- AR e inclusões anteriores são filtradas exclusivamente pelo PLAYER_ALVO;
- logs mostram chamado, origem do player, BP, AR, históricos filtrados e players secundários ignorados;
- regra permanece CANDIDATA_NAO_HOMOLOGADA e sem ações externas.

Caso de validação:
#48318 / REDE SANTA LUCIA / VALECARD.
Esperado: PLAYER_ALVO=VALECARD; BP #8812; AR #43943; inclusões anteriores #44872 e #48281; REDECARD apenas como contexto secundário, nunca como investigação concorrente.

Roadmap UX:
Redesenho completo da UX do produto, não apenas da Central EDNNA, será tratado em entrega própria após estabilização funcional.



---

## Documento legado: `README_v3.28.12.txt`


EDI Capacity Dashboard / EDNNA — v3.28.12

Objetivo: Investigação Orientada à Adquirente + Síntese Operacional.

Principais ajustes:
- investigação de inclusão passa a priorizar o player/adquirente do chamado atual;
- ARs de outros players deixam de poluir a regra candidata;
- inclusões anteriores são filtradas pelo mesmo player;
- resultado da investigação apresenta síntese operacional antes dos detalhes;
- evidências, dados extraídos e diagnóstico técnico ficam em expansores fechados;
- mantém cache resiliente, fila de enriquecimento e rastreabilidade da v3.28.11;
- nenhuma regra candidata executa ações sem homologação explícita.

Caso de validação recomendado:
#48318 / REDE SANTA LUCIA / VALECARD.
Esperado: VALECARD como investigação principal; inclusões #44872 e #48281 como histórico relevante, sem REDECARD concorrendo na síntese.

Nota de roadmap UX:
A UX completa do produto será redesenhada em etapa própria. O problema identificado é global (arquitetura de informação e navegação), não restrito à Central EDNNA.



---

## Documento legado: `README_v3.28.11.txt`


EDI Capacity Dashboard / EDNNA — v3.28.11

Release: EDNNA Investigação Resiliente e Cache de Contexto

Principais ajustes:
- investigação interativa usa consulta pontual curta (connect 4s / read 8s / 1 tentativa);
- fallback imediato para cache SQLite válido ou histórico expirado;
- contexto expirado é identificado como parcial, com procedência e timestamp;
- falhas sem cache entram automaticamente na fila SQLite de enriquecimento;
- monitor EDNNA processa a fila em background com política mais tolerante;
- cache de BP, AR, inclusões e relações permanece persistente entre reinícios;
- Central de Descoberta informa REDMINE x MISTA/CACHE e contexto parcial;
- versão continua centralizada em version.py.

Objetivo operacional:
A interface não deve ficar presa em múltiplos timeouts do Redmine. A ação humana
recebe rapidamente o melhor contexto disponível; o enriquecimento pendente ocorre
em background e melhora a base histórica para investigações futuras.



---

## Documento legado: `README_v3.28.10.txt`


EDNNA v3.28.10 — Resiliência de Investigação

Alterações principais:
1. Versionamento centralizado em version.py (APP_VERSION / APP_RELEASE).
2. Rodapé passa a consumir a versão central, evitando divergência visual.
3. Consultas pontuais de contexto (ex.: Investigar inclusão) podem consultar
   issues/<id>.json mesmo quando o circuit breaker da listagem massiva está ativo.
4. Falha de uma consulta pontual não abre, fecha ou interfere no circuit breaker
   global usado para proteger cargas amplas do Redmine.
5. O cache histórico SQLite continua sendo usado antes da rede e como fallback.

Objetivo do teste:
Central de Descoberta -> #48318 REDE SANTA LUCIA / VALECARD -> Investigar inclusão.
No log, com breaker global ativo, deve aparecer:
[REDMINE] Consulta pontual autorizada apesar do circuit breaker | issues/48318.json



---

## Documento legado: `README_v3.28.1.txt`


EDNNA v3.28.1 — Limpeza de Retornos + Carteira EDNNA + Disparo GETNET
Data: 15/09/2026

Arquivos alterados nesta atualização:
- ednna/monitor_respostas.py
- ednna/planejador_cancelamentos.py
- ui/ednna_workspace.py

1) Retornos de e-mail
- O journal do Redmine passa a registrar somente a parte nova da resposta da adquirente.
- Remove blocos citados iniciados por "Mensagem original", "Original Message" ou cabeçalhos Outlook De/Enviado/Para.
- Mantém remetente, assunto, recebido em e inteligência/complementação EDNNA.

2) Chamados com a EDNNA
- Nova carteira na Visão geral da Central EDNNA.
- Usa o campo "Atribuído a" do snapshot atual e lista chamados cujo responsável contém "ednna".
- Exibe total e dados operacionais principais.

3) Cancelamentos GETNET
- O plano assistido passa a permitir disparo real após aprovação humana explícita.
- Continua sem execução automática.
- Antes do envio exige Cliente + pelo menos 1 EC + destinatários + assunto + corpo e valida que todos os ECs aparecem no corpo.
- Ao enviar: Graph -> acompanhamento local -> atribuição EDNNA (ID configurado) -> journal/status Redmine -> monitor de respostas.
- Status pós-envio: Aguardando Retorno Adquirente.
- O chamado atual é consultado antes do histórico para aproveitar EC informado diretamente na solicitação.

Configuração esperada no Azure:
REDMINE_EDNNA_USER_ID=166
REDMINE_EDNNA_USERNAME=ednna.ia

Observação de segurança:
CANCELAMENTO-GETNET-001 continua sujeito a aprovação humana. Não há disparo automático em lote.



## 3.28.7.1 — Reconciliação de Órfãos

- Recupera acompanhamentos GETNET enviados antes do orquestrador ou sem ação local elegível.
- Usa snapshot persistido para localizar cancelamentos GETNET atribuídos à EDNNA e compara com a fila local.
- Para órfãos, procura o e-mail real em Sent Items pelo ID do chamado e reconstrói a etapa `AGUARDANDO_RESPOSTA`.
- O monitor procura resposta posterior na Inbox e o ciclo normal atualiza o Redmine.
- Inclui logs explícitos do funil de reconciliação.
- Caso de homologação histórico: #48567 MAIS CAMPUS.

## 3.28.24 — Motor de Workflows e Executores

- Separa formalmente **conhecimento homologado**, **workflow**, **canal** e **executor**.
- Introduz catálogo declarativo de workflows de inclusão, evitando `if` por player no motor.
- Regras homologadas passam a ter prontidão operacional independente: `ASSISTIDA_DISPONIVEL`, `AGUARDANDO_EXECUTOR` ou `SEM_WORKFLOW`.
- Nenhuma execução automática é liberada nesta versão; a operação disponível permanece assistida e exige confirmação humana.
- Workflows mapeados com conhecimento operacional validado:
  - VALECARD, ALELO, TICKET, ONECARD, POLICARD, TRUCKPAG, VEROCHEQUE e VR BENEFÍCIOS: e-mail + estabelecimento do chamado.
  - SODEXO/PLUXEE: inclusão por e-mail reutilizando contatos/padrão operacional de Falta de Arquivo, mantendo conteúdo de inclusão.
  - CIELO: API (`CIELO_API`, executor ainda a implementar/validar).
  - TICKETLOG: abertura de chamado (`TICKETLOG_CHAMADO`, executor ainda a implementar/validar).
  - REDECARD: Opt-in via API primeiro; depois solicitação de autorização do cliente por e-mail.
  - GREENCARD: gerar formulário; enviar ao cliente para assinatura; receber assinado; encaminhar à GreenCard.
  - BANRISUL: banco; localizar Abertura de Relacionamento e obter os dados do gerente/conta antes da solicitação.
- A homologação deixa de exigir destinatário de e-mail para workflows que não são exclusivamente por e-mail.
- A fila operacional passa a exibir canal, workflow e prontidão de execução.
- Incluído `preparar_operacao_inclusao()` para transformar regra homologada em plano operacional sem disparar ação externa.

## 3.28.26 — Nova Home Operacional EDNNA
- Nova camada frontal simples, inspirada na linguagem visual do painel Tradutor.
- Avatar EDNNA em destaque com movimento visual suave.
- Frases e percentuais dinâmicos calculados a partir do estado real da operação e das regras.
- Cards com botões para Atendimentos, Aprendizado, Revisões e Automações.
- Separação explícita entre `✨ Início` e `⚙️ Área técnica`.
- Toda a interface técnica anterior foi preservada integralmente na Área técnica.
