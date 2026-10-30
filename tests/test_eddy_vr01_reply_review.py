"""Safety regression: a Graph reply is not proof of VR portal authorization."""
from pathlib import Path


def test_reply_requires_authorization_review_and_never_auto_returns():
    source = Path("ednna/eddy_vr_mysql_followups.py").read_text(encoding="utf-8")
    assert '"AGUARDA_CLASSIFICACAO_AUTORIZACAO"' in source
    assert '"RESPOSTA_RECEBIDA"' not in source
    assert '"execucao_externa": False' in source


def test_lifecycle_requires_explicit_authorization_and_evidence():
    from ednna.eddy_vr01_lifecycle import VR01State, VR01Evidence, next_transition
    e = VR01Evidence(
        original_owner_id=97, eddy_owner_id=999, redmine_assignee_id=999,
        redmine_snapshot_fresh=True, original_owner_persisted=True,
        graph_send_confirmed=True, redmine_evidence_recorded=True,
        customer_portal_authorization_confirmed=False,
    )
    assert next_transition(VR01State.AGUARDA_CONFIRMACAO_CLIENTE, e)[0] == "ACOMPANHAR_E_COBRAR"
    assert next_transition(VR01State.EVIDENCIAS_REGISTRADAS, e)[0] == "BLOQUEADO_EVIDENCIAS"
