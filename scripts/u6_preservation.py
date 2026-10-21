"""The destructive archive of a U6 environment (cicd-pipeline §4.4; security design D14).

U5's preservation deletes nothing. U6's deletes the token key, because a key kept beside
the preserved database would let the preserved sealed tokens be opened. Its order:

1. **Every check first**, as U5's `archive_owned` runs them: the preservation identity
   (an expired environment is accepted), the manifest identity, the running container
   and the volume, the application port idle, nothing open in the folder, the file
   inventory, the database identity with no other client, a free destination name, the
   resources once more and an acknowledged database stop. The inventory requires every
   folder at 0700 and every regular file at 0600 with one link, with one exception: the
   key file and one first-key staging name in `export-keys/` that share one inode with
   exactly two links each, the state a crash during first-key creation leaves.
2. **Then the key file, as the single deciding step.** Every leftover staging file is
   removed first; if any removal fails the archive refuses before the key unlink, with
   the key untouched and the environment stopped and intact. Then one `unlink` of the
   key file and a sync of the key folder. Once it succeeds the sealed tokens can never
   be opened again.
3. **Then the rest of the key folder**: the marker, the lock file and the folder. These
   hold no key material, so a failure here is reported and the archive goes on.
4. **Last, the rename** of the environment folder, then a sync of its parent.

A refusal at any check of step 1 leaves the key folder intact. The helpers come in
through `ArchiveContext`, built by `scripts/verify_docsuri_u6.py`, so this module never
imports the runner (R-05). The key-folder names and the staging pattern are imported
from the token keyring, which alone defines them.
"""

from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from backend.modules.export.token_keyring import KEY_FILE, STAGING_NAME

FOLDER_MODE = 0o700
FILE_MODE = 0o600
PRESERVED_PREFIX = "docsuri-u6-preserved-"


@dataclass(frozen=True)
class ArchiveContext:
    """The runner's helpers; every one is a check or an action the runner owns."""

    run: Path
    key_folder: Path
    database: str
    refused: type[Exception]
    identity: Callable[[Path], dict]
    resources: Callable[[dict], None]
    idle_port: Callable[[], None]
    open_files: Callable[[Path], object]
    inventory: Callable[[Path], list[Path]]
    connect_admin: Callable[[dict], object]
    stop_database: Callable[[dict], None]
    sync: Callable[[Path], None]


def remove(path: Path) -> None:
    """One unlink; the single place the archive deletes a file."""
    os.unlink(path)


def _custody_refusal(entry: Path) -> bool:
    """Whether one entry breaks custody; links are judged separately."""
    info = entry.lstat()
    directory = stat.S_ISDIR(info.st_mode)
    return (
        info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != (FOLDER_MODE if directory else FILE_MODE)
        or not (directory or stat.S_ISREG(info.st_mode))
    )


def _first_key_pair(entry: Path, context: ArchiveContext) -> bool:
    """An entry that may carry two links: the key file or a first-key staging name."""
    return entry.parent == context.key_folder and (
        entry.name == KEY_FILE or STAGING_NAME.fullmatch(entry.name) is not None
    )


def check_inventory(entries: list[Path], context: ArchiveContext) -> None:
    """Folders 0700, files 0600 with one link; only the first-key staging pair differs."""
    linked: dict[tuple[int, int], list[str]] = {}
    for entry in entries:
        if _custody_refusal(entry):
            raise context.refused("preservation entry custody differs")
        info = entry.lstat()
        if stat.S_ISDIR(info.st_mode) or info.st_nlink == 1:
            continue
        if info.st_nlink != 2 or not _first_key_pair(entry, context):
            raise context.refused("preservation entry custody differs")
        linked.setdefault((info.st_dev, info.st_ino), []).append(entry.name)
    if not linked:
        return
    names = next(iter(linked.values()))
    if len(linked) != 1 or len(names) != 2 or KEY_FILE not in names:
        raise context.refused("preservation entry custody differs")


def check_database(value: dict, context: ArchiveContext) -> None:
    with context.connect_admin(value) as conn:
        identity = conn.execute(
            "SELECT run_id,current_database() FROM public.docsuri_local_identity"
        ).fetchone()
        if tuple(identity or ()) != (value["runId"], context.database):
            raise context.refused("preservation database identity differs")
        active = conn.execute(
            "SELECT count(*) FROM pg_stat_activity WHERE pid<>pg_backend_pid() "
            "AND backend_type='client backend'"
        ).fetchone()[0]
        if active:
            raise context.refused("other database clients prevent safe preservation")


def checks(path: Path, context: ArchiveContext) -> tuple[dict, Path]:
    """Step 1: every check, then an acknowledged database stop. Nothing is deleted."""
    value = context.identity(path)
    context.resources(value)
    context.idle_port()
    opened = context.open_files(context.run)
    if opened.returncode != 1 or opened.stdout.strip():
        raise context.refused("owned directory is in use or custody could not be checked")
    check_inventory(context.inventory(context.run), context)
    check_database(value, context)
    destination = context.run.with_name(
        f"{PRESERVED_PREFIX}{value['runId']}-{secrets.token_hex(4)}"
    )
    if destination.exists() or destination.is_symlink():
        raise context.refused("preservation destination exists")
    context.resources(value)
    context.stop_database(value)
    return value, destination


def delete_key(context: ArchiveContext) -> bool:
    """Step 2: staging files first, then the single key unlink. Returns whether a key
    file was there; any failure refuses with the key untouched."""
    folder = context.key_folder
    if not folder.is_dir():
        return False
    staged = [entry for entry in folder.iterdir() if STAGING_NAME.fullmatch(entry.name)]
    for entry in staged:
        try:
            remove(entry)
        except OSError:
            raise context.refused(
                "a staging file could not be removed; the key is untouched and the "
                "environment is stopped and intact"
            ) from None
    key = folder / KEY_FILE
    present = key.exists() or key.is_symlink()
    if present:
        try:
            remove(key)
        except OSError:
            raise context.refused(
                "the key file could not be removed; it is untouched and the environment "
                "is stopped and intact"
            ) from None
    context.sync(folder)
    return present


def clear_key_folder(context: ArchiveContext) -> bool:
    """Step 3: the marker, the lock file and the folder; no key material remains."""
    if not context.key_folder.is_dir():
        return True
    complete = True
    for entry in list(context.key_folder.iterdir()):
        try:
            remove(entry)
        except OSError:
            complete = False
    try:
        context.key_folder.rmdir()
    except OSError:
        complete = False
    return complete


def archive(path: Path, context: ArchiveContext) -> dict:
    """The destructive archive; its result adds `keyDeleted: true` to U5's fields."""
    value, destination = checks(path, context)
    key_found = delete_key(context)
    folder_cleared = clear_key_folder(context)
    try:
        os.rename(context.run, destination)
    except OSError:
        raise context.refused(
            "the environment folder could not be renamed; it stays stopped under its own "
            "name without its key"
        ) from None
    context.sync(destination.parent)
    return {
        "state": "preserved",
        "path": str(destination),
        "runId": value["runId"],
        "expiresAt": value["expiresAt"],
        "containerStopped": True,
        "volumePreserved": value["volume"],
        "keyDeleted": True,
        "keyFileFound": key_found,
        "keyFolderRemoved": folder_cleared,
    }
