import tseslint from 'typescript-eslint';
import nextPluginImport from '@next/eslint-plugin-next';
import reactHooksPluginImport from 'eslint-plugin-react-hooks';

const nextPlugin = await import('@next/eslint-plugin-next').then(m => m.default);
const reactHooksPlugin = await import('eslint-plugin-react-hooks').then(m => m.default);
const typescriptEslintParser = await import('@typescript-eslint/parser').then(m => m.default);

export default [
  { ignores: ['types/generated/**', '.next/**', 'node_modules/**'] },
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
];
