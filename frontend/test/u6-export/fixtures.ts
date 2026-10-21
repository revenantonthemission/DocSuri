// U6 export test doubles: a Transport-compatible double whose every C09 request and
// response is checked against the canonical schema defs, wire-shaped factories, an
// error `envelope` factory and a per-mount SWR provider.
import React from 'react';
import { render } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { ApiError, type Transport } from '../../src/api';
import type {
  Approval,
  Capability,
  Connection,
  DestinationEntry,
  Destinations,
  Effect,
  HistoryEntry,
  HistoryPage,
  Preview,
} from '../../src/u6-export/api';
import schema from '../../../shared/dtos/workspace.schema.json';

type Schema = {
  $ref?: string;
  type?: string | string[];
  required?: string[];
  properties?: Record<string, Schema | undefined>;
  additionalProperties?: boolean;
  enum?: unknown[];
  const?: unknown;
  items?: Schema;
  oneOf?: Schema[];
  anyOf?: Schema[];
  allOf?: Schema[];
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  maxItems?: number;
  pattern?: string;
};

const defs = schema.$defs as Record<string, Schema>;

function matches(spec: Schema, data: unknown): boolean {
  if (spec.$ref) return matches(defs[spec.$ref.split('/').pop()!]!, data);
  if (spec.const !== undefined && data !== spec.const) return false;
  if (spec.enum && !spec.enum.includes(data)) return false;
  if (spec.oneOf && spec.oneOf.filter((item) => matches(item, data)).length !== 1) return false;
  if (spec.anyOf && !spec.anyOf.some((item) => matches(item, data))) return false;
  if (spec.allOf && !spec.allOf.every((item) => matches(item, data))) return false;
  const types = Array.isArray(spec.type) ? spec.type : [spec.type];
  return types.some((type) => matchesType(type, spec, data));
}

function matchesType(type: string | undefined, spec: Schema, data: unknown): boolean {
  if (type === 'null') return data === null;
  if (type === 'string')
    return (
      typeof data === 'string' &&
      data.length >= (spec.minLength ?? 0) &&
      data.length <= (spec.maxLength ?? Infinity) &&
      (!spec.pattern || new RegExp(spec.pattern, 'u').test(data))
    );
  if (type === 'integer' || type === 'number')
    return (
      typeof data === 'number' &&
      Number.isFinite(data) &&
      (type !== 'integer' || Number.isInteger(data)) &&
      data >= (spec.minimum ?? -Infinity) &&
      data <= (spec.maximum ?? Infinity)
    );
  if (type === 'boolean') return typeof data === 'boolean';
  if (type === 'array')
    return (
      Array.isArray(data) &&
      data.length <= (spec.maxItems ?? Infinity) &&
      data.every((item) => matches(spec.items ?? {}, item))
    );
  if (type === 'object' || spec.properties || spec.required) {
    if (!data || typeof data !== 'object' || Array.isArray(data)) return false;
    const record = data as Record<string, unknown>;
    if (spec.required?.some((key) => !(key in record))) return false;
    if (
      spec.additionalProperties === false &&
      Object.keys(record).some((key) => !(key in (spec.properties ?? {})))
    )
      return false;
    return Object.entries(spec.properties ?? {}).every(
      ([key, item]) => !(key in record) || (item !== undefined && matches(item, record[key])),
    );
  }
  return true;
}

/** Whether a value conforms to one canonical C09 def. */
export function conforms(name: string, value: unknown): boolean {
  const spec = defs[name];
  if (!spec) throw new Error(`missing canonical schema ${name}`);
  return matches(spec, value);
}

