# Frontend Components — U8 complete service operations and integration

Date: 2026-10-21 (Asia/Seoul)
Unit: u8-service-operations-integration. Sources: confirmed [functional-design-questions.md](functional-design-questions.md) (Q2, Q3, Q8, Q14), [functional-spec.md](functional-spec.md) (Workflows 2, 3, 4, 7, 15 and 16), [rules.md](rules.md) (BR3, BR5, BR7, BR8.6, BR9.6), the earlier record's interaction spec C01 (workspace navigation) and mockups M16 (administration and MFA) and O01–O02 (operations records), with their shared state contract (`../../../../261010-docsuri-v2-rebuild/inception/refined-mockups/`), and the current v2 workspace (`frontend/src/App.tsx`, `frontend/src/u4-research/jobs.tsx`, U6's dialog shell).

Everything here lives in the v2 workspace, which becomes the only browser application (Q2, BR5.7). Labels are Korean. Every new or changed screen meets WCAG 2.2 AA (BR5.8).

## Component hierarchy

```text
AppShell (existing, changed)
├── MovedNotice (new; returning users after the switch)
├── WorkspaceNavigation (changed; server-resolved entries only)
│   ├── NavigationEntry (enabled | degraded | sign-in prompt | disabled with reason)
│   └── 운영 entry (administrators only)
├── destination views (existing): 검색, 내 서재, 연구, 참신성 분석, 주제 구독, 내보내기, 설정, 사용량, 계정
├── PaperView (existing; opened from results with return context)
├── JobsView 작업 (new)
│   ├── JobKindFilter
│   ├── JobListItem
│   └── JobLiveStatus (live stream with polling fallback, inside an error boundary)
├── OperationsView 운영 (new; administrator with current MFA)
│   ├── CapabilityTable
│   ├── IncidentList
│   └── RecoveryPanel (+ RecoveryConfirmDialog)
├── FirstSignInSteps (new; migrated accounts)
│   ├── ConsentStep
│   ├── ResetRequiredNotice
│   └── AdminMfaPrompt
├── ProviderStateNotice (new; shared)
└── Footer → LegalLinks (개인정보 처리방침, 이용약관)

LegalPage (new; /privacy and /terms, readable without scripts)
MaintenanceNotice (new; static, shown while writes are stopped; never in place of the legal pages)
```

## WorkspaceNavigation (changed)

- **Purpose.** Render exactly the navigation the server resolves (BR5.1). The current browser-side owner-bound list and the silent search-only fallback are removed.
- **Inputs:**
  - the resolved items (routeId, titleKey, path, capabilityId, available, reasonKey, placement), via amendment A1;
  - the current route;
  - the owner's safe display identity, or none.
- **States:**
  - loading;
  - resolved;
  - error: only public entries, with "다른 메뉴를 확인하지 못했습니다" and a 다시 시도 button.
- **Entry rendering (BR5.2):**

  | Resolved state | Presentation |
  |---|---|
  | available | enabled link |
  | degraded | enabled, with the limitation shown as text beside the label |
  | needs a session, signed out | shown; activating it opens sign-in |
  | unavailable, unknown or stale | disabled, with its reason text visible and linked as the entry's description |
  | administrator-only, caller not an administrator | absent |

- **Placement.** Primary entries in manifest order. 논문 never appears as a primary entry. 개인정보 처리방침 and 이용약관 appear in the footer and are always enabled, because they are backed by public.static (BR5.3, BR5.6).
- **Owner changes.** Sign-in, sign-out, an account switch or expiry triggers resolution again. Private views, caches and live regions are cleared first (BR5.5).
- **Responsive (interaction spec C01).** A desktop rail; a compact rail on tablets; a disclosure menu on phones with every destination reachable.
- **Accessibility:**
  - a `nav` landmark named "주요 이동", with `aria-current` on the active entry;
  - disabled entries keep `aria-disabled` and expose their reason through `aria-describedby`, never by colour alone;
  - after a route change, focus moves to the destination heading;
  - Escape closes the phone menu and returns focus to its trigger.
- **API.** `POST /api/v2/c01/host-resolve-navigation` (existing).

Reason keys and their Korean text:

