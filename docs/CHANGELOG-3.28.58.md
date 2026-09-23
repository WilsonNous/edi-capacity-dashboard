# EDNNA 3.28.58

- Regra homologada passa a resolver destinatário por prioridade: confirmação humana, destinatário padrão do workflow e evidência operacional aprendida.
- Remove falso `AGUARDANDO_DESTINATARIO` quando a própria homologação já possui evidência de contato.
- Central de Regras ganha comando para promover em lote para `AUTOMATICA` todas as regras já homologadas cujo executor está implementado.
- Regras sem executor continuam bloqueadas.
- Mantidas as travas de atuação anterior, acompanhamento, lock de envio e Redmine outbox.
