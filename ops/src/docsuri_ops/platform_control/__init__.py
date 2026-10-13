"""U7 ``PlatformControl`` — the local controlled platform-operator executable.

The package implements the approved U7 design: a retained-inventory operator
vocabulary, an owner-scoped ``PlatformControl`` PostgreSQL schema with
``SECURITY DEFINER`` guard functions, locally provisioned independent operator
authority, on-demand bound platform evidence, a bounded native executor, and
durable append-only operation receipts with unknown-outcome reconciliation.

It is an independent local executable (contract C10 transport: local
stdin/stdout JSON). Nothing here authorises a real destructive or release
operation; design and tests use synthetic targets only.
"""

from __future__ import annotations

SCHEMA = "platform_control"
RUNTIME_ROLE = "platform_control_runtime"
PROVISIONER_ROLE = "platform_control_provisioner"
OWNER_ROLE = "platform_control_owner"

__all__ = ["SCHEMA", "RUNTIME_ROLE", "PROVISIONER_ROLE", "OWNER_ROLE"]