| Reason key | Text |
|---|---|
| nav.authenticationRequired | 로그인 후 이용할 수 있습니다 |
| nav.capabilityPending | 준비 중입니다 |
| nav.capabilityDegraded | 일부 기능이 제한되어 있습니다 |
| nav.capabilityUnavailable | 일시적으로 사용할 수 없습니다 |
| nav.capabilityStale | 상태 정보가 오래되어 다시 확인하는 중입니다 |
| nav.capabilityUnknown | 상태를 확인할 수 없습니다 |
| nav.administratorOnly | (entry not shown) |

## JobsView 작업 (new)

- **Purpose.** The owner's read-only list of research and novelty jobs, newest first (BR5.4).
- **Data:**
  - ResearchWorkspace's owner job list (amendment A2), read through the shared transport with stale-while-revalidate caching;
  - "더 보기" loads the next page by cursor.
- **Item contents:**
  - the job's label;
  - its kind (연구 or 참신성 분석);
  - its state: 대기 중, 진행 중, 완료, 실패, 취소됨, or 확인 중 for an unknown outcome;
  - the last update, formatted for ko-KR;
  - one link: 결과 보기 when a result is available, otherwise 진행 상황 보기, which opens the job's existing view.
- **Live state:**
  - While any visible job is unfinished, the list refreshes at the list interval (policy) and stops once every visible job has finished. A 자동 새로 고침 일시 중지 toggle pauses and resumes it (WCAG 2.2.2).
  - The selected job uses its event stream, resuming from the last event id, and falls back to polling when the stream fails.
  - The live component sits inside an error boundary, and its state changes are announced in a polite live region.
- **Filter.** 전체, 연구 or 참신성 분석.
- **States:**
  - loading: skeleton rows the size of real rows;
  - empty: "아직 작업이 없습니다", with a link to 연구;
  - error: a plain message and 다시 시도;
  - partial: "실시간 연결이 끊겨 주기적으로 확인합니다".
- **Never.** No cancel, retry or start control. Reading the list never starts, repeats or cancels work. Cancelling stays in the job's own view.
- **API:**
  - the list read (A2);
  - `GET /api/v2/jobs/{jobId}`;
  - `GET /api/v2/jobs/{jobId}/events`.

## OperationsView 운영 (new)

- **Access.**
  - Only administrators see the entry.
  - Opening it with MFA that is not current shows AdminMfaPrompt instead of data.
  - Anyone else gets the ordinary not-found page (BR3.8, M16).
- **CapabilityTable:**
  - Columns: 기능; 상태 (정상, 제한, 중단, 알 수 없음, 오래됨); 마지막 확인 (age, for example "3분 전"); 제한 사항; 관련 사고.
  - Problems sort first.
  - It refreshes at the dashboard interval (policy) and on demand. A 자동 새로 고침 일시 중지 toggle pauses and resumes the automatic refresh (WCAG 2.2.2).
  - The runtime arrangement adds two reasons with their own labels: 런타임 격리 확인 실패 (runtime-isolation-lapsed) on the 런타임 격리 row (platform.isolation), and 모델 검증값 불일치 (model-evidence-mismatch) on the model runtime's row (BR6.11). The 런타임 격리 row's 제한 사항 names each failed item: 프로그램, 설정 파일, 계정, 데이터베이스, 패킷 필터, 백업 볼륨 or 부팅 시작 (BR6.12).
  - A measured zero, an estimate and unknown are shown differently (O01).
- **IncidentList:**
  - Unresolved incidents come first.
  - Each shows its capabilities, when it opened, its state, its diagnosis label, its linked recovery requests and its opaque evidence references.
  - Actions:
    - 조사 시작;
    - 복구 요청, which opens RecoveryPanel prefilled;
    - 해결 처리, enabled only when evidence is present (BR3.7).
  - A resolved incident shows how it was resolved: 기능 복구됨 (capability-available), 중단 검토 완료 (abort-reviewed), 롤백 사본 처리 완료 (rollback-copy-settled) or 환경 중지 (environment-stopped).
  - An abort's incident (전환 중단) cannot be resolved from this view. Until the maintainer's review is recorded through the operator tool, 해결 처리 stays disabled with "관리자 도구에서 전환 중단 검토가 기록되어야 합니다" as its description (BR3.7, BR9.14).
  - A rollback's copy-pending incident (롤백 사본 대기) cannot be resolved from this view either. It resolves only when the stopped database's copy is recorded or waived and the database recreated, so 해결 처리 stays disabled with "관리자 도구에서 롤백 사본이 처리되어야 합니다" as its description (BR3.7, BR9.7).
