#!/usr/bin/env python3
"""Fetch pinned official scanner archives into an explicit unprivileged tool directory."""

import argparse
import hashlib
import io
import json
import os
import platform
import tarfile
import urllib.request
from pathlib import Path

TOOLS = {
    "syft": ("1.52.0", "014d561b6d13059124155f74a6c5a9a99501f5e209313638dd884f39eb418ee6"),
    "grype": ("0.119.0", "500c9b2b6c089d21481815f57a553fabbd441ec7d1e79d95e3aaf40c3bfc7e36"),
}


def fetch(name, destination):
    version, expected = TOOLS[name]
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("this verified tool profile requires Darwin arm64")
    url = f"https://github.com/anchore/{name}/releases/download/v{version}/{name}_{version}_darwin_arm64.tar.gz"
    with urllib.request.urlopen(url, timeout=30) as response:
        archive = response.read(64 * 1024**2 + 1)
    if len(archive) > 64 * 1024**2 or hashlib.sha256(archive).hexdigest() != expected:
        raise ValueError("scanner archive integrity mismatch")
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
        members = [entry for entry in bundle.getmembers() if entry.name == name]
        if len(members) != 1 or not members[0].isfile() or members[0].size > 256 * 1024**2:
            raise ValueError("invalid scanner archive")
        with bundle.extractfile(members[0]) as stream:
            binary = stream.read(256 * 1024**2 + 1)
    actual = hashlib.sha256(binary).hexdigest()
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = destination / name
    if target.exists():
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != actual:
            raise ValueError("existing scanner differs from verified artifact")
    else:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o700)
        with os.fdopen(fd, "wb") as output:
            output.write(binary)
            output.flush()
            os.fsync(output.fileno())
    return {"tool": name, "version": version, "url": url, "archiveSha256": expected,
            "binarySha256": actual, "platform": "darwin-arm64"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps({"tools": [fetch(name, args.destination) for name in TOOLS]}, indent=2))


if __name__ == "__main__":
    main()
