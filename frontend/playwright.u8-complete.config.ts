// U8 complete-verification browser journeys over the served composed realm, through its
// public stand-in. Run only through `scripts/verify_docsuri_u8.py`'s journey phases, never
// directly and never against :3000 (U8 plan Step 43, "Allowlist sites" row 10).
import { defineConfig, devices } from '@playwright/test';
import { createHash, X509Certificate } from 'node:crypto';
import { lstatSync, readFileSync, realpathSync } from 'node:fs';
import { join } from 'node:path';

const directory = join(realpathSync('/tmp'), 'docsuri-u8-run');
const expected = join(directory, 'environment.json');
const environmentFile = process.env.DOCSURI_U8_ENVIRONMENT_FILE;
if (
  !environmentFile ||
  lstatSync(environmentFile).isSymbolicLink() ||
  realpathSync(environmentFile) !== expected
)
  throw new Error('U8 requires its explicit owned environment manifest');

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
    throw new Error('U8 private metadata boundary refused');
  return readFileSync(path);
}

const directoryStat = lstatSync(directory);
if (
  directoryStat.isSymbolicLink() ||
  directoryStat.uid !== process.getuid?.() ||
  directoryStat.mode & 0o077
)
  throw new Error('U8 run directory is not private and owned');

const bytes = privateFile('environment.json');
const manifest = JSON.parse(bytes.toString()) as {
  runId: string;
  profile: string;
  unit: string;
  realm: string;
  database: string;
  applicationPort: number;
  publicPort: number;
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
  !/^docsuri-u8-[a-f0-9]{16}$/.test(manifest.runId) ||
  manifest.profile !== 'synthetic-local' ||
  manifest.unit !== 'u8-service-operations-integration' ||
  manifest.realm !== 'service-operations' ||
  manifest.database !== 'docsuri_u8' ||
  manifest.applicationPort !== 18109 ||
  manifest.publicPort !== 18110 ||
  manifest.databasePort !== 15509 ||
  manifest.expiresAt <= Date.now() / 1000
)
  throw new Error('U8 manifest identity, listener or retention mismatch');

// The public stand-in's certificate (`service-operations-tls`), pinned by its SPKI.
const tls = JSON.parse(privateFile('service-operations-tls.json').toString()) as {
  runId: string;
  database: string;
  origin: string;
  expiresAt: number;
  certificateSha256: string;
  spkiSha256: string;
};
const certificate = new X509Certificate(privateFile('service-operations-tls.crt'));
const actualPin = createHash('sha256')
  .update(certificate.publicKey.export({ type: 'spki', format: 'der' }))
  .digest('base64');
if (
  tls.runId !== manifest.runId ||
  tls.database !== manifest.database ||
  tls.origin !== 'https://127.0.0.1:18110' ||
  tls.expiresAt <= Date.now() / 1000 ||
  tls.certificateSha256 !== createHash('sha256').update(certificate.raw).digest('hex') ||
  tls.spkiSha256 !== actualPin ||
  Date.parse(certificate.validTo) <= Date.now() ||
  !certificate.checkIP('127.0.0.1')
)
  throw new Error('U8 certificate custody or identity mismatch');

// The identity stand-in's own certificate for `localhost` (Google's and ORCID's pages on
// https://localhost:18114, a different site), pinned by its SPKI beside the public one.
function identityPin(): string | null {
  try {
    const identity = new X509Certificate(privateFile('identity-standin-tls.crt'));
    if (!identity.checkHost('localhost') || Date.parse(identity.validTo) <= Date.now())
      throw new Error('U8 identity stand-in certificate mismatch');
    return createHash('sha256')
      .update(identity.publicKey.export({ type: 'spki', format: 'der' }))
      .digest('base64');
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return null;
    throw error;
  }
}
const pins = [actualPin, identityPin()].filter((value): value is string => !!value);

export default defineConfig({
  testDir: './e2e/u8-complete',
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  globalTimeout: 280_000,
  expect: { timeout: 10_000 },
  outputDir: join(directory, 'browser-evidence'),
  reporter: [['junit', { outputFile: process.env.PLAYWRIGHT_JUNIT_OUTPUT_FILE }]],
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
            `--ignore-certificate-errors-spki-list=${pins.join(',')}`,
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
