"""MAMBO VR01 recipient matrix: no MySQL or Graph network calls."""
from unittest.mock import patch

import pytest

from ednna.eddy_vr01_integrated import _mambo_recipients


NAMES = (
    "Tais Vieira", "Henrique Mota", "Raiza Vieira", "Ingrid Santos",
    "Agata Palladino", "Anderson Cavalcanti", "Wilamy Tolentino",
    "Augusto Silva", "Claudimar Freitas", "Gustavo Mengue",
)


def contacts():
    return [
        {"nome": name, "email": f"person{i}@mambo.com.br",
         "source_id": i + 1, "documento_id": 77, "chamado_id": 50334}
        for i, name in enumerate(NAMES)
    ]


def test_manager_and_thirteen_cc():
    rows = contacts()
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql", return_value=rows), \
         patch("ednna.eddy_vr01_integrated._valid_bp", return_value=rows[0]):
        primary, cc = _mambo_recipients()
    assert primary == ["person0@mambo.com.br"]
    assert len(cc) == 13
    assert len(set(cc)) == 13
    assert primary[0] not in cc
    assert set(cc) >= {
        "bpo@netunna.com.br", "edi@netunna.com.br",
        "suporte@netunna.com.br", "consultores@netunna.com.br",
    }


def test_missing_contact_fails_closed():
    rows = contacts()[:-1]
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql", return_value=rows), \
         patch("ednna.eddy_vr01_integrated._valid_bp", return_value=rows[0]):
        with pytest.raises(RuntimeError, match="incompleta"):
            _mambo_recipients()


def test_wrong_manager_approval_fails_closed():
    rows = contacts()
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql", return_value=rows), \
         patch("ednna.eddy_vr01_integrated._valid_bp", return_value=rows[1]):
        with pytest.raises(RuntimeError, match="Gerente"):
            _mambo_recipients()


def test_ambiguous_contact_fails_closed():
    rows = contacts()
    rows.append({**rows[0], "email": "other@mambo.com.br"})
    with patch("ednna.mysql_blueprint_participants.selecionar_contatos_cliente_mysql", return_value=rows), \
         patch("ednna.eddy_vr01_integrated._valid_bp", return_value=rows[0]):
        with pytest.raises(RuntimeError, match="ambiguo"):
            _mambo_recipients()
