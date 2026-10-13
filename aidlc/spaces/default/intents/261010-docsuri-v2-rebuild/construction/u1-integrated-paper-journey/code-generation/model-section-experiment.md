# Bounded source-grouping generation experiments

The parent authorized a source-grouping experiment at the completed search
component boundary: retain the same pinned local models and original exact
source, at most eight sections, 2048 context/224 output tokens per call, and one
90-second deadline across the whole work item including admission waits.

The first experiment generated a structured result for each original block and
assembles their text without a second synthesizing step. Each section retains
exact anchors, source hash and request identity. A failed section rejects the
whole result; prior sections remain private diagnostic attempts only. The
aggregate request hash includes the strategy, options and ordered section
request hashes. No canned answer or manufactured citation is inserted.

An in-process reentrant permit is held across the complete work item, preventing
other callers from interleaving section/embedding calls. Each inference clamps
its deadline to the work deadline. An active timer force-stops the owned process
group at the deadline, including during an HTTP call or admission wait; it is
cancelled/joined before releasing the permit. Process close is serialized.
Cross-process isolation remains Step 13 work.

After implementation, targeted fault tests verified permit exclusion, a timer
firing while the caller is blocked, and whole-result rejection after one valid
section followed by an invalid reference. This timer test substitutes the stop
callback; actual native process fault/recovery enforcement still needs the
later operations tests. Component phase: **65 passed, zero skips, 3.10s**.

The approved real model command then returned **5 transport/reference checks
passed, zero skips, 59.21s**. Protected evidence is
`/tmp/docsuri-u1-run/model-output-1791725161031146000.json`. P1 scaling used two
calls/10.22s, position four/13.97s, P2 six/24.62s, and the selected Korean
translation one/2.63s. Every section attempt, raw output, exact source mapping,
source/config identity and sampled resource observation is retained there.
The owned server exited 0. No model download, paid fallback, shared-service
mutation, database job or Usage reservation occurred.

## Result: useful summary readiness remains false

Per-block generation fits the finite deadline and avoids aggregate compression,
but sparse blocks encourage unsupported surrounding explanations. The position
output turns possible extrapolation into enabled extrapolation; P2 adds
performance/relevance claims absent from individual supplied blocks and
imprecisely describes the denoising objective as parametric memory. P1 scaling
also shifts source certainty and gives ambiguous formula prose. Valid structured
references alone do not establish support for those claims.

The selected Korean sentence preserves its meaning again. The real two-paper
embedding diagnostic remains separate from full application research-query
acceptance. This experiment does not close the P1/P2 summary requirement and
does not select successes from different implementations as a readiness result.
Keep the previous failed/incomplete attempts and the parent's bounded rubric
corrections. Any further source grouping or model strategy needs its own explicit
bounded evidence; no further prompt-only iteration was run here.
## Evidence attribution correction after the run

Parent inspection found that validating each block immediately before its call
could attribute the previous raw response to a later block that failed validation
before inference. The complete bound source/action/language is now validated
before any work begins, and each attempt clears its raw-response slot.
The added changed-later-source/invalid-anchor regression initially failed in
test setup because of a duplicate keyword (65 passed/1 failed, 4.63s); correcting
that fixture expression yielded **66 passed, zero skips, 3.04s**. Scoped Ruff
passed. No real model rerun was needed to relabel the previous result: its exact
tested source remains in the protected manifest, and this input/evidence fix
does not claim improved output quality.

## Exact section hierarchy candidate

Parent review authorized one follow-up that groups blocks by their exact full
section path, keeping the scaling equation with its prose and the four position
blocks together. P2 has five source-section groups. The instruction changed
from universal component-storage/candidate language to neutral preservation of
definitions, mathematical meaning, causal reasoning, distinctions and source
certainty. Both grouping and instruction changed; this is not a single-variable
ablation. Per-call and whole-work allocations remained unchanged.

Component checks: **66 passed, 3.01s**. Real model phase: **5 binding checks
passed, 42.17s**, server exit 0. Evidence:
`/tmp/docsuri-u1-run/model-output-1791725385087554000.json`.
Parent review accepts bounded P1 scaling/position and the selected translation.
P2 preserves the variant/index distinction but still omits the explicit
BART-parameters/parametric-memory definition. Overall readiness remains false.

## Generic definition-priority refinement

Parent then authorized one generic refinement prioritizing explicitly defined
terms and what they denote ahead of benchmark/history/training/model-size detail.
No paper-specific expected answer or glossary was inserted. This preserves the
same section grouping and all finite limits. Component checks returned
**66 passed, 3.15s**; a subsequent source-line wrap preserved the same prompt
string, and scoped Ruff passed.

Real model phase returned **5 binding checks passed, 44.74s**, server exit 0.
Evidence: `/tmp/docsuri-u1-run/model-output-1791725542704492000.json`.
P1 scaling now incorrectly says scaling prevents large gradients, reversing the
source's extremely-small-gradient problem. P2 again omits the explicit
parametric-memory definition. The selected Korean sentence remains faithful,
but this same-implementation aggregate is not ready. This is a substantive
semantic failure, despite successful JSON/citation/deadline checks. No further
model run followed this failed refinement. All raw attempts and exact source
identities are retained; successful pieces from different revisions are not
combined into an acceptance claim.
