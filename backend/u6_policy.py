"""Finite export operating values; a real export requires an explicit activation.

Every value is a finite positive integer: the NFR4.10 operating values, the security
design §9.1 read budgets, the D15 interactive caps and the per-pass batch bounds. Tests
build smaller values (shorter windows, faster pace) through the same constructor; the
real activation policy refuses anything faster or larger than the free limits below.
This policy does not establish a Notion integration or authorize an export.
"""

import re
from dataclasses import dataclass, field, fields

# Notion documents an average of 3 requests per second per integration. NFR4.6 keeps
# every connection at 2 per second (one slot each 500 ms), so a real policy may never
# pace faster than that.
REAL_MIN_PACE_INTERVAL_MS = 500
# Notion's own server-side request deadline; a write attempt deadline must exceed it,
# or an unclear write could be classified before Notion has finished with it.
NOTION_SERVER_DEADLINE_SECONDS = 60
# Upper bounds a real activation may not exceed (NFR4.5, NFR4.6, NFR4.10, NFR4.11, D15).
REAL_MAXIMA = {
    "rate_limit_max_attempts": 4,
    "read_retries": 3,
    "in_flight_per_owner": 1,
    "binds_per_window": 20,
    "response_cap_bytes": 2_000_000,
    "interactive_per_process": 2,
    "interactive_per_connection": 1,
}
# Lower bounds a real activation may not go under: shorter windows or waits would
# retry or check faster than the approved schedule.
REAL_MINIMA = {
    "pace_interval_ms": REAL_MIN_PACE_INTERVAL_MS,
    "write_deadline_seconds": NOTION_SERVER_DEADLINE_SECONDS + 1,
    "rate_limit_window_seconds": 600,
    "settling_wait_seconds": 180,
    "binds_window_seconds": 3600,
}
_DESTINATION = re.compile(r"[0-9a-f]{32}")
_EVIDENCE = re.compile(r"[\x21-\x7e]{1,256}")
_TEXT_FIELDS = frozenset(
    {"policy_id", "revision", "activation_destination_id", "free_terms_reference"}
)
# Fields checked by their own rules rather than as finite positive integers.
_FLAG_FIELDS = frozenset({"production_live", "live_authority"})
# Held only by `production_live_export`: a live policy built by any other caller is
# refused (U6's re-check, minor). The complete assembly's production builder is the one
# caller of that function, behind the provider gate.
_LIVE_AUTHORITY = object()


