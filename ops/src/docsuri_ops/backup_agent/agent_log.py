"""The backup agent's own log (U8 plan Step 62(c); NFR9.8).

`cli.run` appends one line per run, refusals included, to
`<agent folder>/logs/backup-agent.log` (in production
`/Library/DocSuri/backup-agent/logs/backup-agent.log`, in the folder the arrangement
makes for the backup account).

- The folder is made at 0700 when it is absent and never used when it is a link; the
  file is opened with `O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW` at 0600, relative to
  the folder's own descriptor.
- The line is built by an `EventLog(strict=True)` the agent owns (`backend/log_events.py`);
  the agent never calls `log_events.configure`, which would replace the root logger's
  handlers and the process-wide log.
- It holds `component` `backup-agent`, `event` `command.answered` or `command.refused`,
  `state` (the word, when it is one of the agent's words), `reason` (the refusal's key)
  and `durationMs`: no database name, path, volume identity or address.
- A line that cannot be written (a planted link, a folder that is not the agent's) is
  skipped, and nothing outside the folder is touched. Logging never changes the word's
  result.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from backend.log_events import EventLog

COMPONENT = "backup-agent"
FOLDER = "logs"
FILE = "backup-agent.log"
ANSWERED = "command.answered"
REFUSED = "command.refused"


def line(*, word: str | None, reason: str | None, duration_ms: int) -> dict:
    """The one JSON object a run logs; a field outside its registered form is left out."""
    fields: dict = {"durationMs": duration_ms}
    if word is not None:
        fields["state"] = word
    if reason is not None:
        fields["reason"] = reason
    events = EventLog(strict=True)
    try:
        return events.line(COMPONENT, REFUSED if reason is not None else ANSWERED, **fields)
    except ValueError:
        # A key outside the registered form is dropped rather than written.
        kept = {"durationMs": duration_ms}
        return events.line(COMPONENT, REFUSED if reason is not None else ANSWERED, **kept)


def _open_folder(folder: Path) -> int | None:
    """The logs folder's descriptor: made at 0700 when absent, never followed as a link."""
    path = folder / FOLDER
    try:
        os.mkdir(path, 0o700)
    except FileExistsError:
        pass
    except OSError:
        return None
    try:
        info = os.lstat(path)
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return None
    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError:
        return None


def append(folder: Path, *, word: str | None, reason: str | None, duration_ms: int) -> bool:
    """Append the run's line; False when it could not be written (and nothing changed)."""
    payload = (json.dumps(line(word=word, reason=reason, duration_ms=duration_ms),
                          sort_keys=True, separators=(",", ":")) + "\n").encode()
    directory = _open_folder(folder)
    if directory is None:
        return False
    try:
        descriptor = os.open(FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
    except OSError:
        return False
    finally:
        os.close(directory)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return False
        os.write(descriptor, payload)
        return True
    except OSError:
        return False
    finally:
        os.close(descriptor)
