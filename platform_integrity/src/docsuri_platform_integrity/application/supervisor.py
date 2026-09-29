"""Bounded one-shot tool supervisor. No shell and no inherited credentials/environment."""

import fcntl
import os
import selectors
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from ..adapters.filesystem import durable_file, flush_directory, read_regular
from ..contracts.codec import canonical, digest


class RunBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class Tool:
    argv: tuple[str, ...]
    executable_digest: str
    timeout_s: float
    output_limit: int = 64 * 1024**2
    rss_limit: int = 2 * 1024**3


@dataclass(frozen=True)
class ToolResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    elapsed_s: float
    peak_rss: int


class Supervisor:
    def __init__(self, root: Path, tools: dict[str, Tool]):
        self.root = root
        self.tools = dict(tools)

    def run(self, name: str, *, additional_peak: int = 0) -> ToolResult:
        import psutil

        tool = self.tools[name]  # allowlisted composition-owned command, not arbitrary request argv
        executable = Path(tool.argv[0])
        if (
            not executable.is_absolute()
            or executable.is_symlink()
            or digest(read_regular(executable, 256 * 1024**2)) != tool.executable_digest
        ):
            raise RunBlocked("unverified tool executable")
        if not 0 < tool.timeout_s <= 1800 or additional_peak < 0:
            raise RunBlocked("invalid action budget")
        if shutil.disk_usage(self.root).free < 10 * 1024**3 + 2 * additional_peak:
            raise RunBlocked("insufficient disk reserve")
        # Installer owns root/lock. Do not unlink the lock inode or reclaim a stale marker blindly.
        lock_fd = os.open(self.root / "heavy.lock", os.O_RDWR | os.O_NOFOLLOW)
        process = None
        completed = False
        selector = selectors.DefaultSelector()
        marker = self.root / "holder.json"
        started = time.monotonic()
        try:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RunBlocked("heavy lane occupied") from exc
            if marker.exists():
                raise RunBlocked("previous holder needs reconciliation")
            durable_file(
                marker,
                canonical({"phase": "spawn_possible", "tool": name, "supervisor": os.getpid()}),
            )
            flush_directory(self.root)
            process = subprocess.Popen(
                tool.argv,
                cwd=self.root,
                env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8", "PYTHONUNBUFFERED": "1"},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            observed = psutil.Process(process.pid)
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            outputs = {process.stdout: bytearray(), process.stderr: bytearray()}
            peak_rss = 0
            while selector.get_map():
                if time.monotonic() - started > tool.timeout_s:
                    raise RunBlocked("tool deadline exceeded")
                try:
                    rss = sum(
                        p.memory_info().rss
                        for p in [observed, *observed.children(recursive=True)]
                        if p.is_running()
                    )
                except psutil.NoSuchProcess:
                    rss = 0
                peak_rss = max(rss, peak_rss)
                if peak_rss > tool.rss_limit:
                    raise RunBlocked("tool RSS limit exceeded")
                for key, _ in selector.select(timeout=0.05):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        outputs[key.fileobj].extend(chunk)
                        if sum(map(len, outputs.values())) > tool.output_limit:
                            raise RunBlocked("tool output limit exceeded")
            returncode = process.wait(
                timeout=max(0.01, tool.timeout_s - (time.monotonic() - started))
            )
            # A child may have closed inherited streams and outlived its parent. Detect the
            # process group before releasing the host-heavy slot; unknown remains fenced.
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                completed = True
            else:
                raise RunBlocked("tool descendants still running")
            return ToolResult(
                returncode,
                bytes(outputs[process.stdout]),
                bytes(outputs[process.stderr]),
                time.monotonic() - started,
                peak_rss,
            )
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    # A denied group signal cannot prove quiescence; keep the holder witness.
                    # Do not let cleanup hide the original resource-limit failure.
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    completed = False
                process.stdout.close()
                process.stderr.close()
            selector.close()
            if completed:
                marker.unlink()
                flush_directory(self.root)
            os.close(lock_fd)
