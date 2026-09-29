import argparse
import json
from pathlib import Path

from ..adapters.filesystem import read_regular
from ..contracts.codec import decode, digest
from ..domain.actions import (
    ROLES,
    authorize,
    is_readonly,
    non_success,
    resolve_request,
)
from ..domain.bindings import validate_catalog
from ..domain.supply_chain import parse_pip_audit


def _emit(payload) -> int:
    print(json.dumps(payload))
    return 0 if payload.get("state") == "PASS" else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="REM-1 explicit readonly verification")
    sub = parser.add_subparsers(dest="action", required=True)
    schema = sub.add_parser("check-schemas")
    schema.add_argument("root", type=Path)
    schema.add_argument(
        "--flat", action="store_true", help="Explicit unmanifested test/developer catalog"
    )
    audit = sub.add_parser("verify-audit")
    audit.add_argument("report", type=Path)
    audit.add_argument("inventory", type=Path)
    audit.add_argument("--returncode", type=int, required=True)
    sub.add_parser("capabilities")
    # No implicit apply: privileged actions need native-current authority and installation proof.
    sub.add_parser("apply")
    sub.add_parser("plan")
    sub.add_parser("reconcile")
    backup = sub.add_parser("backup")
    backup.add_argument("--generation", required=True)
    # The command a user types is not the action it performs; the action is what is authorized.
    COMMAND_ACTION = {
        "check-schemas": "check", "capabilities": "check", "verify-audit": "verify",
        "plan": "plan", "apply": "apply", "reconcile": "reconcile", "backup": "backup",
    }
    for command in COMMAND_ACTION:
        # Optional: an unroled invocation is still refused below, it is simply refused later.
        sub.choices[command].add_argument("--role", choices=ROLES)
    args = parser.parse_args(argv)
    action = COMMAND_ACTION[args.action]
    try:
        if args.role is not None:
            authorize(args.role, action)
        if args.action == "check-schemas":
            if not args.flat:
                from docsuri_schema import load_catalog

                catalog = load_catalog(args.root).resources
            else:
                files = sorted(args.root.rglob("*.schema.json"))
                if not files or len(files) > 1000:
                    raise ValueError("schema catalog missing or oversized")
                documents = []
                total = 0
                for path in files:
                    raw = read_regular(path, 16 * 1024**2)
                    total += len(raw)
                    if total > 64 * 1024**2:
                        raise ValueError("schema catalog byte limit")
                    documents.append(decode(raw))
                catalog = validate_catalog(documents)
            print(
                json.dumps(
                    {
                        "state": "PASS",
                        "scope": "local-schema-closure" if args.flat else "declared-schema-catalog",
                        "resources": len(catalog),
                    }
                )
            )
            return 0
        if args.action == "verify-audit":
            report_bytes = read_regular(args.report, 64 * 1024**2)
            findings = parse_pip_audit(
                decode(report_bytes, max_bytes=64 * 1024**2),
                returncode=args.returncode,
                expected=decode(read_regular(args.inventory, 16 * 1024**2)),
                source="pypi",
            )
            print(
                json.dumps(
                    {
                        "state": "BLOCKED" if findings else "PASS",
                        "report": digest(report_bytes),
                        "findings": [f.model_dump(mode="json") for f in findings],
                    }
                )
            )
            return 1 if findings else 0
        if args.action == "reconcile" and args.role is not None:
            resolve_request(args.role, "target", "reconcile")
        if args.action == "backup" and args.role is not None:
            resolve_request(args.role, "generation", "current")
        print(
            json.dumps(
                non_success(
                    "BLOCKED",
                    "native_authority_clock_installation_required",
                    action=action,
                    role=args.role,
                    readonly=is_readonly(action),
                    mutationReady=False,
                )
            )
        )
        return 2
    except PermissionError:
        # Never echo the requested value; a refusal must not become an oracle.
        print(json.dumps(non_success("REFUSED", "action_not_permitted_for_role")))
        return 3
    except Exception:
        # Raw parser/DB/OS exceptions can carry paths/DSNs. Keep machine failures generic.
        print(json.dumps({"state": "INCOMPLETE", "reason": "verification_failed"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
