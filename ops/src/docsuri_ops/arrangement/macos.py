"""The installer's thin adapter to macOS's tools (U8 plan Step 37; decision "Root paths and
accounts in tests").

Every tool the installer, its verification and the release command need is run here,
through one `run` callable, and each answer is parsed by a function of its own, so the
parsing is tested with recorded output and the real tools run only at the installation,
or in `ci.yml`'s `macos-filesystem` job (measured in `.coveragerc.u8-macos`): `dscl`,
`launchctl`, `pfctl`, `tmutil`, `security`, `diskutil`, `otool`, `plutil`, `visudo`,
`vm_stat`, `git` and the build tools. A tool that fails answers `None` or raises
`ToolFailed` with a fixed key, never a pass. Nothing here prints or logs an argument or
an input, so a password handed to `security` or `psql` on standard input stays there.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path

DSCL = "/usr/bin/dscl"
LAUNCHCTL = "/bin/launchctl"
PFCTL = "/sbin/pfctl"
TMUTIL = "/usr/bin/tmutil"
SECURITY = "/usr/bin/security"
DISKUTIL = "/usr/sbin/diskutil"
OTOOL = "/usr/bin/otool"
PLUTIL = "/usr/bin/plutil"
VISUDO = "/usr/sbin/visudo"
VM_STAT = "/usr/bin/vm_stat"
GIT = "/usr/bin/git"
SYSTEM_KEYCHAIN = "/Library/Keychains/System.keychain"
TOOL_SECONDS = 60
BUILD_SECONDS = 3600
FETCH_SECONDS = 120
MAX_FETCH = 512 * 1024 * 1024
NO_LOGIN = "/usr/bin/false"
NO_HOME = "/var/empty"


class ToolFailed(RuntimeError):
    """A tool did not do what was asked; the message is a fixed key."""


# --- parsing (recorded output) -----------------------------------------------------------


def parse_dscl_user(text: str) -> dict | None:
    uid = re.search(r"^UniqueID:\s*(-?\d+)$", text, re.MULTILINE)
    shell = re.search(r"^UserShell:\s*(\S+)$", text, re.MULTILINE)
    gid = re.search(r"^PrimaryGroupID:\s*(-?\d+)$", text, re.MULTILINE)
    if uid is None or shell is None:
        return None
    return {"uid": int(uid.group(1)), "shell": shell.group(1),
            "gid": int(gid.group(1)) if gid else None}


def parse_vm_stat(text: str) -> int | None:
    """Bytes available: free plus inactive pages (cicd-pipeline § 5.2)."""
    size = re.search(r"page size of (\d+) bytes", text)
    free = re.search(r"^Pages free:\s+(\d+)\.", text, re.MULTILINE)
    inactive = re.search(r"^Pages inactive:\s+(\d+)\.", text, re.MULTILINE)
    if size is None or free is None or inactive is None:
        return None
    return int(size.group(1)) * (int(free.group(1)) + int(inactive.group(1)))


def parse_plutil_lint(text: str) -> bool:
    lines = [line for line in text.splitlines() if line.strip()]
    return bool(lines) and all(line.rstrip().endswith(": OK") for line in lines)


def parse_visudo_check(text: str) -> bool:
    return "parsed OK" in text and "syntax error" not in text


def parse_tmutil_isexcluded(text: str) -> bool | None:
    match = re.search(r"^\[(Excluded|Included)\]", text.strip(), re.MULTILINE)
    return None if match is None else match.group(1) == "Excluded"


def parse_otool(text: str) -> list[str] | None:
    lines = text.splitlines()
    if not lines or "is not an object file" in text:
        return None
    return [line.strip().split(" (compatibility", 1)[0] for line in lines[1:] if line.strip()]


def parse_launchctl_state(text: str) -> str | None:
    match = re.search(r"^\s*state = (.+)$", text, re.MULTILINE)
    return None if match is None else match.group(1).strip()


def parse_diskutil_encrypted(text: str) -> dict | None:
    fields = {}
    for line in text.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    if "Volume Name" not in fields and "Device Node" not in fields:
        return None
    return {"locked": fields.get("Locked", "No").startswith("Yes"),
            "encrypted": fields.get("FileVault", fields.get("Encrypted", "No")).startswith("Yes"),
            "identifier": fields.get("Volume UUID")}


def loads_only_from(libraries: list[str], own: Path) -> bool:
    """`otool -L`'s closure stays within the program's own folder and the system's."""
    prefixes = (str(own).rstrip("/") + "/", "/usr/lib/", "/System/Library/", "@rpath/",
                "@loader_path/", "@executable_path/")
    return all(library.startswith(prefixes) for library in libraries)


