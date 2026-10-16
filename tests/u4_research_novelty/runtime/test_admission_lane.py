"""Internal recovery reserves capacity and always restores its caller context."""

import pytest

from backend.control_runtime import RECOVERY_REQUEST
from backend.modules.research.admission import ResearchAdmission
from backend.transactions import Busy, UnknownCommit


@pytest.mark.parametrize("method", ["recover_prepared", "reconcile_release"])
@pytest.mark.parametrize("failure", [None, Busy, UnknownCommit])
@pytest.mark.parametrize("initial", [False, True])
def test_recovery_lane_restores_context(method, failure, initial):
    class Transactions:
        def run(self, owner, action):
            assert owner == "research"
            assert RECOVERY_REQUEST.get() is True
            if failure:
                raise failure("synthetic recovery failure")
            return None

    admission = ResearchAdmission(Transactions())
    token = RECOVERY_REQUEST.set(initial)
    try:
        action = getattr(admission, method)
        args = (None,) if method == "reconcile_release" else ()
        if failure:
            with pytest.raises(failure):
                action(*args)
        else:
            assert not action(*args)
        assert RECOVERY_REQUEST.get() is initial
    finally:
        RECOVERY_REQUEST.reset(token)
