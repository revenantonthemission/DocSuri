# Reverse Engineering — bounded test evidence

Recorded: 2026-10-11 09:31 Asia/Seoul (00:31 UTC).
Source commit: `fa671f7f6cf9b29a72ca2189b73ec03eb31f3da3`.

## Purpose and scope

Verify the source finding that the content-job events route emits literal
backslash-n characters where its SSE consumer expects newline delimiters.
One existing isolated test was selected. It uses an in-memory job store,
fake request and authentication objects, and a terminal job. It invokes the
route directly; it does not require a running database, queue, API server,
browser, or model service.

This is evidence about this test and source boundary only. It is not a full
suite result, production reproduction, browser journey baseline, or v2 fix.
Application source and test files were not edited for this check.

## First attempt: module environment

Working directory: `backend/modules/summarization`.

```sh
.venv/bin/python -m pytest tests/test_content_job_api.py::test_events_streams_from_after_seq -q
```

Exit code: **4**. Collection failed while importing
`summarization.api.router`: `ModuleNotFoundError: No module named 'fastapi'`.
The test did not execute. This is an environment limitation, not the SSE
assertion result.

## Executed test: existing backend environment

Same working directory; no dependency installation was performed.

```sh
PYTHONPATH=src:../../../shared/python/src:../../.. ../../.venv/bin/python -m pytest tests/test_content_job_api.py::test_events_streams_from_after_seq -q
```

Exit code: **1**. The selected test executed and failed at
`tests/test_content_job_api.py:248`:

```text
assert states == ["ACCEPTED", "QUEUED", "RUNNING", "COMPLETED"]
AssertionError: assert [] == ['ACCEPTED', ..., 'COMPLETED']
```

The consumer returned no parsed events. This was an assertion failure, not a
skip or collection error. No broader suite was run.

Installed interpreter and package versions for this executed attempt:

| Item | Observed version |
| --- | --- |
| Python | 3.13.7 |
| pytest | 9.1.0 |
| pytest-asyncio | 1.4.0 |
| FastAPI | 0.137.1 |
| Starlette | 1.3.1 |

These are versions observed in the existing environment, not newly selected
dependencies or a statement that it matches every declared project constraint.

## Source interpretation

- Producer: `backend/modules/summarization/src/summarization/api/router.py:156`
  uses escaped backslashes in the SSE event string, yielding literal `\n`
  characters instead of newline separators.
- Consumer: `backend/modules/summarization/tests/test_content_job_api.py:80-102`
  splits on real newline delimiters and looks for a separate `data:` line.
- Test: `backend/modules/summarization/tests/test_content_job_api.py:236-250`
  submits an in-memory job, drives it through four states, and consumes the
  route's stream. The observed empty parsed list agrees with the delimiter
  mismatch in the inspected source.

The scan should carry this reproducible defect into the current-state quality
assessment. Fixing it and verifying browser delivery remain later work.