- **RecoveryPanel**, with three actions:
  - 백업 만들기 (backup.create);
  - 복원 검증 (restore.verify): choose a backup set whose integrity passed;
  - 운영 데이터 복원 요청 (restore.production): choose a set. The panel explains that this needs the maintainer's decision and the operator in person, that the operator first takes a fresh backup after the service stops writing, and that nothing changes until the operator runs it (BR4.2, BR4.7).

  Each request shows its environment (리허설 or 운영), its origin (관리자 or 예약), and its state: 요청됨, 운영자 대기, 실행 중, 검증 중, 복원 후 백업 대기 (post-restore-pending), 복원 보류 (held), 완료, 실패, 확인 중, 취소됨, 거절됨 or 만료됨. The two production-restore waits say why the service stays in maintenance: "복원된 데이터베이스의 백업이 통과해야 서비스가 다시 시작됩니다" for 복원 후 백업 대기, and "다른 백업으로 다시 복원하려면 관리자 도구에서 결정이 필요합니다" for 복원 보류 (BR4.7).

  A new request is always accepted. When a conflicting request is already active in the same environment, or a switch is in progress, the new one waits as 요청됨 and the panel says "같은 환경의 다른 복구 작업이 끝나면 진행됩니다" (BR4.4).
- **RecoveryConfirmDialog (M16):**
  - It names the target, its current state and the effect, and states that the operator performs the effect.
  - A production restore also needs the box "이 백업으로 운영 데이터를 되돌리는 요청임을 이해했습니다" ticked.
  - It reuses the workspace dialog shell, with its focus containment and Escape behaviour.
  - Opening the dialog creates a new submissionId for that deliberate submission. Retries of the same submission reuse it; a new submission gets a new one (BR4.9).
  - The idempotency key is a SHA-256 hash of the origin (관리자), the account, operation, target, expected revision and submissionId, computed with the browser's crypto API (BR4.9).
  - A conflict shows "다른 요청이 먼저 처리되었습니다. 새로 고친 뒤 다시 확인하세요".
- **Accessibility:**
  - real tables with header cells;
  - each state shown as icon plus text;
  - request-state changes announced in a polite live region.
- **API:**
  - `POST /api/v2/c11/read-dashboard`;
  - `POST /api/v2/c11/list-incidents`;
  - `POST /api/v2/c11/request-recovery`;
  - the recovery status read (A5).

## FirstSignInSteps (new)

- **MovedNotice (BR9.6).** Shown on the entry and sign-in screens after the switch: "DocSuri가 새 버전으로 옮겨졌습니다. 한 번만 다시 로그인해 주세요. 저장한 논문과 설정은 그대로 있습니다."

  Its 자세히 link explains what moved, what stayed in the archived copy (the archive-only kinds you decided) and where to ask about it. Once dismissed, it stays dismissed on that device.
- **ConsentStep (BR8.6, A3).** Shown right after a migrated account's first sign-in.
  - It shows v2's consent purposes with the same wording as sign-up. Required ones must be ticked before 계속; optional ones start off.
  - Nothing personal loads until the consents are recorded.
  - An error keeps the choices made and focuses the error summary.
- **ResetRequiredNotice.** Shown when a reset-required account tries to sign in. It says only what actually happened (BR8.6, BR7.2):
  - the reset email was accepted for sending: "보안을 위해 비밀번호를 다시 설정해야 합니다. 이메일로 재설정 링크를 보냈습니다.";
  - mail is held, unavailable or over the allowance: "보안을 위해 비밀번호를 다시 설정해야 합니다. 지금은 이메일을 보낼 수 없습니다. 잠시 후 다시 시도해 주세요." (BR7.4).
- **AdminMfaPrompt.** An administrator without current MFA enrols or confirms it through U2's existing MFA flow before any 운영 data or action appears.

## ProviderStateNotice (new, shared)

Wherever a feature depends on a provider, its state is shown from the capability catalog (BR7.2). Signed out, the catalog returns only the public projection: states and reason keys of the capabilities behind visible entries, account.entry and the sign-in providers (BR5.9).
- **Sign-in buttons.** When Google or ORCID is unavailable, the button is disabled with "지금은 Google 로그인을 사용할 수 없습니다. 비밀번호로 로그인해 주세요." (or ORCID).
- **Flows that send mail.** These show the allowance message.
- **Paper assistance.** While its readiness evidence is pending, it shows "요약·번역 기능을 준비 중입니다" (BR7.7).

