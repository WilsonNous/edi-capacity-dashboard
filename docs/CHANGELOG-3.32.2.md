# EDNNA v3.32.2

## Blueprint legado / ID PROJETO
- Reconhece arquivos `BLUE PRINT` além de `BLUEPRINT`.
- Quando não existe aba `PARTICIPANTES`, extrai contatos da aba `ID PROJETO`.
- Importa `Gerente/Coord. Projeto` e os registros do bloco `Contatos no Cliente`.
- Ignora deliberadamente `Contatos Netunna` como destinatários do cliente.
- Normaliza os contatos legados na mesma tabela `blueprint_participantes` usada pelos Blueprints modernos.
- Seleção de contato preserva FINANCEIRO como primeira preferência e usa Gerente/Coord. Projeto como fallback prioritário.
- O restante dos workflows (VR, Greencard/Rotacard e regras que usam contatos do Blueprint) passa a consumir o legado sem tratamento específico por cliente.
