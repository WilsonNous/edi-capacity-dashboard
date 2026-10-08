# Diretrizes permanentes — Escola do EDDY e experiência operacional

## Missão
O EDDY deve estudar os chamados do Redmine, aprender com journals, anexos, Blueprints, e-mails e resultados, propor procedimentos verificáveis e executar apenas regras homologadas e autorizadas.

## Ciclo de evolução
1. **Estudar:** identificar evidências, fontes, datas, participantes, respostas e desfechos.
2. **Aprender:** extrair padrões e exceções por player, adquirente, banco, benefício, cliente e operação; preservar referências aos chamados.
3. **Propor:** apresentar candidatos a regras e lacunas de conhecimento sem tratar hipótese como fato.
4. **Homologar:** revisão humana explícita, com evidências e destinatários/canais corretos.
5. **Autorizar:** execução assistida ou automática apenas quando executor estiver disponível e permissão registrada.
6. **Executar e comprovar:** preflight Redmine, controle de duplicidade, evidência Graph, journal/outbox e observabilidade.
7. **Retroalimentar:** respostas, falhas e correções alimentam a Escola; aprendizado nunca amplia permissões sozinho.

## UX — grade estilo Excel
Priorizar tabelas com células, cabeçalhos claros, filtros, ordenação, seleção de linha, detalhes contextuais, estados e prazos. Identidade de cada linha deve incluir chamado **e regra**, sem sobrescrever registros com mesmo número de chamado. Edição apenas com perfil e fluxo de aprovação adequados; dados de execução não podem ser alterados por simples edição da grade.

## Linguagem e segurança
Preservar frases humanas curtas e orientadas à ação, como “Tenho X decisões para você”, sempre com métricas reais. Diferenciar **aprendido**, **homologado**, **autorizado**, **executado** e **confirmado**. Nunca repetir um envio Graph de resultado ambíguo sem reconciliação. Não inventar prazos, contatos ou evidências; respeitar o prazo original, estados terminais, permissões e indisponibilidade de serviços.

## Aplicação
Consultar estas diretrizes em mudanças de interface, motor, regras, Escola, automações, follow-ups e integrações. A Escola é uma capacidade permanente do produto, não uma tela isolada.

## Quatro pilares NETUNNA — critérios transversais obrigatórios
Toda evolução da NETUNNA (EDDY, EDNNA, Escola, endpoints, integrações, painéis, workers e automações) deve ser revisada sob **Flexibilidade, Escalabilidade, Segurança e Performance**. Nenhum pilar substitui os demais.

- **Flexibilidade:** regras parametrizáveis por cliente, player, operação e canal; componentes desacoplados e extensíveis; novas integrações sem duplicar lógica de negócio.
- **Escalabilidade:** processamento incremental e paginado, filas e workers controlados, persistência adequada, concorrência segura e capacidade de crescer sem bloquear a interface.
- **Segurança:** menor privilégio, autorização humana explícita, proteção de segredos e dados, idempotência, preflight, quarentena de resultados ambíguos e trilha auditável.
- **Performance:** cache com validade conhecida, consultas eficientes, índices quando necessários, atualização seletiva, observabilidade de tempos e grades responsivas.

### Checklist para toda PR
1. **Flexibilidade:** a mudança suporta variações de cliente/player sem remendos específicos?
2. **Escalabilidade:** o custo de consultas, dados e execução continua controlado com aumento de volume?
3. **Segurança:** quais permissões, validações, controles de duplicidade e evidências protegem o fluxo?
4. **Performance:** quais são os impactos em latência, cache, renderização e recursos?
5. **Operação contínua:** o EDDY permanece operante e observável durante a evolução da Escola e do endpoint EDNNA?

Documentar exceções e compromissos técnicos; CI bem-sucedido não substitui validação operacional no Azure.

## Central de Envios — janela operacional obrigatória
- **Comunicações externas:** permitir envio somente de segunda a sexta-feira, entre **07:00 (inclusive) e 19:00 (exclusive)**, no fuso **America/Sao_Paulo**. Inclui e-mails e follow-ups para clientes, adquirentes, bancos, benefícios, fornecedores e parceiros.
- **Atividades internas:** executar **24×7**, incluindo aprendizagem, classificação, leitura de respostas, reconciliação, observabilidade, filas, auditoria e atualizações internas sem comunicação externa.
- **Fora da janela:** manter a comunicação externa pendente na fila durável até a próxima abertura, sem perder prazo original, prioridade, rastreabilidade ou autorização; não marcar como enviada.
- **Controle central:** verificar o horário imediatamente antes de cada ação externa, inclusive em execuções assistidas, automáticas e retentativas. Não confiar apenas no horário do agendador.
- **Falhas e reinício:** respeitar idempotência, bloqueios de envios incertos e auditoria; janela aberta não é autorização para duplicar envio.
- **Feriados obrigatórios:** a Central deve considerar **feriados nacionais, estaduais e municipais** do contexto aplicável ao envio. Dia de segunda a sexta não é automaticamente dia útil.
- **Calendário contextual:** identificar unidade federativa e município relevantes à operação; não presumir que o município da sede NETUNNA se aplica a todos os destinatários. A regra de escolha da localidade e a fonte oficial do calendário devem ser parametrizadas e auditáveis.
- **Agendamento:** calcular a próxima janela de envio somente após validar dia da semana, horário local e feriados aplicáveis; não avançar por simples acréscimo de 24 horas.
- **Falha de calendário:** na ausência de confirmação de feriados ou de localidade necessária, não presumir dia útil para um disparo externo automático; sinalizar pendência de configuração para revisão.
- **Governança:** manter calendário versionado por ano/localidade, fontes e exceções aprovadas, com testes para feriados móveis, estaduais, municipais e virada de ano.
