import { defineConfig, devices } from '@playwright/test';
import { createHash } from 'node:crypto';
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';

const root = realpathSync('/tmp');
const directory = join(root, 'docsuri-u2-run');
const expected = join(directory, 'environment.json');
const path = process.env.DOCSURI_U2_ENVIRONMENT_FILE;
if (!path || lstatSync(path).isSymbolicLink() || realpathSync(path) !== expected) {
  throw new Error('U2 requires its explicit owned environment manifest');
}
for (const file of [directory, expected, join(directory, 'ownership.json')]) {
  const info = lstatSync(file);
  if (info.isSymbolicLink() || info.uid !== process.getuid?.() || info.mode & 0o077) {
    throw new Error('U2 environment is not private and owned');
  }
  if (info.isFile() && info.size > 16_384) throw new Error('U2 manifest exceeds bound');
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
  !/^docsuri-u2-[a-f0-9]{16}$/.test(manifest.runId) ||
  ownership.manifestSha256 !== createHash('sha256').update(bytes).digest('hex') ||
  manifest.profile !== 'synthetic-local' ||
  manifest.unit !== 'u2-account-personal-controls' ||
  manifest.applicationPort !== 18049 ||
  manifest.databasePort !== 15449 ||
  manifest.expiresAt <= Date.now() / 1000
) {
  throw new Error('U2 manifest identity, listener or retention mismatch');
}

export default defineConfig({
  testDir: './e2e/u2-account-personal-controls',
  forbidOnly: true,
  workers: 1,
  retries: 0,
  // One bounded wait for the finite entry-admission minute window is allowed.
  timeout: 200_000,
  globalTimeout: 260_000,
  expect: { timeout: 10_000 },
  outputDir: join(directory, 'browser-evidence'),
  use: {
    baseURL: 'https://127.0.0.1:18049',
    // Only this validated disposable loopback origin uses its self-signed cert.
    ignoreHTTPSErrors: true,
    trace: 'off',
    // Failure evidence is the sanitized error context plus the helper's
    // secret-free diagnostics; automatic media capture stays off.
    screenshot: 'off',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Keep the finite browser process tree inside its 1 GiB safety budget.
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
  // The owned Python runner supervises the actual host; never attach to an
  // arbitrary existing dev server or replace mounted routes with fixtures.
});
