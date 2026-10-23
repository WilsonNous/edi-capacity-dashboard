"""Durable EDDY ownership ledger; no Redmine writes or external effects.

Transitions are append-only audited and optimistic-version checked under an
InnoDB row lock. The Redmine adapter must confirm authoritative assignments
before invoking confirm_claim/confirm_return in eddy_ownership.
"""
from __future__ import annotations

from ednna.eddy_ownership import Ownership, OwnershipError, OwnershipState
from ednna.mysql_storage import connect

DDL = (
    """CREATE TABLE IF NOT EXISTS eddy_ownership (
        issue_id BIGINT NOT NULL PRIMARY KEY,
        original_assignee_id BIGINT NOT NULL,
        eddy_assignee_id BIGINT NOT NULL,
        redmine_version VARCHAR(80) NOT NULL,
        state VARCHAR(48) NOT NULL,
        last_evidence TEXT NULL,
        revision BIGINT NOT NULL DEFAULT 1,
        updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
            ON UPDATE CURRENT_TIMESTAMP(6)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
    """CREATE TABLE IF NOT EXISTS eddy_ownership_events (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        issue_id BIGINT NOT NULL,
        revision BIGINT NOT NULL,
        state VARCHAR(48) NOT NULL,
        redmine_version VARCHAR(80) NOT NULL,
        evidence TEXT NULL,
        recorded_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
        UNIQUE KEY uq_ownership_revision (issue_id, revision),
        KEY idx_ownership_events_issue (issue_id, recorded_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
)


def _record(row) -> Ownership:
    return Ownership(
        issue_id=int(row[0]), original_assignee_id=int(row[1]),
        eddy_assignee_id=int(row[2]), version=row[3],
        state=OwnershipState(row[4]), last_evidence=row[5],
    )


def bootstrap_ownership() -> None:
    with connect() as conn:
        with conn.cursor() as cursor:
            for statement in DDL:
                cursor.execute(statement)


def load_ownership(issue_id: int) -> tuple[Ownership, int] | None:
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT issue_id, original_assignee_id, eddy_assignee_id,
                          redmine_version, state, last_evidence, revision
                   FROM eddy_ownership WHERE issue_id=%s""", (issue_id,)
            )
            row = cursor.fetchone()
    return (_record(row), int(row[6])) if row else None


def save_transition(item: Ownership, *, expected_revision: int | None) -> int:
    """Persist exactly one validated transition, fail closed on concurrent edits.

    expected_revision=None creates the first CAPTURED record only. Subsequent
    writes require the revision returned by load_ownership/save_transition.
    No external Redmine action is performed here.
    """
    if not isinstance(item, Ownership):
        raise TypeError("Ownership required")
    if expected_revision is None and item.state != OwnershipState.CAPTURED:
        raise OwnershipError("Initial state must be CAPTURADO")
    if expected_revision is not None and expected_revision < 1:
        raise OwnershipError("Invalid expected revision")
    with connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """SELECT issue_id, original_assignee_id, eddy_assignee_id,
                          redmine_version, state, last_evidence, revision
                   FROM eddy_ownership WHERE issue_id=%s FOR UPDATE""",
                (item.issue_id,),
            )
            row = cursor.fetchone()
            if expected_revision is None:
                if row:
                    raise OwnershipError("Ownership already captured")
                revision = 1
                cursor.execute(
                    """INSERT INTO eddy_ownership
                       (issue_id, original_assignee_id, eddy_assignee_id,
                        redmine_version, state, last_evidence, revision)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (item.issue_id, item.original_assignee_id,
                     item.eddy_assignee_id, item.version, item.state.value,
                     item.last_evidence, revision),
                )
            else:
                if not row or int(row[6]) != expected_revision:
                    raise OwnershipError("Concurrent ownership revision change")
                prior = _record(row)
                if (prior.original_assignee_id != item.original_assignee_id or
                        prior.eddy_assignee_id != item.eddy_assignee_id):
                    raise OwnershipError("Ownership identities cannot change")
                if prior == item:
                    raise OwnershipError("No state change to persist")
                revision = expected_revision + 1
                cursor.execute(
                    """UPDATE eddy_ownership
                       SET redmine_version=%s, state=%s, last_evidence=%s,
                           revision=%s WHERE issue_id=%s AND revision=%s""",
                    (item.version, item.state.value, item.last_evidence,
                     revision, item.issue_id, expected_revision),
                )
                if cursor.rowcount != 1:
                    raise OwnershipError("Concurrent ownership update")
            cursor.execute(
                """INSERT INTO eddy_ownership_events
                   (issue_id, revision, state, redmine_version, evidence)
                   VALUES (%s,%s,%s,%s,%s)""",
                (item.issue_id, revision, item.state.value, item.version,
                 item.last_evidence),
            )
    return revision