/** The request and response defs of the eleven C09 routes. */
export const OPERATION_DEFS: Record<string, [string, string]> = {
  'configure-notion-connection': ['ExportConnectionConfigureHttp', 'ExportConnection'],
  'read-notion-connection': ['ExportConnectionReadHttp', 'ExportConnection'],
  'disconnect-notion': ['ExportConnectionReadHttp', 'ExportConnection'],
  'list-export-destinations': ['ExportConnectionReadHttp', 'ExportDestinations'],
  'prepare-export-preview': ['ExportPreviewRequestHttp', 'ExportPreview'],
  'approve-export-preview': ['ExportApprovalRequestHttp', 'ExportApproval'],
  'execute-approved-export': ['ExportExecuteHttp', 'ExportEffect'],
  'read-export-effect': ['ExportEffectReadHttp', 'ExportEffect'],
  'cancel-export-approval': ['ExportCancelHttp', 'ExportApproval'],
  'list-export-history': ['ExportHistoryListHttp', 'ExportHistoryPage'],
  'settle-export-effect': ['ExportSettleHttp', 'ExportEffect'],
};

export const MUTATIONS = new Set([
  'configure-notion-connection',
  'disconnect-notion',
  'prepare-export-preview',
  'approve-export-preview',
  'execute-approved-export',
  'cancel-export-approval',
  'settle-export-effect',
]);

export type Call = { name: string; path: string; body: unknown; key: string | undefined };
type Handler = (body: unknown, call: Call) => unknown;

/** A recording C09 Transport double. A nonconformant request or response is recorded
in `violations` and fails the call, so no component can pass on an impossible shape. */
export class ExportDouble {
  generation = 1;
  calls: Call[] = [];
  violations: string[] = [];
  private handlers = new Map<string, Handler>();

  on(name: string, handler: Handler): this {
    this.handlers.set(name, handler);
    return this;
  }

  async post<T>(path: string, body: unknown, key?: string): Promise<T> {
    const name = path.split('/').pop()!;
    const call = { name, path, body, key };
    this.calls.push(call);
    const operation = OPERATION_DEFS[name];
    if (!operation || !path.startsWith('/api/v2/c09/')) {
      this.violations.push(`unknown route ${path}`);
      throw new Error(`Unexpected route ${path}`);
    }
    if (!conforms(operation[0], body)) {
      this.violations.push(`request ${name}`);
      throw new Error(`nonconformant request ${name}`);
    }
    const handler = this.handlers.get(name);
    if (!handler) throw new Error(`Unexpected operation ${name}`);
    const result = await handler(body, call);
    if (!conforms(operation[1], result)) {
      this.violations.push(`response ${name}`);
      throw new Error(`nonconformant response ${name}`);
    }
    return result as T;
  }

  named(name: string): Call[] {
    return this.calls.filter((call) => call.name === name);
  }

  mutations(): Call[] {
    return this.calls.filter((call) => MUTATIONS.has(call.name));
  }

  client(): Transport {
    return this as unknown as Transport;
  }
}

/** An ApiError as the shared Transport raises it. */
export function envelope(code: string, status = 409, extra: { retryAfterSeconds?: number } = {}) {
  return new ApiError(status, {
    code,
    requestId: 'request-u6-1',
    retryable: false,
    messageKey: `request.${code.toLowerCase()}`,
    ...extra,
  });
}

/** Each mount gets its own SWR cache, so no test sees another test's reads. */
export function mount(ui: React.ReactElement) {
  return render(
    React.createElement(
      SWRConfig,
      { value: { provider: () => new Map(), dedupingInterval: 0 } },
      ui,
    ),
  );
}

export const POLICY = { policyId: 'u6-synthetic-export', revision: '1' };
export const OWNER = '11111111-1111-4111-8111-111111111111';
export const CONNECTION_ID = '22222222-2222-4222-8222-222222222222';
export const PREVIEW_ID = '33333333-3333-4333-8333-333333333333';
export const APPROVAL_ID = '44444444-4444-4444-8444-444444444444';
export const EFFECT_ID = '55555555-5555-4555-8555-555555555555';
export const ARTIFACT_ID = '66666666-6666-4666-8666-666666666666';
export const WORKSPACE_ID = 'w'.repeat(8);
export const PAGE_A = 'a'.repeat(32);
export const PAGE_B = 'b'.repeat(32);
export const PAGE_C = 'c'.repeat(32);
export const HASH = 'd'.repeat(64);
export const TOKEN = 'secret_synthetic_u6_token_value_0001';

