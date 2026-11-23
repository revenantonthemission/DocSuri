// The isolation journey's records and probes (U8 plan Step 168(d); L4-13), kept apart from
// `isolation.spec.ts` so that each file stays under 800 lines. One probe for every probed
// row of the isolation table (`tests/u8_service_operations_integration/isolation_routes.json`):
// the requests for memberA's own records on that row and, for a read by identifier, the
// same request with made-up identifiers of the same shape.
import { expect, type Page } from '@playwright/test';
import { apiCall, fixtures, madeUpHash, madeUpId, type Ask, type IsolationRow } from './helpers';

export const LIMIT = { page: { limit: 50 } };
const stamp = Date.now();

// memberA's records, made by the first test, and memberB's, made by the second. The
// research turn may sit in an earlier session of memberA's (`turnSessionId`).
export const owner = {
  topicName: `격리-${stamp}`,
  sessionName: `격리 연구 ${stamp}`,
  searchLabel: `격리 검색 ${stamp}`,
  query: `격리질의 ${stamp}`,
  topicId: '',
  sessionId: '',
  turnSessionId: '',
  turnId: '',
  savedPaperId: '',
  savedSearchId: '',
  historyId: '',
  resetId: '',
  connectionId: '',
  effectId: '',
};
export const other = {
  topicName: `격리B-${stamp}`,
  topicId: '',
  savedPaperId: '',
  connectionId: '',
  linkId: '',
};

export type Probe = {
  /** The requests for memberA's own records on this row. */
  real: () => Ask[];
  /** The same request with made-up identifiers of the same shape (reads by identifier). */
  madeUp?: () => Ask;
  /** What memberA's own answer holds and memberB's must not. */
  markers?: () => string[];
  /** A list memberA holds nothing on; memberB's record on it is asked in reverse. */
  mayBeEmpty?: boolean;
};

export const post = (name: string, body: object): Ask => ({ path: `/api/v2/${name}`, body });
export const get = (path: string): Ask => ({ path: `/api/v2/${path}` });
const own = (): string[] => [fixtures().accounts.memberA.accountId];
const noSuchPaper = `u8-none-${stamp}`;

function artifactOf(artifactId: string, contentHash: string) {
  return { artifact: { artifactId, revision: fixtures().novelty.revision, contentHash } };
}

function ownContext(): string {
  return fixtures().novelty.contextId;
}

function attachmentBody(contextId: string) {
  return { contextId, attachmentId: madeUpId() };
}

/** A made-up enrollment with a made-up proof; never an account's password. */
function materialBody() {
  return { enrollmentId: madeUpId(), deliveryReference: madeUpId(), currentProof: madeUpHash() };
}

const LIST_PROBES: Record<string, Probe> = {
  consents: { real: () => [post('c02/access-list-consents', LIMIT)], markers: own },
  identityLinks: { real: () => [post('c02/access-list-identity-links', LIMIT)], mayBeEmpty: true },
  history: {
    real: () => [post('c03/library-list-history', LIMIT)],
    markers: () => [owner.historyId],
  },
  savedPapers: {
    real: () => [post('c03/library-list-saved-papers', LIMIT)],
    markers: () => [owner.savedPaperId],
  },
  savedSearches: {
    real: () => [post('c03/library-list-saved-searches', LIMIT)],
    markers: () => [owner.savedSearchId, owner.searchLabel],
  },
  recentPapers: {
    real: () => [post('c03/settings-list-recent-papers', LIMIT)],
    markers: () => [owner.savedPaperId],
  },
  suggestions: { real: () => [post('c03/settings-list-suggestions', LIMIT)] },
  resets: {
    real: () => [get('c03/settings-resets?view=history&limit=25')],
    markers: () => [owner.resetId],
  },
  usage: { real: () => [post('c03/usage-inspect', LIMIT)] },
  // The fixtures' two reservations are memberA's: each record names its account.
  usageRecords: { real: () => [post('c03/usage-list-records', LIMIT)], markers: own },
  assistanceHistory: {
    real: () => [
      post('c06/read-assistance-history', { paper: fixtures().assistanceJob.paper, ...LIMIT }),
    ],
    markers: () => [fixtures().assistanceJob.jobId],
  },
  researchJobs: {
    real: () => [post('c07/list-research-jobs', { limit: 50 })],
    markers: () => [fixtures().novelty.jobId],
  },
  researchSessions: {
    real: () => [post('c07/list-research-sessions', LIMIT)],
    markers: () => [owner.sessionId],
  },
  exportDestinations: {
    real: () => [post('c09/list-export-destinations', {})],
    markers: () => [owner.connectionId],
  },
  exportHistory: {
    real: () => [post('c09/list-export-history', { limit: 20 })],
    markers: () => [owner.effectId],
  },
  topics: { real: () => [get('topics')], markers: () => [owner.topicId, owner.topicName] },
};

