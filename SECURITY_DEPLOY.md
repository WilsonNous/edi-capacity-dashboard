# EDNNA 3.34.0 — implantação segura

A EDNNA usa Microsoft Entra ID via Azure App Service Authentication (Easy Auth). O App Service autentica; a aplicação aplica autorização por perfil.

## Perfis
- `ADMIN`: acesso completo, incluindo regras, ensino/homologação e área técnica.
- `EDI`: módulos operacionais, sem governança/edição de regras.
- `VIEWER`: somente Home executiva e resumo read-only da Central de Operações.

## Variáveis do App Service
Configure em **App Service > Environment variables / Application settings**:

- `EDNNA_ADMIN_EMAILS`: e-mails ADMIN separados por vírgula.
- `EDNNA_EDI_EMAILS`: e-mails da equipe EDI separados por vírgula.
- `EDNNA_ALLOWED_EMAIL_DOMAINS`: opcional; padrão `netunna.com.br`.
- `EDNNA_ADMIN_GROUP_IDS`: opcional; Object IDs de grupos Entra separados por vírgula.
- `EDNNA_EDI_GROUP_IDS`: opcional; Object IDs de grupos Entra separados por vírgula.

Exemplo:
`EDNNA_ADMIN_EMAILS=wilson.martins@netunna.com.br`

Não configure `EDNNA_DEV_BYPASS_AUTH` no Azure. Mesmo que seja configurado acidentalmente, o código ignora o bypass quando detecta App Service.

## Easy Auth esperado
- Microsoft / Workforce tenant atual
- Require authentication
- HTTP 302 para Microsoft
- Token store habilitado
- tenant emissor restrito

## Ordem de deploy
1. Confirmar Easy Auth com janela anônima.
2. Configurar `EDNNA_ADMIN_EMAILS` antes do deploy.
3. Publicar 3.34.0.
4. Confirmar que o administrador aparece como `Administrador EDNNA`.
5. Configurar `EDNNA_EDI_EMAILS` e testar um integrante EDI.
6. Testar um usuário Netunna fora das listas: deve aparecer como `Visualizador`, sem botões operacionais.
7. Tentar URL direta de Regras/Operação com VIEWER: deve ser bloqueada.

## Auditoria
Acessos negados/bloqueados são registrados em `data/ednna_security.db`, tabela `security_audit`.
