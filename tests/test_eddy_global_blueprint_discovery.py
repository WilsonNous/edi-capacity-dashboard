"""Regressions: Redmine relation discovery never touches SQLite."""
from unittest.mock import patch

from ednna.mysql_blueprint_participants import (
    _descobrir_fontes_redmine, descobrir_e_sincronizar_participantes_mysql,
)


def _issue(i, relations=(), bp=False):
    return {"id": i, "subject": "Novo Cliente" if bp else "Solicitacao",
            "tracker": {"name": "Novo Cliente" if bp else "Suporte"},
            "relations": list(relations)}


def _rel(a, b):
    return {"issue_id": a, "issue_to_id": b}


def test_descobre_bp_e_todas_relacoes_sem_sqlite():
    issues = {50318: _issue(50318, [_rel(50318, 111), _rel(50318, 222)]),
              111: _issue(111, [_rel(111, 50318), _rel(111, 333)], bp=True),
              222: _issue(222)}
    with patch("redmine_api.buscar_detalhes_chamado", side_effect=lambda i, **kw: issues[i]), \\
         patch("ednna.contexto_relacionamentos.analisar_contexto_operacional",
               side_effect=AssertionError("SQLite must not be consulted")), \\
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql",
               return_value={"participantes_processados": 2, "resultados": []}) as sync:
        resultado = descobrir_e_sincronizar_participantes_mysql({50318: "MAMBO"}, aplicar=True)
    sync.assert_called_once_with({111: "MAMBO", 222: "MAMBO", 333: "MAMBO",
                                  50318: "MAMBO"}, aplicar=True, skip_imported=True)
    assert resultado["fontes_descobertas"] == 4
    assert resultado["descoberta"][0]["status"] == "CONTEXTO_RESOLVIDO"


def test_falha_remota_nao_importa_parcial():
    with patch("redmine_api.buscar_detalhes_chamado", side_effect=TimeoutError), \\
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql") as sync:
        resultado = descobrir_e_sincronizar_participantes_mysql({50318: "MAMBO"})
    sync.assert_not_called()
    assert resultado["fontes_descobertas"] == 0
    assert resultado["descoberta"][0]["status"] == "CONTEXTO_INDISPONIVEL"


def test_multiplos_clientes_sem_confundir_origens():
    issues = {1: _issue(1), 2: _issue(2)}
    with patch("redmine_api.buscar_detalhes_chamado", side_effect=lambda i, **kw: issues[i]), \\
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql",
               return_value={"resultados": []}) as sync:
        resultado = descobrir_e_sincronizar_participantes_mysql({1: "MAMBO", 2: "OUTRO"})
    assert resultado["fontes_descobertas"] == 2
    assert sync.call_args.args[0] == {1: "MAMBO", 2: "OUTRO"}


def test_cliente_conflitante_nao_importado():
    issues = {1: _issue(1, [_rel(1, 9)]), 2: _issue(2, [_rel(2, 9)]),
              9: _issue(9)}
    with patch("redmine_api.buscar_detalhes_chamado", side_effect=lambda i, **kw: issues[i]), \\
         patch("ednna.mysql_blueprint_participants.sincronizar_blueprints_redmine_mysql",
               return_value={"resultados": []}) as sync:
        resultado = descobrir_e_sincronizar_participantes_mysql({1: "MAMBO", 2: "OUTRO"})
    assert resultado["fontes_descobertas"] == 2
    assert 9 not in sync.call_args.args[0]
    assert any(d["status"] == "CLIENTE_CONFLITANTE" for d in resultado["descoberta"])


def test_blueprint_como_raiz():
    with patch("redmine_api.buscar_detalhes_chamado",
               return_value=_issue(7, [_rel(7, 8)], bp=True)):
        ids, bp = _descobrir_fontes_redmine(7)
    assert ids == {7, 8}
    assert bp == 7
