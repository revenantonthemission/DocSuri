"""The runtime isolation check's thin adapter to macOS's tools (U8 plan Step 35; D10).

Every tool the check needs is run here, through one `run` callable, and its output is
parsed by a function of its own, so the parsing is tested with recorded output and the
real tools run only on this Mac at the installation (measured in `.coveragerc.u8-macos`):
`launchctl print`, `pfctl -s info` and `pfctl -a … -s rules`, `diskutil info`, `tmutil
isexcluded`, `otool -L`, `lsof`, `dscl` and the runtime's `psql` (`SHOW hba_file`, `SHOW
ident_file`). A
tool that fails or answers outside its expected form yields `None`, which the check
records as a failed item, never as a pass.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Callable

LAUNCHCTL = "/bin/launchctl"
PFCTL = "/sbin/pfctl"
DISKUTIL = "/usr/sbin/diskutil"
TMUTIL = "/usr/bin/tmutil"
OTOOL = "/usr/bin/otool"
LSOF = "/usr/sbin/lsof"
DSCL = "/usr/bin/dscl"
ANCHOR = "com.apple/org.docsuri.v2"
TOOL_SECONDS = 10


# --- parsing (recorded output) -----------------------------------------------------------


def parse_launchctl_print(text: str) -> dict | None:
    """`launchctl print system/<label>`: its state and pid."""
    state = re.search(r"^\s*state = (.+)$", text, re.MULTILINE)
    if state is None:
        return None
    pid = re.search(r"^\s*pid = (\d+)$", text, re.MULTILINE)
    return {"state": state.group(1).strip(), "pid": int(pid.group(1)) if pid else None}


def parse_print_disabled(text: str) -> dict[str, bool]:
    """`launchctl print-disabled system`: each label's disabled flag."""
    found = {}
    for label, value in re.findall(r'"([^"]+)"\s*=>\s*(true|false|disabled|enabled)', text):
        found[label] = value in ("true", "disabled")
    return found


def parse_pf_info(text: str) -> bool | None:
    match = re.search(r"^Status:\s+(Enabled|Disabled)", text, re.MULTILINE)
    return None if match is None else match.group(1) == "Enabled"


def rules_digest(text: str) -> str:
    """The loaded anchor's rules, one per line with spacing normalized, as a digest."""
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def parse_diskutil_info(text: str) -> dict | None:
    """`diskutil info <volume>`: whether it is present, locked and encrypted."""
    if "Could not find disk" in text:
        return {"present": False}
    fields = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    if "Volume Name" not in fields and "Device Node" not in fields:
        return None
    return {"present": True,
            "locked": fields.get("Locked", "No").startswith("Yes"),
            "encrypted": fields.get("FileVault", fields.get("Encrypted", "No")).startswith("Yes")}


def parse_tmutil_isexcluded(text: str) -> bool | None:
    match = re.search(r"^\[(Excluded|Included)\]", text.strip(), re.MULTILINE)
    return None if match is None else match.group(1) == "Excluded"


def parse_otool(text: str) -> list[str] | None:
    """`otool -L <program>`: the libraries it loads (the first line names the program)."""
    lines = text.splitlines()
    if not lines or "is not an object file" in text:
        return None
    return [line.strip().split(" (compatibility", 1)[0] for line in lines[1:] if line.strip()]


def parse_lsof_listen(text: str) -> list[tuple[str, str]] | None:
    """`lsof -nP -iTCP:<port> -sTCP:LISTEN`: each listener's user and address."""
    rows = [line.split() for line in text.splitlines() if line.strip()]
    if not rows:
        return []
    if rows[0][:3] != ["COMMAND", "PID", "USER"]:
        return None
    found = []
    for row in rows[1:]:
        if len(row) < 9:
            return None
        address = row[-2] if row[-1] == "(LISTEN)" else row[-1]
        found.append((row[2], address))
    return found


def parse_show(text: str) -> str | None:
    """`psql -At -c 'SHOW <setting>'`: the one line of a setting's value, an absolute path
    here; anything else (no line, several lines, a relative value) is no answer."""
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1 or not lines[0].startswith("/"):
        return None
    return lines[0].strip()


