import { mergeConfig, defineConfig } from 'vitest/config';
import base from './vitest.config';

// U3-owned tests plus the retained asset/viewer compatibility files (asset
// relay, BFF route, document viewer, asset loading/classification, paper
// composition). Other Units continue to run in the unchanged full-suite lane.
export default mergeConfig({ ...base, test: { ...base.test, include: [] } }, defineConfig({
  test: {
    include: [
      'test/u3*.test.{ts,tsx}',
      'test/assetDelivery.test.ts',
      'test/bffRoute.test.ts',
      'test/docModelViewer.test.tsx',
      'test/useAssets.test.ts',
      'test/classifyAssets.test.ts',
      'test/paperDetailBody.test.tsx',
      'test/paperDetailSource.test.tsx',
      'test/httpTransportPayloadHash.test.ts',
    ],
    passWithNoTests: false,
    // The viewer tests render MathJax-heavy doc-model fixtures; under coverage
    // load a single render can occasionally exceed the 5s default even though
    // the suite is green — give the lane headroom instead of flaking.
    testTimeout: 15000,
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage/u3',
      reporter: ['text', 'json', 'json-summary', 'lcov'],
      include: [
        'components/{DocModelViewer,AssetViewer,ZoomPanControls,UnsubscribePage}.tsx',
        'lib/useAssets.ts',
        'lib/api/assetSrc.ts',
        'lib/jobDiagnostics.ts',
      ],
      // This whole-file report does not replace the final frozen-baseline,
      // changed-executable-line gate across Python/frontend/helpers/shell. The
      // shared BFF route's asset branch is proven by the u3 branch tests but its
      // whole-file report stays out of this lane floor (U1/U2 precedent), and
      // comment-only files (TranslationView, FullTranslationIsland) keep their
      // existing suites/lanes instead of diluting this one.
      thresholds: { lines: 80 },
    },
  },
}));
