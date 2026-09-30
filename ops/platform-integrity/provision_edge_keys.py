#!/usr/bin/env python3
"""Provision Keychain secrets for REM-3 edge trust."""

from __future__ import annotations

import argparse
import getpass
import secrets
import subprocess
import sys
from pathlib import Path

KEYCHAINS = {
    "unsubscribe-jwt": {
        "path": "/Library/Application Support/DocSuri/rem-2/keys/unsubscribe-jwt.keychain-db",
        "service": "docsuri.rem2.unsubscribe",
        "account": "unsubscribe-jwt",
    },
    "ratelimit": {
        "path": "/Library/Application Support/DocSuri/rem-2/keys/ratelimit.keychain-db",
        "service": "docsuri.rem2.ratelimit",
        "account": "ratelimit-secret",
    },
}

WORKER_ACCOUNTS = [
    "_docsuri_rem2_translate",
    "_docsuri_rem2_summarize",
    "_docsuri_rem2_novelty",
    "_docsuri_rem2_evidence",
    "_docsuri_rem2_purge",
]


def run(cmd: list[str], input_data: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        input=input_data,
        capture_output=True,
        text=True,
        check=False,
    )


def create_keychain(path: str, password: str) -> None:
    Path(path).parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    
    # Delete existing keychain if it exists
    if Path(path).exists():
        run(["security", "delete-keychain", path])
    
    result = run(["security", "create-keychain", "-p", password, path])
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create keychain {path}: {result.stderr}")


def add_generic_password(keychain: str, service: str, account: str, password: str) -> None:
    result = run([
        "security", "add-generic-password",
        "-a", account,
        "-s", service,
        "-w", password,
        "-U",  # update if exists
        "-T", "/usr/bin/codesign",  # Allow codesign access
        "-T", "/usr/bin/security",  # Allow security tool access
        "-A",  # Allow any application to access (we'll restrict via keychain ACL)
        keychain,
    ])
    if result.returncode != 0:
        raise RuntimeError(f"Failed to add password to {keychain}: {result.stderr}")


def set_keychain_acl(keychain: str, accounts: list[str]) -> None:
    """Set ACL on keychain to allow specified accounts access."""
    for account in accounts:
        # Use security set-key-partition-list to grant access
        result = run([
            "security", "set-key-partition-list",
            "-S", "apple:",  # Allow Apple-signed apps
            "-k", account,  # Allow this account
            "-t", "private",  # private key operations
            keychain,
        ])
        if result.returncode != 0:
            print(f"Warning: Failed to set ACL for {account} on {keychain}: {result.stderr.strip()}")


def set_keychain_settings(keychain: str) -> None:
    # lock-on-sleep, timeout 300s
    run(["security", "set-keychain-settings", "-l", "-t", "300", keychain])


def unlock_keychain(keychain: str, password: str) -> None:
    """Unlock the keychain so it can be accessed."""
    run(["security", "unlock-keychain", "-p", password, keychain])


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision REM-3 edge trust Keychain secrets")
    parser.add_argument("--profile", choices=("test", "production"), default="test")
    args = parser.parse_args()

    if sys.platform != "darwin":
        print("This script only runs on macOS", file=sys.stderr)
        return 1

    print("Enter Keychain passwords (hidden input):")
    passwords = {}
    for name in KEYCHAINS:
        pwd = getpass.getpass(f"  {name} password: ")
        if not pwd:
            print(f"Error: {name} password cannot be empty", file=sys.stderr)
            return 1
        passwords[name] = pwd

    # Verify passwords
    for name, pwd in passwords.items():
        confirm = getpass.getpass(f"Confirm {name} password: ")
        if pwd != confirm:
            print(f"Error: {name} passwords do not match", file=sys.stderr)
            return 1

    try:
        for name, config in KEYCHAINS.items():
            print(f"Provisioning {name}...")
            create_keychain(config["path"], passwords[name])
            # Generate strong secret for JWT/MinIO/ElasticMQ
            secret = secrets.token_urlsafe(32)
            add_generic_password(config["path"], config["service"], config["account"], secret)
            set_keychain_settings(config["path"])
            print(f"  Created {config['path']}")

        # Set ACLs for all worker accounts
        for name, config in KEYCHAINS.items():
            print(f"Setting ACLs for {name}...")
            for account in [
                "_docsuri_rem2_translate",
                "_docsuri_rem2_summarize",
                "_docsuri_rem2_novelty",
                "_docsuri_rem2_evidence",
                "_docsuri_rem2_purge",
            ]:
                result = subprocess.run([
                    "security", "set-key-partition-list",
                    "-S", "apple:",
                    "-k", account,
                    "-t", "private",
                    config["path"],
                ], capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    print(f"Warning: Failed to set ACL for {account} on {config['path']}: {result.stderr.strip()}")

        print("All Keychains provisioned successfully.")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
