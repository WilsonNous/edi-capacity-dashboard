# VR01 #50318 — Homologação por operação (PR #189)

Esta entrega separa as dependências de prontidão; **não homologa integrações por decreto** e não habilita execução automática. O piloto permanece observacional até validação operacional documentada.

## Condições comuns a todas as operações

- `EDDY_DB_ENGINE=mysql` e credenciais MySQL presentes.
- `EDDY_VR01_EXTERNAL_ENABLED=true` **somente após liberação operacional explícita**.
- Preflight Redmine ativo e fresco em cada invocação `execute=True`, identidade institucional válida e nenhuma operação pendente no ledger.
- Aprovação específica por operação externa, vinculada a `issue_id=50318` e ao `updated_on` atual; o executor preserva a reserva pendente em falha ambígua para reconciliação manual.
- **Nunca** executar `execute=True` no scheduler automático sem autorização e testes reais; o agendador de cinco minutos continua observacional.

## Dependências específicas

| Operação | Homologação adicional |
|---|---|
| `ASSUMIR_REDMINE` | `EDDY_VR01_REDMINE_MYSQL_AUDIT_READY` |
| `BUSCAR_CONTATO_BP` | MySQL, identidade e preflight |
| `SOLICITAR_AUTORIZACAO_PORTAL` | `EDDY_VR01_TRANSPORT_MYSQL_READY`, `EDDY_VR01_RECIPIENT_RESOLVER_READY`, credenciais Graph |
| `MONITORAR_CLIENTE` | `EDDY_VR01_REPLY_RECONCILIATION_READY` |
| `FOLLOWUP_CLIENTE` | Transporte, destinatário, respostas e credenciais Graph |
| `CONFIRMACAO_VALIDADA` | `EDDY_VR01_REPLY_RECONCILIATION_READY` e evidência positiva revisada |
| `REGISTRAR_EVIDENCIAS_REDMINE` | Respostas homologadas e auditoria Redmine homologada |
| `DEVOLVER_AO_RESPONSAVEL_ORIGINAL` | Auditoria Redmine homologada |
| `NOTIFICAR_RESPONSAVEL_COM_CRONOLOGIA` | Transporte, destinatário e credenciais Graph |

## Evidências para aceite

1. **Assunção:** confirmar responsável original 97, Redmine atualizado para EDNNA, evento MySQL e fase `ASSUMIDO_EDDY`.
2. **Solicitação:** contato BP inequívoco e aprovado, mensagem Graph enviada e conciliada, evento MySQL e fase `SOLICITACAO_ENVIADA`.
3. **Resposta:** resposta real `INBOX_REPLY` conciliada, revisão humana registrada, autorização no portal confirmada; ausência de resposta não é aprovação.
4. **Devolução:** evidências registradas no Redmine, atribuição retornada ao responsável original e notificação interna Graph confirmada; verificar cronologia MySQL.

A autorização do portal não comprova o recebimento dos arquivos pela Netunna; essa verificação permanece humana.

## Diagnóstico no deploy

Verificar `[EDDY-VR01-STAGES]`: campos `proxima_operacao`, `prontidao_operacao`, `fase`, `operacao_pendente`. A prontidão global permanece como indicador conservador de todos os requisitos, enquanto `prontidao_operacao` representa a ação atual. Não confundir `pronto=true` com aprovação ou ação executada.
