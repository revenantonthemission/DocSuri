"""Private immutable bytes; owner metadata and permission remain in owner stores."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

ARTIFACT_IDENTITY = re.compile(r"[0-9a-f]{32}\.blob")


@dataclass(frozen=True)
class Artifact:
    name: str
    sha256: str
    size: int


class ArtifactUnavailable(RuntimeError):
    pass


class PrivateArtifacts:
    def __init__(
        self, root: Path, *, maximum_bytes: int = 131072, production_root: Path | None = None
    ):
        expected = {
            Path("/tmp/docsuri-u1-run").resolve(),
            Path("/tmp/docsuri-u2-run").resolve(),
            Path("/tmp/docsuri-u3-run").resolve(),
            Path("/tmp/docsuri-u4-run").resolve(),
            Path("/tmp/docsuri-u5-run").resolve(),
            Path("/tmp/docsuri-u6-run").resolve(),
            Path("/tmp/docsuri-u8-run").resolve(),
        }
        if production_root is not None:
            # A9: the production profile's roots live under its validated root, and
            # only there; `for_profile` passes it, so no caller names a root by hand.
            expected = {production_root}
        if root.parent not in expected or root.name not in (
            "corpus-files",
            "assistance-files",
            "verification-mail",
        ):
            raise ValueError("artifact root outside explicit fixture allocation")
        # 16 MiB only for corpus sources under CorpusContent's production limits (U8 Step
        # 23, performance-design § 11); every other bound is the built one.
        if maximum_bytes not in (131072, 2097152) and not (
            maximum_bytes == 16777216 and root.name == "corpus-files"
        ):
            raise ValueError("unapproved artifact bound")
        root.mkdir(mode=0o700, exist_ok=True)
        info = root.lstat()
        if root.is_symlink() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError("artifact root is not private")
        self.root = root
        self.maximum_bytes = maximum_bytes

    @classmethod
    def for_profile(cls, profile, name: str, *, maximum_bytes: int = 131072) -> PrivateArtifacts:
        """The artifact root `name` of a profile: under the production profile's root for
        the production profile (A9), and the synthetic `/tmp` run roots otherwise."""
        production = profile.root if getattr(profile, "is_production", False) else None
        return cls(profile.root / name, maximum_bytes=maximum_bytes, production_root=production)

    def publish(self, content: bytes) -> Artifact:
        if not content or len(content) > self.maximum_bytes:
            raise ValueError("artifact size outside finite bound")
        name = uuid4().hex + ".blob"
        staging = self.root / ("." + name + ".part")
        destination = self.root / name
        try:
            fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            # A link cannot overwrite a previously published immutable name.
            os.link(staging, destination, follow_symlinks=False)
            staging.unlink()
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return Artifact(name, hashlib.sha256(content).hexdigest(), len(content))
        except OSError as exc:
            raise ArtifactUnavailable(
                "private publication failed; owner reconciliation required"
            ) from exc
        finally:
            staging.unlink(missing_ok=True)

    def read(self, artifact: Artifact) -> bytes:
        if not ARTIFACT_IDENTITY.fullmatch(artifact.name):
            raise ArtifactUnavailable("invalid artifact identity")
        if not 0 < artifact.size <= self.maximum_bytes:
            raise ArtifactUnavailable("invalid artifact bound")
        try:
            fd = os.open(self.root / artifact.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600
                ):
                    raise ArtifactUnavailable("artifact custody mismatch")
                content = stream.read(self.maximum_bytes + 1)
            if (
                len(content) != artifact.size
                or hashlib.sha256(content).hexdigest() != artifact.sha256
            ):
                raise ArtifactUnavailable("artifact is partial or corrupt")
            return content
        except OSError as exc:
            raise ArtifactUnavailable("artifact unavailable") from exc

    def erase(self, name: str) -> None:
        """Trusted owner erasure: one exact immutable name, idempotent after a crash."""
        if not ARTIFACT_IDENTITY.fullmatch(name):
            raise ArtifactUnavailable("invalid artifact identity")
        path = self.root / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            return
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ArtifactUnavailable("artifact custody mismatch")
        path.unlink()
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
