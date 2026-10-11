# U1 payload codec and publication evidence allocation

## Implemented boundary

The worker codec consumes the generated canonical AssistanceExecutionPayload
and AssistanceAcceptedInput models. It binds immutable accepted paper/version,
eligibility, content hash/revision, owner glossary snapshot, acceptance time,
usage reservation and selected source sections. CorpusContent owns the content
revision calculation. Missing legacy diagnostic fields reject rather than being
reconstructed from current mutable preferences.

Selections preserve original headings and anchors and verify original UTF-8
hashes. A selected span additionally freezes Unicode code-point start/end and
selected UTF-8 hash. This can represent the supported P1 Korean sentence at
s3.5.p1 offsets 227:343 without claiming paragraph or whole-paper translation.
The codec checks the trusted worker identity and current execution authority
before and after CorpusContent reads. Finite limits are eight selections,
256 source chunks and 7,000 selected UTF-8 bytes.

These are codec/component checks. Typed option allocation, canonical admission,
real payload boundary, mounted transport and real executor integration remain
to implement and verify. Normal assistance quality remains unready.

## Publication harness correction

The first repository attempt reached an implementation-specific 16-file
publication evidence cap: 77 passed and one failed in 20.94 seconds. All 16
records occupied 2,217,691 bytes; none was removed. The original worst-case
allocation was 16 × 524,288 bytes = 8 MiB.

The implementation now enforces that same 8 MiB aggregate allocation with a
full 524,288-byte reserve before starting, plus a finite 64-file cap. The owned
publication lock encloses inspection, reservation and final publication for
both CLI and direct Python callers. Direct os.scandir enumeration stops after
1,025 total entries or 65 matching paths, refusing an exceeded allocation;
private regular-file custody, single link, filename, count and latest digest
must reconcile. Orphans, pending records and changed evidence refuse rather
than being adopted or deleted. Serialized size uses the exact sorted,
two-space JSON encoding written by private_json, which adds no newline.

The final successful replay retained every previous attempt and added attempt 19.
Total retained attempt bytes were 2,636,450. Latest record:
corpus-publication-attempt-1791735347686872000.json, SHA-256
76837173a39cf870e7e4591ca9375379b0b5ee3401117b1c57c462febed980d7.
No new model inference was needed for this cached publication replay.

## Executed evidence

Commands (each run independently from the repository root):

```text
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

- Initial codec component run: 139 passed in 3.17 seconds.
- Initial repository run: 77 passed, one evidence-cap failure; preserved under
  `/tmp/docsuri-u1-run/payload-publication-cap-repository-{result.json,junit.xml}`.
- First budget component attempt: 139 passed, ten new tests deselected because
  their phase marker was missing. Preserved as `publication-budget-unmarked-*`;
  this is not evidence that the new checks passed. The marker was corrected.
- Intermediate budget checks passed 149 component / 78 repository cases,
  retained as `payload-budget-final-*`. Inspection of Python 3.13 showed that
  Path.glob eagerly buffers scandir, so the implementation switched to direct
  bounded os.scandir and added an enumeration-stop regression.
- Direct-scandir intermediate run passed 150 component / 78 repository cases,
  retained as `payload-scandir-final-*`. A final review identified that a
  correctly hashed running attempt could still pass; it now refuses and has a
  dedicated unchanged-evidence regression.
- Final component run: 151 collected/executed/passed, no failures/errors/skips,
  in 3.23 seconds. Budget cases cover exhaustion without modifying evidence,
  finite file count, malformed/changed custody and overlapping admission.
- Final repository run: 78 collected/executed/passed, no failures/errors/skips,
  in 21.30 seconds, including real retained corpus publication replay.

Both final runs report unchanged source during execution and source SHA-256
5001ca988527d515054f92dc9054d721339cb720fce599e598ec4140ef2965ef.
Protected reports, full source inventories and JUnit are retained under
`/tmp/docsuri-u1-run/payload-closed-final-{component,repository}-{result.json,junit.xml}`.
Scoped Ruff formatting and lint passed for the six source/test paths.
Graph coverage generation 2026-10-11T16:10:13Z recorded no issue for those paths;
this is best-effort metadata, not exhaustive correctness proof.

Per-module cumulative coverage remains for the completed U1 coverage pass.
Step 13 must reject unassigned collected tests, retain attempt-specific runner
evidence and reject collection/execution mismatches. No completion checkpoint,
normal-model readiness or full contract closure is asserted by this record.
