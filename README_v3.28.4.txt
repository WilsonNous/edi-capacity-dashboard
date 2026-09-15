EDNNA v3.28.4 — Navegação Redmine

Objetivo
- Padronizar a navegação para o Redmine: sempre que a interface exibir um número de chamado operacional, oferecer acesso clicável ao chamado.
- Atualizar a identificação visual da versão no rodapé.

Arquivos alterados
- app.py
- ui/ednna_workspace.py

Principais ajustes
1. Carteira "Chamados com a EDNNA": coluna de chamado agora é LinkColumn e abre o Redmine.
2. Central de Cancelamentos: carteira usa a mesma função central de links.
3. Contexto histórico: chamado atual e Blueprint são links clicáveis.
4. Fontes históricas e cancelamento anterior: IDs passam a ser exibidos como links na área expandida, evitando IDs não clicáveis dentro da tabela-resumo.
5. Linha do tempo histórica: coluna de chamado usa LinkColumn.
6. Rodapé atualizado para v3.28.4.

Regra de UX consolidada
Todo número de chamado Redmine exibido como referência operacional deve ser navegável para /issues/{id}. Novas tabelas com a coluna # devem reutilizar preparar_tabela_com_link_redmine().

Validação
- app.py: py_compile OK
- ui/ednna_workspace.py: py_compile OK
