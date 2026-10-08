# EDDY — publicação única: prontidão operacional e Central de Envios

## 1. Workers Azure
A tela **Operação → Prontidão do colaborador digital** lê `EDDY_WORKER_HEARTBEATS` (padrão `/home/data/eddy_worker_heartbeats.json`). Contrato por worker: `{"monitor_email":{"ultimo_ciclo_em":"2026-10-08T10:00:00-03:00","ultimo_erro":""},"followup":{...},"aprendizado":{...},"redmine":{...}}`. **A instrumentação dos workers para produzir esse arquivo não está incluída nesta PR.** Sem emissão, a UI diz SEM_EVIDENCIA, não "ativo". O startup Azure ainda precisa ser verificado com logs.

## 2. Central de Envios
`ednna.central_envios.exigir_janela_externa` bloqueia **sendMail** e **replyAll** Graph antes do POST, inclusive chamadas assistidas. Janela: 07:00 inclusive a 19:00 exclusive, segunda a sexta, America/Sao_Paulo. Operações internas seguem 24×7. Follow-up fora da janela não reserva tentativa nem avança contador; mantém registro existente. Se o limite de janela ocorrer entre a pré-verificação e o Graph, a quarentena existente é preservada por segurança.

**Configuração obrigatória antes do deploy:** `EDDY_ENVIO_UF`, `EDDY_ENVIO_MUNICIPIO`, `EDDY_FERIADOS_ARQUIVO` (padrão `/home/data/eddy_feriados.json`). JSON de listas de datas `YYYY-MM-DD`:
```json
{
  "nacional:2026": [],
  "estadual:SC:2026": [],
  "municipal:SC:FLORIANOPOLIS:2026": []
}
```
**Exemplo de formato, NÃO calendário oficial**: preencher as três listas com fontes oficiais verificadas, incluindo feriados móveis e locais; manter anos seguintes para transição. Não publicar listas vazias como se representassem ausência de feriados. O município padrão representa a política da operação; para múltiplas localidades, falta implementar roteamento contextual antes de habilitar envio para cada contexto.

**Falha fechada intencional:** calendário ausente/incompleto ou localidade indefinida impede envios externos. Preparar calendário real antes de publicar. A fila durável de novos envios iniciais e o agendamento ativo para a próxima janela ainda precisam de validação/implementação; esta PR não afirma que estão resolvidos.

## 3. Regras autorizadas
A Escola já exibe a grade de regras, etapas, modo de motor e executor. **Não promove nem ativa regras automaticamente**: é preciso executor existente, homologação, autorização humana e teste de execução real por chamado. Contar regras autorizadas não é contar trabalho realizado.

## 4. Resultados
A nova visão exibe os cinco KPIs com **Não medido** até existir evidência transacional auditável: chamados resolvidos automaticamente, follow-ups confirmados, intervenções evitadas, falhas e minutos economizados. Não inventar economia com base em tarefas elegíveis.

## Gate de publicação
- CI verde e testes do calendário.
- Conferir pacote no Azure, startup, instâncias e logs após deploy.
- Validar calendário oficial por UF/município/ano antes de habilitar comunicação externa.
- Validar manualmente: 06:59, 07:00, 18:59, 19:00, sábado, domingo, feriados dos três níveis e virada do ano.
- Confirmar que Graph não recebe POST fora da janela e que ações internas continuam 24×7.
- Verificar workers com logs reais e contadores confirmados; sem isso, **operacionalidade não comprovada**.

Quatro pilares NETUNNA: Flexibilidade (localidade e calendário configuráveis), Escalabilidade (consulta local), Segurança (falha fechada e autorização), Performance (sem Graph adicional por checagem).
