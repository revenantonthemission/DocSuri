import { mergeConfig } from 'vitest/config';
import base from './vitest.u2-account-controls.config';

// Frontend layer only: retained U1 and U2 behavior against the same complete
// workspace source inventory and unchanged 80% line-coverage floor.
export default mergeConfig(base, {
  test: {
    include: [
      'test/u1-integrated-paper-journey/**/*.test.{ts,tsx}',
      'test/u2-account-personal-controls/**/*.test.{ts,tsx}',
    ],
  },
});
