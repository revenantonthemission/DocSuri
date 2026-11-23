<!-- INVARIANT: examples are single-line HTML comments so a fresh template parses to total=0 (MEMORY_EMPTY). Do NOT un-comment or split across lines. t100 guards this. -->
> This file is kept up to date automatically while the stage runs. Add observations at the review step, not by editing here directly.

## Interpretations
<!-- example: 2026-05-29T10:14:32Z — chose REST over GraphQL; the consuming team only needs CRUD, revisit if subscriptions land -->
- 2026-10-22T02:57:20Z [unit u8-service-operations-integration] — project.md's Mandated "ALWAYS deploy continuously to production on merge" (affirmed 2026-10-02 for the Phase 7 frontend on AWS) conflicts with U8's approved release path, which changes the root-owned release folder only in person (BR6.5). The person chose in-person installs (Q1 A); the rule is read as not covering this Mac's production, to be recorded through the learnings step at U8's checkpoint.

## Deviations
<!-- example: 2026-05-29T10:14:32Z — skipped the optional caching layer the stage prose suggested; the dataset is small enough that it adds risk -->
- 2026-10-22T02:57:20Z [unit u8-service-operations-integration] — release.yml's tagging step gains create_annotated_tag: true: the action's documented default is false (lightweight tags), while CONVENTIONS.md requires annotated tags. The workspace build also moves into the release workflow as a release asset with its SHA-256, so no Node.js is needed on this Mac.

## Tradeoffs
<!-- example: 2026-05-29T10:14:32Z — picked TDD over BDD this run; the team is unit-first and the domain is well-understood -->
- 2026-10-22T03:06:29Z [unit u8-service-operations-integration] — Made branch protection require only the checks that always report (ci.yml's every-push jobs and the new unfiltered complete verification lane), not the path-filtered per-unit lanes, which would hold a pull request forever; and made the isolation check compare against an installer-written arrangement manifest instead of the running release's templates, so a switch back never leaves the check failing.
- 2026-10-22T03:06:29Z [unit u8-service-operations-integration] — The fork has no main and no tags (v1.19.0 is local and lightweight), so the first v2 release pushes an annotated v1.19.0 baseline, creates main with a one-off push of a commit carrying BREAKING CHANGE, and guards that the computed tag is v2.0.0, instead of trusting the tagger to find a baseline that is not there.
- 2026-10-22T02:57:20Z [unit u8-service-operations-integration] — The performance phase runs on this Mac at each install (about 20 minutes, sharing the machine with production) rather than only in CI, because NFR8.11 requires measuring before a release reaches production and GitHub's runners say nothing about this Mac's hardware. The pre-release backup is taken after v2 stops, so it is consistent, at the price of a few more minutes behind the maintenance notice.

## Open questions
<!-- example: 2026-05-29T10:14:32Z — confirm the retention window with compliance before the next stage hardens the schema -->
- 2026-10-22T03:15:18Z [unit u8-service-operations-integration] — cicd-pipeline.md § 3.1 says every required check reports on every push and pull request, but ci.yml's dependency-review runs on pull requests only. It blocks nothing, since required checks gate pull requests; left as a wording fix for Code Generation and U8's checkpoint, because the reviewed file is closed to edits.
- 2026-10-22T03:15:18Z [unit u8-service-operations-integration] — Each release lives in releases/<tag>/ with its uv environment built at that final path, and release and release-previous are root-owned links, because uv environments record absolute paths and do not survive a folder rename; Code Generation should prove the swap and the switch back import from the linked real path.
- 2026-10-22T02:57:20Z [unit u8-service-operations-integration] — An isolation lapse shows on 운영 and blocks the soak and the switch but emails nobody, because platform.isolation is not a required capability; a fourth healthchecks.io check would carry it, which changes NFR9.6's three checks and is the person's decision.
