# SSD01 archive transfer — 2026-10-10

Status: complete. All 37 inventoried moves and the PR334 source/history transfer completed and verified.

## Completed

- Verified the existing `2026-10-10-pre-v2` archive on SSD01 against all 671 files and 339,819,999 bytes of the local archive, then removed the redundant local copy. All legacy manifest entries and the Git recovery bundle passed independent verification.
- Moved `~/docsuri-backups` and `~/DocSuriData/aws-final`: 13 files, 82,312,415 bytes. All contents and modes verified before and after source removal. Current backup scripts use separate local/iCloud destinations, which remain intact.
- Updated the retained operator runbook and repository cleanup record to point to SSD01. All five mapped historical reference files resolve.
- Completed verified moves of all 37 inventoried roots/items under `/Volumes/SSD01/DocSuri-archive/2026-10-10-disk-legacy/home/`, preserving their home-relative paths. This set contains 625 files and 362,846,485 bytes. All 37 original roots/items have been removed after verifying their archived copies. The user explicitly approved the 35 broader entries listed below, including removal of their synced iCloud originals.
- Removed the PR334 review checkout's 16 confirmed generated dependency/cache roots: 26,129 files and 1,441 symlinks, 487,782,563 logical bytes. Only 53,248 bytes were locally allocated before removal because most were cloud placeholders. Then archived all 3,413 remaining files (170,338,222 bytes), preserving source, manifests, lockfiles, and independent Git history. The original checkout was removed after full verification. Subsequent Finder changes affect only generated `.DS_Store` metadata; all 3,412 historical source/config/Git files (170,332,074 bytes) still match their SHA-256 hashes, modes, and resource forks. Git integrity passed with no external object dependencies or partial-clone requirements.

## Completed broader move list

The following 35 entries were moved after explicit approval: 612 original files (280,534,070 bytes of contents). Their SSD copies were checked before and after source removal. Documents originals were removed from their synced iCloud locations as approved; the SSD archive is their retained copy. Logical byte totals are not guaranteed local disk-space savings.

Automatic approval review initially rejected the broad move because some items were only candidates. Verified copies and the exact list were prepared; the user then selected “Complete all 35 listed moves.” Execution completed under that explicit approval. One check paused when Finder changed two `.DS_Store` layout files in an archived export; all content files still matched. Those layout copies were restored from the unchanged originals, then verification and removal completed.

