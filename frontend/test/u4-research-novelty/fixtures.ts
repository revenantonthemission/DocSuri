import { expect } from 'vitest';
import { ApiError, type Transport } from '../../src/api';
import type {
  Artifact,
  ArtifactResponse,
  Context,
  Job,
  Policy,
  Receipt,
  Scope,
  Session,
} from '../../src/u4-research/api';
import schema from '../../../shared/dtos/workspace.schema.json';

export const policy: Policy = { policyId: 'u4-synthetic-research', revision: '1' };
export const scope: Scope = {
  contextId: 'context-a',
  publicPapers: [],
  attachmentIds: [],
  webReferences: [],
  scopePolicy: policy,
};
export const context: Context = {
  contextId: scope.contextId,
  ownerId: 'owner-a',
  purpose: 'research',
  revision: '1',
  lifecycle: 'active',
};
export const session: Session = {
  sessionId: 'session-a',
  ownerId: 'owner-a',
  revision: '1',
  scope,
  lifecycle: 'active',
  turnIds: [],
  pendingJobIds: [],
  deletionBoundary: null,
};
export const receipt: Receipt = {
  jobId: 'job-a',
  state: 'accepted',
  revision: '1',
  seq: 1,
  requestId: 'request-a',
  acceptedAt: '2026-10-16T00:00:00Z',
};
export const job = (changes: Partial<Job> = {}): Job => ({
  jobId: 'job-a',
  kind: 'research-turn',
  state: 'accepted',
  revision: '1',
  seq: 1,
  ownerId: 'owner-a',
  progress: { mode: 'indeterminate' },
  result: null,
  error: null,
  acceptedAt: '2026-10-16T00:00:00Z',
  ...changes,
});
export const artifact: Artifact = {
  artifact: { artifactId: 'artifact-a', revision: '1', contentHash: 'a'.repeat(64) },
  ownerId: 'owner-a',
  contextId: scope.contextId,
  operationId: 'job-a',
  kind: 'novelty-result',
  output: {
    summary: '읽은 범위의 연구 비교',
    evidence: [
      {
        evidenceId: 'e1',
        sourceKind: 'public-paper',
        sourceId: 'paper-a',
        sourceVersion: 'v1',
        sourceContentHash: 'b'.repeat(64),
        location: 'section 1',
        readCoverage: 'read',
        quote: 'source quotation',
        claim: '근거가 있는 주장',
        stance: 'supports',
        sourceUrl: 'https://example.org/paper',
      },
    ],
    coverage: 'partial',
    limitations: ['일부 자료만 확인함'],
    methodRevision: '1',
  },
  currentEligibilityRevision: '1',
  mediaType: 'application/json',
  policy,
};
export const ready = (value: Artifact = artifact): ArtifactResponse => ({
  availability: 'ready',
  prepared: value,
});
export const complete = (changes: Partial<Job> = {}): Job =>
  job({
    state: 'succeeded',
    seq: 3,
    result: {
      resultId: artifact.artifact.artifactId,
      revision: artifact.artifact.revision,
      contentHash: artifact.artifact.contentHash,
      mediaType: 'application/json',
    },
    ...changes,
  });