export const capability = (changes: Partial<Capability> = {}): Capability => ({
  id: 'export',
  state: 'degraded',
  modeIds: ['synthetic-only'],
  languageIds: ['ko'],
  levelIds: [],
  formatIds: ['notion'],
  policy: POLICY,
  ...changes,
});

export const connection = (changes: Partial<Connection> = {}): Connection => ({
  connectionId: CONNECTION_ID,
  ownerId: OWNER,
  revision: '1',
  provider: 'notion',
  state: 'connected',
  destinationScopeIds: [],
  limitations: ['synthetic-only'],
  workspaceName: '시험 워크스페이스',
  ...changes,
});

export const entry = (changes: Partial<DestinationEntry> = {}): DestinationEntry => ({
  connectionId: CONNECTION_ID,
  workspaceId: WORKSPACE_ID,
  parentPageId: PAGE_A,
  formatRevision: '1',
  destinationId: PAGE_A,
  title: '연구 노트',
  context: '팀 공간 / 연구',
  readable: true,
  creationCapability: 'unknown',
  writable: true,
  ...changes,
});

export const destinations = (
  items: DestinationEntry[],
  changes: Partial<Destinations> = {},
): Destinations => ({
  connectionId: CONNECTION_ID,
  connectionRevision: '1',
  destinations: items,
  listingComplete: true,
  ...changes,
});

export const source = { artifactId: ARTIFACT_ID, revision: '1', contentHash: HASH };

export const preview = (changes: Partial<Preview> = {}): Preview => ({
  previewId: PREVIEW_ID,
  ownerId: OWNER,
  revision: '1',
  source,
  sourceEligibilityRevision: '1',
  connectionRevision: '1',
  destination: entry(),
  renderedText: '읽은 범위의 연구 비교\n\n근거가 있는 주장\n\nDocSuri export marker: m-1',
  renderedContentHash: HASH,
  bindingHash: 'e'.repeat(64),
  renderPolicy: POLICY,
  earlierExports: [],
  marker: 'DocSuri export marker: m-1',
  sourceTitle: '읽은 범위의 연구 비교',
  ...changes,
});

export const approval = (changes: Partial<Approval> = {}): Approval => ({
  approvalId: APPROVAL_ID,
  ownerId: OWNER,
  previewId: PREVIEW_ID,
  previewRevision: '1',
  bindingHash: 'e'.repeat(64),
  approvedAt: '2026-10-20T01:00:00+00:00',
  expiresAt: null,
  state: 'approved',
  policy: { policyId: 'u6-approval-validity', revision: '1' },
  ...changes,
});

export const effect = (changes: Partial<Effect> = {}): Effect => ({
  effectId: EFFECT_ID,
  approvalId: APPROVAL_ID,
  ownerId: OWNER,
  revision: '1',
  bindingHash: 'e'.repeat(64),
  state: 'accepted',
  remoteReference: null,
  remoteUrl: null,
  reconciliationEvidenceHash: null,
  limitations: [],
  settlementOffered: false,
  ...changes,
});

export const historyEntry = (changes: Partial<HistoryEntry> = {}): HistoryEntry => ({
  approvalId: APPROVAL_ID,
  previewId: PREVIEW_ID,
  previewRevision: '1',
  bindingHash: 'e'.repeat(64),
  state: 'approved',
  approvedAt: '2026-10-20T01:00:00+00:00',
  sourceTitle: '읽은 범위의 연구 비교',
  destinationTitle: '연구 노트',
  continuable: true,
  ...changes,
});

export const historyPage = (
  entries: HistoryEntry[],
  nextCursor: string | null = null,
): HistoryPage => ({ entries, nextCursor }) as HistoryPage;

export const PAGE_URL = `https://www.notion.so/DocSuri-${'f'.repeat(32)}`;
