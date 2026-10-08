# Rough Wireframes — Phase 7 Frontend Wiring

**Intent ID:** 261001-rem-2-phase-7-frontend
**Scope:** feature
**Date:** 2026-10-02

---

## Overview

These wireframes illustrate the UI changes for wiring the durable content-job contract into the frontend. Focus is on JobStatus integration and AssetViewer migration.

---

## 1. JobStatus Component — Wireframe

### 1.1 Default State (No Active Job)

```
┌─────────────────────────────────────────────────────────────┐
│  Paper Detail View                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Paper Title                                           │  │
│  │  Authors, Date, Abstract...                            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │  Summarize          │  │  Translate          │          │
│  │  [Button]           │  │  [Button]           │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  (JobStatus not rendered when no jobId)                    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Active Job — SSE Connected

```
┌─────────────────────────────────────────────────────────────┐
│  Paper Detail View                                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Paper Title                                           │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐          │
│  │  Summarize          │  │  Translate          │          │
│  │  [Button]           │  │  [Button]           │          │
│  └─────────────────────┘  └─────────────────────┘          │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  🔄 Job Status: RUNNING                    [✕ Dismiss] │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│   │  │
│  │  │  45% — Processing content...                    │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │  Started: 2 min ago  |  Last update: 3s ago  🟢 Live  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**States:**
- 🟢 **Live** — SSE connected, receiving real-time updates
- 🟡 **Reconnecting** — SSE disconnected, attempting resume with Last-Event-ID
- 🔴 **Polling** — SSE failed, falling back to 2s polling

### 1.3 Completed Job

```
┌─────────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ✅ Job Status: COMPLETED                              │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │██████████████████████████████████████████████████│   │  │
│  │  │  100% — Summary generated successfully           │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │  [View Result]  [Dismiss]                             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 1.4 Failed Job — Inline Retry

```
┌─────────────────────────────────────────────────────────────┐
│  ┌───────────────────────────────────────────────────────┐  │
│  │  ❌ Job Status: FAILED                                 │  │
│  │  ┌─────────────────────────────────────────────────┐   │  │
│  │  │████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│   │  │
│  │  │  60% — Error: Model timeout                      │   │  │
│  │  └─────────────────────────────────────────────────┘   │  │
│  │  Error: The summarization model timed out.            │  │
│  │  [🔄 Retry with same idempotency key]  [Dismiss]      │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. AssetViewer Component — Wireframe

### 2.1 Before Migration (Presigned URL — REMOVED)

```
┌─────────────────────────────────────────────────────────────┐
│  Figure 1: Architecture Diagram                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  <img src="https://s3.amazonaws.com/...?X-Amz-Signature=..." /> │  │
│  └───────────────────────────────────────────────────────┘  │
│  Caption: System architecture overview                      │
│  ⚠️ SECURITY-08 VIOLATION — Presigned 307 redirect         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 After Migration (Same-Origin Delivery)

```
┌─────────────────────────────────────────────────────────────┐
│  Figure 1: Architecture Diagram                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  <img src="/bff/api/papers/abc123/assets/fig1.png" /> │  │
│  └───────────────────────────────────────────────────────┘  │
│  Caption: System architecture overview                      │
│  🔒 SEC-9 COMPLIANT — Auth re-checked at delivery          │
└─────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Direct `<img>` src to same-origin endpoint
- Browser sends cookies/auth headers automatically via BFF
- Backend validates ownership (RJ-AC05) before serving bytes
- `cache-control: private, max-age=60` for browser caching
- No 307 redirect, no presigned URL generation

---

## 3. User Flow — Job Submission to Completion

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  User clicks│     │  Submit to  │     │  JobStatus  │     │  Job        │
│  "Summarize"│────▶│  /bff/api/  │────▶│  mounts,    │────▶│  completes  │
│             │     │  content-   │     │  SSE opens  │     │  or fails   │
│             │     │  jobs       │     │             │     │             │
└─────────────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
                           │                     │                  │
                    ┌──────▼──────┐      ┌──────▼──────┐      ┌──────▼──────┐
                    │ Returns     │      │ SSE:        │      │ Result      │
                    │ jobId +     │      │ SUBMITTED   │      │ delivered   │
                    │ idempotency │      │ → ACCEPTED  │      │ or Retry    │
                    │ key         │      │ → QUEUED    │      │ shown       │
                    └─────────────┘      │ → RUNNING   │      └─────────────┘
                                         │ → COMPLETED │
                                         │    or       │
                                         │ → FAILED    │
                                         └─────────────┘
```

---

## 4. Error Boundary Fallback (JobStatus)

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ Unable to load job status                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Something went wrong displaying the job progress.    │  │
│  │  The job may still be running in the background.      │  │
│  └───────────────────────────────────────────────────────┘  │
│  [🔄 Retry Connection]  [Dismiss]                           │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Accessibility Notes

| Element | ARIA / Semantic | Notes |
|---------|-----------------|-------|
| JobStatus container | `role="status"` `aria-live="polite"` | Announces state changes |
| Progress bar | `role="progressbar"` `aria-valuenow` `aria-valuemin="0"` `aria-valuemax="100"` | Screen reader progress |
| State text | Visually hidden live region | "Job status: RUNNING, 45% complete" |
| Retry button | `aria-label="Retry failed job"` | Keyboard accessible |
| Dismiss button | `aria-label="Dismiss job status"` | Keyboard accessible |
| Asset images | `alt` text from caption | Figures have descriptive alt |

---

## 6. Responsive Behavior

| Breakpoint | JobStatus | AssetViewer |
|------------|-----------|-------------|
| Mobile (<640px) | Full width, below actions | Stack vertically, full width |
| Tablet (640-1024px) | Inline with actions | Side-by-side with caption |
| Desktop (>1024px) | Inline with actions | Side-by-side with caption |

---

## 7. Design Tokens (Reference)

| Token | Value | Usage |
|-------|-------|-------|
| `--color-status-running` | `#3B82F6` (blue-500) | RUNNING state |
| `--color-status-completed` | `#22C55E` (green-500) | COMPLETED state |
| `--color-status-failed` | `#EF4444` (red-500) | FAILED state |
| `--color-status-pending` | `#F59E0B` (amber-500) | SUBMITTED/ACCEPTED/QUEUED |
| `--progress-height` | `8px` | Progress bar height |
| `--jobstatus-radius` | `8px` | Card border radius |
| `--jobstatus-shadow` | `0 1px 3px rgba(0,0,0,0.1)` | Card elevation |