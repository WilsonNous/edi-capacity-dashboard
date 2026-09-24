# EDNNA 3.29.0 — Base de Conhecimento do Cliente

## Objetivo
Criar a fundação estrutural para transformar o Blueprint Excel do cliente em conhecimento operacional persistente, sem alterar os executores homologados existentes.

## Alterações
- Redmine Gateway passa a suportar `include=attachments` e download autenticado de anexos.
- Novo módulo `ednna/blueprint_knowledge.py`.
- Suporte a Blueprint `.xlsx` e `.xls` (`openpyxl` + `xlrd`).
- Reconhecimento por nome **ou assinatura estrutural das abas**; não depende do nome da filial.
- Persistência incremental no `ednna.db`: documentos, linhas normalizadas, participantes e log de sincronização.
- Hash SHA-256 e `attachment_id` impedem reimportação/duplicidade.
- Blueprints novos complementam o conhecimento; versões anteriores são preservadas.
- Participantes são normalizados com proveniência (documento/chamado/attachment).
- `contexto_relacionamentos.sincronizar_conhecimento_blueprint()` usa BP/Novo Cliente + relações já reconstruídas pela EDNNA.

## Segurança da versão
Esta versão cria a fundação e o cache. Ela **não muda automaticamente** destinatários de workflows nem executa VR/Greencard/bancos com dados do Blueprint. A ligação dos consumidores será feita após validação do conhecimento importado.
