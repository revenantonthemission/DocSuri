# Frontend Components — U5 topics & digests

Date: 2026-10-17 (Asia/Seoul)
Unit: u5-topics-digests (UI contribution). Sources: approved [wireframes](../../../ideation/rough-mockups/wireframes.md) W1/W2, confirmed [functional-design-questions.md](functional-design-questions.md) Q6.

## Component hierarchy

```
TopicsView (route page; h1)
├── FollowedTopicsSection (h2: "followed topics" per approved wireframe W1)
│   └── TopicList
│       └── TopicRow (per followed topic)
│           ├── TopicSummary (name, last-digest indicator, status)
│           ├── DigestSettingsLink (opens settings form)
│           ├── ResolveUnknownControl (when a run outcome is unknown: "delivered" / "not delivered", assumption named)
│           └── UnsubscribeButton (destructive, confirmed)
├── FollowTopicAction (below the list, per approved wireframe W1)
└── DigestSettingsForm (per-topic dialog or dedicated view; h2)
    ├── CadenceSelect (daily | weekly)
    ├── DeliveryTimeInput (owner timezone, labelled)
    ├── DeliveryDaySelect (weekly only: mon–sun)
    ├── ContentWindowSelect (7 | 30 days)
    ├── InheritedLevelNote (language/level from preferences, read-only)
    ├── SaveButton
    └── UnsubscribeButton (destructive, confirmed)
```

## Props/state design

| Component | State | Notes |
|---|---|---|
| TopicsView | `topics[]`, `viewState: loading\|empty\|error\|ready\|partial` | Server state via the established SWR pattern; refresh on mutation |
| TopicRow | `topic`, `busy` | Row actions disabled while an action is in flight; double-submit prevented |
| DigestSettingsForm | `draft`, `validation`, `saveState: idle\|saving\|saved\|failed` | Inline validation on blur; save acknowledged explicitly (never silently assumed); a save sent twice with no response is retried only from the saved-state check, and a stale-revision response tells the account the settings changed elsewhere and offers a reload — never an overwriting blind retry |
| ConfirmationDialog (unsubscribe) | `topic`, `open` | Names the affected topic; focus trapped; Escape closes; focus returns to trigger |

## Interaction flows

- Follow: list action below the rows -> topic entered -> optimistic row appears only after the acknowledgement (no silent success); duplicate -> inline notice naming the existing subscription; re-follow of an unsubscribed topic -> confirmation that reactivates the same topic with its history and watermark preserved.
- Settings: row link -> form prefilled from the topic's settings; save -> acknowledged state shown; inherited fields visibly read-only.
- Unsubscribe: confirm -> row leaves the active list (history preserved server-side); queued-work note shown ("queued work for this topic is dropped").
- Status: last-digest indicator and outcome states announced via a polite live region; never color-only (icon + text).

## Form validation rules

- Cadence: one of daily/weekly (select, not free text).
- Delivery time: valid time; displayed and stored in the account's timezone with the zone labelled.
- Content window: one of 7/30 (select).
- No required-field guessing: every field labelled (visible labels, not placeholder-only).

## API integration points

- `GET topics` (owner-scoped list with settings + last outcome)
- `POST topics` (follow), `DELETE topics/{id}` (unsubscribe)
- `GET/PUT topics/{id}/settings` (revision-checked save)
- `POST topics/{id}/runs/{runId}/resolve` (explicit unknown-outcome resolution; body names the assumption)
- All calls through the established Transport/SWR patterns; owner isolation errors surface as plain refusals.

## Accessibility

Per screen: one `h1`; sections as `h2`; all actions keyboard-reachable with visible focus; destructive unsubscribe confirmed via a dialog that names the topic; status changes via `aria-live="polite"`; contrast per WCAG 2.2 AA; Korean labels throughout.
