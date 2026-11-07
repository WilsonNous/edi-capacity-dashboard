"""Per-ticket VR01 context isolation and template safety."""
import pytest
from ednna.eddy_vr01_integrated import _context, escopo_vr01
from ednna.eddy_vr01_email_templates import assunto_vr01, assunto_followup_vr01, mensagem_autorizacao


def test_context_is_isolated_and_restored():
    initial = _context().copy()
    with escopo_vr01(50671, 123, "CLIENTE TESTE", "12.345.678/0001-99"):
        assert _context()["chamado_id"] == 50671
        assert _context()["original_owner_id"] == 123
        assert _context()["cliente"] == "CLIENTE TESTE"
        with escopo_vr01(50318, 97, "MAMBO", "71.676.316/0033-23"):
            assert _context()["chamado_id"] == 50318
        assert _context()["chamado_id"] == 50671
    assert _context() == initial


@pytest.mark.parametrize("cnpj", ["", "123", "não informado"])
def test_context_rejects_missing_cnpj(cnpj):
    with pytest.raises(ValueError):
        with escopo_vr01(50671, 123, "CLIENTE TESTE", cnpj):
            pass


def test_subject_and_body_use_actual_issue_context():
    subject = assunto_vr01(50671, "CLIENTE TESTE")
    followup = assunto_followup_vr01(50671, "CLIENTE TESTE")
    assert "50671" in subject and "CLIENTE TESTE" in subject
    assert subject != followup
    assert "50671" in followup
    body = mensagem_autorizacao(50671, "12.345.678/0001-99", "CLIENTE TESTE")
    assert "CLIENTE TESTE" in body and "12.345.678/0001-99" in body
    assert "MAMBO" not in body
