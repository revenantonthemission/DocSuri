// U5 real-delivery evidence, credentials kept out of client state: after a member signs in
// and uses the topics view, a topic's settings form and the account preferences, no
// credential that the realm or the session holds appears in browser storage (local and
// session storage, IndexedDB, Cache Storage), in a cookie a script can read, or in the
// page, and none appears in any file of the served bundle: every text file of the built
// bundle, fetched from the host that serves it. The realm's credentials are its database
// logins and administrator, its two signing keys, its TLS private key and the fixture
// accounts' passwords; the session's are its cookies and CSRF token. A finding names the
// credential and where it was found, never the value.
import { lstatSync, readdirSync, readFileSync, realpathSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test, expect, type Page } from '@playwright/test';
import { captureTopicsFailures, fixtures, login, openTopics, scrub } from './helpers';

const BUNDLE = fileURLToPath(new URL('../../dist/', import.meta.url));
const TEXT = /\.(html|js|mjs|css|map|json|txt|svg|xml|webmanifest)$/;
// Names of the server's credential configuration: none belongs in a client file.
const MARKERS = [
  'PRIVATE KEY-----',
  'RESEND_API_KEY',
  'EMAIL_PROVIDER',
  'databaseAdminPassword',
  'owner-credentials',
  'migration-credentials',
];
// A credential form shorter than this could match unrelated text by chance.
const SHORTEST = 16;

type Credential = { name: string; forms: string[] };
type Source = { name: string; text: string };

const failures = new WeakMap<Page, ReturnType<typeof captureTopicsFailures>>();
test.beforeEach(({ page }) => {
  failures.set(page, captureTopicsFailures(page));
});

test.afterEach(async ({ page }, info) => {
  await failures.get(page)?.(info);
  await scrub(page);
});

/** One of the realm's private files, under the same custody rules as its fixtures. */
function privateFile(name: string): Buffer {
  const path = join(realpathSync('/tmp/docsuri-u5-run'), name),
    info = lstatSync(path);
  if (
    !info.isFile() ||
    info.isSymbolicLink() ||
    info.uid !== process.getuid?.() ||
    info.mode & 0o077 ||
    info.size > 16_384
  )
    throw new Error('U5 private realm file boundary refused');
  return readFileSync(path);
}

function realmCredentials(): Credential[] {
  const owners = JSON.parse(privateFile('owner-credentials.json').toString('utf8')) as {
    roles: Record<string, string>;
  };
  const migration = JSON.parse(privateFile('migration-credentials.json').toString('utf8')) as {
    databaseAdminPassword: string;
  };
  const key = (bytes: Buffer) => [
    bytes.toString('hex'),
    bytes.toString('base64'),
    bytes.toString('base64url'),
  ];
  const pem = privateFile('topics-digests-tls.key').toString('utf8');
  const body = pem.split('\n').filter((line) => line.trim() && !line.startsWith('-----'));
  const accounts = fixtures().accounts;
  return [
    ...Object.entries(owners.roles).map(([owner, password]) => ({
      name: `database login ${owner}`,
      forms: [password],
    })),
    { name: 'database administrator', forms: [migration.databaseAdminPassword] },
    { name: 'account verifier key', forms: key(privateFile('account-verifier.key')) },
    { name: 'search cursor key', forms: key(privateFile('search-cursor.key')) },
    { name: 'TLS private key', forms: [body.join(''), ...body] },
    { name: 'memberA password', forms: [accounts.memberA.password] },
    { name: 'memberB password', forms: [accounts.memberB.password] },
  ];
}

/** Each (credential, source) pair where a form of the credential appears. */
function findings(sources: Source[], credentials: Credential[]): string[] {
  return sources.flatMap((source) =>
    credentials
      .filter((credential) =>
        credential.forms.some((form) => form.length >= SHORTEST && source.text.includes(form)),
      )
      .map((credential) => `${credential.name} in ${source.name}`),
  );
}

/** Every text file of the built bundle, as a path the host serves. */
function bundlePaths(): string[] {
  const found: string[] = [];
  const visit = (directory: string) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      if (entry.name.startsWith('.')) continue;
      const path = join(directory, entry.name);
      if (entry.isDirectory()) visit(path);
      else if (entry.isFile() && TEXT.test(entry.name)) found.push(`/${relative(BUNDLE, path)}`);
    }
  };
  visit(BUNDLE);
  return found.sort();
}