const OWN_READ_PROBES: Record<string, Probe> = {
  inspectSession: { real: () => [post('c02/access-inspect-session', {})], markers: own },
  session: { real: () => [get('session')], markers: own },
  profile: { real: () => [post('c02/access-read-profile', {})], markers: own },
  settings: { real: () => [post('c03/settings-read', {})], markers: own },
  plan: { real: () => [post('c03/usage-read-plan', {})], markers: own },
  glossary: { real: () => [post('c06/read-glossary', {})], markers: own },
  notionConnection: {
    real: () => [post('c09/read-notion-connection', {})],
    markers: () => [owner.connectionId],
  },
};

const JOB_PROBES: Record<string, Probe> = {
  jobSnapshot: {
    real: () => [
      get(`jobs/${fixtures().novelty.jobId}`),
      get(`jobs/${fixtures().assistanceJob.jobId}`),
    ],
    madeUp: () => get(`jobs/${madeUpId()}`),
  },
  jobEvents: {
    real: () => [
      get(`jobs/${fixtures().novelty.jobId}/events`),
      get(`jobs/${fixtures().assistanceJob.jobId}/events`),
    ],
    madeUp: () => get(`jobs/${madeUpId()}/events`),
  },
  jobResult: {
    real: () => [get(`jobs/${fixtures().assistanceJob.jobId}/result`)],
    madeUp: () => get(`jobs/${madeUpId()}/result`),
    markers: () => [fixtures().assistanceJob.resultId],
  },
  assistanceJob: {
    real: () => [post('c06/read-assistance-job', { jobId: fixtures().assistanceJob.jobId })],
    madeUp: () => post('c06/read-assistance-job', { jobId: madeUpId() }),
    markers: () => [fixtures().assistanceJob.resultId],
  },
  preparedAssistance: {
    real: () => [post('c06/read-prepared-assistance', { jobId: fixtures().assistanceJob.jobId })],
    madeUp: () => post('c06/read-prepared-assistance', { jobId: madeUpId() }),
    markers: () => [fixtures().assistanceJob.resultId],
  },
  researchJob: {
    real: () => [
      post('c07/read-research-job', {
        kind: 'novelty-analysis',
        jobId: fixtures().novelty.jobId,
        contextId: fixtures().novelty.contextId,
      }),
    ],
    madeUp: () =>
      post('c07/read-research-job', {
        kind: 'novelty-analysis',
        jobId: madeUpId(),
        contextId: madeUpId(),
      }),
  },
  researchArtifact: {
    real: () => [
      post(
        'c07/read-research-artifact',
        artifactOf(fixtures().novelty.artifactId, fixtures().novelty.contentHash),
      ),
    ],
    madeUp: () => post('c07/read-research-artifact', artifactOf(madeUpId(), madeUpHash())),
    markers: () => [fixtures().novelty.contentHash],
  },
};

