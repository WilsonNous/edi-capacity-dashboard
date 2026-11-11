"""Regression: historical EDDY ownership requires verified human provenance."""
import pytest

from ednna import eddy_vr01_integrated as vr
from ednna.eddy_vr_original_owner import recuperar_responsavel_por_journals


class Cursor:
    def __init__(self, rows):
        self.rows = rows
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params=None):
        if "INSERT IGNORE INTO eddy_vr01_lifecycle_audit" in sql:
            self.rows.append(params)
    def fetchone(self):
        return None


class Connection:
    def __init__(self, rows):
        self.rows = rows
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def cursor(self):
        return Cursor(self.rows)


@pytest.mark.parametrize("owner,recovered,expected_phase", [
    (97, None, "PRONTO_PARA_ASSUMIR"),
    (200, 97, "ASSUMIDO_EDDY"),
])
def test_initialize_proven_ownership(monkeypatch, owner, recovered, expected_phase):
    rows = []
    monkeypatch.setattr(vr, "connect", lambda: Connection(rows))
    monkeypatch.setattr(vr, "_load", lambda: {
        "fase": rows[-1][1], "original_owner_id": 97, "eddy_owner_id": 200
    })
    with vr.escopo_vr01(48786, 97, "CLIENTE", "12345678000190"):
        result = vr._initialize({"assigned_to": {"id": owner}}, 200, recovered_owner_id=recovered)
    assert result["fase"] == expected_phase
    assert rows == [(48786, expected_phase, 97, 200)]


@pytest.mark.parametrize("owner,recovered", [
    (200, None), (200, 98), (300, 97), (0, 97),
])
def test_initialize_rejects_unproven_ownership(monkeypatch, owner, recovered):
    rows = []
    monkeypatch.setattr(vr, "connect", lambda: Connection(rows))
    with vr.escopo_vr01(49119, 97, "CLIENTE", "12345678000190"):
        with pytest.raises(RuntimeError, match="Responsavel original divergente"):
            vr._initialize({"assigned_to": {"id": owner}}, 200, recovered_owner_id=recovered)
    assert rows == []


def test_recover_only_complete_journals():
    issue = {"id": 48786, "assigned_to": {"id": 200}, "_eddy_journals_completos": True}
    journals = [{"id": 12, "details": [{"property": "attr", "name": "assigned_to_id",
                                      "old_value": "97", "new_value": "200"}]}]
    assert recuperar_responsavel_por_journals(issue, journals, 200) == 97
    issue["_eddy_journals_completos"] = False
    assert recuperar_responsavel_por_journals(issue, journals, 200) is None
