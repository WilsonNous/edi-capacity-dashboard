"""Focused follow-up and scheduler safety tests."""
from unittest.mock import patch

from ednna.eddy_vr01_integrated_scheduler import ciclo_piloto, planejar_followup_piloto


def test_scheduler_dry_run_does_not_send():
    with patch("ednna.eddy_vr01_integrated.planejar_vr01",
               return_value={"acao": "ACOMPANHAR_E_COBRAR"}), \
         patch("ednna.eddy_vr01_integrated_scheduler.planejar_followup_piloto",
               return_value={"situacao": "FOLLOWUP_VENCIDO"}), \
         patch("ednna.email_sender.enviar_email_graph") as send:
        result = ciclo_piloto()
        assert result["envios_realizados"] == 0
        send.assert_not_called()


def test_scheduler_cannot_send_before_specific_approval():
    with patch("ednna.eddy_vr01_integrated.planejar_vr01",
               return_value={"acao": "ACOMPANHAR_E_COBRAR"}), \
         patch("ednna.eddy_vr01_integrated_scheduler.planejar_followup_piloto",
               return_value={"situacao": "FOLLOWUP_VENCIDO"}), \
         patch("ednna.eddy_vr_readiness.verificar_prontidao_vr01",
               return_value={"pronto": True}), \
         patch("ednna.eddy_vr01_integrated_scheduler._read_issue",
               create=True) as unused, \
         patch("ednna.eddy_vr01_integrated._read_issue",
               return_value={"updated_on": "v1"}), \
         patch("ednna.email_sender.enviar_email_graph") as send:
        try:
            ciclo_piloto(execute=True, approvals={})
            assert False, "Unapproved follow-up must be rejected"
        except PermissionError:
            pass
        send.assert_not_called()


def test_reviewed_reply_blocks_automatic_followup():
    from ednna.eddy_vr01_integrated_scheduler import planejar_followup_piloto
    with patch("ednna.eddy_vr01_integrated._load",
               return_value={"fase": "AGUARDA_CONFIRMACAO_CLIENTE",
                             "autorizacao_confirmada": 1}):
        result = planejar_followup_piloto()
        assert result["situacao"] == "AUTORIZACAO_CONFIRMADA"
        assert result["execucao_externa"] is False