Digest and export screens keep the notices U5 and U6 defined.

## LegalPage and MaintenanceNotice (new)

- **LegalPage, /privacy and /terms (BR5.6):**
  - served as documents readable without scripts, at the same addresses as today, by v2 and, while writes are stopped, by the maintenance server as static copies (BR5.6, BR9.10);
  - the text is carried over unchanged from the Next.js pages;
  - the layout uses the workspace's global styles, with `lang="ko"`, a readable line length, a real heading outline and a link back to 검색;
  - linked from the footer, the entry screen and the sign-in screen.
- **MaintenanceNotice:**
  - while writes are stopped during the switch, an abort, a rollback or a production restore, the static maintenance server serves it at every address of the public origin except /privacy and /terms, which it serves as static copies of the legal pages (BR9.10);
  - while admission is maintainer-only, v2 itself shows the same notice on every page except /privacy and /terms, with a small 관리자 로그인 link; only administrator accounts can sign in (BR6.4);
  - text: "DocSuri를 점검하고 있습니다. 잠시 후 다시 접속해 주세요.";
  - no scripts, and no promised end time.

## Interaction flows

1. **Navigation.**
   1. The page loads, and navigation is resolved.
   2. Entries render with their states.
   3. The owner changes: private state is cleared, and navigation is resolved again.
   4. Resolution fails: public entries are shown with 다시 시도.
2. **Opening a paper.**
   1. The owner selects a search, library, digest or job result.
   2. PaperView opens with the return context.
   3. Going back restores the result position and focus.
3. **Following a job.**
   1. In 작업, the owner selects an item.
   2. The job's existing view opens, with its live stream.
   3. If the stream fails, it falls back to polling; the end is announced once.
4. **Recovering.**
   1. An administrator opens an incident and chooses 복구 요청.
   2. The confirmation dialog appears.
   3. The request is recorded as 요청됨 and moves to 운영자 대기 once admitted; its state is announced as it changes.
   4. 해결 처리 becomes available only when evidence is present.
5. **Returning after the switch.**
   1. The returning user sees the MovedNotice and signs in.
   2. ConsentStep, ResetRequiredNotice or AdminMfaPrompt appears, as the account requires.
   3. The owner's workspace opens.

## Form validation rules

| Form | Rule | Message |
|---|---|---|
| ConsentStep | every required consent ticked | 필수 항목에 동의해야 계속할 수 있습니다 |
| RecoveryPanel, both restore actions | one backup set selected, with integrity passed | 복원할 백업을 선택하세요 |
| RecoveryConfirmDialog, production restore | acknowledgement ticked | 내용을 확인했다는 항목을 선택하세요 |

## API integration points

| Component | Operation | Route |
|---|---|---|
| WorkspaceNavigation | C01 host.resolveNavigation | `POST /api/v2/c01/host-resolve-navigation` |
| ProviderStateNotice | capability catalog | `GET /api/v2/capabilities` |
| JobsView | owner job list (A2) | under `/api/v2/c07/` |
| JobLiveStatus | job snapshot and events | `GET /api/v2/jobs/{jobId}`, `GET /api/v2/jobs/{jobId}/events` |
| OperationsView | C11 readDashboard, listIncidents, requestRecovery, recovery status (A5) | `POST /api/v2/c11/read-dashboard`, `/list-incidents`, `/request-recovery` |
| FirstSignInSteps | AccountAccess entry, consent step (A3), password reset, MFA | existing C02 routes plus A3 |
| LegalPage | static documents | `GET /privacy`, `GET /terms` |

## Implementation constraints carried from the team and project rules

- Requests go through the native fetch-based transport. Server state is cached with stale-while-revalidate.
- Live updates use the native event stream, resuming from the last event id, with polling fallback, inside an error boundary and with live-region announcements.
- Class names are composed with `clsx` and `tailwind-merge`. Styling uses CSS Modules and Tailwind.
- TypeScript is strict. Hashing uses the browser's crypto API, and dates use `Intl.DateTimeFormat`.
- No axios, query-cache library, lodash, date library, classnames, styled-components or emotion.
