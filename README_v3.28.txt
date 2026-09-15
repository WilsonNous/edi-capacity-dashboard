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
