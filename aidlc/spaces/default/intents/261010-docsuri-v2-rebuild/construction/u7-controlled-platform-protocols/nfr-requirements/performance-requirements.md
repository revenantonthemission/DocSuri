# U7 performance requirements

## Scope and method

U7 is a local, single-operator controlled executable; its performance envelope is
boundedness, not throughput. This document derives performance requirements from
the workflows in [functional-spec.md](../functional-design/functional-spec.md).
Per the requirements, numeric latency targets are **deferred to a measured
baseline** and every number is marked to-be-agreed; only qualitative, checkable
bounds are fixed here.

## Requirements

| ID | Requirement | Source | Measure / closure |
|---|---|---|---|
| NFR2.1 | Every evidence inspection (WF1) completes within a finite, declared per-protocol bound and returns an explicit compatibility label; it never blocks indefinitely. | NFR2 | Timeout enforced; a run that exceeds its bound returns a labelled failure, never a silent wait |
| NFR2.2 | Every controlled operation (WF2/WF3) runs under a finite, per-protocol execution deadline; an effect that exceeds it settles `unknown` for reconciliation, never `completed`. | NFR2, NFR3 | Deadline enforced around the effect; exceedance recorded as unknown |
| NFR2.3 | A receipt read/reconciliation (WF4) is bounded and returns the recorded receipt without triggering new work. | NFR2 | Read latency bounded; no operation created by a read |
| NFR2.4 | No path renders an infinite wait, repeated unintended effect, or render feedback loop; refusals return promptly with a stable error vocabulary. | NFR2 | Negative fixtures assert prompt refusal with no effect |
| NFR2.5 | The operator surface gives timely, distinct feedback for loading, refusal, failure and completion in plain text. | NFR2, NFR6 | Each terminal state has a distinct, announced message (see observability requirements) |

## Bounded execution posture

- At most **one in-flight effect per target**, held under the effect's exclusive
  target lock (also a scalability constraint, NFR8.3).
- No automatic retry: a replay returns the recorded receipt; an indeterminate
  effect is reconciled (WF4/WF6), never re-run.
- Expensive native work stays outside any authority/guard evaluation, so an
  operation's admission is not slowed by the effect it authorizes.

## Deferred numeric targets

Time to evidence inspection, execution latency, reconciliation latency and
cold-start time are recorded as **to-be-agreed**; the baseline run (U8 cumulative
or U7-local) will produce distributions with sample sizes, hardware and
configuration, and the human agrees thresholds afterwards.

## Sources

- [functional-spec.md](../functional-design/functional-spec.md) — workflows WF1–WF7
- [requirements.md](../../../inception/requirements-analysis/requirements.md) — NFR2 and the numeric-target deferral
