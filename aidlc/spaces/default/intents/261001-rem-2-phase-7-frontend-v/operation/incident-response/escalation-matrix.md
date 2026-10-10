# Escalation Matrix — DocSuri

Single-owner operation on a single host. Contacts are deliberately minimal: the real contact channels (alert destinations, provider accounts) live in the private configuration, not in this repository.

| Trigger | First responder | Escalate to | Channel | SLA expectation |
|---|---|---|---|---|
| P1 (public down) | Owner (`revenantonthemission`) | — (single owner; provider escalation below if the fault is at the edge) | healthchecks.io alert (existing path) → owner's configured channels | Immediate |
| P2 (core capability broken) | Owner | — | Same | Same day |
| P3 (component down) | Owner | — | Monitoring entry | Next maintenance window |
| P4 (minor/observability) | Owner | — | Backlog | Scheduled |

## External dependencies

| Dependency | Role | Escalation path |
|---|---|---|
| Cloudflare (edge + tunnel) | TLS/ingress; if edge is down the public probe fails while local probes pass | Cloudflare status page, then the provider's support via the owner's account (credentials in the private config) |
| healthchecks.io | Alerting authority (dead-man's switch) | Account owner: `revenantonthemission` |
| Home utilities | Power/ISP — the most likely single-point failures for a home-hosted server | Owner; no external escalation |

## Notes

- No invented phone numbers, rotations or on-call schedules: this is a single-owner deployment, and the truthful contact is the owner handle plus the channels configured in `~/.config/docsuri/monitoring.env` and the owner's account settings.
- If the deployment ever gains additional operators, this matrix gains a rotation row and paging integration — recorded as a growth item, not current fact.
- Incident communication always flows through the owner; nothing in this repository asserts an external communications channel it cannot verify.
