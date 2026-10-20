// U6 browser journeys over the real served realm; owned-environment custody.
// Run only through `scripts/verify_docsuri_u6.py --phase browser`, never against :3000.
import { defineConfig, devices } from '@playwright/test';
import { createHash, X509Certificate } from 'node:crypto';
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';

const directory = join(realpathSync('/tmp'), 'docsuri-u6-run');
const expected = join(directory, 'environment.json');
const environmentFile = process.env.DOCSURI_U6_ENVIRONMENT_FILE;
if (
  !environmentFile ||
  lstatSync(environmentFile).isSymbolicLink() ||
  realpathSync(environmentFile) !== expected
)
  throw new Error('U6 requires its explicit owned environment manifest');
function privateFile(name: string): Buffer {
  const path = join(directory, name),
    stat = lstatSync(path);
  if (
    !stat.isFile() ||
    stat.isSymbolicLink() ||
    stat.uid !== process.getuid?.() ||
    stat.mode & 0o077 ||
    stat.size > 16_384
  )
    throw new Error('U6 private metadata boundary refused');
  return readFileSync(path);
}
const directoryStat = lstatSync(directory);
if (
  directoryStat.isSymbolicLink() ||
  directoryStat.uid !== process.getuid?.() ||
  directoryStat.mode & 0o077
)
  throw new Error('U6 run directory is not private and owned');
const bytes = privateFile('environment.json');
const manifest = JSON.parse(bytes.toString()) as {
  runId: string;
  profile: string;
  unit: string;
  realm: string;
  database: string;
  applicationPort: number;
  databasePort: number;
  expiresAt: number;
};
const ownership = JSON.parse(privateFile('ownership.json').toString()) as {
  runId: string;
  manifestSha256: string;
};
if (
  ownership.runId !== manifest.runId ||
  ownership.manifestSha256 !== createHash('sha256').update(bytes).digest('hex') ||
  !/^docsuri-u6-[a-f0-9]{16}$/.test(manifest.runId) ||
  manifest.profile !== 'synthetic-local' ||
  manifest.unit !== 'u6-approved-export' ||
  manifest.realm !== 'approved-export' ||
  manifest.database !== 'docsuri_u6' ||
  manifest.applicationPort !== 18099 ||
  manifest.databasePort !== 15499 ||
  manifest.expiresAt <= Date.now() / 1000
)
  throw new Error('U6 manifest identity, listener or retention mismatch');
const tls = JSON.parse(privateFile('approved-export-tls.json').toString()) as {
  runId: string;
  database: string;
  origin: string;
  expiresAt: number;
  certificateSha256: string;
  spkiSha256: string;
};
const certificateBytes = privateFile('approved-export-tls.crt');
const certificate = new X509Certificate(certificateBytes);
const actualPin = createHash('sha256')
  .update(certificate.publicKey.export({ type: 'spki', format: 'der' }))
  .digest('base64');
if (
  tls.runId !== manifest.runId ||
  tls.database !== manifest.database ||
  tls.origin !== 'https://127.0.0.1:18099' ||
  tls.expiresAt <= Date.now() / 1000 ||
  Math.abs(tls.expiresAt - manifest.expiresAt) >= 1 ||
  tls.certificateSha256 !== createHash('sha256').update(certificate.raw).digest('hex') ||
  tls.spkiSha256 !== actualPin ||
  Date.parse(certificate.validTo) <= Date.now() ||
  !certificate.checkIP('127.0.0.1')
)
  throw new Error('U6 certificate custody or identity mismatch');

export default defineConfig({
  testDir: './e2e/u6-approved-export',
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  globalTimeout: 300_000,
  expect: { timeout: 10_000 },
  outputDir: join(directory, 'browser-evidence'),
  use: {
    baseURL: tls.origin,
    ignoreHTTPSErrors: false,
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
            `--ignore-certificate-errors-spki-list=${actualPin}`,
            '--disable-dev-shm-usage',
            '--disable-extensions',
            '--renderer-process-limit=1',
            '--js-flags=--max-old-space-size=128 --max-semi-space-size=8',
          ],
        },
      },
    },
  ],
});
