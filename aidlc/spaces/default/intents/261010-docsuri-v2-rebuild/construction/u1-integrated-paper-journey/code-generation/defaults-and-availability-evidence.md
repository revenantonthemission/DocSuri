# Explicit defaults and unavailable saved references

Date: 2026-10-11. Step 7/8 component work; mounted presentation is pending.

Personalization now owns revision-bound explicit defaults through the generated
`SettingsSnapshot` and `SettingsUpdateInputHttp` bindings. Cold-start reads return
a deterministic owner-bound absence revision without inserting settings or
inventing interests. Manual defaults work with behavioral consent disabled.
Current authority precedes exact receipt replay; fresh updates require CAS.

Six new component tests cover read-only cold start, fresh-service persistence,
receipt replay after later mutation, changed intent/stale revision, manual use
without behavioral consent, current/cross-account authority and invalid input.
The component phase passed **33 tests**, zero skips/errors/failures, in 2.98
seconds. The current local option vocabulary is explicitly bounded and must be
coordinated with actual Discovery/Assistance options before mounted use. It does
not redefine the later-unit retained option set or claim full personalization.

CorpusContent now exposes a narrow locked `reference_availability` function to
Library and PaperAssistance. It returns a disposition without exposing corpus
text or granting content access. Owner-authorized saved-paper and assistance
history lists retain the original paper/version identity when its source is
withdrawn; one withdrawn item no longer hides independent eligible saved work.
Direct content/result guards still deny withdrawn material.

The repository phase passed **22 tests**, zero skips/errors/failures, in 38.26
seconds. The real corpus-publication test now saves both an eligible reference
and the exact source subsequently withdrawn, verifies both remain listed with
different availability, and verifies withdrawn content remains denied. The
result-history check verifies withdrawn disposition while direct result bytes
remain denied. Scoped Ruff checks passed. These are service/repository results;
the Korean UI must still render the per-item disposition accurately.

```bash
python3 scripts/verify_docsuri_u1.py --phase component --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
python3 scripts/verify_docsuri_u1.py --phase repository --profile synthetic-local --environment-file /tmp/docsuri-u1-run/environment.json
```

The append-only corpus availability amendment was applied through the owned
synthetic bootstrap. No legacy source, production user state or old reviewed
schema bytes were rewritten. Final per-file coverage remains part of the next
cumulative measurement and does not follow from these counts alone.
