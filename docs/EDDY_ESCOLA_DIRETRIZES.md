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
