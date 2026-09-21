# EDNNA v3.28.52

## Hotfix de inicialização + Integridade operacional + TrioCard

- Corrige o contrato de versionamento centralizado: `version.py` volta a fornecer `APP_VERSION` e `APP_RELEASE`.
- Elimina o `ImportError: cannot import name 'APP_RELEASE' from 'version'` na inicialização do Streamlit.
- Preserva integralmente as correções da v3.28.51: extração contextual de ECs, TICKET multi-EC e regra assistida de Falta de Arquivo da TRIOCARD.
- Mantém TRIOCARD com destinatário `arquivos@personalcard.com.br` e CC institucional.
