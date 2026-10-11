"""Owned, finite native inference for the synthetic local research environment.

Only this supervisor may launch/stop its process group. It never connects to or
stops the user's default Ollama service, pulls models, or accepts a caller URL.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import socket
import stat
import subprocess
import threading
import time
from pathlib import Path

import httpx

GIB = 1024**3
MODEL_PINS = {
    "qwen3:8b": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41",
    "bge-m3:latest": "7907646426070047a77226ac3e684fbbe8410524f7b4a74d02837e43f2146bab",
}


class ModelUnavailable(RuntimeError):
    """No inference result may be accepted from this attempt."""


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pressure() -> int:
    result = subprocess.run(
        ["/usr/bin/memory_pressure", "-Q"],
        capture_output=True,
        text=True,
        timeout=3,
        check=True,
    )
    match = re.search(r"free percentage: (\d+)%", result.stdout)
    if not match:
        raise ModelUnavailable("memory pressure measurement unavailable")
    return int(match.group(1))


def validate_response(response: dict, *, model: str) -> None:
    if response.get("model") != model or response.get("error"):
        raise ModelUnavailable("model response identity or error mismatch")
    if model == "qwen3:8b":
        if response.get("done") is not True or response.get("done_reason") != "stop":
            raise ModelUnavailable("generation incomplete or output limit reached")
        if not 0 < response.get("eval_count", 0) <= 224:
            raise ModelUnavailable("generation token evidence outside policy")
        if not 0 < response.get("prompt_eval_count", 0) <= 1824:
            raise ModelUnavailable("source context exceeds reserved output capacity")
        message = response.get("message", {})
        if not isinstance(message.get("content"), str) or not message["content"].strip():
            raise ModelUnavailable("generation returned no usable text")


def validate_request(model: str, body: dict) -> None:
    if body.get("model") != model or model not in MODEL_PINS or body.get("keep_alive") != 0:
        raise ModelUnavailable("request model or lifetime outside policy")
    if len(json.dumps(body).encode()) > 16384:
        raise ModelUnavailable("model request allocation exceeded")
    options = body.get("options", {})
    expected = {"num_ctx": 2048, "num_thread": 2}
    if model == "qwen3:8b":
        expected.update(num_predict=224, temperature=0)
        fields = {"model", "messages", "stream", "think", "keep_alive", "options"}
        if "format" in body:
            fields.add("format")
            try:
                anchors = body["format"]["properties"]["citations"]["items"]["enum"]
                if body["format"] != grounded_format(anchors):
                    raise ValueError("unexpected schema")
            except (KeyError, TypeError, ValueError) as exc:
                raise ModelUnavailable("generation schema outside bounded contract") from exc
        if set(body) != fields or body.get("stream") is not False or body.get("think") is not False:
            raise ModelUnavailable("generation request policy mismatch")
        messages = body.get("messages", [])
        if len(messages) != 2 or [m.get("role") for m in messages] != ["system", "user"]:
            raise ModelUnavailable("generation messages outside bounded contract")
    else:
        if (
            set(body) != {"model", "input", "truncate", "keep_alive", "options"}
            or body.get("truncate") is not False
        ):
            raise ModelUnavailable("embedding request policy mismatch")
        texts = body.get("input", [])
        if (
            not isinstance(texts, list)
            or not 1 <= len(texts) <= 8
            or any(not isinstance(t, str) or not t.strip() or len(t.encode()) > 8192 for t in texts)
        ):
            raise ModelUnavailable("embedding input outside bounded contract")
    if options != expected:
        raise ModelUnavailable("model context/output options differ from finite policy")


def grounded_format(anchors: list[str]) -> dict:
    if (
        not isinstance(anchors, list)
        or not 1 <= len(anchors) <= 8
        or any(
            not isinstance(a, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", a)
            for a in anchors
        )
    ):
        raise ValueError("invalid bounded anchor vocabulary")
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "citations": {
                "type": "array",
                "items": {"type": "string", "enum": anchors},
                "minItems": 1,
                "maxItems": len(anchors),
                "uniqueItems": True,
            },
        },
        "required": ["text", "citations"],
    }


def validate_clone_allocation(created: list[str], before: dict, after: dict, growth: int) -> None:
    if created and growth > 64 * 1024**2:
        raise ModelUnavailable("model clone setup exceeded scratch growth allocation")
    if not created and after != before:
        raise ModelUnavailable("read-only model clone allocation changed")


class LocalModelRuntime:
    def __init__(self, root: Path, run_id: str, expires_at: float):
        if root != Path("/tmp/docsuri-u1-run").resolve():
            raise ValueError("explicit synthetic root required")
        raw = (root / "environment.json").read_bytes()
        marker = json.loads((root / "ownership.json").read_text())
        if marker != {"runId": run_id, "manifestSha256": hashlib.sha256(raw).hexdigest()}:
            raise ValueError("model supervisor environment custody mismatch")
        manifest = json.loads(raw)
        if manifest["expiresAt"] != expires_at or manifest["modelPort"] != 11439:
            raise ValueError("model supervisor policy mismatch")
        self.root = root / "model-runtime"
        self.run_id = run_id
        self.expires_at = expires_at
        self.process = None
        self.log = None
        self.permit = threading.BoundedSemaphore(1)
        self.samples = []
        self.last_response = None
        self.identity = {}

    def _floor(self, *, starting: bool) -> dict:
        free = shutil.disk_usage(self.root.parent).free
        available = pressure()
        sample = {"at": time.time(), "freeBytes": free, "memoryFreePercent": available}
        self.samples.append(sample)
        if free < 8 * GIB or available < (35 if starting else 20):
            raise ModelUnavailable("model resource floor reached")
        if time.time() >= self.expires_at:
            raise ModelUnavailable("synthetic model retention expired")
        return sample

    def _wait_admission(self, deadline: float) -> None:
        # GPU unload acknowledgement can precede release of host memory.
        # Wait within the same finite request deadline; never lower the floor.
        admission_deadline = min(deadline, time.monotonic() + 10)
        while True:
            try:
                self._floor(starting=True)
                if not self._request("/api/ps").get("models"):
                    return
            except ModelUnavailable:
                if (
                    time.time() >= self.expires_at
                    or shutil.disk_usage(self.root.parent).free < 8 * GIB
                ):
                    raise
            if time.monotonic() >= admission_deadline:
                raise ModelUnavailable("model resource admission deadline reached")
            time.sleep(0.25)

    def _prepare(self) -> None:
        starting = self._floor(starting=True)
        self.root.mkdir(mode=0o700, exist_ok=True)
        info = self.root.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700
        ):
            raise ModelUnavailable("model runtime root custody mismatch")
        marker = self.root / "run-id"
        if marker.exists():
            if marker.is_symlink() or marker.read_text() != self.run_id:
                raise ModelUnavailable("unknown model runtime allocation")
        else:
            if list(self.root.iterdir()):
                raise ModelUnavailable("unowned model runtime allocation")
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as stream:
                stream.write(self.run_id)
        original = Path.home() / ".ollama/models"
        target = self.root / "models"
        verified = {}
        created = []
        allocated_before = {}
        allocated_after = {}
        for model, expected in MODEL_PINS.items():
            name, tag = model.split(":")
            relative = Path(f"manifests/registry.ollama.ai/library/{name}/{tag}")
            manifest = original / relative
            if manifest.is_symlink() or file_hash(manifest) != expected:
                raise ModelUnavailable("cached model manifest differs from selected pin")
            data = json.loads(manifest.read_text())
            members = [(relative, expected)]
            for item in [data["config"], *data["layers"]]:
                digest = item["digest"]
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    raise ModelUnavailable("model blob identity malformed")
                members.append((Path("blobs") / digest.replace(":", "-"), digest[7:]))
            for relative, digest in members:
                source, destination = original / relative, target / relative
                allocated_before.setdefault(
                    str(relative), destination.stat().st_blocks * 512 if destination.exists() else 0
                )
                if source.is_symlink() or not source.is_file() or file_hash(source) != digest:
                    raise ModelUnavailable("cached model blob verification failed")
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                if destination.exists():
                    if destination.is_symlink() or file_hash(destination) != digest:
                        raise ModelUnavailable("owned model clone changed")
                else:
                    # APFS cloning preserves the existing shared cache and
                    # refuses an unsupported clone; no full-copy fallback.
                    subprocess.run(
                        ["/bin/cp", "-c", str(source), str(destination)], check=True, timeout=30
                    )
                    destination.chmod(0o600)
                    created.append(str(relative))
                allocated_after[str(relative)] = destination.stat().st_blocks * 512
                verified[str(relative)] = digest
                self._floor(starting=False)
        ending = self._floor(starting=True)
        growth = max(0, starting["freeBytes"] - ending["freeBytes"])
        self.identity = {
            "models": dict(MODEL_PINS),
            "files": verified,
            "cloneSetup": {
                "startFreeBytes": starting["freeBytes"],
                "endFreeBytes": ending["freeBytes"],
                "observedFilesystemGrowthBytes": growth,
                "createdMembers": created,
                "reusedMembers": len(verified) - len(created),
                "ownedAllocatedBlocksDeltaBytes": sum(allocated_after.values())
                - sum(allocated_before.values()),
                "allocationNote": (
                    "APFS shared blocks are not exclusive physical usage; read-only reuse "
                    "cannot attribute unrelated filesystem writes to cloning."
                ),
                "growthCeilingBytes": 64 * 1024**2,
            },
        }
        validate_clone_allocation(created, allocated_before, allocated_after, growth)

    def _request(self, path: str, body: dict | None = None, *, timeout: float = 3) -> dict:
        with httpx.Client(trust_env=False, timeout=timeout, follow_redirects=False) as client:
            with client.stream(
                "GET" if body is None else "POST", "http://127.0.0.1:11439" + path, json=body
            ) as response:
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 1048576:
                        raise ModelUnavailable("model response allocation exceeded")
                return json.loads(data)

    def __enter__(self):
        self._prepare()
        with socket.socket() as candidate:
            try:
                candidate.bind(("127.0.0.1", 11439))
            except OSError as exc:
                raise ModelUnavailable("dedicated model listener already occupied") from exc
        executable = Path("/opt/homebrew/bin/ollama")
        self.identity["runtimeSha256"] = file_hash(executable)
        self.log_path = self.root / f"server-{time.time_ns()}.log"
        fd = os.open(self.log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.log = os.fdopen(fd, "w")
        env = {
            "PATH": "/usr/bin:/bin:/opt/homebrew/bin",
            "HOME": str(self.root),
            "OLLAMA_MODELS": str(self.root / "models"),
            "OLLAMA_HOST": "127.0.0.1:11439",
            "OLLAMA_NO_CLOUD": "1",
            "OLLAMA_NOPRUNE": "1",
            "OLLAMA_MAX_LOADED_MODELS": "1",
            "OLLAMA_NUM_PARALLEL": "1",
            "OLLAMA_MAX_QUEUE": "1",
            "OLLAMA_CONTEXT_LENGTH": "2048",
            "OLLAMA_KEEP_ALIVE": "0",
            "OLLAMA_LOAD_TIMEOUT": "60s",
        }
        try:
            self.process = subprocess.Popen(
                [str(executable), "serve"],
                env=env,
                stdout=self.log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise ModelUnavailable("owned model server exited during startup")
                try:
                    version = self._request("/api/version")
                    break
                except httpx.TransportError:
                    time.sleep(0.1)
            else:
                raise ModelUnavailable("model server startup deadline")
            if (
                version.get("version") != "0.40.2"
                or "cloud disabled" not in self.log_path.read_text().lower()
            ):
                raise ModelUnavailable("runtime version or cloud-disable evidence mismatch")
            tags = {m["name"]: m for m in self._request("/api/tags")["models"]}
            if set(tags) != set(MODEL_PINS) or any(
                tags[n]["digest"] != d or tags[n].get("remote_host") for n, d in MODEL_PINS.items()
            ):
                raise ModelUnavailable("effective model allowlist mismatch")
            self.identity["version"] = version
            self.identity["environment"] = {k: v for k, v in env.items() if k.startswith("OLLAMA_")}
            return self
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        if self.log is not None:
            self.log.close()

    def __exit__(self, *args):
        self.close()

    def infer(self, *, model: str, body: dict) -> dict:
        validate_request(model, body)
        if not self.permit.acquire(blocking=False):
            raise ModelUnavailable("one local model execution is already active")
        stopped = threading.Event()
        violations = []
        self.last_response = None
        timeout = 90 if model == "qwen3:8b" else 60
        deadline = time.monotonic() + timeout

        def monitor():
            while not stopped.wait(0.5):
                try:
                    self._floor(starting=False)
                    if time.monotonic() >= deadline or self.log_path.stat().st_size > 1048576:
                        raise ModelUnavailable("model deadline or log allocation reached")
                    loaded = self._request("/api/ps").get("models", [])
                    if len(loaded) > 1 or sum(m.get("size", 0) for m in loaded) > 8 * GIB:
                        raise ModelUnavailable("model resident allocation exceeded")
                except Exception as exc:
                    violations.append(type(exc).__name__ + ": " + str(exc))
                    self.close()
                    return

        watcher = None
        try:
            if self.process is None or self.process.poll() is not None:
                raise ModelUnavailable("owned model server is unavailable")
            self._wait_admission(deadline)
            watcher = threading.Thread(target=monitor, daemon=True)
            watcher.start()
            response = self._request(
                "/api/chat" if model == "qwen3:8b" else "/api/embed", body, timeout=timeout
            )
            self.last_response = response
            if violations or time.monotonic() >= deadline:
                raise ModelUnavailable("inference exceeded monitored policy")
            validate_response(response, model=model)
            return response
        except (httpx.HTTPError, ValueError) as exc:
            self.close()
            raise ModelUnavailable("inference transport failed; owned server stopped") from exc
        finally:
            stopped.set()
            if watcher:
                watcher.join(timeout=10)
            self.permit.release()