@dataclass(frozen=True)
class ExportPolicy:
    policy_id: str = "u6-synthetic-export"
    revision: str = "1"
    # Deadlines and budgets (NFR4.4, NFR4.10; security design §9.1).
    write_deadline_seconds: int = 90
    read_timeout_seconds: int = 30
    token_check_budget_seconds: int = 30
    listing_budget_seconds: int = 30
    page_read_budget_seconds: int = 30
    read_back_budget_seconds: int = 60
    scan_budget_seconds: int = 300
    # Reconciliation timing (NFR4.7, NFR4.10): the settling wait counts from deadlineAt;
    # checks after 3, 10 and 30 min, then hourly, then every 3 h, for 24 h in total.
    settling_wait_seconds: int = 180
    check_offsets_seconds: tuple[int, ...] = (180, 600, 1800)
    check_hourly_seconds: int = 3600
    # The approved wording does not name where hourly checks give way to 3-hourly ones;
    # this value is recorded for approval at the U6 checkpoint.
    check_hourly_until_seconds: int = 21600
    check_late_interval_seconds: int = 10800
    check_total_seconds: int = 86400
    # Retries and pace (NFR4.5, NFR4.6; D6).
    rate_limit_window_seconds: int = 600
    rate_limit_max_attempts: int = 4
    read_retries: int = 3
    pace_interval_ms: int = 500
    # Waits and thresholds (BR3.3, BR4.6, NFR4.7).
    could_not_check_wait_seconds: int = 86400
    orphan_after_seconds: int = 900
    clock_margin_seconds: int = 300
    # Per-owner limits (NFR4.11, NFR6.4): one export in flight, 20 bound per rolling hour.
    in_flight_per_owner: int = 1
    binds_per_window: int = 20
    binds_window_seconds: int = 3600
    # Retention and caps (NFR1.5, NFR3.8, D15, R-01/R-02).
    preview_retention_days: int = 7
    response_cap_bytes: int = 2_000_000
    interactive_per_process: int = 2
    interactive_per_connection: int = 1
    pending_takeover_seconds: int = 120
    # Key folder waiting lock (security design §4.4): retry every 100 ms for up to 5 s.
    key_lock_retry_ms: int = 100
    key_lock_wait_ms: int = 5000
    # Bounds.
    token_max_length: int = 512
    pass_batch: int = 10
    housekeeping_batch: int = 50
    history_page_max: int = 20
    # Real activation only (BR8.2, BR8.3; security design §11).
    activation_destination_id: str | None = None
    free_terms_reference: str | None = None
    # Production-only (U8 plan Step 21; BR7.6): the live policy, whose single
    # test-destination bound has lifted. Only the complete assembly's production builder
    # composes it, in live mode, behind the provider gate; it names no destination and
    # keeps the free-terms evidence and every free limit.
    production_live: bool = False
    live_authority: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        for item in fields(self):
            if item.name in _TEXT_FIELDS or item.name in _FLAG_FIELDS:
                continue
            value = getattr(self, item.name)
            values = value if isinstance(value, tuple) else (value,)
            if not values or any(type(entry) is not int or entry <= 0 for entry in values):
                raise ValueError(f"finite positive {item.name} required")
        if not self.policy_id or not self.revision:
            raise ValueError("policy reference required")
        self._check_schedule()
        if self.read_timeout_seconds > self.page_read_budget_seconds:
            raise ValueError("one read request must fit its read budget")
        if self.key_lock_retry_ms > self.key_lock_wait_ms:
            raise ValueError("waiting lock retry must fit its bound")
        if self.history_page_max > 20:
            raise ValueError("history pages hold at most 20 entries")
        if type(self.production_live) is not bool:
            raise ValueError("production_live is a flag")
        # Each refusal names its field, as every other field's does (U6's policy checks).
        if self.live_authority is not None and self.live_authority is not _LIVE_AUTHORITY:
            raise ValueError("live_authority is held only by production_live_export")
        if (self.live_authority is _LIVE_AUTHORITY) != self.production_live:
            raise ValueError("production_live is composed only by production_live_export")
        if self.production_live:
            self._check_live()
            return
        if self.activation_destination_id is None and self.free_terms_reference is None:
            return
        self._check_real_activation()

    def _check_live(self) -> None:
        """The live policy: no test destination, the free-terms evidence, the free limits."""
        if self.activation_destination_id is not None:
            raise ValueError("production_live names no test destination")
        evidence = self.free_terms_reference
        if not isinstance(evidence, str) or _EVIDENCE.fullmatch(evidence) is None:
            raise ValueError("production_live requires a free-terms evidence reference")
        self._check_free_terms()

    def _check_schedule(self) -> None:
        offsets = self.check_offsets_seconds
        if list(offsets) != sorted(set(offsets)):
            raise ValueError("check offsets must strictly increase")
        if not (
            offsets[-1]
            < self.check_hourly_until_seconds
            <= self.check_total_seconds
        ):
            raise ValueError("check schedule phases must fit the total check period")

    def _check_real_activation(self) -> None:
        destination = self.activation_destination_id
        if not isinstance(destination, str) or _DESTINATION.fullmatch(destination) is None:
            raise ValueError("real activation requires one 32-hex activation destination")
        self._check_free_terms()

    def _check_free_terms(self) -> None:
        evidence = self.free_terms_reference
        if not isinstance(evidence, str) or _EVIDENCE.fullmatch(evidence) is None:
            raise ValueError("real activation requires a free-terms evidence reference")
        for name, maximum in REAL_MAXIMA.items():
            if getattr(self, name) > maximum:
                raise ValueError(f"real activation refuses {name} above the free limit")
        for name, minimum in REAL_MINIMA.items():
            if getattr(self, name) < minimum:
                raise ValueError(f"real activation refuses {name} faster than the free limit")

    @property
    def synthetic_only(self) -> bool:
        return self.activation_destination_id is None and not self.production_live

    def reference(self) -> dict:
        return {"policyId": self.policy_id, "revision": self.revision}


SYNTHETIC_EXPORT = ExportPolicy()


def real_activation_export(
    *, activation_destination_id: str, free_terms_reference: str
) -> ExportPolicy:
    """The operator-only real activation: the production values plus its activation.

    Inert unless an operator composes it with the real adapter
    (`backend/u6_real_export.py`) after the owner approves the exact content.
    """
    return ExportPolicy(
        policy_id="u6-real-activation",
        activation_destination_id=activation_destination_id,
        free_terms_reference=free_terms_reference,
    )


# The only way to build the real policy; it cannot exist without its activation inputs.
REAL_ACTIVATION_EXPORT = real_activation_export


def production_live_export(*, free_terms_reference: str) -> ExportPolicy:
    """The production-only live policy (U8 plan Step 21; BR7.6): U6's single
    test-destination bound lifts, so owners export to shared pages their own connection
    can read, under U6's rules and the free-terms evidence and limits.

    Only the complete assembly's production builder composes it, and only in live mode;
    while Notion is held there nothing is written, so the bound lifts only once Notion
    is active in live mode. Rehearsal and every synthetic profile keep U6's bound."""
    return ExportPolicy(
        policy_id="u6-production-live",
        free_terms_reference=free_terms_reference,
        production_live=True,
        live_authority=_LIVE_AUTHORITY,
    )