const RECORD_PROBES: Record<string, Probe> = {
  researchSession: {
    real: () => [post('c07/read-research-session', { sessionId: owner.sessionId })],
    madeUp: () => post('c07/read-research-session', { sessionId: madeUpId() }),
  },
  researchTurn: {
    real: () => [
      post('c07/read-research-turn', { sessionId: owner.turnSessionId, turnId: owner.turnId }),
    ],
    madeUp: () => post('c07/read-research-turn', { sessionId: madeUpId(), turnId: madeUpId() }),
  },
  topicSettings: {
    real: () => [get(`topics/${owner.topicId}/settings`)],
    madeUp: () => get(`topics/${madeUpId()}/settings`),
    markers: () => [owner.topicName],
  },
  savedPaper: {
    real: () => [post('c03/library-read-saved-paper', { savedPaperId: owner.savedPaperId })],
    madeUp: () => post('c03/library-read-saved-paper', { savedPaperId: noSuchPaper }),
    markers: () => [owner.savedPaperId],
  },
  historyRecord: {
    real: () => [post('c03/library-read-history', { historyId: owner.historyId })],
    madeUp: () => post('c03/library-read-history', { historyId: madeUpId() }),
    markers: () => [owner.historyId],
  },
  reset: {
    real: () => [get(`c03/settings-resets/${owner.resetId}`)],
    madeUp: () => get(`c03/settings-resets/${madeUpId()}`),
    markers: () => [owner.resetId],
  },
  exportEffect: {
    real: () => [post('c09/read-export-effect', { effectId: owner.effectId })],
    madeUp: () => post('c09/read-export-effect', { effectId: madeUpId() }),
    markers: () => [owner.effectId],
  },
};

// The six rows the table marks `notClaimed`: memberA holds no such record in this realm
// (or the read is switched off), so its own request already carries made-up identifiers
// under its own research context, and the run shows only that the answers are alike.
const NOT_CLAIMED_PROBES: Record<string, Probe> = {
  orcidProfile: {
    real: () => [post('c02/access-read-orcid-profile', { identityLinkId: madeUpId() })],
    madeUp: () => post('c02/access-read-orcid-profile', { identityLinkId: madeUpId() }),
  },
  mfaMaterial: {
    real: () => [post('c02/access-retrieve-mfa-enrollment-material', materialBody())],
    madeUp: () => post('c02/access-retrieve-mfa-enrollment-material', materialBody()),
  },
  lifecycleRequest: {
    real: () => [post('c02/lifecycle-inspect', { lifecycleRequestId: madeUpId() })],
    madeUp: () => post('c02/lifecycle-inspect', { lifecycleRequestId: madeUpId() }),
  },
  privateAttachment: {
    real: () => [post('c07/read-private-attachment', attachmentBody(ownContext()))],
    madeUp: () => post('c07/read-private-attachment', attachmentBody(madeUpId())),
  },
  privateAsset: {
    real: () => [
      post('c07/read-private-asset', { ...attachmentBody(ownContext()), assetId: madeUpId() }),
    ],
    madeUp: () =>
      post('c07/read-private-asset', { ...attachmentBody(madeUpId()), assetId: madeUpId() }),
  },
  draft: {
    real: () => [post('c07/restore-draft', { contextId: ownContext(), draftId: madeUpId() })],
    madeUp: () => post('c07/restore-draft', { contextId: madeUpId(), draftId: madeUpId() }),
  },
};

// The two asset rows keep loop-back 3's four-answer equality (the spec's `readOwnerAssets`).
const ASSET_PROBES: Record<string, Probe> = {
  readAsset: { real: () => [] },
  assetBytes: { real: () => [] },
};

export const PROBES: Record<string, Probe> = {
  ...LIST_PROBES,
  ...OWN_READ_PROBES,
  ...JOB_PROBES,
  ...RECORD_PROBES,
  ...NOT_CLAIMED_PROBES,
  ...ASSET_PROBES,
};

/** The longest list anywhere in an answer: an owner list's own rows. */
export function longestList(value: unknown): number {
  if (Array.isArray(value)) return Math.max(value.length, ...value.map(longestList));
  if (value === null || typeof value !== 'object') return 0;
  return Math.max(0, ...Object.values(value).map(longestList));
}

/** The first value of one field anywhere in an answer, or ''. */
export function firstMatch(body: unknown, field: string): string {
  return new RegExp(`"${field}":"([^"]+)"`).exec(JSON.stringify(body))?.[1] ?? '';
}

/** The owner's research sessions. A list read while the owner's sessions change answers
 * SNAPSHOT_EXPIRED (U4's consistent listing), and is read again. */