# --- the tools ---------------------------------------------------------------------------


class MacTools:
    def __init__(self, run: Callable = subprocess.run, *,
                 fetch_url: Callable[[str, float], bytes] | None = None):
        self._run = run
        self._fetch = fetch_url

    def run(self, argv: list[str], *, input: bytes | None = None, user: int | None = None,
            group: int | None = None, cwd: Path | None = None, env: dict | None = None,
            seconds: float = TOOL_SECONDS, ok_codes: tuple[int, ...] = (0,)) -> bytes:
        """One tool, as `user` when given (the installer runs as root). A run as `user` also
        passes `extra_groups=[]`, so the child drops root's supplementary groups: CPython
        calls setgroups() only when `extra_groups` is given."""
        options: dict = {"capture_output": True, "timeout": seconds, "check": False}
        if input is not None:
            options["input"] = input
        if user is not None:
            options["user"], options["group"] = user, group if group is not None else user
            options["extra_groups"] = []
        if cwd is not None:
            options["cwd"] = str(cwd)
        if env is not None:
            options["env"] = env
        try:
            completed = self._run(argv, **options)
        except (OSError, subprocess.SubprocessError):
            raise ToolFailed(f"tool-unavailable:{Path(argv[0]).name}") from None
        if completed.returncode not in ok_codes:
            raise ToolFailed(f"tool-failed:{Path(argv[0]).name}")
        return completed.stdout or b""

    def _text(self, argv: list[str], **options) -> str | None:
        try:
            return self.run(argv, **options).decode("utf-8", "replace")
        except ToolFailed:
            return None

    # Accounts (Workflow 20 step 1).
    def account(self, name: str) -> dict | None:
        text = self._text([DSCL, ".", "-read", f"/Users/{name}", "UniqueID", "UserShell",
                           "PrimaryGroupID"])
        return None if text is None else parse_dscl_user(text)

    def create_account(self, name: str, uid: int) -> None:
        """A non-login account with no shell and no home, and its group of the same id."""
        group = f"/Groups/{name}"
        for argv in ([DSCL, ".", "-create", group], [DSCL, ".", "-create", group,
                                                      "PrimaryGroupID", str(uid)],
                     [DSCL, ".", "-create", f"/Users/{name}"],
                     [DSCL, ".", "-create", f"/Users/{name}", "UniqueID", str(uid)],
                     [DSCL, ".", "-create", f"/Users/{name}", "PrimaryGroupID", str(uid)],
                     [DSCL, ".", "-create", f"/Users/{name}", "UserShell", NO_LOGIN],
                     [DSCL, ".", "-create", f"/Users/{name}", "NFSHomeDirectory", NO_HOME],
                     [DSCL, ".", "-create", f"/Users/{name}", "IsHidden", "1"]):
            self.run(argv)

    # Files.
    def owner(self, path: Path) -> int | None:
        try:
            return path.lstat().st_uid
        except FileNotFoundError:
            return None

    def moved(self, source: Path, target: Path) -> None:
        """A file renamed over another keeps its own owner; nothing to do on macOS."""

    def chown(self, path: Path, uid: int, gid: int) -> None:
        os.chown(path, uid, gid, follow_symlinks=False)

    def fchown(self, descriptor: int, uid: int, gid: int) -> None:
        """An owner set on an open file's or folder's own descriptor, never through a
        path (your answer of 2026-11-10, "Fix both and sweep the rest")."""
        os.fchown(descriptor, uid, gid)

    def descriptor_owner(self, descriptor: int) -> int:
        return os.fstat(descriptor).st_uid

    def chmod(self, path: Path, mode: int) -> None:
        if path.is_symlink():
            raise ToolFailed("chmod-through-link-refused")
        os.chmod(path, mode)

    def clone(self, source: Path, target: Path) -> None:
        """An APFS clone (`cp -c`), sharing blocks; a later change reaches neither."""
        self.run(["/bin/cp", "-c", str(source), str(target)])

    # Launch jobs.
    def job_state(self, label: str) -> str | None:
        text = self._text([LAUNCHCTL, "print", f"system/{label}"])
        return None if text is None else parse_launchctl_state(text)

    def bootstrap(self, definition: Path) -> None:
        self.run([LAUNCHCTL, "bootstrap", "system", str(definition)], ok_codes=(0, 5, 37))

    def bootout(self, domain_label: str) -> None:
        self.run([LAUNCHCTL, "bootout", domain_label], ok_codes=(0, 3, 113))

    def restart(self, domain_label: str) -> None:
        """A loaded job killed and started again (`kickstart -k`): a restart, never a
        stop, so every stop still goes through service control."""
        self.run([LAUNCHCTL, "kickstart", "-k", domain_label])

    # Rules.
    def plist_lint(self, path: Path) -> bool:
        text = self._text([PLUTIL, "-lint", str(path)], ok_codes=(0, 1))
        return text is not None and parse_plutil_lint(text)

    def sudoers_check(self, path: Path) -> bool:
        try:
            completed = self._run([VISUDO, "-c", "-f", str(path)], capture_output=True,
                                  timeout=TOOL_SECONDS, check=False)
        except (OSError, subprocess.SubprocessError):
            return False
        text = (completed.stdout or b"").decode("utf-8", "replace") + (
            completed.stderr or b"").decode("utf-8", "replace")
        return completed.returncode == 0 and parse_visudo_check(text)

    def anchor_check(self, path: Path) -> bool:
        return self._text([PFCTL, "-n", "-f", str(path)]) is not None

    def anchor_rules(self) -> str | None:
        return self._text([PFCTL, "-a", "com.apple/org.docsuri.v2", "-s", "rules"])

    # Time Machine (security-design § 6.7).
    def exclude(self, path: str) -> None:
        self.run([TMUTIL, "addexclusion", "-p", path])

    def excluded(self, path: str) -> bool | None:
        text = self._text([TMUTIL, "isexcluded", path])
        return None if text is None else parse_tmutil_isexcluded(text)

    # The System keychain (D5): the secret goes in on standard input only.
    def keychain_add(self, service: str, account: str, secret: bytes, *,
                     keychain: str = SYSTEM_KEYCHAIN) -> None:
        """`security -i` reads its command from standard input, so the secret is never
        a process argument. The secret is hexadecimal (`keychain.generate`), so it needs
        no quoting."""
        if not re.fullmatch(rb"[0-9a-f]{32,128}", secret) or not re.fullmatch(
            r"[A-Za-z0-9_.-]{1,64}", service
        ) or not re.fullmatch(r"[a-z0-9_.-]{1,64}", account):
            raise ToolFailed("keychain-item-outside-its-form")
        command = (f'add-generic-password -U -s "{service}" -a "{account}" -w "'.encode()
                   + secret + f'" "{keychain}"\n'.encode())
        self.run([SECURITY, "-i"], input=command)

    def keychain_has(self, service: str, *, keychain: str = SYSTEM_KEYCHAIN) -> bool:
        return self._text([SECURITY, "find-generic-password", "-s", service, keychain]) is not None

    def keychain_read(self, service: str, *, keychain: str = SYSTEM_KEYCHAIN) -> bytearray:
        """One item's value, read back as root (`-w` prints it on standard output), without
        the one newline `security` prints after it, as a buffer the caller clears. An
        absent item raises `ToolFailed`."""
        value = bytearray(self.run([SECURITY, "find-generic-password", "-s", service, "-w",
                                    keychain]))
        if value.endswith(b"\n"):
            del value[-1]
        return value

    # Volumes.
    def volume(self, name: str) -> dict | None:
        text = self._text([DISKUTIL, "info", name], ok_codes=(0, 1))
        return None if text is None else parse_diskutil_encrypted(text)

    # Programs.
    def libraries(self, program: Path) -> list[str] | None:
        text = self._text([OTOOL, "-L", str(program)], ok_codes=(0, 1))
        return None if text is None else parse_otool(text)

    def memory_available(self) -> int | None:
        text = self._text([VM_STAT])
        return None if text is None else parse_vm_stat(text)

    def fetch(self, url: str) -> bytes:
        if not url.startswith("https://"):
            raise ToolFailed("fetch-refused")
        if self._fetch is not None:
            return self._fetch(url, FETCH_SECONDS)
        request = urllib.request.Request(url, headers={"User-Agent": "docsuri-installer"})
        try:
            with urllib.request.urlopen(request, timeout=FETCH_SECONDS) as answer:  # noqa: S310
                data = answer.read(MAX_FETCH + 1)
        except OSError:
            raise ToolFailed("fetch-failed") from None
        if len(data) > MAX_FETCH:
            raise ToolFailed("fetch-too-large")
        return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
