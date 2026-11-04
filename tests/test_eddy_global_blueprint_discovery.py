"""Regressions for global EDDY Blueprint discovery (no external effects)."""
from unittest.mock import patch

from ednna.mysql_blueprint_participants import descobrir_e_sincronizar_participantes_mysql


def test_descobre_bp_e_relacionados():
    contexto = {"cliente": "MAMBO", "blueprint_id": 111,
                "eventos": [{"id": 222}, {"id": 333}]}
    with patch("ednna.contexto_relacionamentos.analisar_contexto_operacional", return_value=contexto), \
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql",
               return_value={"participantes_processados": 2, "resultados": []}) as sync:
        resultado = descobrir_e_sincronizar_participantes_mysql({50318: "MAMBO"}, aplicar=True)
    sync.assert_called_once_with({111: "MAMBO", 222: "MAMBO", 333: "MAMBO", 50318: "MAMBO"},
                                 aplicar=True, skip_imported=True)
    assert resultado["fontes_descobertas"] == 4
    assert resultado["descoberta"][0]["status"] == "CONTEXTO_RESOLVIDO"


def test_contexto_indisponivel_nao_inventa_fontes():
    with patch("ednna.contexto_relacionamentos.analisar_contexto_operacional", side_effect=TimeoutError), \
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql") as sync:
        resultado = descobrir_e_sincronizar_participantes_mysql({50318: "MAMBO"})
    sync.assert_not_called()
    assert resultado["fontes_descobertas"] == 0
    assert resultado["descoberta"][0]["status"] == "CONTEXTO_INDISPONIVEL"


def test_multiplos_clientes_sem_confundir_origens():
    def contexto(issue_id):
        return {"cliente": "MAMBO" if issue_id == 1 else "OUTRO",
                "blueprint_id": issue_id + 10, "eventos": []}
    with patch("ednna.contexto_relacionamentos.analisar_contexto_operacional", side_effect=contexto), \
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql",
               return_value={"resultados": []}) as sync:
        resultado = descobrir_e_sincronizar_participantes_mysql({1: "MAMBO", 2: "OUTRO"})
    assert resultado["fontes_descobertas"] == 4
    assert sync.call_args.args[0] == {1: "MAMBO", 11: "MAMBO", 2: "OUTRO", 12: "OUTRO"}
