# Performance Requirements — U8 complete service operations and integration

Date: 2026-10-22 (Asia/Seoul)
Unit: u8-service-operations-integration (service). Sources:

- confirmed [nfr-requirements-questions.md](nfr-requirements-questions.md) (Q4, Q10, Q12, Q20–Q22);
- inception [requirements FR4.1 and FR4.2](../../../inception/requirements-analysis/requirements.md);
- this Unit's [functional spec](../functional-design/functional-spec.md) and [rules](../functional-design/rules.md);
- the [technology stack](../../../../../codekb/DocSuri/technology-stack.md);
- this Mac: Apple M4 Pro, 14 cores, 24 GiB of memory, macOS 27.0.1.

The inception requirements name no performance requirement, so **NFR8** is derived here from FR4.1 (production-level operation on this machine). NFR8.1–NFR8.11 are the performance targets. NFR8.12–NFR8.18, the capacity targets, are in [scalability-requirements.md](scalability-requirements.md).

## Conditions

Every target holds on this Mac at 20 concurrent signed-in users (NFR8.12), with v1 still running beside v2 until the switch and the model runtime shared with v1. Percentiles are 95th unless stated. They are measured by the complete verification's performance phase on the composed realm and during the soak on the production profile. The soak's measurements are recorded with its evidence and shown with your switch-start decision (BR9.14).

## Response targets (NFR8)

| ID | Measure | Target | How it is measured | Source |
|---|---|---|---|---|
| **NFR8.1** | Health route, local | under 200 ms | the heartbeat and the complete verification, against `127.0.0.1:18200` | [Q10] |
| **NFR8.2** | Loading the workspace through the public address | first load under 2 s, later navigation under 1 s | a real browser through the public address, from navigation start until the shell is rendered with navigation resolved (BR5.1); later navigation from the click to the destination view rendered | [Q10] |
| **NFR8.3** | API reads, server time | under 500 ms | the host's server timing per route class, with identifiers only (NFR3.9) | [Q10] |
| **NFR8.4** | Search results | under 3 s, including the local embedding of the query | from the request to the first results page, with the pinned `bge-m3` model | [Q10] |
| **NFR8.5** | Accepting a research, novelty or export request | under 1 s; the work itself runs in the background | from the request to its accepted answer | [Q10] |
| **NFR8.6** | Start to ready after a restart | under 3 minutes | from the moment the restarted jobs start (boot completed, or a crashed job relaunched) to readiness true (BR3.1), including PostgreSQL's own start and crash recovery, the model runtime and the tunnel. Measured at the installation's authorized restart (Workflow 20 step 10), at v1's restart rehearsal, and in the complete verification for a crashed host and a crashed PostgreSQL | [Q10] |

## Resource targets (NFR8)

- **NFR8.7** — Memory [Q10]:
  - v2's host and workers together use under 4 GiB of resident memory at 20 concurrent users.
  - v2's PostgreSQL instance runs with `shared_buffers` of 512 MiB and at most 50 connections.
  - The rest of the 24 GiB stays for the shared model runtime with its two pinned models, v1's data plane until it retires, and macOS.
- **NFR8.8** — A dry run, from the start of its snapshot to its parity report, completes within 2 hours. The final run is the same work inside the 4-hour switch time bound (Q4), so this leaves room for the switch's other steps. Each dry run records its duration, and the accepted dry run's duration is shown with your switch-start decision (BR8.15, BR9.14).
  - Every migrated paper is embedded again locally (Q12), and the duration includes that.
  - At today's 599 documents the run is expected to take minutes.
- **NFR8.9** — For a database within the 8 GiB budget, a backup completes within 25 minutes, and a restore into a database within 45 minutes. A restore verification, with its checks and the scratch database's removal, completes within 60 minutes. These are the same bounds NFR7.9 uses for a production restore. That way the 04:00 backup and the Sunday 05:00 verification settle before the day's traffic, and the disposal pass, which runs after each scheduled backup, is not held back (BR4.3, BR4.5, BR9.17).
- **NFR8.10** — The runtime isolation check completes within 60 seconds, well inside its 5-minute interval (Q21, BR6.12).
- **NFR8.11** — Pinned versions are part of every measurement [Q22]. A runtime upgrade (PostgreSQL, Ollama, cloudflared or Python) is measured again against NFR8.1–NFR8.6 before its release reaches production, because the targets are measured on the pinned versions.
