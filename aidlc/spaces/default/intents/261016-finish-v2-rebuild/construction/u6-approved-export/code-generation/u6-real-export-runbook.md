# U6 one real Notion export — operator runbook

Status on 2026-10-20: **not run.** Nothing in this runbook has been done. No Notion
integration, token or `real-export.json` exists, and no request has gone to
`api.notion.com`. This runbook is the procedure of cicd-pipeline §5 written against
the code as built.

**When it runs.** At **Build and Test**, never in Code Generation and never in CI, and
only **after the owner explicitly approves the exact content** shown in the preview
(BR8.2, NFR6.3). The synthetic Construction Verification Command and the U6
checkpoint come first; the real export is separate operator evidence and is never
part of that command.

**Where it goes.** Into the owner's **own single-member Free Notion workspace**
(infrastructure Q2 A, NFR6.1, NFR6.2), onto **one** page that the owner shares with
the integration (the activation destination). No other workspace, page or person's
data is involved.

**How it ends** (Q2 A). Straight after the evidence is recorded: DocSuri
disconnects, which deletes the stored token; the environment is archived, which
deletes its key; and the owner is advised to remove the integration's access in
Notion. Section 9 to section 12 below.

**Run order.** 1 → 2 → 3 → 4 → 5 → 6 → **STOP for approval** → 7 → 8 → 9 → 10 → 11
→ 12. Each step is for the operator (the person) to run, in order, with the stated
stops. All commands run from the repository root.

