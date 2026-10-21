"""Operator steps for the one real export (cicd-pipeline §5 steps 4 and 9). Never exports.

  check    validate the environment's `real-export.json` and name every gap in it, plus
           an environment that already holds evidence files (the real composition
           refuses one). It never reads a token: the settings never hold one.
  outcome  read the one export's outcome and print digests only: the SHA-256 of
           Notion's request id and of the page link, the final state and reason, the
           attempt's outcome class and whether the page lists the integration as its
           creator. No token, header, workspace name, plaintext identifier or page
           content is printed.

Neither action builds a Notion client. The export itself happens only in the owned host
started with `scripts/serve_docsuri_u6.py --real-export`, after the owner approves the
exact content in the preview.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ops/src"))

from backend.local_profile import LocalProfile, private_bytes
from backend.modules.export.errors import ExportError
from backend.u6_host import ACTIVATION_FILE
from backend.u6_real_export import (
    CHECKED_ON,
    DESTINATION,
    EVIDENCE_PATTERN,
    FIELDS,
    FREE_PLAN,
    FREE_TERMS_FIELDS,
    SETTINGS_MAXIMUM,
    SINGLE_MEMBER,
    RealExportActivation,
    _published_limits,
    load_activation,
    real_policy,
)

REALM = "approved-export"
# Seven days is the longest time U6 keeps a rendered copy (NFR1.5); the preserved
# environment must be removed by then (cicd-pipeline §5 step 13).
RETENTION_DAYS = 7


class OutcomeRefused(RuntimeError):
    """The outcome action cannot name one export; carries a fixed category."""


def _checked_on_gap(value, today: dt.date) -> bool:
    if not isinstance(value, str) or CHECKED_ON.fullmatch(value) is None:
        return True
    try:
        return dt.date.fromisoformat(value) > today
    except ValueError:
        return True


def _published_limits_gap(value) -> bool:
    try:
        _published_limits(value)
    except ExportError:
        return True
    return False


def free_terms_gaps(value, today: dt.date) -> list[str]:
    """Every gap in the free-terms evidence, each named by its field."""
    if not isinstance(value, dict):
        return ["freeTerms"]
    gaps = [] if set(value) == FREE_TERMS_FIELDS else ["freeTerms"]
    if value.get("plan") != FREE_PLAN:
        gaps.append("freeTerms.plan")
    count = value.get("memberCount")
    if type(count) is not int or count != SINGLE_MEMBER:
        gaps.append("freeTerms.memberCount")
    if _checked_on_gap(value.get("checkedOn"), today):
        gaps.append("freeTerms.checkedOn")
    if _published_limits_gap(value.get("publishedLimits")):
        gaps.append("freeTerms.publishedLimits")
    return gaps


def value_gaps(value, profile: LocalProfile, today: dt.date) -> list[str]:
    """Every gap in the parsed settings; an empty list means they are complete."""
    if not isinstance(value, dict):
        return ["settings"]
    gaps = [] if set(value) == FIELDS else ["settings"]
    if value.get("runId") != profile.run_id:
        gaps.append("runId")
    destination = value.get("activationDestinationId")
    if not isinstance(destination, str) or DESTINATION.fullmatch(destination) is None:
        gaps.append("activationDestinationId")
    return gaps + free_terms_gaps(value.get("freeTerms"), today)


def settings_gaps(profile: LocalProfile, *, today: dt.date | None = None) -> list[str]:
    """`check`: the settings file and the environment, every gap named."""
    today = today or dt.datetime.now(dt.UTC).date()
    gaps = ["environment"] if any(profile.root.glob(EVIDENCE_PATTERN)) else []
    try:
        raw = private_bytes(profile.root / ACTIVATION_FILE, maximum=SETTINGS_MAXIMUM)
    except FileNotFoundError:
        return [*gaps, "settings-absent"]
    except (OSError, ValueError):
        return [*gaps, "settings-custody"]
    try:
        value = json.loads(raw)
    except ValueError:
        return [*gaps, "settings"]
    gaps += value_gaps(value, profile, today)
    if gaps:
        return gaps
    # The authoritative path must agree: the composition's own parse and policy.
    try:
        real_policy(load_activation(profile, today=today))
    except ExportError as error:
        return [str((error.current or {}).get("field", "settings"))]
    return []


def check(profile: LocalProfile, *, today: dt.date | None = None) -> dict:
    gaps = settings_gaps(profile, today=today)
    return {"action": "check", "state": "gaps" if gaps else "ready", "gaps": gaps}


def _sha256(value: str | None) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest() if value else None


OUTCOME_QUERY = (
    "SELECT e.id,e.state,e.outcome_reason,e.settled_by,e.remote_url,"
    "a.response_class,a.provider_request_id,a.creator_confirmed,a.path_kind "
    "FROM export.effect e LEFT JOIN LATERAL (SELECT * FROM export.attempt t "
    "WHERE t.effect_id=e.id ORDER BY t.attempt_number DESC LIMIT 1) a ON true "
    "WHERE (%s::uuid IS NULL OR e.id=%s::uuid) ORDER BY e.accepted_at LIMIT 2"
)


def outcome(
    transactions,
    profile: LocalProfile,
    activation: RealExportActivation,
    *,
    effect_id: UUID | None = None,
    source_commit: str | None = None,
    today: dt.date | None = None,
) -> dict:
    """`outcome`: the one export's result as digests and fixed values only."""
    if activation.run_id != profile.run_id:
        raise OutcomeRefused("activation-run-differs")
    rows = transactions.run(
        "export", lambda conn: conn.execute(OUTCOME_QUERY, (effect_id, effect_id)).fetchall()
    )
    if len(rows) != 1:
        raise OutcomeRefused("exactly-one-export-required")
    row = rows[0]
    today = today or dt.datetime.now(dt.UTC).date()
    return {
        "action": "outcome",
        "date": today.isoformat(),
        "runId": profile.run_id,
        "sourceCommit": source_commit,
        "freeTermsReference": activation.free_terms_reference,
        "effectState": row["state"],
        "outcomeReason": row["outcome_reason"],
        "settledBy": row["settled_by"],
        "outcomeClass": row["response_class"],
        "pathKind": row["path_kind"],
        "creatorConfirmed": row["creator_confirmed"],
        "requestIdSha256": _sha256(row["provider_request_id"]),
        "pageLinkSha256": _sha256(row["remote_url"]),
        "retentionDeadline": (today + dt.timedelta(days=RETENTION_DAYS)).isoformat(),
    }


def source_commit() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def run_action(action: str, profile: LocalProfile, effect_id: UUID | None) -> tuple[dict, int]:
    if profile.realm != REALM:
        raise ValueError("U6 real-export steps require the approved-export realm")
    if action == "check":
        result = check(profile)
        return result, 0 if result["state"] == "ready" else 1
    from backend.transactions import OwnerTransactions

    activation = load_activation(profile)
    transactions = OwnerTransactions(profile, process="maintenance")
    try:
        record = outcome(
            transactions, profile, activation, effect_id=effect_id, source_commit=source_commit()
        )
    finally:
        transactions.close()
    return record, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment-file", type=Path, required=True)
    parser.add_argument("--action", choices=["check", "outcome"], required=True)
    parser.add_argument("--effect-id", type=UUID)
    args = parser.parse_args(argv)
    try:
        result, code = run_action(
            args.action, LocalProfile.load(args.environment_file), args.effect_id
        )
    except ExportError as error:
        result = {"state": "refused", "category": error.code, **(error.current or {})}
        code = 1
    except OutcomeRefused as error:
        result, code = {"state": "refused", "category": str(error)}, 1
    except (ValueError, OSError) as error:
        result, code = {"state": "refused", "category": type(error).__name__}, 1
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
