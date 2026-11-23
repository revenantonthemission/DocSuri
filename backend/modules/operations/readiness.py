"""Capability states and service readiness (U8 plan Step 15; BR1.3, BR3.1, BR3.2, BR5.9).

Each read derives every capability's state from its latest admitted observation and
its age, checked in BR3.2's order (functional-spec.md § Capability state derivation):

1. `public.static` is available while the host serves (carrying its latest row's
   24-hour error rate, never stale or unknown);
2. a capability of an unavailable contribution is unavailable, with that reason;
3. a provider whose secret is missing is unavailable as `unconfigured` (BR6.7);
4. no observation: unknown;
5. the latest observation older than the freshness bound: stale;
6. otherwise the latest outcome, with its reason and limitations.

The freshness bound is observability-design § 3.2's, from the operations policy. Stale
is never stored; it is derived from age on every read. Unknown and stale never count as
available.

`/health/live` answers from memory. `/health/ready` reads the latest observations in one
short transaction and never asks a producer. The service is ready only when no required
capability is unavailable, unknown or stale (`background.work` and `storage.capacity`
are required, so background work runs and storage admission is open), and the host's
own capacity admission, when given, is open. A degraded required capability is named,
but does not by itself make the service unready (BR3.1).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from backend.u8_registry import CAPABILITY_BY_ID, NAVIGATION, REQUIRED, timing

STATIC = "public.static"
UNREADY = ("unavailable", "unknown", "stale")
# BR5.9: beyond the entries a caller with no session may see, these alone. The mail
# provider is among them so the sign-in screen's mail notice can warn before a reset or
# verification link is asked for (the person's answer of 2026-11-13, "Add mail to the list").
# A held sign-in provider reads as not serving there once admission opens (`SIGN_IN` below).
PUBLIC_EXTRA = ("account.entry", "provider.google", "provider.orcid", "provider.resend")
AVAILABLE_REASON = "available"
# Signed out, the mail provider reads only as serving or not serving, with no reason key of
# its own (the person's answer of 2026-11-13, "Working or not, no reasons"): its reasons and
# its daily-limit state would let a caller with no session test whether an address has an
# account. Not serving: the first-send hold or an observed outage, read from the newest
# observation; and mail not configured or the owning contribution unavailable, decided from
# the settings and the activation with or without one (outside the windows below). The
# daily limit reads serving although every account's mail is refused at the account and
# month limits: only an existing account's message moves its change of state, so showing
# it would tell an account from an unknown address; the up-front refusal tells the caller
# (code summary, records 64 and 65). Unknown and stale read serving: they show no outage.
# The list sees the hold later than the gate the refusals read, either way: by up to one
# 300 s renewal, or the 900 s freshness bound if renewals stop; unknown or stale hides it.
MAIL = "provider.resend"
MAIL_HELD_REASON = "first-effect-pending"
MAIL_NOT_SERVING_REASON = "provider-unreachable"
# A held sign-in provider is refused at the start for everyone once admission opens (U8
# plan Step 106(h); BR7.8, BR7.2, BR5.9), so signed out it then reads as not serving, with
# the generic reason, as the mail hold does; in the maintainer-only window, and in every
# synthetic profile, it reads as built. The list follows the observation renewed every
# 300 s, so it can show the hold up to one renewal late; the start's refusal holds
# meanwhile. `states()`, `/health/ready` and 운영 keep the truthful degraded state.
SIGN_IN = ("provider.google", "provider.orcid")
SIGN_IN_HELD_REASON = "sign-in-unverified"


@dataclass(frozen=True)
class CapabilityState:
    capability: str
    state: str
    reason: str | None
    limitations: tuple[str, ...] = ()
    age_seconds: int | None = None
    observed_at: dt.datetime | None = None
    error_count: int = 0
    total_count: int = 0
    # The producer's dropped observations, from its latest row (Step 58(a), L1-46).
    dropped_count: int = 0

    def brief(self) -> dict:
        return {"state": self.state, "reason": self.reason}


def public_mail(state: CapabilityState) -> tuple[str, str]:
    """`provider.resend` as a caller with no session sees it, decided here from the
    internal state and reason: `unavailable` with the one generic reason while no account's
    mail can be sent, otherwise `available` with the available reason."""
    held = state.state == "degraded" and state.reason == MAIL_HELD_REASON
    if state.state == "unavailable" or held:
        return "unavailable", MAIL_NOT_SERVING_REASON
    return "available", AVAILABLE_REASON


def offers_held_sign_in(profile) -> bool:
    """Whether a held sign-in provider is still offered to a signed-out visitor: False
    only for a production profile in live mode with admission open."""
    return not (
        getattr(profile, "is_production", False)
        and getattr(profile, "mode", None) == "live"
        and getattr(profile, "admission", None) == "open"
    )


def public_sign_in(state: CapabilityState, *, offered: bool) -> tuple[str, str]:
    """A sign-in provider as a caller with no session sees it: unless a held one is
    offered, its degraded `sign-in-unverified` state reads `unavailable` with the generic
    reason; every other state reads as built."""
    if not offered and state.state == "degraded" and state.reason == SIGN_IN_HELD_REASON:
        return "unavailable", MAIL_NOT_SERVING_REASON
    return state.state, state.reason or AVAILABLE_REASON


def observed_state(capability: str, row, now: dt.datetime, policy) -> CapabilityState:
    """The derivation's last steps (4 to 6 above), for one capability from its newest
    stored observation: `unknown` with none, `stale` once it is older than the
    capability's freshness bound, otherwise its own outcome, reason and limitations.
    `Readiness` and the tools outside the composition both derive through it."""
    if row is None:
        return CapabilityState(capability, "unknown", "no-observation")
    observed = row["observed_at"]
    age = max(0, int((now - observed).total_seconds()))
    _, freshness, _ = timing(CAPABILITY_BY_ID[capability], policy)
    common = {
        "age_seconds": age, "observed_at": observed,
        "error_count": row["error_count"], "total_count": row["total_count"],
        # Rows written before Step 49's column, and hand-built rows, carry none.
        "dropped_count": row.get("dropped_count", 0),
    }
    if age > freshness:
        return CapabilityState(capability, "stale", "observation-stale", **common)
    return CapabilityState(
        capability, row["outcome"], row["reason_key"], tuple(row["limitation_keys"]),
        **common,
    )


def stored_state_reader(profile, capability: str, clock: Callable[[], dt.datetime], policy,
                        *, process: str) -> tuple[Callable[[], str], Callable[[], None]]:
    """One capability's stored state for a tool that runs outside the composition (the
    import program and `research-review`, reliability-design § 10, L4-11), read from the
    profile's own database under ServiceOperations' login: the newest observation through
    `observed_state`, and `unknown`, with one logged event, when the store cannot be
    opened or read. Only the newest row is read. Returns the
    reader and what closes its connections; nothing is opened before the first read."""
    opened: list = []

    def read() -> str:
        try:
            if not opened:
                from backend.modules.operations.observation_store import ObservationStore
                from backend.transactions import OwnerTransactions

                opened.append(ObservationStore(OwnerTransactions(profile, process=process)))
            row = opened[0].latest([capability]).get(capability)
        except Exception as error:  # noqa: BLE001 - an unreadable store shows no outage
            # One event for a read that raises, the gates' own event (L4-11).
            from backend.log_events import log_exception

            log_exception("operations", "breaker.state-unreadable", error, reason=capability)
            return "unknown"
        return observed_state(capability, row, clock(), policy).state

    def close() -> None:
        while opened:
            opened.pop().transactions.close()

    return read, close


class Readiness:
    def __init__(self, manifest, activations: dict, providers: dict, store, policy,
                 clock: Callable[[], dt.datetime], *,
                 admission: Callable[[], bool] | None = None,
                 release: dict | None = None,
                 held_sign_in_offered: bool = True):
        self.manifest, self.activations, self.providers = manifest, activations, providers
        self.store, self.policy, self.clock = store, policy, clock
        self.admission = admission
        # Whether a held sign-in provider is offered signed out (`offers_held_sign_in`).
        self.held_sign_in_offered = held_sign_in_offered
        # BR6.5: the running release, its tag and commit only; a release's kind or path
        # never reaches `/health/ready` (Step 79(c)).
        release = release or {}
        self.release = {"tag": release.get("tag"), "commit": release.get("commit")}
        self.contribution_of = {
            capability: contribution
            for contribution in manifest.contributions
            for capability in contribution.provides
        }

    # --- derivation -----------------------------------------------------------------

    def derive(self, latest: dict, now: dt.datetime) -> dict[str, CapabilityState]:
        states = {}
        for capability in sorted(self.contribution_of):
            states[capability] = self._one(capability, latest.get(capability), now)
        return states

    def _one(self, capability: str, row, now: dt.datetime) -> CapabilityState:
        if capability == STATIC:
            # Available while the host serves, never stale or unknown; it carries only
            # its latest row's 24-hour error rate (Step 58(c), L1-47).
            if row is None:
                return CapabilityState(capability, "available", None)
            return CapabilityState(capability, "available", None,
                                   error_count=row["error_count"],
                                   total_count=row["total_count"])
        activation = self.activations[self.contribution_of[capability].contribution_id]
        if activation.activation != "active":
            return CapabilityState(capability, "unavailable", activation.reason)
        if self.providers.get(capability) == "unconfigured":
            return CapabilityState(capability, "unavailable", "unconfigured")
        return observed_state(capability, row, now, self.policy)

    def states(self) -> dict[str, CapabilityState]:
        """One short read of the latest observations; an unreadable store leaves every
        observed capability unknown, never available."""
        now = self.clock()
        # `public.static`'s latest row is read with the others, for its error rate alone
        # (Step 58(c)).
        observed = list(self.contribution_of)
        try:
            latest = self.store.latest(observed)
        except Exception:  # noqa: BLE001 - reduced to a fixed reason below
            states = self.derive({}, now)
            return {
                name: CapabilityState(name, "unknown", "store-unavailable")
                if state.state == "unknown" else state
                for name, state in states.items()
            }
        return self.derive(latest, now)

    # --- answers ------------------------------------------------------------------

    def report(self, states: dict[str, CapabilityState] | None = None) -> dict:
        states = self.states() if states is None else states
        missing = sorted(name for name in REQUIRED if states[name].state in UNREADY)
        degraded = sorted(name for name in REQUIRED if states[name].state == "degraded")
        admission_open = True if self.admission is None else bool(self.admission())
        report = {
            "ready": not missing and admission_open,
            "missing": missing,
            "degraded": degraded,
            "manifestRevision": self.manifest.revision,
            "contributions": {
                name: {"activation": item.activation, "reason": item.reason}
                for name, item in sorted(self.activations.items())
            },
            "release": dict(self.release),
        }
        if not admission_open:
            report["admission"] = "closed"
        return report

    @staticmethod
    def live() -> dict:
        return {"process": "alive"}

    def public_projection(self, states: dict[str, CapabilityState] | None = None) -> dict:
        """C01 `listCapabilities` for a caller with no session (BR5.9): the capabilities
        behind the entries that caller may see, account.entry, provider.google,
        provider.orcid and provider.resend, each with its state and reason key alone.
        provider.resend reads only as serving or not serving (`public_mail`), and a held
        sign-in provider reads as not serving once admission opens (`public_sign_in`,
        U8 plan Step 106(h))."""
        states = self.states() if states is None else states
        visible = [entry.capability_id for entry in NAVIGATION if entry.access == "anonymous"]
        names = list(dict.fromkeys([*visible, *PUBLIC_EXTRA]))
        items = []
        for name in names:
            if name == MAIL:
                state, reason = public_mail(states[name])
            elif name in SIGN_IN:
                state, reason = public_sign_in(states[name], offered=self.held_sign_in_offered)
            else:
                state, reason = states[name].state, states[name].reason or AVAILABLE_REASON
            items.append({"capabilityId": name, "state": state, "reasonKey": reason})
        return {"manifestRevision": self.manifest.revision, "items": items}
