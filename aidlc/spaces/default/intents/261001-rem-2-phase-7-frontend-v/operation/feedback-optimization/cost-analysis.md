# Cost Analysis — DocSuri (mac-mini deployment)

Qualitative cost centers of the current architecture. **No figures are invented** — the four rows needing numbers are marked *owner input*; the previous AWS spend is retired.

## Current (local, single host)

| Cost center | Description | Figure |
|---|---|---|
| Hardware | The Mac mini itself (one-time, already owned); SSD wear from logs at multi-GB/day | Owner input (depreciation) |
| Electricity | Always-on host (Mac mini idle draw) + occasional builds | Owner input (kWh × rate) |
| iCloud storage | Daily pg_dump backups land in iCloud | Owner input |
| Cloudflare | Tunnel + edge (free tier viable; any paid plan) | Owner input (plan tier) |
| healthchecks.io | Dead-man's switch checks (free tier viable at this cadence) | Owner input (plan tier) |
| Engineering time | This workflow's operations; ongoing maintenance (logrotate fix, reconciliation, upgrades) | Owner input (internal) |

## Retired

- **AWS:** ECS/ECR/CDK/OIDC/CloudWatch etc. fully decommissioned (2026-08-17 per the server runbook; the last CD workflow file was deleted in this workflow's deployment-pipeline revision). No cloud compute, storage, egress or observability spend remains in the pipeline.

## Notes

- The dominant real-world costs of this architecture are electricity and engineering attention, not licences/subscriptions; both are owner inputs above.
- If figures are wanted for a report, populate the six rows and keep them alongside this document; this workflow deliberately does not fabricate or estimate them.