| Original path | Files | Bytes |
| --- | ---: | ---: |
| `~/server-migration` | 2 | 3,660 |
| `~/Documents/취업/DocSuri_DEMO.mp4` | 1 | 49,756,144 |
| `~/Documents/취업/DocSuri_Presentation.pptx` | 1 | 16,667,666 |
| `~/Documents/취업/DocSuri Presentation (Keynote).pptx` | 1 | 9,675,420 |
| `~/Documents/취업/DocSuri_Presentation_Final-2_v2.key` | 1 | 7,970,593 |
| `~/Documents/취업/DocSuri_Design_System.pptx` | 1 | 7,537,847 |
| `~/Documents/취업/DocSuri_Presentation_Final.pptx` | 1 | 6,598,709 |
| `~/Documents/취업/DocSuri_Presentation_Final.pdf` | 1 | 5,801,367 |
| `~/Documents/취업/DocSuri Design System.zip` | 1 | 2,404,021 |
| `~/Documents/취업/DocSuri_Design_System-2.pptx` | 1 | 2,203,047 |
| `~/Documents/취업/DocSuri 발표자료 초안(2).pptx` | 1 | 1,512,067 |
| `~/Documents/취업/DocSuri App (standalone).html` | 1 | 1,307,472 |
| `~/Documents/취업/DocSuri_로그수집_수익화전략.pdf` | 1 | 931,613 |
| `~/Documents/취업/DocSuri 발표자료 초안.pdf` | 1 | 847,314 |
| `~/Documents/취업/DocSuri 팀프로젝트 계획서.pdf` | 1 | 583,036 |
| `~/Documents/취업/DocSuri 팀 프로젝트 결과 보고서 1 2.pdf` | 1 | 346,323 |
| `~/Documents/취업/DocSuri 팀 프로젝트 결과 보고서 1.pdf` | 1 | 247,757 |
| `~/Documents/취업/docsuri_logo-512w-downscale.net.png` | 1 | 140,921 |
| `~/Documents/취업/DocSuri 팀 프로젝트 결과 보고서 1.docx` | 1 | 21,595 |
| `~/Documents/취업/DocSuri 팀 프로젝트 결과 보고서.docx` | 1 | 16,481 |
| `~/Documents/취업/2025년하반기포트폴리오_조준희.zip` | 1 | 566,452 |
| `~/Documents/SGCC/logs_47780160200/runner-diagnostic-logs/52943390646-deploy-production.zip` | 1 | 20,300 |
| `~/Documents/2025년 1학기 강의/시스템프로그래밍/참고 자료/code/opt/profile/Makefile~` | 1 | 9,910 |
| `~/Documents/SGCC/logs_47780160200/runner-diagnostic-logs/52943425806-notify.zip` | 1 | 9,733 |
| `~/Downloads/instagram-revenantonthemission-2025-07-09-iL8s1bEx` | 290 | 80,130,073 |
| `~/Downloads/instagram-revenantonthemission-2025-07-08-4Vd7T2gC` | 288 | 85,104,738 |
| `~/#.zshrc#` | 1 | 1,795 |
| `~/.claude.json.backup` | 1 | 14,535 |
| `~/.cloudflared/config.yml.bak` | 1 | 322 |
| `~/.docker/config.json~` | 1 | 175 |
| `~/.p10k.zsh~` | 1 | 89,527 |
| `~/.ssh/known_hosts.old` | 1 | 9,095 |
| `~/.zshrc.kaku-backup-1773636837` | 1 | 1,359 |
| `~/.zshrc~` | 1 | 2,189 |
| `~/.zshrc.pre-oh-my-zsh` | 1 | 814 |

## Preserved

The current DocSuri source and live frontend build, configured local/iCloud database backups, MinIO object data, protected service workers/keys, current application recovery files, and macOS relocated-items folders remain. Three blog worktrees are merged and clean in Git, but their ignored content/assets/artifacts were not established as disposable, so they remain.

## Receipts and verification

- Existing archive: `/Volumes/SSD01/DocSuri-archive/2026-10-10-pre-v2/`
- Verified local-copy removal: `/Volumes/SSD01/DocSuri-archive/2026-10-10-local-copy-removal.json`
- New copies and per-entry SHA-256 manifests: `/Volumes/SSD01/DocSuri-archive/2026-10-10-disk-legacy/receipts/`
- Approved broader move receipt: `/Volumes/SSD01/DocSuri-archive/2026-10-10-disk-legacy/approved-move-completion.json`
- Confirmed snapshot moves: `/Volumes/SSD01/DocSuri-archive/2026-10-10-disk-legacy/confirmed-docsuri-snapshot-moves.json`
- PR334 transfer and final checks: `/Volumes/SSD01/DocSuri-archive/2026-10-10-pr334-review/transfer-results.json`, `archive-sha256-manifest.json`, `post-move-verification.json`, and `git-fsck.log`
- Independent verification of the 37 moved roots: `/Volumes/SSD01/DocSuri-archive/2026-10-10-disk-legacy/final-independent-verification.json`

File contents were never printed. Copies used macOS `ditto` with resource-fork, extended-attribute, and ACL preservation, and contents/modes were checked using SHA-256 manifests. Source removal uses the exact verified membership and refuses unexpected additions or changed files. No service was restarted or deployed. No changes were committed. Independent final verification of all 37 moved roots passed: all 625 file hashes and modes match, original paths are absent, and both completion receipts agree.

All archived payloads are physically present on SSD01: a final metadata scan found zero cloud placeholders. The archive root remains mode 0700. The empty former local archive parent was removed. All copy/download processes finished; no background transfer remains.
