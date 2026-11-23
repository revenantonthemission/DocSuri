"""Files and folders reached only through folder descriptors (your answer of 2026-11-10,
"Fix both and sweep the rest").

A program that runs as root and works inside a folder another account owns must never
act on a path that account can change: the account could put a symbolic link at a name,
a second name of another file (a hard link) at a name, or a link in place of a folder on
the way. Every such place is therefore reached here the way the installation log reaches
its own (`checklist.InstallationLog`):

- the walk starts from a root-owned base (the arrangement's prefix, or a system folder
  root owns) and opens every folder below it relative to its parent with
  `O_DIRECTORY | O_NOFOLLOW`, so a link at any of them is refused;
- a file is created relative to its folder's descriptor with `O_CREAT | O_EXCL |
  O_NOFOLLOW` (which never follows a link and never reuses a name), and its mode and owner
  are set with `os.fchmod` and the caller's `give(descriptor)` on its own descriptor
  before it is closed;
- a rename is `os.replace` and a removal `os.unlink`, both relative to the folder's
  descriptor;
- an existing file is opened with `O_NOFOLLOW | O_NONBLOCK` and refused unless it is a
  regular file (with one name, and the expected owner, where the caller asks for them).

Every refusal is a `PathRefused` whose message is a fixed key: nothing was written, read
or given away.
"""

from __future__ import annotations

import contextlib
import errno
import hashlib
import os
import stat
from collections.abc import Callable, Collection, Iterator
from pathlib import Path


class PathRefused(OSError):
    """A walk or an open met another thing than the folder or file it expects; the
    message (and `reason`) is a fixed key."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


FOLDER_IS_A_LINK = "folder-is-a-link"
FILE_IS_A_LINK = "file-is-a-link"
NOT_ITS_OWN_FILE = "not-its-own-file"
_LINK_ERRORS = (errno.ELOOP, errno.ENOTDIR)
# A UNIX-domain socket answers open(2) with ENXIO on Linux and EOPNOTSUPP on macOS; a FIFO
# opened for writing without a reader answers ENXIO; a folder answers EISDIR.
_NOT_ITS_OWN_FILE_ERRORS = (errno.ENXIO, errno.EISDIR, errno.EOPNOTSUPP)
_NO_LINK_FOLDER = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def walk_base(prefix: Path, folder: Path) -> Path:
    """The root-owned folder a walk to `folder` starts from: the prefix when `folder` is
    the prefix or lies under it, otherwise `folder` itself (a system folder root owns,
    such as `/Library/LaunchDaemons`, which may itself be reached through the system's
    own links, as `/etc` is)."""
    if folder == prefix or prefix in folder.parents:
        return prefix
    return folder


def open_folder(base: Path, folder: Path, *, create: bool = False, mode: int = 0o777) -> int:
    """`folder` as a descriptor: `base` is opened (made first when missing and `create`),
    then each folder below it is made when missing and `create` (at `mode`, less the
    umask) and opened relative to its parent with `O_NOFOLLOW`. A link, or another thing
    than a folder, at any of them is refused with `FOLDER_IS_A_LINK`; without `create`,
    a missing folder raises `FileNotFoundError`."""
    names = folder.relative_to(base).parts
    if create:
        base.mkdir(parents=True, exist_ok=True)
    current = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in names:
            if create:
                with contextlib.suppress(FileExistsError):
                    os.mkdir(name, mode, dir_fd=current)
            child = open_child_folder(current, name)
            os.close(current)
            current = child
    except BaseException:
        os.close(current)
        raise
    return current


def open_child_folder(folder: int, name: str) -> int:
    """One folder relative to its parent's descriptor, never through a link."""
    try:
        return os.open(name, _NO_LINK_FOLDER, dir_fd=folder)
    except OSError as error:
        if error.errno in _LINK_ERRORS:
            raise PathRefused(FOLDER_IS_A_LINK) from None
        raise


@contextlib.contextmanager
def folder_at(base: Path, folder: Path, *, create: bool = False,
              mode: int = 0o777) -> Iterator[int]:
    """`open_folder` as a context: the descriptor is closed on the way out."""
    descriptor = open_folder(base, folder, create=create, mode=mode)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def write_all(descriptor: int, data: bytes) -> None:
    """Every byte: `os.write` may write fewer (a full disk partway through)."""
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise OSError(errno.EIO, "short-write")
        view = view[written:]


def read_all(descriptor: int, limit: int | None = None) -> bytes:
    """Every byte from the descriptor, or at most `limit` + 1 when a limit is given (so a
    caller can tell an oversized file)."""
    chunks, size = [], 0
    while chunk := os.read(descriptor, 1 << 20):
        chunks.append(chunk)
        size += len(chunk)
        if limit is not None and size > limit:
            break
    return b"".join(chunks)


