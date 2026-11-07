"""VR01 delegates status update to the shared Redmine writer."""
from unittest.mock import patch, Mock
from ednna import eddy_vr01_integrated as vr


def test_shared_writer_exposes_post_email_operation():
    from ednna.redmine_writer import registrar_email_e_status_chamado
    assert callable(registrar_email_e_status_chamado)


def test_vr01_redmine_update_still_supports_existing_operations():
    response = Mock()
    with patch("requests.put", return_value=response) as put:
        with vr.escopo_vr01(50318, 97, "CLIENTE", "71676316003323"):
            vr._redmine_update(assigned_to_id=97, notes="Evidencia")
    payload = put.call_args.kwargs["json"]["issue"]
    assert payload["assigned_to_id"] == 97
    assert payload["notes"] == "Evidencia"


def test_vr01_uses_global_outbox_for_post_send_recovery():
    import inspect
    source = inspect.getsource(vr.planejar_vr01)
    assert "registrar_ou_enfileirar" in source
    assert 'regra_id="VR01"' in source
    assert "AGUARDANDO_CLIENTE_REDMINE_PENDENTE" in source
    assert "obter_status_id_por_nome" in source
