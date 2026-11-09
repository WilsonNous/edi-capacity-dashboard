from unittest.mock import patch

import pytest

from ednna import eddy_vr01_integrated as integrated


def _contacts():
    return [
        {"email": "henrique.mota@mambo.com.br"},
        {"email": "tais.vieira@mambo.com.br"},
        {"email": "financeiro@mambo.com.br"},
        {"email": "henrique.mota@mambo.com.br"},
    ]


def test_verified_primary_and_other_contacts_in_cc():
    with patch.object(integrated, "_bp_contacts", return_value=_contacts()), \
         patch.object(integrated, "_context", return_value={"cliente": "MAMBO"}), \
         patch("ednna.eddy_global_config.setting",
               return_value='{"MAMBO":"tais.vieira@mambo.com.br"}'):
        to, cc = integrated._verified_recipients()
    assert to == ["tais.vieira@mambo.com.br"]
    assert cc == ["henrique.mota@mambo.com.br", "financeiro@mambo.com.br"]


def test_primary_must_be_verified_in_blueprint():
    with patch.object(integrated, "_bp_contacts", return_value=_contacts()), \
         patch.object(integrated, "_context", return_value={"cliente": "MAMBO"}), \
         patch("ednna.eddy_global_config.setting",
               return_value='{"MAMBO":"outsider@example.com"}'):
        with pytest.raises(RuntimeError, match="not verified"):
            integrated._verified_recipients()


def test_default_primary_is_first_verified_contact():
    with patch.object(integrated, "_bp_contacts", return_value=_contacts()), \
         patch.object(integrated, "_context", return_value={"cliente": "OTHER"}), \
         patch("ednna.eddy_global_config.setting", return_value="{}"):
        to, cc = integrated._verified_recipients()
    assert to == ["henrique.mota@mambo.com.br"]
    assert cc == ["tais.vieira@mambo.com.br", "financeiro@mambo.com.br"]
