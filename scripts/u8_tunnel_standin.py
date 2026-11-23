"""The composed realm's public stand-in: it plays Cloudflare's edge and the tunnel.

Decision "The composed realm's addresses" of the U8 plan (Step 43; built in Step 10,
whose boundary test runs through it):

- it listens on `127.0.0.1:18110` and terminates TLS with the run's own certificate
  (`service-operations-tls`, from `docsuri_ops.local_transport`);
- it sets `Host` to its own authority, as the tunnel's `httpHostHeader` does, and
  replaces any incoming `CF-Connecting-IP` with the socket's peer;
- it forwards over loopback HTTP to the origin its active registered configuration
  names: v2's host (18109), the maintenance server (18111) or v1's web (18113). The
  active choice is `tunnel-active.json` in the run root, which the realm driver's
  tunnel routing writes (`set_route`); with none, it answers 502;
- it refuses the production profile.

Each connection carries one request and is closed after the origin's answer, which
is relayed as it streams (event streams included).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import sys
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (ROOT, ROOT / "ops/src"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

# The repository's own packages resolve only once the paths above are on sys.path.
from backend.local_profile import LocalProfile, private_bytes  # noqa: E402

PUBLIC_PORT = 18110
AUTHORITY = f"127.0.0.1:{PUBLIC_PORT}"
# The three registered origins (entities.md ProductionProfile.tunnelOrigins).
ORIGINS = {"v2-host": 18109, "maintenance": 18111, "v1-web": 18113}
ACTIVE_FILE = "tunnel-active.json"
MAX_HEAD = 16 * 1024
MAX_BODY = 4 * 1024 * 1024
RELAY_CHUNK = 64 * 1024
TIMEOUT_SECONDS = 30
# Headers the stand-in sets itself or that only one hop may carry.
_DROPPED = frozenset(
    {"host", "cf-connecting-ip", "connection", "keep-alive", "proxy-connection", "te", "upgrade"}
)


def require_realm(profile) -> None:
    """The stand-in serves the composed realm only, never the production profile."""
    if getattr(profile, "is_production", False) or profile.realm != "service-operations":
        raise ValueError("the public stand-in serves only the composed realm")


def set_route(profile, origin: str) -> None:
    """Make one registered origin the active one (the realm driver's tunnel routing)."""
    require_realm(profile)
    if origin not in ORIGINS:
        raise ValueError("unregistered tunnel origin")
    path = profile.root / ACTIVE_FILE
    pending = path.with_name(path.name + ".pending")
    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump({"runId": profile.run_id, "origin": origin}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, path)


def active_origin(profile, root: Path | None = None) -> int | None:
    """The active origin's port, read fresh for every connection, from the run root or a
    journey's own routing folder (the realm driver's `tunnelRoot`)."""
    path = (root or profile.root) / ACTIVE_FILE
    try:
        value = json.loads(private_bytes(path, maximum=512))
    except FileNotFoundError:
        return None
    if value.get("runId") != profile.run_id or value.get("origin") not in ORIGINS:
        raise ValueError("tunnel route binding differs from the run")
    return ORIGINS[value["origin"]]


def tls_context(profile) -> ssl.SSLContext:
    from docsuri_ops.local_transport import inspect_transport

    transport = inspect_transport(profile)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(transport.certificate, transport.key)
    return context


async def _answer(writer, status: int, reason: str) -> None:
    body = json.dumps({"code": "DEPENDENCY_UNAVAILABLE", "retryable": True}).encode()
    writer.write(
        f"HTTP/1.1 {status} {reason}\r\ncontent-type: application/json\r\n"
        f"content-length: {len(body)}\r\nconnection: close\r\n\r\n".encode()
        + body
    )
    await writer.drain()


def _rewrite(head: bytes, peer: str) -> tuple[bytes, int]:
    """The forwarded head and the body length; refuses what one hop cannot carry."""
    lines = head.decode("latin-1").split("\r\n")
    request, fields = lines[0], [line for line in lines[1:] if line]
    if len(request.split(" ")) != 3:
        raise ValueError("malformed request line")
    kept, length = [], 0
    for line in fields:
        name, separator, value = line.partition(":")
        if not separator:
            raise ValueError("malformed header")
        key = name.strip().lower()
        if key == "transfer-encoding":
            raise ValueError("chunked request bodies are not carried")
        if key == "content-length":
            length = int(value.strip())
            if not 0 <= length <= MAX_BODY:
                raise ValueError("request body outside the bound")
        if key in _DROPPED:
            continue
        kept.append(f"{name.strip()}: {value.strip()}")
    kept += [f"Host: {AUTHORITY}", f"CF-Connecting-IP: {peer}", "Connection: close"]
    return ("\r\n".join([request, *kept]) + "\r\n\r\n").encode("latin-1"), length


async def _relay(source, target) -> None:
    while chunk := await source.read(RELAY_CHUNK):
        target.write(chunk)
        await target.drain()


class TunnelStandin:
    """The stand-in for one composed realm."""

    def __init__(self, profile, *, port: int = PUBLIC_PORT, routes_root: Path | None = None):
        require_realm(profile)
        self.profile = profile
        self.port = port
        self.routes_root = routes_root
        self.context = tls_context(profile)

    async def handle(self, reader, writer) -> None:
        peer = writer.get_extra_info("peername")[0]
        try:
            head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), TIMEOUT_SECONDS)
            if len(head) > MAX_HEAD:
                raise ValueError("request head outside the bound")
            forwarded, length = _rewrite(head[:-4], peer)
            body = await reader.readexactly(length) if length else b""
            port = active_origin(self.profile, self.routes_root)
            if port is None:
                return await _answer(writer, 502, "Bad Gateway")
            try:
                origin_reader, origin_writer = await asyncio.open_connection("127.0.0.1", port)
            except OSError:
                return await _answer(writer, 502, "Bad Gateway")
            try:
                origin_writer.write(forwarded + body)
                await origin_writer.drain()
                await _relay(origin_reader, writer)
            finally:
                origin_writer.close()
        except (ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            await _answer(writer, 400, "Bad Request")
        except (TimeoutError, ConnectionError, ssl.SSLError):
            pass
        finally:
            writer.close()

    async def serve(self, stopping: asyncio.Event | None = None) -> None:
        server = await asyncio.start_server(
            self.handle, "127.0.0.1", self.port, ssl=self.context, limit=MAX_HEAD
        )
        async with server:
            if stopping is None:
                await server.serve_forever()
            else:
                await stopping.wait()

    @contextmanager
    def running(self):
        """Serve from a background thread for the length of the block (tests)."""
        loop = asyncio.new_event_loop()
        stopping = asyncio.Event()
        started = threading.Event()
        failure: list[BaseException] = []

        def main() -> None:
            asyncio.set_event_loop(loop)

            async def serve() -> None:
                server = await asyncio.start_server(
                    self.handle, "127.0.0.1", self.port, ssl=self.context, limit=MAX_HEAD
                )
                started.set()
                async with server:
                    await stopping.wait()

            try:
                loop.run_until_complete(serve())
            except BaseException as error:  # noqa: BLE001 - re-raised in the caller
                failure.append(error)
                started.set()
            finally:
                loop.close()

        thread = threading.Thread(target=main, daemon=True)
        thread.start()
        started.wait(10)
        if failure:
            raise failure[0]
        try:
            yield self
        finally:
            loop.call_soon_threadsafe(stopping.set)
            thread.join(10)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment-file", required=True, type=Path)
    args = parser.parse_args()
    asyncio.run(TunnelStandin(LocalProfile.load(args.environment_file)).serve())


if __name__ == "__main__":
    main()
