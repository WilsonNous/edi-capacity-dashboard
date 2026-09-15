EDNNA v3.28.3 — Carteira EDNNA

Correção:
- "Chamados com a EDNNA" agora usa o snapshot GLOBAL de chamados abertos do Redmine.
- Antes a carteira recebia apenas o subconjunto Estado == Aberto (primeiro combate). Assim, chamados já assumidos pela EDNNA e movidos para "Em andamento" ou "Aguardando Retorno" desapareciam da carteira.
- O snapshot passa a expor também "_Atribuído a ID".
- Critério principal: assigned_to.id == REDMINE_EDNNA_USER_ID (padrão 166).
- Fallback por nome contendo "ednna" mantém compatibilidade com snapshots antigos.

Arquivos alterados:
- app.py
- redmine_api.py
- ui/ednna_workspace.py

Validação:
- python -m py_compile app.py redmine_api.py ui/ednna_workspace.py

Teste esperado:
- Após refresh do snapshot, #30846 (se ainda aberto e atribuído à EDNNA/166) deve aparecer em "Chamados com a EDNNA", mesmo estando Em andamento.
