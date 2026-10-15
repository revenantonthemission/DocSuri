import { defineConfig, devices } from '@playwright/test';
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';

/**
 * Scoped U3 paper/corpus browser configuration.
 *
 * The manifest must be the exact owned `/tmp/docsuri-u3-run/environment.json`
 * with its own run identity, listener, profile and finite retention; a
 * U1/U2 manifest is never accepted as an alias. The owned Python runner
 * supervises the actual host; these journeys never attach to an arbitrary
 * existing dev server and never replace mounted routes with fixtures.
 */
const root = realpathSync('/tmp');
const directory = join(root, 'docsuri-u3-run');
const expected = join(directory, 'environment.json');
const path = process.env.DOCSURI_U3_ENVIRONMENT_FILE;
if (!path || lstatSync(path).isSymbolicLink() || realpathSync(path) !== expected) {
  throw new Error('U3 requires its explicit owned environment manifest');
}
for (const file of [directory, expected, join(directory, 'ownership.json')]) {
  const info = lstatSync(file);
  if (info.isSymbolicLink() || info.uid !== process.getuid?.() || info.mode & 0o077) {
    throw new Error('U3 environment is not private and owned');
  }
  if (info.isFile() && info.size > 16_384) throw new Error('U3 manifest exceeds bound');
}
const bytes = readFileSync(expected);
const manifest = JSON.parse(bytes.toString()) as {
  runId: string;
  profile: string;
  unit: string;
  applicationPort: number;
  databasePort: number;
  expiresAt: number;
};
const ownership = JSON.parse(readFileSync(join(directory, 'ownership.json'), 'utf8')) as {
  runId: string;
  manifestSha256: string;
};
if (
  ownership.runId !== manifest.runId ||
  !/^docsuri-u3-[a-f0-9]{16}$/.test(manifest.runId) ||
  ownership.manifestSha256 !== createHash('sha256').update(bytes).digest('hex') ||
  manifest.profile !== 'synthetic-local' ||
  manifest.unit !== 'u3-paper-corpus-capabilities' ||
  manifest.applicationPort !== 18059 ||
  manifest.databasePort !== 15459 ||
  manifest.expiresAt <= Date.now() / 1000
) {
  throw new Error('U3 manifest identity, listener or retention mismatch');
}

export default defineConfig({
  testDir: './e2e/u3-paper-corpus-capabilities',
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 200_000,
  globalTimeout: 300_000,
  expect: { timeout: 10_000 },
  outputDir: join(directory, 'browser-evidence'),
  use: {
    baseURL: 'https://127.0.0.1:18059',
    // Only this validated disposable loopback origin uses its self-signed cert.
    ignoreHTTPSErrors: true,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          args: [
            '--disable-dev-shm-usage',
            '--disable-extensions',
            '--renderer-process-limit=1',
            '--js-flags=--max-old-space-size=256',
          ],
        },
      },
    },
  ],
});