def create_file(folder: int, name: str, content: bytes, *, mode: int,
                give: Callable[[int], None] | None = None) -> None:
    """A new file relative to its folder's descriptor: `O_CREAT | O_EXCL | O_NOFOLLOW`
    (a name already taken, a link included, raises `FileExistsError` and nothing is
    written), then its mode with `os.fchmod` and its owner with `give(descriptor)`, both on
    its own descriptor, before its bytes go in and before it is closed. A failure after
    the create removes the new name again."""
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode,
                         dir_fd=folder)
    try:
        os.fchmod(descriptor, mode)
        if give is not None:
            give(descriptor)
        write_all(descriptor, content)
        os.fsync(descriptor)
    except BaseException:
        os.close(descriptor)
        with contextlib.suppress(OSError):
            os.unlink(name, dir_fd=folder)
        raise
    os.close(descriptor)


def _refusal(error: OSError) -> OSError:
    if error.errno == errno.ELOOP:
        return PathRefused(FILE_IS_A_LINK)
    if error.errno in _NOT_ITS_OWN_FILE_ERRORS:
        return PathRefused(NOT_ITS_OWN_FILE)
    return error


def open_existing(folder: int, name: str, flags: int = os.O_RDONLY, *,
                  single_name: bool = True, owners: Collection[int] | None = None) -> int:
    """An existing file relative to its folder's descriptor, opened with `O_NOFOLLOW |
    O_NONBLOCK` (a planted FIFO is refused at once instead of waiting). A link is refused
    with `FILE_IS_A_LINK`; anything but a regular file, a file with more than one name
    when `single_name`, and a file whose owner is not one of `owners` when they are
    given, with `NOT_ITS_OWN_FILE` (the descriptor closed). A missing file raises
    `FileNotFoundError`."""
    try:
        descriptor = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=folder)
    except OSError as error:
        raise _refusal(error) from None
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or (single_name and info.st_nlink != 1) or (
            owners is not None and info.st_uid not in owners
        ):
            raise PathRefused(NOT_ITS_OWN_FILE)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def read_regular(base: Path, path: Path, *, single_name: bool = True,
                 limit: int | None = None) -> bytes | None:
    """A regular file's bytes through the no-link walk from `base`; None when the file or
    a folder on the way is absent. A link, or another thing than the file, is refused."""
    try:
        folder = open_folder(base, path.parent)
    except FileNotFoundError:
        return None
    try:
        try:
            descriptor = open_existing(folder, path.name, single_name=single_name)
        except FileNotFoundError:
            return None
    finally:
        os.close(folder)
    try:
        return read_all(descriptor, limit)
    finally:
        os.close(descriptor)


def sha256_at(base: Path, path: Path, *, owners: Collection[int] | None = None) -> str | None:
    """A file's SHA-256 through the no-link walk from `base`, read only when it is a
    regular file with one name (and owned by one of `owners`, when given). None when the
    file or a folder on the way is absent, or when the walk or the open refuses it: a link
    at the file or at a folder on the way, a second name, a FIFO or a socket is never
    read (your answer of 2026-11-10, "Fix both and sweep the rest")."""
    try:
        with folder_at(base, path.parent) as folder:
            descriptor = open_existing(folder, path.name, owners=owners)
    except OSError:
        return None
    try:
        accumulator = hashlib.sha256()
        while block := os.read(descriptor, 1 << 20):
            accumulator.update(block)
        return accumulator.hexdigest()
    finally:
        os.close(descriptor)


def lexists(folder: int, name: str) -> bool:
    """Whether a name exists in the folder, a link included (never followed)."""
    try:
        os.stat(name, dir_fd=folder, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def remove(folder: int, name: str) -> None:
    """The name removed relative to its folder's descriptor (a link itself, never what it
    points to); an absent name is nothing to do."""
    with contextlib.suppress(FileNotFoundError):
        os.unlink(name, dir_fd=folder)


def replace(folder: int, source: str, target: str) -> None:
    """`source` renamed over `target`, both relative to the same folder's descriptor."""
    os.replace(source, target, src_dir_fd=folder, dst_dir_fd=folder)


def create_new(base: Path, path: Path, content: bytes, *, mode: int,
               give: Callable[[int], None] | None = None, folder_mode: int = 0o777) -> None:
    """A new file at `path` (never one that is there), its folder reached by the no-link
    walk from `base` and made when missing."""
    with folder_at(base, path.parent, create=True, mode=folder_mode) as folder:
        create_file(folder, path.name, content, mode=mode, give=give)


def write_replacing(base: Path, target: Path, content: bytes, *, mode: int,
                    give: Callable[[int], None] | None = None,
                    pending_suffix: str = ".docsuri-pending",
                    folder_mode: int = 0o777) -> None:
    """`target`'s bytes replaced atomically: a pending file beside it is created new
    (any leftover pending name removed first), given its mode and owner on its own
    descriptor, then renamed over the target, all relative to the folder's descriptor."""
    pending = target.name + pending_suffix
    with folder_at(base, target.parent, create=True, mode=folder_mode) as folder:
        remove(folder, pending)
        create_file(folder, pending, content, mode=mode, give=give)
        replace(folder, pending, target.name)