export async function listSessions(page: Page) {
  for (let attempt = 0; attempt < 5; attempt += 1) {
    const answer = await apiCall(page, '/api/v2/c07/list-research-sessions', LIMIT);
    if (answer.status === 200) return answer.body;
    expect(answer.code).toBe('SNAPSHOT_EXPIRED');
    await page.waitForTimeout(500);
  }
  throw new Error('the research session list never settled');
}

export function sessionIds(body: unknown): string[] {
  return [...JSON.stringify(body).matchAll(/"sessionId":"([0-9a-f-]{36})"/g)].map(
    (match) => match[1]!,
  );
}

/** The first research turn of one session, or '' when the session holds none. */
export async function firstTurn(page: Page, sessionId: string): Promise<string> {
  const session = await apiCall(page, '/api/v2/c07/read-research-session', { sessionId });
  return (session.body as { turnIds?: string[] } | null)?.turnIds?.[0] ?? '';
}

/** A research turn memberA already holds (J01's on a verification run, or an earlier
 * run's on this realm): reading it spends none of memberA's three usage places. */
export async function heldTurn(page: Page, sessions: readonly string[]) {
  for (const sessionId of sessions) {
    const turnId = await firstTurn(page, sessionId);
    if (turnId) return { sessionId, turnId };
  }
  return null;
}

/** The suggestions read with an identity link: memberB's own, and a made-up one. It
 * answers the link's own owner as it answers anyone (503 `POLICY_UNRESOLVED`), so it is
 * asked and reported, never claimed. */
export function suggestionsByLink(): { real: Ask; madeUp: Ask } {
  const suggestions = (identityLinkId: string) =>
    post('c03/settings-list-suggestions', { page: { limit: 5 }, identityLinkId });
  return { real: suggestions(other.linkId), madeUp: suggestions(madeUpId()) };
}

/** The reads by identifier of the records memberB holds, each beside the same read with
 * a made-up identifier. */
export function reverseReads(): { probe: string; real: Ask; madeUp: Ask }[] {
  const connection = (name: string, connectionId: string) => post(`c09/${name}`, { connectionId });
  return [
    {
      probe: 'savedPaper',
      real: post('c03/library-read-saved-paper', { savedPaperId: other.savedPaperId }),
      madeUp: post('c03/library-read-saved-paper', { savedPaperId: noSuchPaper }),
    },
    {
      probe: 'topicSettings',
      real: get(`topics/${other.topicId}/settings`),
      madeUp: get(`topics/${madeUpId()}/settings`),
    },
    {
      probe: 'orcidProfile',
      real: post('c02/access-read-orcid-profile', { identityLinkId: other.linkId }),
      madeUp: post('c02/access-read-orcid-profile', { identityLinkId: madeUpId() }),
    },
    {
      probe: 'notionConnection',
      real: connection('read-notion-connection', other.connectionId),
      madeUp: connection('read-notion-connection', madeUpId()),
    },
    {
      probe: 'exportDestinations',
      real: connection('list-export-destinations', other.connectionId),
      madeUp: connection('list-export-destinations', madeUpId()),
    },
  ];
}

/** Two writes read their payload before they ask for a session: an empty body is refused
 * as malformed (422) before the guard is met. They carry a well-formed made-up payload,
 * so the answer is the guard's. */
function wellFormed(path: string): object | undefined {
  if (path === '/api/v2/c02/access-change-password')
    return { currentPassword: madeUpHash(), newPassword: madeUpHash() };
  if (path === '/api/v2/c02/lifecycle-request')
    return {
      action: 'withdraw',
      policyRef: { policyId: 'u8-synthetic-v1', revision: '1' },
      confirmationRef: madeUpId(),
    };
  return undefined;
}

/** A request for a row with no probe: its route with made-up identifiers and an empty
 * body, enough to meet the guard before anything is read. */
export function plainRequest(row: IsolationRow): Ask {
  const path = row.path.replace(/\{[^}]+\}/g, () => madeUpId());
  if (row.method === 'GET') return { path };
  return { path, body: wellFormed(row.path) ?? {}, method: row.method };
}
