# Log Queries — DocSuri observability (as-built recipes)

All logs live in `~/Library/Logs/DocSuri/` (rotated at 50 MB, 3 generations). Recipes use `rg`/`tail`; run them from any shell on the Mac.

## First looks

```bash
ops/server/docsurictl status
ops/server/docsurictl logs web -f          # live web/BFF log
ops/server/docsurictl logs api -f          # live api log
tail -20 ~/Library/Logs/DocSuri/heartbeat.log
```

## The named failure signatures

| What | Query |
|---|---|
| API refused to start (current outage class) | `rg -n "MigrationBlocked\|NEEDS_RECONCILIATION" ~/Library/Logs/DocSuri/api.log` |
| API crash-loop history | `rg -n "Traceback\|Error" ~/Library/Logs/DocSuri/api.log* \| tail -40` |
| Heartbeat probe failures | `rg -n "FAILED probes" ~/Library/Logs/DocSuri/heartbeat.log` |
| Monitoring blind (ping URL unset) | `rg -n "monitoring is blind" ~/Library/Logs/DocSuri/heartbeat.log` |
| Tunnel/ingress trouble | `rg -ni "error\|refused\|unavailable" ~/Library/Logs/DocSuri/tunnel.log \| tail -40` |
| Worker exits / silent stops | `rg -ni "error\|exception\|shutdown" ~/Library/Logs/DocSuri/worker-*.log \| tail -40` |
| Web/BFF upstream problems (gateway hop) | `rg -n "504\|502\|ECONNREFUSED" ~/Library/Logs/DocSuri/web.log` |
| Logrotate behavior / failures | `cat ~/Library/Logs/DocSuri/logrotate.log` |
| Disk pressure context | `df -h /` and `du -sh ~/Library/Logs/DocSuri` |

## Interpretation notes

- The heartbeat's `FAILED probes: api web public` list names exactly which link of the chain broke — read it before digging.
- A `504` from the BFF (e.g., `/bff/api/content-jobs/...`) means the loopback gateway/API is unreachable — the ENV-01 class; the BFF itself is healthy when `/` is 200.
- Launchd's own view: `launchctl list | rg docsuri` (columns: pid, last exit, label). `-` in the pid column for a keepalive agent means it is down.
