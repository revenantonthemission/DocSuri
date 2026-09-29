"""Protected chrony NTS observations. Missing source, ownership or native context fails closed."""

import ctypes
import hashlib
import ipaddress
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from ..contracts.codec import canonical, decode, digest
from ..contracts.models import U64, Digest, Ref, Value
from ..deployment.launchd import protected_bytes, protected_chain
from .clock import ClockSample, ClockUnavailable


@dataclass(frozen=True)
class NativeTime:
    continuous_ns: int
    wall_us: int
    boot_id: str
    resume_id: str


def native_time():
    if sys.platform != "darwin":
        raise ClockUnavailable("native clock context unavailable")
    library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    query = library.sysctlbyname
    query.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                      ctypes.c_void_p, ctypes.c_size_t]
    query.restype = ctypes.c_int

    def parameter(name):
        size = ctypes.c_size_t(128)
        buffer = ctypes.create_string_buffer(size.value)
        if query(name.encode(), buffer, ctypes.byref(size), None, 0) or not 0 < size.value <= 128:
            raise ClockUnavailable("kernel clock context unavailable")
        return buffer.raw[:size.value]

    class Timebase(ctypes.Structure):
        _fields_ = [("numer", ctypes.c_uint32), ("denom", ctypes.c_uint32)]

    base = Timebase()
    library.mach_timebase_info.argtypes = [ctypes.POINTER(Timebase)]
    library.mach_timebase_info.restype = ctypes.c_int
    if library.mach_timebase_info(ctypes.byref(base)) or not base.denom:
        raise ClockUnavailable("continuous clock timebase unavailable")
    library.mach_continuous_time.argtypes = []
    library.mach_continuous_time.restype = ctypes.c_uint64
    boot = parameter("kern.bootsessionuuid").rstrip(b"\x00").decode("ascii")
    wake = hashlib.sha256(parameter("kern.waketime")).hexdigest()
    now = library.mach_continuous_time() * base.numer // base.denom
    wall = time.time_ns() // 1000
    if (
        parameter("kern.bootsessionuuid").rstrip(b"\x00").decode("ascii") != boot
        or hashlib.sha256(parameter("kern.waketime")).hexdigest() != wake
    ):
        raise ClockUnavailable("kernel clock epoch changed")
    return NativeTime(now, wall, boot, wake)


class NTSFrame(Value):
    status: Literal["AVAILABLE"] = "AVAILABLE"
    utc_us: U64
    continuous_ns: U64
    uncertainty_us: Annotated[int, Field(ge=0, le=1_000_000)]
    drift_ppm: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    boot_id: Ref
    resume_id: Ref
    authenticated: bool
    source: Literal["time.cloudflare.com"]
    address: Ref
    config_digest: Digest


def fields(text):
    result = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = (part.strip() for part in line.split(":", 1))
            if key in result:
                raise ValueError("duplicate chrony field")
            result[key] = value
    return result


def number(value):
    result = Decimal(value.split()[0])
    if not result.is_finite():
        raise ValueError("nonfinite chrony observation")
    return result


def selected_source(text):
    selected = [line.split() for line in text.splitlines() if line.startswith("^*")]
    if len(selected) != 1 or len(selected[0]) < 7:
        raise ValueError("unique selected NTP server required")
    row = selected[0]
    address = str(ipaddress.ip_address(row[1]))
    if not row[5].isdigit() or not 0 <= int(row[5]) < 30 or int(row[4], 8) == 0:
        raise ValueError("NTP source measurement stale")
    return address


