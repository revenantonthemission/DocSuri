"""The frozen operator plan: the identities a release is allowed to act on.

A plan is a build artifact, not an operator preference, so it is read through a protected
path and pinned to a digest the caller already trusts. The ``native_commit_guard`` capability
receipt records the plan digest as its artifact, so a receipt says exactly which plan it was
proven against.
"""

import os
import stat
from pathlib import Path
from typing import Annotated

from pydantic import Field

from ..contracts.codec import canonical, decode, digest
from ..contracts.models import Digest, Ref, Value

MAX_PLAN_BYTES = 256 * 1024
Identity = Annotated[str, Field(pattern=r"^[a-z][a-z0-9:._-]{0,127}$")]


class FrozenPlan(Value):
    """Identity to definition digest. A plan with no identities authorizes nothing."""

    release: Ref
    identities: Annotated[dict[Identity, Digest], Field(min_length=1, max_length=1024)]

    def definition(self, identity: str) -> str | None:
        return self.identities.get(identity)


def read_frozen_plan(path: Path, expected_digest: str, *, release: str,
                     owner: int | None = None) -> FrozenPlan:
    """Read a protected, digest-pinned plan for one release.

    The mode, ownership, link and size checks run before any byte is interpreted, and the
    digest is checked before parsing, so a substituted plan cannot be interpreted at all.
    """
    if path.is_symlink():
        raise PermissionError("frozen plan must not be a symlink")
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid not in ({0, os.getuid()} if owner is None else {owner})
        or stat.S_IMODE(info.st_mode) & 0o022
        or info.st_nlink != 1
        or info.st_size > MAX_PLAN_BYTES
    ):
        raise PermissionError("frozen plan owner or mode is not protected")
    data = path.read_bytes()
    if digest(data) != expected_digest:
        raise PermissionError("frozen plan digest does not match the pinned value")
    plan = FrozenPlan.model_validate_json(canonical(decode(data)))
    if plan.release != release:
        raise PermissionError("frozen plan belongs to another release")
    return plan
