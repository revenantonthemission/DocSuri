import { vi } from 'vitest';
import type { WorkspaceAccessProfile, WorkspaceSettingsSnapshot } from '../../types/wire/dtos';
import { ApiError, Transport } from '../../src/api';
export const policy = { policyId: 'u2-synthetic-v1', revision: '1' };
export const settingsPolicy = { policyId: 'synthetic-personal-settings', revision: '1' };
export const profile: WorkspaceAccessProfile = {
  accountId: 'account-a',
  email: 'a@example.test',
  emailVerified: true,
  revision: 'profile-r1',
  lifecycleRevision: 'lifecycle-r1',
  fieldVocabularyRevision: 'u2-profile-v1',
  definitions: ['displayName', 'affiliation', 'biography'].map((fieldId) => ({
    fieldId,
    labelKey: `profile.${fieldId}`,
    valueKind: 'text',
    mutable: true,
    nullable: false,
    choiceIds: [],
    policyRef: policy,
  })),
  fields: [
    { fieldId: 'displayName', value: '연구자 A' },
    { fieldId: 'affiliation', value: '연구소' },
    { fieldId: 'biography', value: '소개' },
    { fieldId: 'role', value: 'member' },
  ],
};
export const settings: WorkspaceSettingsSnapshot = {
  accountId: 'account-a',
  settingsId: 'account-a',
  revision: 'settings-r1',
  searchDefaults: {
    modeId: 'lexical',
    orderId: 'relevance',
    filters: [],
    vocabularyRevision: 'synthetic-paper-options-1',
  },
  assistanceDefaults: {
    actionId: 'summary',
    languageId: 'en',
    presentationLevelId: 'standard',
    vocabularyRevision: 'synthetic-paper-options-1',
  },
  appearance: 'system',
  onboarding: 'in_progress',
  interestIds: ['1706.03762'],
  policyRef: settingsPolicy,
};
export const fullSession = {
  state: 'authenticated',
  session: {
    accountId: 'account-a',
    sessionId: 'session-a',
    authorityRevision: 'authority-r1',
    authenticationLevel: 'primary',
    verified: true,
  },
};
export const reset = {
  resetId: 'reset-a',
  action: 'delete_behavior',
  acceptedAt: '2026-10-13T17:00:00Z',
  acceptedSettingsRevision: 'settings-r1',
  inputBoundary: 'boundary-r2',
  policyRef: policy,
  manifestRevision: 'manifest-1',
  statusRevision: 'status-1',
  observedAt: '2026-10-13T17:01:00Z',
  disposition: 'pending',
  reasonKey: 'cleanup-pending',
};
export const page = (items: unknown[] = [], extra = {}) => ({
  items,
  page: { snapshotRevision: 'snapshot-1' },
  appliedLimit: 25,
  policyRef: policy,
  ...extra,
});
export const failed = (code = 'DEPENDENCY_UNAVAILABLE') =>
  new ApiError(503, { code, messageKey: 'request.error', requestId: 'request-1', retryable: true });
export function fakeClient(overrides: Record<string, unknown> = {}) {
  const response = (path: string) => {
    if (path in overrides) {
      const value = overrides[path];
      if (value instanceof Error) return Promise.reject(value);
      return Promise.resolve(value);
    }
    const values: Record<string, unknown> = {
      '/api/v2/c02/access-read-profile': profile,
      '/api/v2/c02/access-inspect-session': fullSession,
      '/api/v2/c02/access-list-consents': page([
        {
          consentId: 'personalization',
          accountId: 'account-a',
          purposeId: 'personalization',
          decision: 'granted',
          revision: 'consent-r1',
          effectiveAt: '2026-10-13T17:00:00Z',
          policyRef: policy,
        },
      ]),
      '/api/v2/c02/access-list-identity-links': page(),
      '/api/v2/c03/settings-read': settings,
      '/api/v2/c03/settings-list-suggestions': page([
        {
          interestId: '1706.03762',
          labelKey: 'attention',
          source: 'retained_manual_vocabulary',
          sourceRevision: 'v1',
          reasonKey: 'manual',
        },
        {
          interestId: '2005.11401',
          labelKey: 'rag',
          source: 'retained_manual_vocabulary',
          sourceRevision: 'v1',
          reasonKey: 'manual',
        },
      ]),
      '/api/v2/c03/settings-resets?view=outstanding&limit=25': page([reset]),
      '/api/v2/c03/settings-resets?view=history&limit=25': page([reset]),
      '/api/v2/c03/settings-resets/reset-a': {
        reset,
        scopes: [
          {
            participantId: 'Personalization',
            scopeId: 'behavior',
            manifestRevision: 'manifest-1',
            workGeneration: '1',
            disposition: 'pending',
            reasonKey: 'pending',
            evidenceRef: null,
            updatedAt: '2026-10-13T17:01:00Z',
          },
        ],
      },
      '/api/v2/c03/usage-read-plan': {
        accountId: 'account-a',
        tierId: 'synthetic-free',
        labelKey: 'plan.syntheticFree',
        source: 'mock',
        revision: 'r1',
        policyRef: policy,
        paymentOccurred: false,
      },
      '/api/v2/c03/usage-inspect': page([
        {
          state: 'known',
          metricId: 'paper-assistance',
          allocated: 4,
          used: 1,
          reserved: 1,
          remaining: 2,
          periodId: 'period:1',
          periodStart: '2026-10-13T17:00:00Z',
          periodEnd: '2026-10-13T18:00:00Z',
          policyRef: policy,
        },
      ]),
      '/api/v2/c03/usage-list-records': page(),
    };
    return Promise.resolve(values[path] ?? {});
  };
  const client = {
    read: vi.fn(response),
    get: vi.fn(response),
    post: vi.fn().mockResolvedValue({}),
    bootstrap: vi.fn().mockResolvedValue({
      signedIn: true,
      accountId: 'account-a',
      authorityRevision: 'authority-r1',
      csrfToken: 'csrf',
    }),
    generation: 1,
    subscribe: vi.fn(() => () => undefined),
    invalidateBoundary: vi.fn(),
  };
  return { ...client, transport: client as unknown as Transport };
}
