"""Native C3 reader/clock assembly. Configuration contains handles, never credential bytes."""

import argparse
import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import Field

from .adapters.credentials import KeychainTLS, TLSReference
from .adapters.nts import ChronyCollector, ProtectedClock, publish_frame
from .adapters.postgres import PostgresEvidenceReader
from .adapters.postgres_tls import PostgresTarget, PostgresTLS
from .adapters.read_authority import PostgresReadAuthority
from .application.evidence import EvidenceService
from .contracts.codec import canonical, decode
from .contracts.models import Digest, Ref, SubjectSnapshot, Value
from .deployment.launchd import REALMS, kernel_groups, protected_bytes, protected_chain

CLOCK_SOCKETS = {
    "test": "/var/db/docsuri/rem1-test/clock/chronyd.sock",
    "production": "/var/db/docsuri/rem1/clock/chronyd.sock",
}


class SecretReference(Value):
    keychain: str
    service: Ref
    account: Ref


class SubjectPolicy(Value):
    snapshot: SubjectSnapshot
    slots: Annotated[tuple[Ref, ...], Field(min_length=1, max_length=100)]


class HostConfiguration(Value):
    profile: Literal["test", "production"]
    role: Literal["reader", "clock"]
    uid: Annotated[int, Field(ge=1)]
    gid: Annotated[int, Field(ge=1)]
    clock_uid: Annotated[int, Field(ge=1)]
    clock_config_digest: Digest
    clock_frame: str
    database: PostgresTarget | None = None
    database_tls: SecretReference | None = None
    server_tls: SecretReference | None = None
    chronyc: str | None = None
    chronyc_digest: Digest | None = None
    chrony_socket: str | None = None
    policies: Annotated[tuple[SubjectPolicy, ...], Field(max_length=100)] = ()


def validate_configuration(config: HostConfiguration):
    root = REALMS[config.profile]
    paths = [config.clock_frame]
    for reference in (config.database_tls, config.server_tls):
        if reference is not None:
            paths.append(reference.keychain)
    paths.extend(value for value in (config.chronyc,) if value)
    # chrony config does not implement shell quoting, and Darwin UDS paths are bounded.
    # Only this exact profile-specific socket may live outside the long release realm.
    if config.chrony_socket != CLOCK_SOCKETS[config.profile] and config.chrony_socket:
        paths.append(config.chrony_socket)
    for name in paths:
        path = PurePosixPath(name)
        if (
            not path.is_absolute() or str(path) != name or ".." in path.parts
            or any(char in name for char in "\x00\r\n")
        ):
            raise ValueError("invalid native configuration path")
        Path(name).relative_to(root)
    if config.role == "reader":
        if any(item is None for item in (config.database, config.database_tls, config.server_tls)):
            raise ValueError("reader credential handles required")
        if (
            not config.policies
            or len({p.snapshot.subject for p in config.policies}) != len(config.policies)
        ):
            raise ValueError("unique reader subject policies required")
        expected_port = 15439 if config.profile == "test" else 5432
        if config.database.port != expected_port:
            raise ValueError("database port crosses deployment profile")
    elif any(item is None for item in (
        config.chronyc, config.chronyc_digest, config.chrony_socket,
    )):
        raise ValueError("clock observer configuration missing")
    return config


def require_role(config):
    if (
        (os.getuid(), os.geteuid(), os.getgid(), os.getegid())
        != (config.uid, config.uid, config.gid, config.gid)
        or set(kernel_groups()) - {config.gid}
    ):
        raise PermissionError("native service role mismatch")


def secret_provider(config, reference):
    return KeychainTLS(TLSReference(Path(reference.keychain), reference.service, reference.account),
                       REALMS[config.profile] / config.role)


def build_reader(config, *, current=None):
    config = validate_configuration(config)
    if config.role != "reader":
        raise ValueError("reader configuration required")
    clock = ProtectedClock(Path(config.clock_frame), writer_uid=config.clock_uid,
                           config_digest=config.clock_config_digest)
    database = PostgresTLS(config.database, secret_provider(config, config.database_tls))
    reader = PostgresEvidenceReader(connection_factory=database.connect)
    authority = PostgresReadAuthority(database.connect, clock)
    service = EvidenceService(reader, authority, clock,
                              {p.snapshot.subject: (p.snapshot, p.slots) for p in config.policies},
                              current=current)
    return service


def collect_clock(config):
    path = Path(config.clock_frame)
    info = path.parent.lstat()
    if (
        not stat.S_ISDIR(info.st_mode) or info.st_uid != config.uid
        or info.st_mode & 0o022 or config.clock_uid != config.uid
    ):
        raise PermissionError("clock publisher directory not provisioned")
    collector = ChronyCollector(Path(config.chronyc), config.chronyc_digest,
                               Path(config.chrony_socket), config.clock_config_digest)
    try:
        sample = collector.collect()
    except Exception:
        publish_frame(path, None)
        raise
    publish_frame(path, sample)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("reader", "clock"))
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    try:
        protected_chain(args.config)
        config = validate_configuration(HostConfiguration.model_validate_json(
            canonical(decode(protected_bytes(args.config)))
        ))
        if config.role != args.role:
            raise PermissionError("entry/config role mismatch")
        require_role(config)
        if args.role == "clock":
            collect_clock(config)
            print(json.dumps({"state": "OBSERVED", "role": "clock"}))
        else:
            from .api.app import create_app
            from .api.server import build_server

            service = build_reader(config)
            with secret_provider(config, config.server_tls).materialize() as material:
                server = build_server(
                    create_app(service), certificate=material.certificate,
                    private_key=material.private_key, ca=material.ca,
                    port=18101 if config.profile == "test" else 8101,
                )
            # TLS context is loaded; plaintext server key files have been removed before serving.
            server.run()
        return 0
    except Exception:
        print(json.dumps({"state": "BLOCKED", "role": args.role,
                          "reason": "native_runtime_unavailable"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