def make_frame(reports, before: NativeTime, after: NativeTime, *, config_digest):
    try:
        if any(not isinstance(text, str) or len(text.encode()) > 16384
               for text in reports.values()):
            raise ValueError("chrony report bounds")
        elapsed_us = (after.continuous_ns - before.continuous_ns) // 1000
        if (
            not 0 <= elapsed_us < 1_000_000 or before.boot_id != after.boot_id
            or before.resume_id != after.resume_id
            or abs((after.wall_us - before.wall_us) - elapsed_us) > 10_000
        ):
            raise ValueError("clock context changed during observation")
        address = selected_source(reports["sources"])
        auth = [line.split() for line in reports["authdata"].splitlines()
                if line.split() and line.split()[0] == address]
        if (
            len(auth) != 1 or len(auth[0]) != 10 or auth[0][1] != "NTS"
            or int(auth[0][2]) < 1 or int(auth[0][3]) not in {15, 30}
            or int(auth[0][4]) < 128 or int(auth[0][7]) != 0
            or not 1 <= int(auth[0][8]) <= 8
            or reports["sourcename"].strip() != "time.cloudflare.com"
        ):
            raise ValueError("NTS authentication unavailable")
        packet = fields(reports["ntpdata"])
        if (
            packet["Remote address"].split()[0] != address
            or packet["Authenticated"] != "Yes" or packet["Leap status"] != "Normal"
            or packet["NTP tests"].replace(" ", "") != "1111111111"
            or int(packet["Total good RX"]) < 1
        ):
            raise ValueError("authenticated NTP response unproven")
        first, tracking = fields(reports["tracking_before"]), fields(reports["tracking"])
        reference = (f"{int(ipaddress.ip_address(address)):08X}"
                     if ipaddress.ip_address(address).version == 4 else
                     hashlib.md5(ipaddress.ip_address(address).packed,
                                 usedforsecurity=False).hexdigest()[:8].upper())
        if (
            first["Reference ID"] != tracking["Reference ID"]
            or first["Ref time (UTC)"] != tracking["Ref time (UTC)"]
            or tracking["Reference ID"].split()[0] != reference
            or tracking["Leap status"] != "Normal" or not 1 <= int(tracking["Stratum"]) <= 15
        ):
            raise ValueError("chrony tracking changed or is not synchronised")
        offset = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?) seconds (slow|fast) of NTP time",
                              tracking["System time"])
        if offset is None:
            raise ValueError("unsupported chrony offset")
        correction = Decimal(offset[1]) * (1 if offset[2] == "slow" else -1)
        delay, dispersion = number(tracking["Root delay"]), number(tracking["Root dispersion"])
        skew = number(tracking["Skew"])
        if min(delay, dispersion, skew) < 0:
            raise ValueError("negative clock error bound")
        uncertainty = int(((delay / 2 + dispersion) * 1_000_000).to_integral_value(
            rounding=ROUND_CEILING)) + elapsed_us + 1
        drift = abs(number(tracking["Frequency"])) + abs(number(tracking["Residual freq"])) + skew
        return NTSFrame(
            utc_us=str(after.wall_us + int(correction * 1_000_000)),
            continuous_ns=str(after.continuous_ns), uncertainty_us=uncertainty,
            drift_ppm=float(drift), boot_id=after.boot_id, resume_id=after.resume_id,
            authenticated=True, source="time.cloudflare.com", address=address,
            config_digest=config_digest,
        )
    except Exception:
        raise ClockUnavailable("current NTS observation unavailable") from None


def publish_frame(path: Path, frame: NTSFrame | None):
    content = canonical(frame.model_dump(mode="json") if frame else {"status": "UNAVAILABLE"})
    descriptor, temporary = tempfile.mkstemp(prefix=".clock-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), 0o444)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


class ProtectedClock:
    def __init__(self, path: Path, *, writer_uid: int, config_digest: str, context=native_time,
                 trusted_root=Path("/Library/Application Support/DocSuri")):
        self.path, self.writer_uid, self.config_digest = path, writer_uid, config_digest
        self.context, self.trusted_root = context, trusted_root

    def __call__(self):
        try:
            self.path.relative_to(self.trusted_root)
            for parent in self.path.parents:
                value = parent.lstat()
                if (
                    not stat.S_ISDIR(value.st_mode) or value.st_uid not in {0, self.writer_uid}
                    or value.st_mode & 0o022
                ):
                    raise ValueError("unprotected clock directory")
                if parent == self.trusted_root:
                    break
            before = self.context()
            raw = protected_bytes(self.path, owner=self.writer_uid, limit=16384)
            frame = NTSFrame.model_validate_json(canonical(decode(raw, max_bytes=16384)))
            after = self.context()
            if (
                before.boot_id != after.boot_id or before.resume_id != after.resume_id
                or frame.config_digest != self.config_digest or frame.authenticated is not True
            ):
                raise ValueError("clock producer or epoch changed")
            sample = ClockSample(int(frame.utc_us), int(frame.continuous_ns), frame.uncertainty_us,
                                 frame.drift_ppm, frame.boot_id, frame.resume_id, True)
            return sample.window(continuous_ns=after.continuous_ns, boot_id=after.boot_id,
                                 resume_id=after.resume_id)
        except Exception:
            raise ClockUnavailable("protected NTS clock unavailable") from None


class ChronyCollector:
    def __init__(self, executable: Path, executable_digest: str, socket: Path, config_digest: str):
        self.executable, self.executable_digest = executable, executable_digest
        self.socket, self.config_digest = socket, config_digest

    def collect(self):
        try:
            protected_chain(self.executable)
            executable = protected_bytes(self.executable, limit=64 * 1024**2)
            if digest(executable) != self.executable_digest:
                raise ValueError("chronyc artifact changed")
            socket = self.socket.lstat()
            if (
                "," in str(self.socket) or not stat.S_ISSOCK(socket.st_mode)
                or socket.st_uid != os.geteuid()
            ):
                raise ValueError("protected local chrony socket required")
            before = native_time()
            deadline = time.monotonic() + 0.9

            def query(*args):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("NTS observation budget")
                result = subprocess.run(
                    [str(self.executable), "-n", "-h", str(self.socket), *args],
                    capture_output=True, text=True, timeout=remaining, check=True,
                    stdin=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                )
                if len(result.stdout.encode()) > 16384:
                    raise ValueError("chrony report limit")
                return result.stdout

            reports = {"tracking_before": query("tracking"), "sources": query("sources")}
            address = selected_source(reports["sources"])
            reports.update(authdata=query("authdata"), ntpdata=query("ntpdata", address),
                           sourcename=query("sourcename", address), tracking=query("tracking"))
            return make_frame(reports, before, native_time(), config_digest=self.config_digest)
        except Exception:
            raise ClockUnavailable("native NTS collection unavailable") from None
