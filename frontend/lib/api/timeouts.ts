// The browser leg of the declared generation time budget (REM-2 F05 / NFR-Q11).
//
// The backend declares one budget per task (backend `summarization.domain.timeout_profile`, mirrored
// in `ops/platform-integrity/timeouts.yaml`) and ordered the layers model → worker → api → bff →
// browser so each clears the one it wraps. That ordering is worthless from the browser unless the
// client actually uses the declared browser leg: this slice used to fall back to a bare 10s, which
// is *below* the API budget, so the browser abandoned requests the API still intended to answer —
// the user saw a network error with no way to collect the result.
//
// Only the browser leg is mirrored here. The char thresholds and the inner layers are enforced
// server-side and must not be re-derived in the client.

/** The declared budget tasks (`ops/platform-integrity/timeouts.yaml`). */
export type BudgetTask = 'SUMMARIZE' | 'TRANSLATE' | 'NOVELTY' | 'EVIDENCE';

/**
 * The wire spells tasks lowercase (`"summary" | "translate"`); the declaration uses the verb form.
 * Translating here keeps the declared names intact instead of renaming them to match the wire.
 */
const WIRE_TO_BUDGET: Record<string, BudgetTask> = {
  summary: 'SUMMARIZE',
  translate: 'TRANSLATE',
  novelty: 'NOVELTY',
  evidence: 'EVIDENCE',
};

/** The outermost layer of the declared reverse table, in milliseconds. */
export const BROWSER_BUDGET_MS: Record<BudgetTask, number> = {
  SUMMARIZE: 15_000,
  TRANSLATE: 15_000,
  NOVELTY: 30_000,
  EVIDENCE: 30_000,
};

/** The API leg, kept so the ordering stays assertable rather than assumed. */
export const API_BUDGET_MS: Record<BudgetTask, number> = {
  SUMMARIZE: 10_000,
  TRANSLATE: 10_000,
  NOVELTY: 18_000,
  EVIDENCE: 20_000,
};

/**
 * Browser budget for a wire task. An unrecognized task gets the tightest declared budget rather
 * than a guess: cutting a request short is recoverable (the user retries), while waiting too long
 * is the failure this unit exists to remove.
 */
export function browserBudgetMs(task: string | undefined): number {
  const key = task === undefined ? undefined : WIRE_TO_BUDGET[task];
  return key === undefined ? BROWSER_BUDGET_MS.SUMMARIZE : BROWSER_BUDGET_MS[key];
}
