# EDNNA v3.29.5

- Extrator de estabelecimento passa a reconhecer linhas no padrão `PLAYER - EC`, como `VERO - 041131200978800`, quando o player é conhecido.
- Mantida a proteção para não tratar CNPJ de 14 dígitos como EC.
- O template genérico de inclusão já recebe `estabelecimentos` do pacote e passa a exibi-los no corpo do e-mail.
- Bloco **O que estou fazendo por você** passa a usar o mesmo padrão visual de cards de **Quem está com o quê?**.
- Preparação para futura evolução de variáveis operacionais de template (CNPJ, EC, participante, cliente e outros dados estruturados).
