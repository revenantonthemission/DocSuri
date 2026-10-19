import { mergeConfig } from 'vitest/config';
import base from './vitest.u2-account-controls.config';

// Frontend layer only: every merged unit's frontend tests against the same
// complete workspace source inventory and unchanged 80% line-coverage floor.
// Coverage spans all of src/, so each unit that adds source must add its tests
// here too; otherwise its files count as uncovered in this lane.
export default mergeConfig(base, {
  test: {
    include: [
      'test/u1-integrated-paper-journey/**/*.test.{ts,tsx}',
      'test/u2-account-personal-controls/**/*.test.{ts,tsx}',
      'test/u3-paper-corpus-capabilities/**/*.test.{ts,tsx}',
      'test/u4-research-novelty/**/*.test.{ts,tsx}',
      'test/u5-topics/**/*.test.{ts,tsx}',
    ],
  },
});
