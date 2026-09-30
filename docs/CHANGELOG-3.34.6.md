# EDNNA 3.34.6

- Inclusão SAFRAPAY registrada como `INCLUSAO-SAFRAPAY-001`.
- Procedimento homologado a partir do chamado histórico #45956.
- Destinatário funcional: `conciliador.safrapay@safra.com.br`.
- VAN: Supply Mídia; custo da VAN: Netunna; padrão Safrapay: V2.0 Ed.13.
- Modelo de workflow automático com checkpoints humanos explícitos.
- Checkpoints SAFRAPAY: Termo do cliente, atualização da planilha Supply Mídia e validação final da recepção dos arquivos.
- O worker não executa efeito externo enquanto o checkpoint humano inicial estiver pendente.
- SAFRAPAY passa a aparecer em `Preciso de você` com instrução objetiva, sem ser classificada como erro técnico/executor ausente.