def parse_dscl(text: str) -> dict | None:
    uid = re.search(r"^UniqueID:\s*(-?\d+)$", text, re.MULTILINE)
    shell = re.search(r"^UserShell:\s*(\S+)$", text, re.MULTILINE)
    if uid is None or shell is None:
        return None
    return {"uid": int(uid.group(1)), "shell": shell.group(1)}


# --- the tools ---------------------------------------------------------------------------


class MacTools:
    def __init__(self, run: Callable = subprocess.run):
        self.run = run

    def _out(self, argv: list[str], *, ok_codes: tuple[int, ...] = (0,),
             **options) -> str | None:
        try:
            completed = self.run(argv, capture_output=True, timeout=TOOL_SECONDS, check=False,
                                 **options)
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode not in ok_codes:
            return None
        return (completed.stdout or b"").decode("utf-8", "replace")

    def job(self, label: str) -> dict | None:
        text = self._out([LAUNCHCTL, "print", f"system/{label}"])
        return None if text is None else parse_launchctl_print(text)

    def disabled(self) -> dict[str, bool]:
        text = self._out([LAUNCHCTL, "print-disabled", "system"])
        return {} if text is None else parse_print_disabled(text)

    def filter_enabled(self) -> bool | None:
        text = self._out([PFCTL, "-s", "info"])
        return None if text is None else parse_pf_info(text)

    def anchor_digest(self) -> str | None:
        text = self._out([PFCTL, "-a", ANCHOR, "-s", "rules"])
        return None if text is None else rules_digest(text)

    def volume(self, name: str) -> dict | None:
        """`diskutil info` writes a missing volume's `Could not find disk` line to standard
        error with exit 1 (measured on this Mac, U8 plan Step 74(d)), so an exit 1 also
        reads standard error; every other tool reads standard output alone."""
        try:
            completed = self.run([DISKUTIL, "info", name], capture_output=True,
                                 timeout=TOOL_SECONDS, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode not in (0, 1):
            return None
        text = (completed.stdout or b"").decode("utf-8", "replace")
        if completed.returncode == 1:
            text += (getattr(completed, "stderr", None) or b"").decode("utf-8", "replace")
        return parse_diskutil_info(text)

    def excluded(self, path: str) -> bool | None:
        text = self._out([TMUTIL, "isexcluded", path])
        return None if text is None else parse_tmutil_isexcluded(text)

    def libraries(self, program: str) -> list[str] | None:
        text = self._out([OTOOL, "-L", program], ok_codes=(0, 1))
        return None if text is None else parse_otool(text)

    def listeners(self, port: int) -> list[tuple[str, str]] | None:
        text = self._out([LSOF, "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"], ok_codes=(0, 1))
        return None if text is None else parse_lsof_listen(text)

    def _show(self, psql: str, socket: str, uid: int, setting: str) -> str | None:
        """One server setting, asked as the database account (`uid`) over the private
        socket as the superuser (`render.SUPERUSER`), the login the installer uses: peer,
        through the one map the rendered `pg_ident.conf` holds, no password; `-w` never
        waits for a password prompt. `extra_groups=[]` drops root's supplementary groups
        too: CPython calls setgroups() only when it is given."""
        from docsuri_ops.arrangement.render import SUPERUSER

        text = self._out([psql, "-X", "-w", "-At", "-h", socket, "-p", "15432", "-U",
                          SUPERUSER, "-d", "postgres", "-c", f"SHOW {setting}"],
                         user=uid, group=uid, extra_groups=[])
        return None if text is None else parse_show(text)

    def hba_file(self, psql: str, socket: str, uid: int) -> str | None:
        """The server's effective `hba_file`."""
        return self._show(psql, socket, uid, "hba_file")

    def ident_file(self, psql: str, socket: str, uid: int) -> str | None:
        """The server's effective `ident_file` (your answer of 2026-11-11)."""
        return self._show(psql, socket, uid, "ident_file")

    def account(self, name: str) -> dict | None:
        text = self._out([DSCL, ".", "-read", f"/Users/{name}", "UniqueID", "UserShell"])
        return None if text is None else parse_dscl(text)