Decisions this runbook implements (the person's, authoritative):

- the owner's own single-member Free workspace; $0 budget, no paid plan or service
  (NFR6.1);
- one export, of synthetic content (the fixture novelty result), to one activation
  page;
- an internal integration that may only **read content** and **insert content**:
  no update content, no comment access, no user information (security design §6.4,
  D7);
- close-down straight after the evidence (Q2 A);
- committed evidence holds digests only: no token, no digest of a token, no header,
  no page content, no workspace name and no plaintext provider identifier
  (cicd-pipeline §5 step 9);
- the preserved environment is deleted no later than 7 days after the export
  (NFR1.5; cicd-pipeline §5 step 13).

## 1. What the code provides

| Piece | Where | Behaviour |
|---|---|---|
| Real composition | `backend/u6_real_export.py` → `assemble_u6_real` | Separate from the synthetic `assemble_u6`. Reads `real-export.json`; any missing, extra or invalid value refuses with POLICY_UNRESOLVED naming the field; no fallback. Refuses an environment that holds any evidence file (`*-evidence-*.json`). Only the activation destination is usable (BR8.2). |
| Host flag | `scripts/serve_docsuri_u6.py --real-export` | Without the flag the host is synthetic over the fake Notion, and it refuses an environment holding `real-export.json`. The tool's bounded `serve` phase never passes the flag. Listens only on `https://127.0.0.1:18099`, `access_log=False`. |
| Settings | `/tmp/docsuri-u6-run/real-export.json` (0600, run-bound, at most 4096 bytes) | Exactly `runId`, `activationDestinationId`, `freeTerms` (`plan`, `memberCount`, `checkedOn`, `publishedLimits`). Never holds the token. |
| Token | typed into the connect form only | Sealed (AES-256-GCM envelope) in `docsuri_u6` with the environment's key in `export-keys/`; the form field is cleared after submit; never in a file, an environment variable, a log or the evidence. |
| Operator tool | `scripts/u6_real_export.py --action check\|outcome` | `check` names every gap in the settings and an environment that holds evidence. `outcome` prints digests and fixed values only. Neither builds a Notion client. |
| Isolation | `scripts/verify_docsuri_u6.py` | Every synthetic phase (`fixtures`, the test phases, `frontend`, `browser`, `serve`) refuses while `real-export.json` exists. `archive-owned` is not synthetic and runs. |
| Close-down | `--phase archive-owned` | Deletes the key file once every check passes, keeps the stopped database container and volume and moves the folder to `/tmp/docsuri-u6-preserved-<runId>-<8 hex>`. `teardown` refuses while a key file exists. |

## 2. Fresh real-export environment

Use an environment of its own, never the checkpoint's. If a U6 environment exists,
archive it first (this deletes its key and keeps its evidence):

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase setup --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase migrate --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase fixtures --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

- `setup` must report `base-installed` with the key folder at `0700` and 0 entries;
  `migrate` must report `u6-migrated` (69 migrations at this source).
- `fixtures` prepares the two synthetic accounts and memberA's ready synthetic novelty
  result through U4's own service, so the exported content is synthetic. It writes
  no evidence file.
- **Run no other phase** in this environment. Any test, `frontend`, `browser` or
  `serve` phase writes an evidence file, and the real composition then refuses the
  environment.
- If Docker reports too little free memory at `setup`, archive a finished
  environment with that unit's own `archive-owned` phase; never stop or remove a
  container by hand.
- The environment lives at most 24 hours from `setup`; finish sections 3 to 11
  inside that time.

## 3. Notion: the integration and the one shared page (owner, in Notion)

1. Confirm the workspace is the owner's own, on the **Free** plan, with **one
   member**. Note today's date; it becomes `freeTerms.checkedOn`.
2. Open Notion's published limits that apply and copy them, as published on that
   day, for `freeTerms.publishedLimits`: the block limit for Free workspaces with
   more than one member, and the API request limits. Keep the wording short (each
   entry at most 256 characters, 1 to 8 entries).
3. Create an **internal** integration in that workspace with only these
   capabilities: **Read content** and **Insert content**. Leave **Update content**
   off, give it **no comment** capabilities and **no user information**. These are
   exactly what the connect form's help text names.
4. Create or choose **one** page for the export and share it with the integration
   (the page's connections). Share no other page.
5. Copy that page's id: the 32 hexadecimal characters at the end of its link,
   lowercase, without dashes. It becomes `activationDestinationId`.
6. Keep the integration's token **only in Notion** until section 6. Do not paste it
   into a terminal, a file, a chat, an issue or this repository.

## 4. Settings file (operator writes it; never holds the token)

```bash
umask 077
RUN_ID=$(backend/.venv/bin/python -c 'import json;print(json.load(open("/tmp/docsuri-u6-run/environment.json"))["runId"])')
cat > /tmp/docsuri-u6-run/real-export.json <<EOF
{"runId": "$RUN_ID",
 "activationDestinationId": "<the 32 lowercase hex characters from section 3 step 5>",
 "freeTerms": {"plan": "free", "memberCount": 1, "checkedOn": "<YYYY-MM-DD from section 3 step 1>",
  "publishedLimits": ["<free-workspace block limit as published>", "<API request limits as published>"]}}
EOF
chmod 600 /tmp/docsuri-u6-run/real-export.json
```

From here until the archive in section 11, every synthetic phase refuses. To back
out before section 6, delete this file; the environment is then synthetic again.

## 5. Readiness check

```bash
backend/.venv/bin/python scripts/u6_real_export.py --environment-file /tmp/docsuri-u6-run/environment.json --action check
```

It must print `"state": "ready"` with `"gaps": []`. Otherwise every gap is named:
`settings-absent`, `settings-custody` (mode, owner or size), `settings` (wrong field
set or not JSON), `runId`, `activationDestinationId`, `freeTerms`,
`freeTerms.plan`, `freeTerms.memberCount`, `freeTerms.checkedOn` (malformed or in
the future), `freeTerms.publishedLimits`, or `environment` (it holds an evidence
file: start again at section 2). Fix the named gap and run `check` again.

## 6. Start the real host, connect, choose and preview (no export yet)

1. In its own terminal:

   ```bash
   backend/.venv/bin/python scripts/serve_docsuri_u6.py --real-export --environment-file /tmp/docsuri-u6-run/environment.json
   ```

   Startup refuses with POLICY_UNRESOLVED on any settings gap, and refuses an
   environment that holds evidence. Keep it running until section 10.
2. Open `https://127.0.0.1:18099` in a browser on this machine. The certificate is
   the environment's self-signed local one; before accepting it, compare its SHA-256
   fingerprint with `certificateSha256` in `/tmp/docsuri-u6-run/approved-export-tls.json`.
3. Sign in as memberA. Its e-mail and password are in
   `/tmp/docsuri-u6-run/browser-fixtures.json` (0600) under `accounts.memberA`;
   read them yourself and do not copy them anywhere else. The `notionToken` field in
   that file is the fake's synthetic token and does **not** work here.
4. Open "내보내기" → "Notion 연결" and paste the integration's token into the connect
   form. While the check runs the form shows "확인 중"; afterwards the field is
   empty. The connection panel shows the workspace as connected.
5. Open the research workspace's ready novelty result and choose "Notion으로
   내보내기". Opening or closing the flow never exports.
6. Choose the activation page: it is the only usable destination; every other page
   is shown as not allowed. Its creation capability reads "페이지 만들기 권한: 확인
   전" until the first write.
7. Read the preview: the source and destination summaries, the rendered page with
   its marker line, and any earlier-export notice.

**STOP: show the owner this preview and get explicit approval of this exact content
and destination before section 7.** If anything changes (a different destination, a
new preview revision, a reconnect), preview again and ask again. Without that
approval, go to section 10 and close down without exporting.

## 7. The one approved export

The owner presses "승인하고 내보내기" once. That press is the approval of the exact
content shown and the request to write it; it creates one page under the activation
page. The outcome step follows the export until it ends and announces each change.

- `succeeded`: the link is named by the page title. Open it in Notion and note
  whether the page lists the integration as its creator.
- `unknown`: the result was not observed. Nothing re-sends it. Wait for the shown
  next check; if it stays unknown, settle it in "내보내기 기록" only after looking in
  Notion yourself.
- `failed` with a refusal reason: the hint names the fix (share the page, enable
  content insertion, the block limit). Do **not** export again without a new
  approval of a new preview.

Never start a second `--real-export` host or a second export to "retry".

## 8. Evidence, digests only

With the host still running or stopped (it reads the database only):

```bash
backend/.venv/bin/python scripts/u6_real_export.py --environment-file /tmp/docsuri-u6-run/environment.json --action outcome
```

It prints `date`, `runId`, `sourceCommit`, `freeTermsReference`, `effectState`,
`outcomeReason`, `settledBy`, `outcomeClass`, `pathKind` (must be `real`),
`creatorConfirmed`, `requestIdSha256`, `pageLinkSha256` and `retentionDeadline`.
It refuses with `exactly-one-export-required` unless the environment holds exactly
one export; pass `--effect-id <uuid>` only if told to.

Record in the Unit's Build and Test record, and nowhere else:

- that printed object, unchanged;
- whether the page lists the integration as its creator (the functional spec's
  assumption), as the owner saw it;
- the archive result of section 11 and the retention obligation of section 12.

Never record the token or a digest of it, a request header, the page content, the
workspace name, the plaintext page link or Notion's plaintext request id. Build and
Test records are committed to a public repository and git history outlives the
environment.

## 9. Disconnect (owner, in DocSuri)

In "Notion 연결" choose "연결 해제" and confirm it in the dialog. DocSuri deletes the
stored token in the same step that ends the connection's use (NFR3.7). The view
then says "Notion 연결을 해제했습니다" and the panel shows the state "연결 해제됨".

## 10. Stop the host

Stop the real host in its terminal (Ctrl-C) and confirm nothing listens on 18099:

```bash
lsof -nP -iTCP:18099 -sTCP:LISTEN
```

It must print nothing.

## 11. Archive the environment (deletes the key)

```bash
backend/.venv/bin/python scripts/verify_docsuri_u6.py --phase archive-owned --profile synthetic-local --environment-file /tmp/docsuri-u6-run/environment.json
```

It must print `"state": "preserved"` with `"keyDeleted": true` and
`"keyFileFound": true`. Add this result to the evidence. `teardown` is not an
alternative: it refuses while a key file exists, so the close-down always ends
through this archive (Q2 A).

## 12. Notion access and retention

- **Notion access (suggestion for the owner).** If the integration is no longer
  needed, remove its access to the activation page, or delete the integration, in
  Notion's settings. DocSuri no longer holds its token after section 9 either way.
- **Retention (operator obligation).** Disconnect deletes the token but keeps the
  connection record, so the preserved folder and volume still hold the workspace
  name, the integration identity, the destination and page identifiers, Notion's
  request id and the page link. As soon as the evidence is checked, and **no later
  than 7 days after the export** (the `retentionDeadline` printed in section 8),
  remove, in this order:
  1. the preserved folder `/tmp/docsuri-u6-preserved-<runId>-<8 hex>` named by the
     archive result;
  2. the stopped database container, which is named by the run id: `docker rm <runId>`;
  3. its volume: `docker volume rm <volumePreserved from the archive result>`.

  Nothing removes them automatically. Record the deadline, the folder and the volume
  in the evidence as this obligation.
- **Notion side.** The exported page stays in the owner's workspace; DocSuri never
  edits, archives or deletes it.
