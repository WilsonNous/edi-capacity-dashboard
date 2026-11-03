"""Identity compatibility for VR01 pilot; no external calls."""
import pytest
from ednna.eddy_vr01_integrated import _identity


def test_institutional_identity(monkeypatch):
    monkeypatch.setenv("REDMINE_EDNNA_USER_ID", "166")
    monkeypatch.setenv("REDMINE_EDNNA_USERNAME", "ednna.ia")
    monkeypatch.delenv("EDDY_REDMINE_USER_ID", raising=False)
    assert _identity() == 166


def test_legacy_identity(monkeypatch):
    monkeypatch.delenv("REDMINE_EDNNA_USER_ID", raising=False)
    monkeypatch.delenv("REDMINE_EDNNA_USERNAME", raising=False)
    monkeypatch.setenv("EDDY_REDMINE_USER_ID", "166")
    assert _identity() == 166


@pytest.mark.parametrize("institutional,legacy,username", [
    ("166", "167", "ednna.ia"),
    ("97", "", "ednna.ia"),
    ("", "", "ednna.ia"),
    ("abc", "", "ednna.ia"),
    ("166", "", "outro.usuario"),
])
def test_invalid_identity_fails_closed(monkeypatch, institutional, legacy, username):
    monkeypatch.setenv("REDMINE_EDNNA_USER_ID", institutional)
    monkeypatch.setenv("EDDY_REDMINE_USER_ID", legacy)
    monkeypatch.setenv("REDMINE_EDNNA_USERNAME", username)
    with pytest.raises(ValueError):
        _identity()
