"""The standing job's thin adapter to `sudo` and the fixed programs (U8 plan Step 35;
security-design § 5.2, D6).

The scheduler account holds only unattended grants, so every call is `sudo -n -u
<account> <fixed program> <word>`: a password prompt can never appear, and a rule that
does not allow the call fails at once. The only two pieces here:

- `run_fixed`: one fixed program's one word, its input as bounded JSON on standard
  input, its one JSON result read from standard output;
- `ledger_copy`: `docsuri-ledger copy` (as the service account) piped into
  `docsuri-backup-agent ledger-copy` (as the backup account), so the copy reaches the
  agent only as a stream; each program's JSON result comes on its standard error.

Its parsing is tested with recorded output, and its real calls run only at the
installation (measured in `.coveragerc.u8-macos`).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path

SUDO = "/usr/bin/sudo"
BIN = Path("/Library/DocSuri/release/ops/bin")
SERVICE = "_docsuri_v2"
BACKUP = "_docsuri_r1t_backup"
PROGRAM_SECONDS = 1800
MAX_RESULT = 64 * 1024


def sudo_argv(account: str, program: str, word: str, *, folder: Path = BIN) -> list[str]:
    return [SUDO, "-n", "-u", account, str(folder / program), word]


def last_json(stream: bytes) -> dict:
    """The program's one JSON result: its last line, a JSON object."""
    lines = [line for line in stream[-MAX_RESULT:].splitlines() if line.strip()]
    if not lines:
        raise ValueError("no-result")
    value = json.loads(lines[-1])
    if not isinstance(value, dict):
        raise ValueError("no-result")
    return value


def run_fixed(account: str, program: str, word: str, document: dict | None = None, *,
              run: Callable = subprocess.run, folder: Path = BIN) -> dict:
    completed = run(sudo_argv(account, program, word, folder=folder),
                    input=json.dumps(document or {}).encode(), capture_output=True,
                    timeout=PROGRAM_SECONDS, check=False, env={"PATH": "/usr/bin:/bin"})
    result = last_json(completed.stdout)
    if completed.returncode != 0 or not result.get("ok", False):
        raise RuntimeError(str(result.get("reason", "program-refused")))
    return result


def ledger_copy(*, popen: Callable = subprocess.Popen, folder: Path = BIN) -> dict:
    """The ledger component's copy streamed into the agent: (ledger result, agent
    result), each read from its program's standard error."""
    environment = {"PATH": "/usr/bin:/bin"}
    source = popen(sudo_argv(SERVICE, "docsuri-ledger", "copy", folder=folder),
                   stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                   env=environment)
    try:
        sink = popen(sudo_argv(BACKUP, "docsuri-backup-agent", "ledger-copy", folder=folder),
                     stdin=source.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     env=environment)
        if source.stdout is not None:
            source.stdout.close()  # the agent alone holds the stream now
        _, agent_errors = sink.communicate(timeout=PROGRAM_SECONDS)
    finally:
        source_errors = source.stderr.read() if source.stderr is not None else b""
        source.wait(timeout=PROGRAM_SECONDS)
    ledger = last_json(source_errors)
    agent = last_json(agent_errors)
    if source.returncode != 0 or sink.returncode != 0 or not agent.get("ok"):
        raise RuntimeError(str(agent.get("reason") or ledger.get("reason") or "copy-refused"))
    return {"head": ledger, "agent": agent}
