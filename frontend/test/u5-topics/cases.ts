// One merged test's cases (plan Step 38, decision L3-1). A component above eight tests
// merges its same-rule cases into one Vitest test, since each `it.each` row counts as a
// test of its own. Every case keeps its original body and assertions, renders on its own
// and is unmounted before the next, and a failure names the case that failed.
import { cleanup } from '@testing-library/react';

export type Cases = Record<string, () => Promise<void> | void>;

export async function eachCase(cases: Cases): Promise<void> {
  for (const [name, run] of Object.entries(cases)) {
    try {
      await run();
    } catch (failure) {
      if (failure instanceof Error) failure.message = `[case: ${name}] ${failure.message}`;
      throw failure;
    } finally {
      cleanup();
      window.localStorage.clear();
    }
  }
}
