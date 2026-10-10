# Internal-disk backup and legacy inventory — 2026-10-10

Follow-up execution is recorded in [SSD01 archive transfer](ssd-archive-transfer-2026-10-10.md). This inventory describes the scan before those moves.

This supplements the completed repository cleanup. It records files outside the DocSuri checkout; none of the discovered files were moved, deleted, or changed. Names and dates identify candidates, not proof that the files are obsolete. `~` means `/Users/revenantonthemission`.

## DocSuri historical candidates

| Location | Logical size | Local allocation | Evidence and disposition |
| --- | ---: | ---: | --- |
| `~/docsuri-backups` | 14.3 MiB | 14.3 MiB | July 12 production database snapshot and two sensitive configuration companions. Candidate for a separately protected historical archive. |
| `~/DocSuriData/aws-final` | 64.2 MiB | 64.2 MiB | Six July–August PostgreSQL snapshots, a final Aurora snapshot, and sensitive companions. Historical migration backup candidate. A newer `.DS_Store` timestamp does not make the snapshots current. |
| `~/Documents/Codex/2026-07-02/review-pr-334-from-a-clean/DocSuri-pr334-review` | 8.40 MiB | 16 KiB | Dated review checkout, latest observed file timestamp August 14. Of 1,198 files counted, 1,196 are cloud placeholders. Git state and uniqueness were not inspected to avoid downloading cloud content. Counts exclude dependencies, Git internals, builds, and caches. |
| `~/Documents/취업/DocSuri Design System.zip` | 2.29 MiB | 0 | June 30 design export; cloud placeholder. |
| Other DocSuri files in `~/Documents/취업` | Varies | 0 observed | June–July demo video, presentation variants, design slides, reports, logo, and standalone HTML. Potential historical materials; may still be useful portfolio evidence. |

The first two directories total **78.5 MiB of logical contents**. Both include sensitive companions, whose contents were not opened. Six files in `aws-final` match local scheduled dumps by filename and size only. This does not establish byte identity or safe deletion.

## Backup sets and service data to preserve

| Location | Observed size | Reason |
| --- | ---: | --- |
| `~/Backups/docsuri` | 401.7 MiB local allocation | Configured local database backup destination; 38 dumps, names dated July 23–September 24. |
| `~/Library/Mobile Documents/com~apple~CloudDocs/DocSuriBackups` | 402.3 MiB logical; 0 local allocation | Configured iCloud backup destination. All 39 observed files are cloud placeholders; none were downloaded. |
| `~/DocSuriData/minio` | 24.2 GiB local allocation | Object-store data with current metadata. The service runbook identifies parse/embed artifacts here and says they have no offsite backup. Live use was not established; do not classify as disposable legacy. |
| `/Library/Application Support/DocSuri` | Unknown | Contains `rem-2` workers and keys, plus `rem-1-test`. Protected subdirectories could not be read; unknown size is not zero. |
| `~/Projects/DocSuri-archive/2026-10-10-pre-v2` | Previously inventoried | Existing verified archive from this cleanup. Excluded from new-candidate totals. |

`~/Library/LaunchAgents/dev.docsuri.backup.plist` configures a daily 03:30 run through `~/.local/bin/docsuri-backup-db.sh`; the script configures both local and cloud destinations. The latest discovered dump is September 24. `launchctl list dev.docsuri.backup` exited 1, so a loaded or functioning schedule was **not confirmed**. Thirty-eight local/cloud files share names and sizes; their contents were not hashed.

The current Docker context lists seven stopped DocSuri/rem-1 containers and no running containers. Their mounts do not establish live use of `~/DocSuriData/minio`; other runtime contexts were not exhaustively examined. No containers, volumes, services, or schedules were changed.

Source: `ops/server/README.md:185–195` identifies the backup destinations and MinIO data. This is documentation evidence, not proof of present runtime state. Graph coverage for this file reported metadata match with no recorded issue (generation `2026-10-10T08:21:17Z`), and the relevant source text was read directly.

## Other historical copies and exports

| Location | Local allocation | Assessment |
| --- | ---: | --- |
| `~/server-migration` | 8 KiB | Two August 18 plist copies for the blog and its tunnel; separate from DocSuri. |
| `~/Downloads/instagram-revenantonthemission-2025-07-09-iL8s1bEx` | 76.98 MiB | Dated personal data export; retention is a personal choice. Contents not opened. |
| `~/Downloads/instagram-revenantonthemission-2025-07-08-4Vd7T2gC` | 81.73 MiB | A second dated personal export; no content comparison performed. |
| `/Users/Shared/Previously Relocated Items*`, `/Users/Shared/Relocated Items`, and the Korean-named relocated-items directory | 3.65 MiB combined | Ten macOS relocation directories. Historical system/configuration material; contents and ongoing relevance not verified. |

