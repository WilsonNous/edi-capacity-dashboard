"""Identity contract after the Redmine rename from ednna.ia to eddy.ia."""
from unittest.mock import patch

import pytest

from ednna.eddy_vr01_integrated import _identity


def test_eddy_account_with_existing_id_166():
    with patch.dict("os.environ", {
        "REDMINE_EDNNA_USERNAME": "eddy.ia",
        "REDMINE_EDNNA_USER_ID": "166",
        "EDDY_REDMINE_USER_ID": "166",
    }):
        assert _identity() == 166


def test_old_username_rejected_after_rename():
    with patch.dict("os.environ", {
        "REDMINE_EDNNA_USERNAME": "ednna.ia",
        "REDMINE_EDNNA_USER_ID": "166",
        "EDDY_REDMINE_USER_ID": "166",
    }):
        with pytest.raises(ValueError, match="eddy.ia"):
            _identity()


def test_conflicting_user_ids_still_fail_closed():
    with patch.dict("os.environ", {
        "REDMINE_EDNNA_USERNAME": "eddy.ia",
        "REDMINE_EDNNA_USER_ID": "166",
        "EDDY_REDMINE_USER_ID": "167",
    }):
        with pytest.raises(ValueError, match="divergentes"):
            _identity()


def test_original_owner_is_not_eddy():
    with patch.dict("os.environ", {
        "REDMINE_EDNNA_USERNAME": "eddy.ia",
        "REDMINE_EDNNA_USER_ID": "97",
        "EDDY_REDMINE_USER_ID": "97",
    }):
        with pytest.raises(ValueError, match="nao identificada"):
            _identity()
