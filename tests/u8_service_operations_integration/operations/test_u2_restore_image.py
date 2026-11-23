"""U2's restore rehearsal accepts U1's pinned image or U8's pinned database image, each
matched exactly, and refuses every other image (Step 6, the person's decision of
2026-10-22).

Both of `IsolatedRestore`'s image checks run here: the manifest's recorded
`databaseImage` (constructor) and the running container's configured image
(`_verify_container`). The profile and `docker` are stand-ins, so no U2 environment is
touched; U2's own restore files prove the rehearsal itself in U2's realm and in the
`u2-regression` phase.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from docsuri_ops import u2_restore
from docsuri_ops.arrangement import runtimes
from docsuri_ops.u2_restore import IsolatedRestore, RestoreRefused

U1_IMAGE = "postgres@sha256:a3b7f434b2dc57ce85a67e171163eb8ab1a1ebcb39d27484661f26b1dfbe30d6"
U8_IMAGE = "docsuri/u8-postgres:16.14-pgvector-0.8.7-r2"
RUN = "docsuri-u2-0123456789abcdef"
NEAR_MISSES = (
    U1_IMAGE[:-1] + "7",  # one digest character changed
    U1_IMAGE.removeprefix("postgres@"),  # the bare digest
    "postgres:16.14",
    U1_IMAGE.upper(),
    "docsuri/u8-postgres:16.14-pgvector-0.8.7-r1",  # an earlier build revision
    "docsuri/u8-postgres:16.14-pgvector-0.8.7-r3",
    "docsuri/u8-postgres:16.14-pgvector-0.8.6-r2",  # another pgvector release
    "docsuri/u8-postgres:16.15-pgvector-0.8.7-r2",  # another server release
    U8_IMAGE + " ",
    "docker.io/" + U8_IMAGE,
    U8_IMAGE + "@sha256:" + "0" * 64,
    "pgvector/pgvector:0.8.7-pg16",
    "",
)


def make_profile(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        realm="account-controls", database_name="docsuri_u2", root=root, run_id=RUN,
        expires_at=time.time() + 3600,
    )


@pytest.fixture
def construct(tmp_path, monkeypatch):
    """Build an `IsolatedRestore` whose manifest records `image`; the container check is
    recorded rather than run, so only the constructor's own image check decides."""
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    verified = []

    def build(image: str | None) -> IsolatedRestore:
        record = {"container": RUN, "volume": RUN + "-pgdata"}
        if image is not None:
            record["databaseImage"] = image
        monkeypatch.setattr(u2_restore.LocalProfile, "load", lambda _path: make_profile(root))
        monkeypatch.setattr(u2_restore, "private_bytes", lambda _path: json.dumps(record).encode())
        monkeypatch.setattr(
            IsolatedRestore, "_verify_container", lambda self: verified.append(self)
        )
        return IsolatedRestore(
            root / "environment.json", source_digest="s", policy_digest="p",
            manifest_digest="m",
        )

    build.verified = verified
    return build


def container_check(record: dict) -> None:
    """Run `_verify_container` alone against a stand-in `docker inspect` answer."""
    restore = object.__new__(IsolatedRestore)
    restore.run = RUN
    volume = {"Labels": {"dev.docsuri.u2.run": RUN}}

    def docker(arguments, **_kwargs):
        return json.dumps([volume if arguments[0] == "volume" else record]).encode()

    restore._docker = docker
    restore._verify_container()


def container(image: str, *, memory: int = 1024**3, status: str = "running") -> dict:
    return {
        "Config": {"Labels": {"dev.docsuri.u2.run": RUN}, "Image": image},
        "State": {"Status": status},
        "HostConfig": {"Memory": memory},
    }


def test_the_accepted_images_are_u1s_pin_and_u8s_single_definition():
    assert u2_restore.IMAGE == U1_IMAGE
    assert runtimes.DATABASE_IMAGE_TAG == U8_IMAGE
    assert u2_restore.ACCEPTED_IMAGES == (U1_IMAGE, runtimes.DATABASE_IMAGE_TAG)


@pytest.mark.parametrize("image", [U1_IMAGE, U8_IMAGE])
def test_both_pinned_images_pass_the_manifest_check(construct, image):
    restore = construct(image)
    assert construct.verified == [restore]


@pytest.mark.parametrize("image", [*NEAR_MISSES, None])
def test_any_third_image_is_refused_by_the_manifest_check(construct, image):
    with pytest.raises(RestoreRefused, match="U2 container identity differs"):
        construct(image)
    assert construct.verified == []


@pytest.mark.parametrize("image", [U1_IMAGE, U8_IMAGE])
def test_both_pinned_images_pass_the_container_check(image):
    container_check(container(image))


@pytest.mark.parametrize("image", NEAR_MISSES)
def test_any_third_image_is_refused_by_the_container_check(image):
    with pytest.raises(RestoreRefused, match="owned bounded database container unavailable"):
        container_check(container(image))


@pytest.mark.parametrize("image", [U1_IMAGE, U8_IMAGE])
@pytest.mark.parametrize("memory", [2 * 1024**3, 512 * 1024**2, 0])
def test_the_one_gib_memory_check_is_unchanged_for_either_image(image, memory):
    with pytest.raises(RestoreRefused, match="owned bounded database container unavailable"):
        container_check(container(image, memory=memory))


def test_a_stopped_container_is_still_refused():
    with pytest.raises(RestoreRefused, match="owned bounded database container unavailable"):
        container_check(container(U8_IMAGE, status="exited"))
