import { mergeConfig, defineConfig } from 'vitest/config';
import base from './vitest.config';

// Exact compatibility files plus the explicitly U1-owned tests. Other Units
// continue to run in the unchanged full-suite lane.
export default mergeConfig({ ...base, test: { ...base.test, include: [] } }, defineConfig({
  test: {
    include: [
      'test/u1*.test.{ts,tsx}',
      'test/summaryModal.test.tsx',
      'test/paperDetailBody.test.tsx',
      'test/paperDetailSource.test.tsx',
      'test/bffRoute.test.ts',
      'test/httpTransportPayloadHash.test.ts',
      'test/assetDelivery.test.ts',
      'test/agentSse.test.ts',
      'test/routeGuard.test.tsx',
      'test/libraryAuthRedirect.test.tsx',
    ],
    passWithNoTests: false,
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage/u1',
      reporter: ['text', 'json', 'json-summary', 'lcov'],
      include: [
        'components/{PaperDetailIsland,JobStatus,SummaryModal,JobSubmissionForm,ErrorBoundary,ErrorBoundaryFallback,JobDialog}.tsx',
        'components/session/SessionContext.tsx',
        'lib/api/{contentJobApi,contentJobContracts,httpTransport,routeHandlerTransport,transport}.ts',
        'lib/{idempotencyService,jobState,jobDiagnostics,cn}.ts',
        'app/bff/[[]...path[]]/route.ts',
        'instrumentation*.ts',
        'sentry.server.config.ts',
      ],
      // This whole-file report does not replace the final frozen-baseline,
      // changed-executable-line gate across Python/frontend/helpers/shell.
      thresholds: { lines: 80 },
    },
  },
}));