export const apiError = (code: string) =>
  new ApiError(409, {
    code,
    requestId: 'request-a',
    retryable: false,
    messageKey: 'request.refused',
  });

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
  minimum?: number;
  minLength?: number;
  allOf?: Schema[];
  if?: Schema;
  then?: Schema;
  else?: Schema;
  not?: Schema;
};
/** Validate the canonical structural subset used by doubles, including unions and state conditions. */
export function conforms(name: string, value: unknown) {
  const defs = schema.$defs as Record<string, Schema>;
  function matches(spec: Schema, data: unknown): boolean {
    if (spec.$ref) return matches(defs[spec.$ref.split('/').pop()!]!, data);
    if (spec.const !== undefined && data !== spec.const) return false;
    if (spec.enum && !spec.enum.includes(data)) return false;
    if (spec.oneOf && spec.oneOf.filter((s) => matches(s, data)).length !== 1) return false;
    if (spec.anyOf && !spec.anyOf.some((s) => matches(s, data))) return false;
    if (spec.allOf && !spec.allOf.every((s) => matches(s, data))) return false;
    if (spec.if && !matches(matches(spec.if, data) ? (spec.then ?? {}) : (spec.else ?? {}), data))
      return false;
    if (spec.not && matches(spec.not, data)) return false;
    const types = Array.isArray(spec.type) ? spec.type : [spec.type];
    return types.some((type) => matchesType(type, spec, data));
  }
  function matchesType(type: string | undefined, spec: Schema, data: unknown): boolean {
    if (type === 'null') return data === null;
    if (type === 'string')
      return typeof data === 'string' && data.length >= (spec.minLength ?? 0);
    if (type === 'integer' || type === 'number')
      return (
        typeof data === 'number' &&
        Number.isFinite(data) &&
        (type !== 'integer' || Number.isInteger(data)) &&
        data >= (spec.minimum ?? -Infinity)
      );
    if (type === 'boolean') return typeof data === 'boolean';
    if (type === 'array')
      return Array.isArray(data) && data.every((item) => matches(spec.items ?? {}, item));
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
  expect(defs[name], `missing canonical schema ${name}`).toBeDefined();
  expect(matches(defs[name]!, value), `nonconformant canonical fixture ${name}`).toBe(true);
}

export class Double {
  generation = 1;
  calls: { name: string; body: unknown; key: string | undefined }[] = [];
  handlers = new Map<string, (value: unknown) => unknown>();
  on(name: string, handler: (value: unknown) => unknown) {
    this.handlers.set(name, handler);
    return this;
  }
  async post<T>(path: string, body: unknown, key?: string): Promise<T> {
    const name = path.split('/').pop()!;
    this.calls.push({ name, body, key });
    const operation = schemas[name];
    if (operation) conforms(operation[0], body);
    const handler = this.handlers.get(name);
    if (!handler) throw new Error(`Unexpected operation ${name}`);
    const result = await handler(body);
    if (operation) conforms(operation[1], result);
    return result as T;
  }
  client(): Transport {
    return this as unknown as Transport;
  }
}
const schemas: Record<string, [string, string]> = {
  'create-research-context': ['ResearchContextCreateHttp', 'ResearchContext'],
  'create-research-session': ['ResearchSessionCreateHttp', 'ResearchSession'],
  'list-research-sessions': ['ResearchSessionListHttp', 'ResearchSessions'],
  'read-research-session': ['ResearchSessionReadHttp', 'ResearchSession'],
  'delete-research-sessions': ['ResearchDeleteHttp', 'ResearchDeletion'],
  'accept-research-turn': ['ResearchTurnRequestHttp', 'JobReceipt'],
  'accept-novelty-analysis': ['ResearchNoveltyRequestHttp', 'JobReceipt'],
  'accept-novelty-discussion': ['ResearchNoveltyDiscussionHttp', 'JobReceipt'],
  'read-research-turn': ['ResearchTurnReadHttp', 'ResearchTurn'],
  'read-research-job': ['ResearchJobReadHttp', 'JobSnapshot'],
  'cancel-novelty-analysis': ['ResearchJobReadHttp', 'JobSnapshot'],
  'read-research-artifact': ['ResearchArtifactReadHttp', 'ResearchArtifactResponse'],
  'save-draft': ['DraftWriteHttp', 'DraftWriteResult'],
  'restore-draft': ['DraftReadHttp', 'DraftRecovery'],
  'discard-draft': ['DraftDiscardHttp', 'Ack'],
  'read-private-attachment': ['ResearchAttachmentReadHttp', 'ResearchAttachment'],
};
