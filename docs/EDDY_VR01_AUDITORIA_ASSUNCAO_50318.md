# VR01 #50318 — Marco de assunção: auditoria Redmine/MySQL

## O que esta entrega comprova

`diagnosticar_auditoria_assuncao()` é um probe **somente leitura** que verifica identidade EDNNA, ledger e fase, ausência de operação pendente, consulta à tabela de eventos MySQL, preflight Redmine fresco, versão `updated_on` e responsável original 97.

Mesmo com todas as leituras aprovadas, retorna `homologado=false` e `TESTE_ESCRITA_E_RECONCILIACAO_NAO_HOMOLOGADO`. **Uma consulta bem-sucedida não homologa a escrita.** Nenhuma flag é alterada e o scheduler continua observacional.

## Procedimento de homologação assistida (exige ambiente autorizado)

1. Confirmar que o #50318 está aberto, atribuído ao responsável original 97, com versão atual no Redmine, e que o ledger está em `PRONTO_PARA_ASSUMIR` sem operação pendente.
2. Executar o probe em ambiente de produção com credenciais de leitura e registrar o resultado, sem copiar segredos.
3. Validar, em ambiente de homologação autorizado, que o usuário institucional EDNNA tem permissão de editar atribuição; que a leitura após PUT reflete a alteração; que a reserva MySQL, evento `ASSUNCAO_EDDY` e avanço de fase são persistidos; e que timeout após PUT mantém a operação pendente para reconciliação humana.
4. Registrar evidências do teste, aprovação do responsável operacional e plano de reversão; só então homologar `EDDY_VR01_REDMINE_MYSQL_AUDIT_READY=true`.
5. Liberar `EDDY_VR01_EXTERNAL_ENABLED=true` somente em janela controlada. Fornecer aprovação específica `ASSUMIR_REDMINE` vinculada ao `updated_on` atual. Executar **uma única** chamada assistida `planejar_vr01(execute=True, approvals={...})`.
6. Confirmar no Redmine a atribuição à identidade EDNNA e no MySQL a fase `ASSUMIDO_EDDY`, o evento `ASSUNCAO_EDDY` e `operacao_pendente IS NULL`. Em resultado ambíguo, não repetir PUT: reconciliar manualmente.

**Não** usar o chamado real como teste destrutivo de permissões, não forçar flags com base apenas no probe e não executar em scheduler recorrente.

## Critério de aceite

A PR pode ser integrada após CI, mas a **assunção operacional** só é considerada concluída quando Redmine e MySQL concordarem, com auditoria e aprovação específica registradas.