Other compressed files in Documents include course materials and installers. The largest name match, `LG_Way_Fit_Test_Mac.zip`, is 429.42 MiB logical but has zero local allocated blocks. A compressed format alone is not evidence of a redundant backup, so ordinary document archives were not labeled disposable.

Additional small candidates, all with zero observed local allocation:

- `~/Documents/취업/2025년하반기포트폴리오_조준희.zip` — 553 KiB logical; dated portfolio package that may still be useful.
- `~/Documents/SGCC/logs_47780160200/runner-diagnostic-logs/52943390646-deploy-production.zip` and `52943425806-notify.zip` — 29 KiB combined; downloaded CI diagnostic archives. Their stored 1979 timestamps are unreliable.
- `~/Documents/2025년 1학기 강의/시스템프로그래밍/참고 자료/code/opt/profile/Makefile~` — 9.7 KiB logical; editor backup in course reference materials.

## Alternate blog worktrees requiring separate review

| Location | Observed local allocation | Status |
| --- | ---: | --- |
| `~/Projects/obsidian-blog-u1-nfr` | 1.76 GiB | Registered worktree on `codex/fix/diagram-render-gate`; clean Git status. |
| `~/Projects/obsidian-blog/.claude/worktrees/u2-home-boundary` | 2.57 GiB | Registered worktree on `codex/feature/resume-home-boundary`; clean Git status. |
| `~/Projects/obsidian-blog/.claude/worktrees/u3-quality-gates` | 2.53 GiB | Registered worktree on `codex/feature/resume-quality-gates`; clean Git status. |

These total approximately 6.86 GiB of observed allocated blocks, excluding dependencies, build output, caches, and Git internals. They are related to a different project; their names do not establish that the branches have been merged or that the work is finished.

Read-only `git worktree list --porcelain` and per-worktree `git status --porcelain=v1 -z` ran with `GIT_OPTIONAL_LOCKS=0`. All three status results had zero staged, unstaged, and untracked entries. Latest observed file timestamps are October 10. Ignored files and merge state were not assessed; retain pending branch/ownership review.

## Small configuration backups

Historical-copy candidates: `~/.claude.json.backup`, `~/.cloudflared/config.yml.bak`, `~/.docker/config.json~`, `~/.p10k.zsh~`, `~/.ssh/known_hosts.old`, `~/#.zshrc#`, `~/.zshrc~`, `~/.zshrc.kaku-backup-1773636837`, and `~/.zshrc.pre-oh-my-zsh`. They occupy roughly 140 KiB combined. No configuration contents or credentials were read for this list.

Application-managed recovery files are separate: `~/.claude/backups` occupies about 640 KiB, and `~/.codex/.codex-global-state.json.bak` about 448 KiB with an October 10 timestamp. Preserve these as recovery state. `~/.DDLocalBackups` reported zero allocated blocks.

## Scope and limitations

- Metadata scan covered 83,496 regular files across Projects, Documents, Downloads, Desktop, Public, Sites, PS, rvnnt-til, and zhuangtzu-pdftolatex, plus 39,167 filenames in selected hidden configuration/application roots. DocSuri backup and service-data roots were inspected separately.
- The DocSuri checkout and its existing archive were excluded from the user-folder scan. Dependencies, Git internals, build output, caches, installed plugins, application bundles, and other noisy runtime trees were pruned as appropriate. Symlinks and additional volumes were not followed.
- Protected DocSuri workers, keys, and test storage under `/Library/Application Support/DocSuri` were inaccessible. The detailed MinIO file walk hit a 20-second limit; its whole-folder allocation above comes from a separately completed `du -sk`, not the partial count.
- This is a bounded scan of likely backup locations on the internal disk, not a complete enumeration of all protected macOS data, snapshots, or virtual-machine filesystems. SSD01 was not scanned.
- Cloud placeholders were identified from filesystem metadata and left undownloaded. Allocated blocks are estimates, not guaranteed disk-space savings: APFS sharing, compression, and cloud behavior may affect actual recovery.
- False-positive filenames such as AWS Backup icon assets, `copy-button.ts`, compatibility source files, and installed archive-tool implementations were excluded from the findings above.
- Raw working inventories are at `/tmp/docsuri-disk-backups.json`, `/tmp/docsuri-disk-userfiles.json`, `/tmp/docsuri-disk-hidden.json`, and `/tmp/docsuri-disk-system-backups.json`. The filtered user-folder inventory and Git findings are at `/tmp/docsuri-disk-userfiles-filtered.json`. They are diagnostic scratch files, not a deletion manifest.
