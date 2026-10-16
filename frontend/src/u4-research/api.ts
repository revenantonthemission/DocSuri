/** C07 browser bindings. Authority and CommandContext are always server-derived. */
import { ApiError, type Transport } from '../api';
import type * as W from '../../types/wire/dtos';

export const RESEARCH_POLICY = { policyId: 'u4-synthetic-research', revision: '1' } as const;
// Bound to the current synthetic policy; the server remains authoritative.
export const RESEARCH_LIMITS = {
  titleBytes: 1024,
  textBytes: 32_768,
  papers: 2,
  links: 8,
} as const;
export const utf8Bytes = (value: string): number => new TextEncoder().encode(value).byteLength;
export type Policy = W.WorkspacePolicyRef;
export type Scope = W.WorkspaceResearchScope;
export type Session = W.WorkspaceResearchSession;
export type Sessions = W.WorkspaceResearchSessions;
export type Deletion = W.WorkspaceResearchDeletion;
export type Context = W.WorkspaceResearchContext;
export type Receipt = W.WorkspaceJobReceipt;
export type ArtifactRef = W.WorkspaceResearchArtifactRef;
export type Artifact = W.WorkspaceResearchArtifact;
export type ArtifactResponse = W.WorkspaceResearchArtifactResponse;
export type Evidence = W.WorkspaceResearchEvidence;
export type DraftRevision = W.WorkspaceDraftRevision;
export type DraftRef = W.WorkspaceDraftRef;
export type DraftKind = DraftRevision['kind'];
export type JobKind = W.WorkspaceResearchJobReadHttp['kind'];
export type Job = {
  jobId: string;
  kind: JobKind;
  state: 'accepted' | 'running' | 'cancel_requested' | 'cancelled' | 'succeeded' | 'failed';
  revision: string;
  seq: number;
  ownerId: string;
  progress: W.WorkspaceProgress;
  result: W.WorkspaceResultRef | null;
  error: W.WorkspaceError | null;
  acceptedAt: string;
};

type Operations = {
  'create-research-context': [W.WorkspaceResearchContextCreateHttp, Context];
  'create-research-session': [W.WorkspaceResearchSessionCreateHttp, Session];
  'read-research-session': [W.WorkspaceResearchSessionReadHttp, Session];
  'list-research-sessions': [W.WorkspaceResearchSessionListHttp, Sessions];
  'delete-research-sessions': [
    (
      | {
          scope: 'one-session';
          sessionId: string;
          expectedRevision: string;
          confirmed: true;
          policy: Policy;
        }
      | { scope: 'all-sessions'; expectedRevision: string; confirmed: true; policy: Policy }
    ),
    W.WorkspaceResearchDeletion,
  ];
  'accept-research-turn': [W.WorkspaceResearchTurnRequestHttp, Receipt];
  'read-research-turn': [W.WorkspaceResearchTurnReadHttp, W.WorkspaceResearchTurn];
  'accept-novelty-analysis': [W.WorkspaceResearchNoveltyRequestHttp, Receipt];
  'accept-novelty-discussion': [W.WorkspaceResearchNoveltyDiscussionHttp, Receipt];
  'read-research-job': [W.WorkspaceResearchJobReadHttp, Job];
  'cancel-novelty-analysis': [W.WorkspaceResearchJobReadHttp, Job];
  'read-research-artifact': [W.WorkspaceResearchArtifactReadHttp, ArtifactResponse];
  'save-draft': [W.WorkspaceDraftWriteHttp, W.WorkspaceDraftWriteResult];
  'restore-draft': [W.WorkspaceDraftReadHttp, W.WorkspaceDraftRecovery];
  'discard-draft': [W.WorkspaceDraftDiscardHttp, W.WorkspaceAck];
  'begin-private-attachment': [
    W.WorkspaceResearchAttachmentStartHttp,
    W.WorkspaceResearchUploadPermit,
  ];
  'finish-private-attachment': [
    W.WorkspaceResearchAttachmentFinishHttp,
    W.WorkspaceResearchAttachment,
  ];
  'read-private-attachment': [W.WorkspaceResearchAttachmentReadHttp, W.WorkspaceResearchAttachment];
  'read-private-asset': [W.WorkspaceResearchPrivateAssetReadHttp, W.WorkspaceResearchPrivateAsset];
};

export function researchCall<K extends keyof Operations>(
  client: Transport,
  operation: K,
  body: Operations[K][0],
  key?: string,
): Promise<Operations[K][1]> {
  return client.post<Operations[K][1]>(`/api/v2/c07/${operation}`, body, key);
}

/** Reject a mismatched or malformed progress envelope before displaying success. */
export function checkedJob(value: Job, expected: { jobId: string; kind: JobKind }): Job {
  if (
    value.jobId !== expected.jobId ||
    value.kind !== expected.kind ||
    !Number.isInteger(value.seq) ||
    value.seq < 0 ||
    !['accepted', 'running', 'cancel_requested', 'cancelled', 'succeeded', 'failed'].includes(
      value.state,
    ) ||
    (value.state === 'succeeded' && (!value.result || value.error)) ||
    (value.state === 'failed' && (!value.error || value.result)) ||
    (!['succeeded', 'failed'].includes(value.state) && value.result !== null)
  ) {
    throw new ApiError(502, {
      code: 'INVALID_CONTENT',
      requestId: 'research-response',
      retryable: false,
      messageKey: 'research.invalid-response',
    });
  }
  return value;
}

export const emptyScope = (contextId: string, policy: Policy): Scope => ({
  contextId,
  publicPapers: [],
  attachmentIds: [],
  webReferences: [],
  scopePolicy: policy,
});