/** Everything the page keeps where a script can read it. */
async function clientState(page: Page): Promise<Source[]> {
  const state = await page.evaluate(async () => {
    const dump = (storage: Storage) =>
      Array.from({ length: storage.length }, (_, index) => {
        const key = storage.key(index) ?? '';
        return `${key}=${storage.getItem(key) ?? ''}`;
      }).join('\n');
    const records: string[] = [];
    const databases = typeof indexedDB.databases === 'function' ? await indexedDB.databases() : [];
    for (const database of databases) {
      const name = database.name;
      if (!name) continue;
      records.push(name);
      const opened = await new Promise<IDBDatabase>((resolve, reject) => {
        const request = indexedDB.open(name);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      for (const store of Array.from(opened.objectStoreNames)) {
        const values = await new Promise<unknown[]>((resolve, reject) => {
          const request = opened.transaction(store).objectStore(store).getAll();
          request.onsuccess = () => resolve(request.result);
          request.onerror = () => reject(request.error);
        });
        records.push(`${name}/${store}=${JSON.stringify(values)}`);
      }
      opened.close();
    }
    const cached: string[] = [];
    if ('caches' in window) {
      for (const name of await caches.keys()) {
        const cache = await caches.open(name);
        cached.push(name, ...(await cache.keys()).map((request) => request.url));
      }
    }
    return {
      localStorage: dump(window.localStorage),
      sessionStorage: dump(window.sessionStorage),
      cookie: document.cookie,
      indexedDB: records.join('\n'),
      cacheStorage: cached.join('\n'),
      page: document.documentElement.outerHTML,
    };
  });
  return Object.entries(state).map(([name, text]) => ({ name, text }));
}

/** The bundle's text files as the host serves them, fetched by the page itself. */
async function servedBundle(page: Page, paths: string[]): Promise<(Source & { status: number })[]> {
  const served = await page.evaluate(async (files) => {
    const results: { name: string; status: number; text: string }[] = [];
    for (const file of files) {
      const response = await fetch(file, { cache: 'no-store', credentials: 'same-origin' });
      results.push({ name: file, status: response.status, text: await response.text() });
    }
    return results;
  }, paths);
  return served;
}

test('no credential reaches browser storage, the page or the served bundle', async ({ page }) => {
  const credentials = realmCredentials();
  const csrf = new Set<string>();
  page.on('response', (response) => {
    if (new URL(response.url()).pathname !== '/api/v2/session') return;
    void response
      .json()
      .then((value: unknown) => {
        const token = (value as { csrfToken?: unknown } | null)?.csrfToken;
        if (typeof token === 'string') csrf.add(token);
      })
      .catch(() => undefined);
  });
  const loaded = new Set<string>();
  page.on('response', (response) => {
    const url = new URL(response.url());
    const kind = response.request().resourceType();
    if (['document', 'script', 'stylesheet'].includes(kind)) loaded.add(url.pathname);
  });

  // Use the U5 surface as a member does: the topics view, a settings form and the
  // account preferences, then close the form unsaved.
  await login(page, fixtures().accounts.memberA);
  await openTopics(page);
  const row = page.getByTestId('topic-row').filter({ hasText: '해결 확인 주제' });
  await row.getByTestId('settings-link').click();
  const form = page.getByTestId('settings-form');
  await page.getByTestId('preferences-toggle').click();
  await expect(form.getByTestId('digest-language')).toBeVisible();
  await form.getByTestId('settings-close').click();
  await expect(form).toHaveCount(0);

  // The session's own credentials: its cookies and its CSRF token.
  const cookies = await page.context().cookies();
  expect(cookies.length, 'the session holds a cookie').toBeGreaterThan(0);
  expect(
    cookies.filter((cookie) => !cookie.httpOnly).map((cookie) => cookie.name),
    'no cookie is readable by a script',
  ).toEqual([]);
  await expect
    .poll(() => csrf.size, { message: 'the session CSRF token was seen' })
    .toBeGreaterThan(0);
  const session: Credential[] = [
    ...cookies.map((cookie) => ({ name: `cookie ${cookie.name}`, forms: [cookie.value] })),
    { name: 'session CSRF token', forms: [...csrf] },
  ];
  const all = [...credentials, ...session];
  // Every credential has a form long enough to be found.
  expect(
    all
      .filter((credential) => !credential.forms.some((form) => form.length >= SHORTEST))
      .map((credential) => credential.name),
  ).toEqual([]);
  // The scan finds each credential where it is planted, and only there.
  const planted = all.map((credential) => ({
    name: `planted ${credential.name}`,
    text: `x${credential.forms.find((form) => form.length >= SHORTEST) ?? ''}y`,
  }));
  expect(findings(planted, all)).toEqual(
    all.map((credential) => `${credential.name} in planted ${credential.name}`),
  );

  const state = await clientState(page);
  expect(findings(state, all), 'no credential in browser storage or the page').toEqual([]);

  const paths = bundlePaths();
  expect(paths, 'the built bundle has its shell').toContain('/index.html');
  for (const path of loaded) {
    if (path.startsWith('/assets/')) expect(paths, `${path} is a bundle file`).toContain(path);
  }
  const bundle = await servedBundle(page, paths);
  expect(
    bundle.filter((file) => file.status !== 200).map((file) => `${file.name} ${file.status}`),
    'the host serves every bundle file',
  ).toEqual([]);
  for (const extension of ['.js', '.css', '.map']) {
    expect(
      bundle.some((file) => file.name.endsWith(extension)),
      `the bundle has a ${extension} file`,
    ).toBe(true);
  }
  expect(findings(bundle, all), 'no credential in the served bundle').toEqual([]);
  expect(
    bundle.flatMap((file) =>
      MARKERS.filter((marker) => file.text.includes(marker)).map(
        (marker) => `${marker} in ${file.name}`,
      ),
    ),
    'no credential configuration name in the served bundle',
  ).toEqual([]);
});
