"""Immutable generations and atomic heads; an absent head is uninitialized, never inferred."""

import fcntl
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from ..contracts.codec import canonical, decode, digest
from ..contracts.models import GateVerdict
from ..domain.generation import (
    DurabilityReceipt,
    ImportedGeneration,
    collectible,
    receipt_matches,
)


class PublicationConflict(RuntimeError):
    pass


def durable_file(path: Path, data: bytes) -> None:
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(fd)
            if hasattr(fcntl, "F_FULLFSYNC"):
                fcntl.fcntl(fd, fcntl.F_FULLFSYNC)
    finally:
        os.close(fd)


def flush_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_regular(path: Path, limit: int) -> bytes:
    import stat

    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("expected regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("file byte limit")
        return data
    finally:
        os.close(fd)


def safe_relative(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if (
        not name
        or str(path) != name
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in name
        or "\x00" in name
        or name == "manifest.json"
    ):
        raise ValueError("invalid generation path")
    return path


class GenerationStore:
    """Constructing/reading never creates files. Provisioning is an explicit writer action.

    seal copies bytes into a fresh publisher-owned directory. Consumer pin resolves a head ONCE
    and returns fully verified bytes; it never follows a mutable current symlink during imports.
    Cross-UID ownership/revocation is enforced by the protected host launcher, not this class.
    """

    def __init__(self, root: Path):
        self.root = root.absolute()

    def provision(self) -> None:
        if self.root.is_symlink():
            raise ValueError("publication root is a symlink")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        (self.root / "generations").mkdir(mode=0o700, exist_ok=True)
        fd = os.open(self.root / "publication.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        flush_directory(self.root)

    @contextmanager
    def _lock(self):
        fd = os.open(self.root / "publication.lock", os.O_RDWR | os.O_NOFOLLOW)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            os.close(fd)

    def seal(self, files: dict[str, bytes]) -> str:
        if not files or len(files) > 10_000 or sum(map(len, files.values())) > 256 * 1024**2:
            raise ValueError("generation size limit")
        for name in files:
            safe_relative(name)
        manifest = {name: digest(data) for name, data in sorted(files.items())}
        manifest_bytes = canonical(manifest)
        generation = digest(manifest_bytes).split(":", 1)[1]
        destination = self.root / "generations" / generation
        with self._lock():
            if destination.exists():
                self._read_generation(generation)
                return generation
            staged = Path(tempfile.mkdtemp(prefix="staged-", dir=self.root))
            # Failed staging is retained as evidence, never published. Maintenance cleans it.
            for name, data in files.items():
                target = staged / name
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                durable_file(target, data)
                target.chmod(0o400)
            durable_file(staged / "manifest.json", manifest_bytes)
            (staged / "manifest.json").chmod(0o400)
            for directory in sorted(
                (p for p in staged.rglob("*") if p.is_dir()),
                key=lambda p: len(p.parts),
                reverse=True,
            ):
                flush_directory(directory)
                directory.chmod(0o500)
            flush_directory(staged)
            os.rename(staged, destination)
            destination.chmod(0o500)
            flush_directory(destination.parent)
        return generation

    def head(self) -> dict | None:
        try:
            value = decode(read_regular(self.root / "head.json", 16_384))
        except FileNotFoundError:
            return None
        if (
            not isinstance(value, dict)
            or set(value) != {"generation", "revision", "previous"}
            or not isinstance(value["revision"], int)
            or isinstance(value["revision"], bool)
            or value["revision"] < 1
        ):
            raise ValueError("invalid binding head")
        return value

    def activate(self, generation: str, *, expected: dict | None, guard) -> dict:
        if guard is None:
            raise PermissionError("current publication authority required")
        with self._lock():
            if self.head() != expected:
                raise PublicationConflict("head changed")
            self._read_generation(generation)
            new = {
                "generation": generation,
                "revision": (expected or {}).get("revision", 0) + 1,
                "previous": digest(canonical(expected)) if expected else None,
            }
            with guard():
                fd, name = tempfile.mkstemp(prefix="head-", dir=self.root)
                os.close(fd)
                Path(name).unlink()  # only this newly created staging file
                durable_file(Path(name), canonical(new))
                os.replace(name, self.root / "head.json")
                flush_directory(self.root)
            return new

    def _read_generation(self, generation: str) -> dict[str, bytes]:
        import re

        if not isinstance(generation, str) or not re.fullmatch("[0-9a-f]{64}", generation):
            raise ValueError("invalid generation identity")
        root = self.root / "generations" / generation
        if root.is_symlink():
            raise ValueError("generation symlink")
        raw = read_regular(root / "manifest.json", 16 * 1024**2)
        if digest(raw) != "sha256:" + generation:
            raise ValueError("manifest integrity mismatch")
        manifest = decode(raw)
        if not isinstance(manifest, dict) or len(manifest) > 10_000:
            raise ValueError("invalid manifest")
        actual = set()
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("generation symlink")
            if path.is_file() and path != root / "manifest.json":
                actual.add(path.relative_to(root).as_posix())
        if actual != set(manifest):
            raise ValueError("generation file set mismatch")
        result = {}
        total = 0
        for name, expected in manifest.items():
            safe_relative(name)
            path = root / name
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("generation path escape")
            content = read_regular(path, 256 * 1024**2)
            total += len(content)
            if total > 256 * 1024**2 or digest(content) != expected:
                raise ValueError("generation integrity mismatch")
            result[name] = content
        return result

    def pin(self) -> tuple[dict, dict[str, bytes]]:
        head = self.head()
        if head is None:
            raise FileNotFoundError("publication is uninitialized")
        return head, self._read_generation(head["generation"])


def _erase_tree(root: Path) -> None:
    """Remove a collected generation deepest-first, widening each sealed entry as we go.

    A sealed generation is 0500/0400, so deletion has to reopen every directory and file. Doing
    it explicitly rather than through rmtree keeps the removal order reviewable and keeps a
    partially erased generation inside trash/, never inside the published namespace.
    """
    os.chmod(root, 0o700)
    directories = sorted(
        (p for p in root.rglob("*") if p.is_dir() and not p.is_symlink()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    # Widen every sealed directory first: unlinking an entry needs write access on its parent.
    for directory in directories:
        os.chmod(directory, 0o700)
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_symlink() or not path.is_dir():
            os.chmod(path, 0o600)
            path.unlink()
    for directory in directories:
        directory.rmdir()
    root.rmdir()


class PinRegistry:
    """Reader/backup pins. A pinned generation is never collected, even if it is not the head."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pins: dict[str, int] = {}

    def pin(self, generation: str) -> None:
        with self._lock:
            self._pins[generation] = self._pins.get(generation, 0) + 1

    def release(self, generation: str) -> None:
        with self._lock:
            remaining = self._pins.get(generation, 0) - 1
            if remaining < 0:
                raise ValueError("unheld generation pin")
            if remaining:
                self._pins[generation] = remaining
            else:
                del self._pins[generation]

    def held(self) -> frozenset[str]:
        with self._lock:
            return frozenset(self._pins)

    @contextmanager
    def hold(self, generation: str):
        self.pin(generation)
        try:
            yield
        finally:
            self.release(generation)


class GenerationBoundary(GenerationStore):
    """GenerationStore plus the durability receipt, verified import and pinned collection.

    Collection never uses rmtree. A collectible generation is renamed out of the published
    namespace in one step, so a crash leaves it visible in ``trash/`` rather than half-deleted
    inside ``generations/``, and never partially activated.
    """

    def __init__(self, root: Path, pins: PinRegistry | None = None):
        super().__init__(root)
        self.pins = pins if pins is not None else PinRegistry()

    # -- durability receipt ------------------------------------------------

    def _receipt_path(self, generation: str) -> Path:
        return self.root / "receipts" / f"{generation}.json"

    def write_receipt(self, generation: str, head_revision: int) -> DurabilityReceipt:
        """Written only after seal() and activate() returned, i.e. after everything is durable."""
        with self._lock():
            files = self._read_generation(generation)
            manifest = digest(canonical({n: digest(d) for n, d in sorted(files.items())}))
            body = {
                "generation": "sha256:" + generation,
                "manifest": manifest,
                "files": str(len(files)),
                "bytes": str(sum(len(d) for d in files.values())),
                "head_revision": str(head_revision),
            }
            body["receipt"] = digest(canonical(body))
            (self.root / "receipts").mkdir(mode=0o700, exist_ok=True)
            durable_file(self._receipt_path(generation), canonical(body))
            self._receipt_path(generation).chmod(0o400)
            flush_directory(self.root / "receipts")
        return DurabilityReceipt(**body)

    def receipt(self, generation: str) -> DurabilityReceipt:
        value = decode(read_regular(self._receipt_path(generation), 16_384))
        if not isinstance(value, dict) or set(value) != {
            "generation", "manifest", "files", "bytes", "head_revision", "receipt"
        }:
            raise ValueError("invalid durability receipt")
        body = {k: v for k, v in value.items() if k != "receipt"}
        if digest(canonical(body)) != value["receipt"]:
            raise ValueError("durability receipt is not self-consistent")
        return DurabilityReceipt(**value)

    def has_receipt(self, generation: str) -> bool:
        try:
            self.receipt(generation)
        except (FileNotFoundError, ValueError):
            return False
        return True

    def durable(self, generation: str) -> bool:
        """True only when a self-consistent receipt agrees with the generation on disk."""
        try:
            receipt = self.receipt(generation)
        except (FileNotFoundError, ValueError):
            return False
        try:
            files = self._read_generation(generation)
        except (FileNotFoundError, ValueError):
            return False
        head = self.head() or {}
        return receipt_matches(
            receipt,
            generation="sha256:" + generation,
            manifest=digest(canonical({n: digest(d) for n, d in sorted(files.items())})),
            files=len(files),
            total_bytes=sum(len(d) for d in files.values()),
            head_revision=int(head.get("revision", 0)),
        )

    # -- verified import ---------------------------------------------------

    def import_metadata(self, source: Path, *, expected_manifest: str | None = None
                        ) -> ImportedGeneration:
        """Verify a foreign generation and return its metadata. Publishes and activates nothing.

        A wrong manifest is a hard failure, not a verdict: importing unverified bytes must not
        be able to become a quiet BLOCKED entry that a later step treats as evidence.
        """
        if source.is_symlink():
            raise ValueError("import source is a symlink")
        if not source.is_dir():
            raise ValueError("import source is not a generation directory")
        raw = read_regular(source / "manifest.json", 16 * 1024**2)
        generation = digest(raw).split(":", 1)[1]
        if expected_manifest is not None and expected_manifest != "sha256:" + generation:
            raise ValueError("imported manifest is not the expected one")
        files = self._read_foreign(source, generation)
        return ImportedGeneration(
            generation="sha256:" + generation,
            manifest="sha256:" + generation,
            files=str(len(files)),
            bytes=str(sum(len(d) for d in files.values())),
            verifiable=GateVerdict.ELIGIBLE,
        )

    def _read_foreign(self, root: Path, generation: str) -> dict[str, bytes]:
        if root.is_symlink():
            raise ValueError("generation symlink")
        manifest = decode(read_regular(root / "manifest.json", 16 * 1024**2))
        if not isinstance(manifest, dict) or len(manifest) > 10_000:
            raise ValueError("invalid manifest")
        actual = set()
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("generation symlink")
            if path.is_file() and path != root / "manifest.json":
                actual.add(path.relative_to(root).as_posix())
        if actual != set(manifest):
            raise ValueError("generation file set mismatch")
        result, total = {}, 0
        for name, expected in manifest.items():
            safe_relative(name)
            path = root / name
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("generation path escape")
            content = read_regular(path, 256 * 1024**2)
            total += len(content)
            if total > 256 * 1024**2 or digest(content) != expected:
                raise ValueError("generation integrity mismatch")
            result[name] = content
        return result

    # -- collection --------------------------------------------------------

    def collect(self) -> tuple[str, ...]:
        """Remove unpinned, receipted, non-head generations.

        Interrupted collection leaves the generation in ``trash/``, never half-deleted inside
        ``generations/``, and never partially activated.
        """
        with self._lock():
            head = self.head() or {}
            current = head.get("generation")
            pins = self.pins.held()
            base = self.root / "generations"
            removed = []
            for entry in sorted(base.iterdir()):
                generation = entry.name
                if not entry.is_dir() or entry.is_symlink():
                    continue
                if not collectible(
                    generation, head=current, pins=pins, receipts=self._receipted()
                ):
                    continue
                trash = self.root / "trash"
                trash.mkdir(mode=0o700, exist_ok=True)
                os.chmod(entry, 0o700)
                os.rename(entry, trash / generation)
                flush_directory(base)
                flush_directory(trash)
                _erase_tree(trash / generation)
                removed.append(generation)
            if removed:
                flush_directory(base)
            return tuple(removed)

    def _receipted(self) -> frozenset[str]:
        directory = self.root / "receipts"
        if not directory.is_dir():
            return frozenset()
        return frozenset(
            path.name[:-5] for path in directory.iterdir()
            if path.is_file() and path.name.endswith(".json") and self.has_receipt(path.name[:-5])
        )
