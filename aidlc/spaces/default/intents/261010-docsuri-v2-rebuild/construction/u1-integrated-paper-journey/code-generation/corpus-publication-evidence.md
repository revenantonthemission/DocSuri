# Corpus publication prerequisite for Discovery

CorpusContent now owns a publication generation, mutable snapshot revision,
manifest hash and timestamp. Publication/withdrawal lock this barrier before
paper/version rows and atomically update the snapshot. Aggregate projection
allocation is 256 chunks across the owned two-source environment, rather than
256 for each publication. Replaying a version with changed parsed content or
projection hash is refused, preserving the immutable source/derived binding.

Discovery obtains a same-transaction share lock through a fixed, no-argument,
schema-qualified Corpus-owned SECURITY DEFINER function. It receives SELECT
and that function's EXECUTE only, without publication UPDATE rights. Its
snapshot query rejects an over-allocation rather than silently truncating.
Search ranking, bound cursors and browser integration are still pending.

Applied the explicit append-only amendment with
`backend/.venv/bin/python scripts/bootstrap_docsuri_u1.py` against the named
owned PostgreSQL 16.15 persistent environment. The command returned
`verified-with-explicit-amendments`. No existing service or user migration ran.

Executed:

```text
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

**22 passed, zero skips, 37.94s.** Existing real persistence/container replacement
cases remained green. The publication case additionally verifies aggregate-cap
rollback, unchanged snapshot after rejected immutable-content replay, denied
Discovery mutation, and changed revision/hash with preserved generation after
withdrawal. Its extra allocation-control row is explicitly named, belongs to the
existing diagnostic source, and is removed in `finally`; no accepted normal
work or accounting was removed. Full concurrent publication/search cursor checks
belong to the forthcoming Discovery component tests. Per-file cumulative
coverage remains to be remeasured; the completed-U1 floor is unchanged.

Scoped Ruff checks passed for the changed repository/bootstrap/test files.
Tier 2 graph generation 2026-10-11T13:12:53Z identified both repository classes;
current exact source was read. Coverage reported no recorded issues for the
Python paths and Discovery schema; Corpus SQL had partial parsing, so its
entire source was read before use. These are bounded findings, not exhaustive
consumer coverage or completed search readiness.
