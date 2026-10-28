# EDDY — Separação entre regras ativas e histórico de aprendizado

## Decisão
- **MySQL operacional:** regras homologadas e versionadas serão consultadas por ID/versão; sem leitura de histórico em cada ciclo.
- **MySQL histórico:** evidências de aprendizado, revisões, testes e classificações permanecem consultáveis sob demanda, sem poder autorizar execução.
- **SQLite legado:** preservado até reconciliar cópia íntegra e consumidores restantes. Não é excluído nesta etapa.

## Entrega inicial
`scripts/eddy_archive_legacy_knowledge.py` inventaria em modo leitura uma **cópia offline** do SQLite, incluindo análises, classificações, aprendizados, revisões, regras treináveis e testes. O arquivo original não é tocado. O comando `--apply` é opt-in e grava registros JSON e SHA-256 em `eddy_legacy_knowledge_archive`, com verificação de existência após escrita. Registros duplicados são idempotentes. O arquivo de histórico **não ativa** regras.

Exemplo, após gerar uma cópia consistente e verificar integridade:

```bash
python -m scripts.eddy_archive_legacy_knowledge --sqlite-copy /backup/ednna-copy.db
# Somente após revisar inventário e confirmar destino MySQL:
python -m scripts.eddy_archive_legacy_knowledge --sqlite-copy /backup/ednna-copy.db --apply
```

**Nunca executar diretamente contra `/home/data/ednna.db`.** Se a cópia estiver corrompida, o script recusa migração: primeiro é necessária recuperação offline verificada. Evitar registrar payloads históricos nos logs.

## Pendências obrigatórias antes de substituir leitura de regras
1. Auditar a estrutura real de `aprendizados_operacionais`, `revisoes_regras_operacionais`, `regras_treinaveis` e suas versões no arquivo real.
2. Definir tabela operacional de regras com chave, versão, estado, origem, assinatura e política explícita de publicação/homologação.
3. Migrar regras homologadas com reconciliação de conteúdo e sem promoção automática de rascunhos.
4. Substituir consumidores do `ednna.armazenamento` por repositórios MySQL com testes e comportamento fail-closed.
5. Homologar em Azure, manter rollback e só então retirar `ednna.db` do circuito.

## Limitações
A migração inicial preserva conteúdo de tabelas conhecidas, **não** é uma migração integral de todas as tabelas SQLite, nem muda a fonte de regras ativas. Conteúdo sem tabela conhecida exige inventário separado. O arquivo de produção não foi acessado. Nenhum merge/deploy significa validação de dados de produção.
