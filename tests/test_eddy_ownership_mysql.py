"""Contract tests for the durable ownership ledger without a live MySQL server."""
from unittest.mock import patch
import pytest

from ednna.eddy_ownership import Ownership, OwnershipError, OwnershipState
from ednna import eddy_ownership_mysql as ledger


class Cursor:
    def __init__(self, existing=None):
        self.existing = existing
        self.statements = []
        self.rowcount = 1

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchone(self):
        return self.existing

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def item(state=OwnershipState.CAPTURED):
    return Ownership(49227, 12, 99, "2026-10-23T17:00:00Z", state)


def test_capture_is_audited():
    cursor = Cursor()
    with patch.object(ledger, "connect", return_value=Connection(cursor)):
        assert ledger.save_transition(item(), expected_revision=None) == 1
    assert len(cursor.statements) == 3
    assert "INSERT INTO eddy_ownership_events" in cursor.statements[-1][0]


def test_cannot_start_as_owned():
    with pytest.raises(OwnershipError):
        ledger.save_transition(item(OwnershipState.OWNED), expected_revision=None)


def test_stale_revision_rejected():
    old = (49227, 12, 99, item().version, "CAPTURADO", None, 4)
    cursor = Cursor(old)
    with patch.object(ledger, "connect", return_value=Connection(cursor)):
        with pytest.raises(OwnershipError, match="Concurrent"):
            ledger.save_transition(item(OwnershipState.CLAIM_PENDING), expected_revision=3)
    assert len(cursor.statements) == 1


def test_identity_change_rejected():
    old = (49227, 12, 98, item().version, "CAPTURADO", None, 1)
    cursor = Cursor(old)
    with patch.object(ledger, "connect", return_value=Connection(cursor)):
        with pytest.raises(OwnershipError, match="identities"):
            ledger.save_transition(item(OwnershipState.CLAIM_PENDING), expected_revision=1)


def test_transition_is_audited():
    old = (49227, 12, 99, item().version, "CAPTURADO", None, 1)
    cursor = Cursor(old)
    with patch.object(ledger, "connect", return_value=Connection(cursor)):
        assert ledger.save_transition(item(OwnershipState.CLAIM_PENDING), expected_revision=1) == 2
    assert "UPDATE eddy_ownership" in cursor.statements[1][0]
    assert "INSERT INTO eddy_ownership_events" in cursor.statements[2][0]
