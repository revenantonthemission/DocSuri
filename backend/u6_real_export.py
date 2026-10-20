"""Operator-only real export composition: one owner, one activation page, one export.

This entry is separate from the synthetic `assemble_u6` and runs only when an operator
starts the owned U6 host with `--real-export` (cicd-pipeline §5). Its non-secret
settings come from one place, the environment's private, run-bound `real-export.json`
(cicd-pipeline §4.6), read through `private_bytes`:

```json
{
  "runId": "<this environment's run id>",
  "activationDestinationId": "<32 lowercase hex: the one page shared with the integration>",
  "freeTerms": {
    "plan": "free",
    "memberCount": 1,
    "checkedOn": "<YYYY-MM-DD>",
    "publishedLimits": ["<the published limits that apply>"]
  }
}
```

It carries exactly these fields; any missing, extra or invalid value refuses with
POLICY_UNRESOLVED, and there is no fallback. It never carries the token: the owner pastes
it into the connect form, and it is stored sealed. The composition also refuses an
environment that holds any evidence file (`*-evidence-*.json`), so the environment
cannot have run a test, frontend, browser or serve phase (cicd-pipeline §4.3).

`assemble_u6_real(..., transport_factory=...)` is the test-only seam; without it the
session builds the network transport through `notion_session.network_transport()`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from backend.local_profile import LocalProfile, private_bytes
from backend.modules.export.errors import ExportError
from backend.u5_host import assemble_u5
from backend.u6_host import ACTIVATION_FILE, export_contribution
from backend.u6_policy import ExportPolicy, real_activation_export

FIELDS = frozenset({"runId", "activationDestinationId", "freeTerms"})
FREE_TERMS_FIELDS = frozenset({"plan", "memberCount", "checkedOn", "publishedLimits"})
SETTINGS_MAXIMUM = 4096
EVIDENCE_PATTERN = "*-evidence-*.json"
DESTINATION = re.compile(r"[0-9a-f]{32}")
CHECKED_ON = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# Q2 A: the owner's own single-member Free workspace.
FREE_PLAN = "free"
SINGLE_MEMBER = 1
MAX_PUBLISHED_LIMITS = 8
PUBLISHED_LIMIT_CHARACTERS = 256


@dataclass(frozen=True)
class RealExportActivation:
    run_id: str
    activation_destination_id: str
    free_terms: dict
    free_terms_reference: str


def refused(field: str) -> ExportError:
    """The one refusal of the real settings: POLICY_UNRESOLVED naming the gap."""
    return ExportError("POLICY_UNRESOLVED", current={"field": field})


def _published_limits(value) -> list[str]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_PUBLISHED_LIMITS:
        raise refused("freeTerms.publishedLimits")
    for item in value:
        if (
            not isinstance(item, str)
            or not item.strip()
            or len(item) > PUBLISHED_LIMIT_CHARACTERS
            or not item.isprintable()
        ):
            raise refused("freeTerms.publishedLimits")
    return list(value)


def _checked_on(value, today: dt.date) -> str:
    if not isinstance(value, str) or CHECKED_ON.fullmatch(value) is None:
        raise refused("freeTerms.checkedOn")
    try:
        checked = dt.date.fromisoformat(value)
    except ValueError:
        checked = None
    if checked is None or checked > today:
        raise refused("freeTerms.checkedOn")
    return value


def _free_terms(value, today: dt.date) -> dict:
    if not isinstance(value, dict) or set(value) != FREE_TERMS_FIELDS:
        raise refused("freeTerms")
    if value["plan"] != FREE_PLAN:
        raise refused("freeTerms.plan")
    if type(value["memberCount"]) is not int or value["memberCount"] != SINGLE_MEMBER:
        raise refused("freeTerms.memberCount")
    return {
        "plan": FREE_PLAN,
        "memberCount": SINGLE_MEMBER,
        "checkedOn": _checked_on(value["checkedOn"], today),
        "publishedLimits": _published_limits(value["publishedLimits"]),
    }


def free_terms_reference(terms: dict) -> str:
    """A printable reference to the recorded free-terms evidence: its check date and the
    digest of its canonical form, so the evidence itself stays in the settings file."""
    canonical = json.dumps(terms, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"notion-free:{terms['checkedOn']}:{digest}"


def parse_activation(
    value, profile: LocalProfile, *, today: dt.date | None = None
) -> RealExportActivation:
    """Validate the operator's settings; every gap refuses, nothing defaults."""
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise refused("settings")
    if value["runId"] != profile.run_id:
        raise refused("runId")
    destination = value["activationDestinationId"]
    if not isinstance(destination, str) or DESTINATION.fullmatch(destination) is None:
        raise refused("activationDestinationId")
    terms = _free_terms(value["freeTerms"], today or dt.datetime.now(dt.UTC).date())
    return RealExportActivation(
        run_id=profile.run_id,
        activation_destination_id=destination,
        free_terms=terms,
        free_terms_reference=free_terms_reference(terms),
    )


def load_activation(profile: LocalProfile, *, today: dt.date | None = None):
    """Read the environment's private, owner-only settings (never a token)."""
    failure = None
    try:
        raw = private_bytes(profile.root / ACTIVATION_FILE, maximum=SETTINGS_MAXIMUM)
    except FileNotFoundError:
        failure = "settings-absent"
    except (OSError, ValueError):
        failure = "settings-custody"
    if failure is not None:
        raise refused(failure)
    try:
        value = json.loads(raw)
    except ValueError:
        value = None
    if value is None:
        raise refused("settings")
    return parse_activation(value, profile, today=today)


def require_no_evidence(root: Path) -> None:
    """The real composition refuses an environment that has run any synthetic phase."""
    if any(root.glob(EVIDENCE_PATTERN)):
        raise refused("environment")


def real_policy(activation: RealExportActivation) -> ExportPolicy:
    try:
        policy = real_activation_export(
            activation_destination_id=activation.activation_destination_id,
            free_terms_reference=activation.free_terms_reference,
        )
    except ValueError:
        policy = None
    if policy is None:
        raise refused("policy")
    return policy


def real_export_factory(activation: RealExportActivation, *, transport_factory=None):
    """The export contribution with the real policy; the network unless the seam is set."""
    return partial(
        export_contribution, policy=real_policy(activation), transport_factory=transport_factory
    )


def assemble_u6_real(
    profile: LocalProfile, activation: RealExportActivation, *, transport_factory=None
):
    """Assemble the owned U6 host with the real export; refuses instead of degrading."""
    if not isinstance(activation, RealExportActivation) or activation.run_id != profile.run_id:
        raise refused("runId")
    require_no_evidence(profile.root)
    factory = real_export_factory(activation, transport_factory=transport_factory)
    return assemble_u5(profile, export_factory=factory)
