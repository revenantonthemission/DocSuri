import tseslint from 'typescript-eslint';
import nextPluginImport from '@next/eslint-plugin-next';
import reactHooksPluginImport from 'eslint-plugin-react-hooks';

const nextPlugin = await import('@next/eslint-plugin-next').then(m => m.default);
const reactHooksPlugin = await import('eslint-plugin-react-hooks').then(m => m.default);
const typescriptEslintParser = await import('@typescript-eslint/parser').then(m => m.default);

export default [
  { ignores: ['types/generated/**', '.next/**', 'coverage/**', 'node_modules/**'] },
  ...tseslint.configs.recommended,
  {
    plugins: {
      '@next/next': nextPlugin,
      'react-hooks': reactHooksPlugin,
    },
    rules: {
      '@typescript-eslint/no-unused-vars': 'warn',
      'react-hooks/exhaustive-deps': 'warn',
    },
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parser: typescriptEslintParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
        project: './tsconfig.json',
      },
    },
  },
  {
    files: [
      'components/{PaperDetailIsland,JobStatus,SummaryModal,JobSubmissionForm,ErrorBoundary,ErrorBoundaryFallback,JobDialog}.tsx',
      'components/session/SessionContext.tsx',
      'lib/api/{contentJobApi,contentJobContracts,httpTransport,routeHandlerTransport,transport}.ts',
      'lib/{idempotencyService,jobState,jobDiagnostics,cn}.ts',
      'app/bff/[[]...path[]]/route.ts',
      'instrumentation*.ts',
      'sentry.server.config.ts',
    ],
    rules: {
      '@typescript-eslint/no-explicit-any': 'error',
      'no-restricted-imports': ['error', {
        patterns: [
          'axios', '@tanstack/react-query', '@tanstack/react-query/*',
          'lodash', 'lodash/*', 'moment', 'moment/*', 'date-fns', 'date-fns/*',
          'classnames', 'styled-components', '@emotion/*',
        ],
      }],
    },
  },
];
