/** C09 browser bindings for the approved Notion export (C09 2.1.0).

Authority, the owner and every destination fact are server-derived: the browser
sends only identifiers it was given, and every response is checked before a
screen shows it. A malformed response is refused as INVALID_CONTENT rather than
displayed. The Notion token passes through `exportCall` once, inside the
configure body, and is never kept here. */

import { ApiError, type Transport } from '../api';
import type * as W from '../../types/wire/dtos';

export type Policy = W.WorkspacePolicyRef;
export type ArtifactRef = W.WorkspaceResearchArtifactRef;
export type Capability = W.WorkspaceCapabilityCatalog['capabilities'][number];
export type Connection = W.WorkspaceExportConnection;
export type ConnectionState = Connection['state'];
export type DestinationEntry = W.WorkspaceExportDestinationEntry;
export type DestinationRequest = W.WorkspaceExportDestination;
export type Destinations = W.WorkspaceExportDestinations;
export type Preview = W.WorkspaceExportPreview;
export type EarlierExport = W.WorkspaceExportEarlierExport;
export type Approval = W.WorkspaceExportApproval;
export type ApprovalState = W.WorkspaceExportApprovalState;
export type Effect = W.WorkspaceExportEffect;
export type EffectState = W.WorkspaceExportEffectState;
export type HistoryPage = W.WorkspaceExportHistoryPage;
export type HistoryEntry = W.WorkspaceExportHistoryEntry;
export type HistoryEffect = W.WorkspaceExportHistoryEffect;
export type PossibleDuplicate = W.WorkspaceExportPossibleDuplicate;
export type OutcomeReason = W.WorkspaceExportOutcomeReason;
export type InvalidationReason = W.WorkspaceExportInvalidationReason;
export type SettleDisposition = W.WorkspaceExportSettleDisposition;
export type CreationCapability = W.WorkspaceExportCreationCapability;

/** The capability id the shell catalog names for this unit. */
export const EXPORT_CAPABILITY_ID = 'export';
/** The token bound the trusted side enforces (BR1.2); Notion validates the rest. */
export const TOKEN_MAX_LENGTH = 512;
/** The largest history page the contract allows (A2). */
export const HISTORY_PAGE_SIZE = 20;
/** The placeholder title the server gives an untitled Notion page (BR1.5). */
export const UNTITLED_TITLE = '제목 없음';

type Operations = {
  'configure-notion-connection': [W.WorkspaceExportConnectionConfigureHttp, Connection];
  'read-notion-connection': [W.WorkspaceExportConnectionReadHttp, Connection];
  'disconnect-notion': [W.WorkspaceExportConnectionReadHttp, Connection];
  'list-export-destinations': [W.WorkspaceExportConnectionReadHttp, Destinations];
  'prepare-export-preview': [W.WorkspaceExportPreviewRequestHttp, Preview];
  'approve-export-preview': [W.WorkspaceExportApprovalRequestHttp, Approval];
  'execute-approved-export': [W.WorkspaceExportExecuteHttp, Effect];
  'read-export-effect': [W.WorkspaceExportEffectReadHttp, Effect];
  'cancel-export-approval': [W.WorkspaceExportCancelHttp, Approval];
  'list-export-history': [W.WorkspaceExportHistoryListHttp, HistoryPage];
  'settle-export-effect': [W.WorkspaceExportSettleHttp, Effect];
};
export type ExportOperation = keyof Operations;

const CONNECTION_STATES: readonly string[] = [
  'connected',
  'disconnected',
  'revoked',
  'unavailable',
];
const APPROVAL_STATES: readonly string[] = [
  'approved',
  'invalidated',
  'consumed',
  'cancelled',
  'expired',
];
const EFFECT_STATES: readonly string[] = [
  'accepted',
  'executing',
  'succeeded',
  'failed',
  'unknown',
  'cancelled',
  'invalidated',
];
const ENDED_EFFECT_STATES: readonly string[] = ['succeeded', 'failed', 'cancelled', 'invalidated'];
const CREATION_CAPABILITIES: readonly string[] = ['unknown', 'confirmed', 'refused'];
const EARLIER_DISPOSITIONS: readonly string[] = ['exported', 'may-exist'];
const SETTLED_BY: readonly string[] = ['provider', 'reconciliation', 'owner'];
export const OUTCOME_REASONS: readonly OutcomeReason[] = [
  'token-invalid',
  'no-access',
  'destination-missing',
  'content-rejected',
  'workspace-block-limit',
  'provider-blocked',
  'rate-limit-budget-spent',
  'not-found-after-checks',
  'owner-settled-delivered',
  'owner-settled-not-delivered',
  'dependency-unavailable',
  'policy-unresolved',
  'source-changed',
  'destination-changed',
  'connection-changed',
  'authority-revoked',
  'account-withdrawn',
  'owner-cancelled',
];
export const INVALIDATION_REASONS: readonly InvalidationReason[] = [
  'source-changed',
  'destination-changed',
  'connection-changed',
  'authority-revoked',
  'account-withdrawn',
];

type Value = Record<string, unknown>;

const isRecord = (value: unknown): value is Value =>
  typeof value === 'object' && value !== null && !Array.isArray(value);
const isText = (value: unknown): value is string => typeof value === 'string' && value.length > 0;
const isOptional = (value: unknown, check: (item: unknown) => boolean): boolean =>
  value === undefined || check(value);
const oneOf =
  (allowed: readonly string[]) =>
  (value: unknown): boolean =>
    typeof value === 'string' && allowed.includes(value);
const isBoolean = (value: unknown): boolean => typeof value === 'boolean';
const isTextList = (value: unknown): boolean => Array.isArray(value) && value.every(isText);
/** A link a screen may render: only an https URL, never a script or relative target. */
export const isSafeLink = (value: unknown): value is string => {
  if (!isText(value)) return false;
  try {
    return new URL(value).protocol === 'https:';
  } catch {
    return false;
  }
};
const hasText = (value: Value, ...keys: string[]): boolean =>
  keys.every((key) => isText(value[key]));

function validConnection(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(value, 'connectionId', 'ownerId', 'revision') &&
    value.provider === 'notion' &&
    oneOf(CONNECTION_STATES)(value.state) &&
    isTextList(value.destinationScopeIds) &&
    isTextList(value.limitations) &&
    isOptional(value.workspaceName, isText)
  );
}

function validEntry(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(
      value,
      'connectionId',
      'workspaceId',
      'parentPageId',
      'formatRevision',
      'destinationId',
      'title',
    ) &&
    isOptional(value.context, isText) &&
    isOptional(value.readable, isBoolean) &&
    isOptional(value.writable, isBoolean) &&
    isOptional(value.creationCapability, oneOf(CREATION_CAPABILITIES))
  );
}

function validDestinations(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(value, 'connectionId', 'connectionRevision') &&
    Array.isArray(value.destinations) &&
    value.destinations.every(validEntry) &&
    isOptional(value.listingComplete, isBoolean) &&
    isOptional(value.lastDestinationId, isText)
  );
}

function validEarlier(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(value, 'effectId', 'endedAt') &&
    oneOf(EARLIER_DISPOSITIONS)(value.disposition) &&
    isOptional(value.remoteUrl, isSafeLink) &&
    isOptional(value.outcomeReason, oneOf(OUTCOME_REASONS))
  );
}

function validPreview(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(value, 'previewId', 'ownerId', 'revision', 'bindingHash', 'renderedContentHash') &&
    isRecord(value.source) &&
    hasText(value.source, 'artifactId', 'revision', 'contentHash') &&
    validEntry(value.destination) &&
    typeof value.renderedText === 'string' &&
    isOptional(
      value.earlierExports,
      (items) => Array.isArray(items) && items.every(validEarlier),
    ) &&
    isOptional(value.marker, isText) &&
    isOptional(value.sourceTitle, isText)
  );
}

function validApproval(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(value, 'approvalId', 'previewId', 'previewRevision', 'bindingHash', 'approvedAt') &&
    oneOf(APPROVAL_STATES)(value.state) &&
    isOptional(value.invalidationReason, oneOf(INVALIDATION_REASONS))
  );
}

function validEffect(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(value, 'effectId', 'approvalId', 'revision', 'bindingHash') &&
    oneOf(EFFECT_STATES)(value.state) &&
    (value.remoteUrl === null || isSafeLink(value.remoteUrl)) &&
    isTextList(value.limitations) &&
    isOptional(value.outcomeReason, oneOf(OUTCOME_REASONS)) &&
    isOptional(value.settledBy, oneOf(SETTLED_BY)) &&
    isOptional(value.nextCheckAt, isText) &&
    isOptional(value.settlementOffered, isBoolean)
  );
}

function validDuplicate(value: unknown): boolean {
  return (
    isRecord(value) && isText(value.remoteReference) && isOptional(value.remoteUrl, isSafeLink)
  );
}

function validHistoryEffect(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(value, 'effectId', 'revision') &&
    oneOf(EFFECT_STATES)(value.state) &&
    Array.isArray(value.possibleDuplicates) &&
    value.possibleDuplicates.every(validDuplicate) &&
    isBoolean(value.settlementOffered) &&
    isOptional(value.remoteUrl, isSafeLink) &&
    isOptional(value.outcomeReason, oneOf(OUTCOME_REASONS)) &&
    isOptional(value.settledBy, oneOf(SETTLED_BY)) &&
    isOptional(value.nextCheckAt, isText)
  );
}

function validHistoryEntry(value: unknown): boolean {
  return (
    isRecord(value) &&
    hasText(
      value,
      'approvalId',
      'previewId',
      'previewRevision',
      'bindingHash',
      'approvedAt',
      'sourceTitle',
      'destinationTitle',
    ) &&
    oneOf(APPROVAL_STATES)(value.state) &&
    isBoolean(value.continuable) &&
    isOptional(value.invalidationReason, oneOf(INVALIDATION_REASONS)) &&
    isOptional(value.endedAt, isText) &&
    isOptional(value.effect, validHistoryEffect)
  );
}

function validHistoryPage(value: unknown): boolean {
  return (
    isRecord(value) &&
    Array.isArray(value.entries) &&
    value.entries.length <= HISTORY_PAGE_SIZE &&
    value.entries.every(validHistoryEntry) &&
    (value.nextCursor === null || isText(value.nextCursor))
  );
}

const RESPONSE_CHECKS: Record<ExportOperation, (value: unknown) => boolean> = {
  'configure-notion-connection': validConnection,
  'read-notion-connection': validConnection,
  'disconnect-notion': validConnection,
  'list-export-destinations': validDestinations,
  'prepare-export-preview': validPreview,
  'approve-export-preview': validApproval,
  'execute-approved-export': validEffect,
  'read-export-effect': validEffect,
  'cancel-export-approval': validApproval,
  'list-export-history': validHistoryPage,
  'settle-export-effect': validEffect,
};

/** The refusal for a response that does not match its declared shape. */
export function invalidContent(operation: string): ApiError {
  return new ApiError(502, {
    code: 'INVALID_CONTENT',
    requestId: `export-${operation}`,
    retryable: false,
    messageKey: 'export.invalid-response',
  });
}

/** Check one C09 response against its operation's shape before any screen uses it. */
export function checkedResponse<K extends ExportOperation>(
  operation: K,
  value: unknown,
): Operations[K][1] {
  if (!RESPONSE_CHECKS[operation](value)) throw invalidContent(operation);
  return value as Operations[K][1];
}

/** One C09 operation over the shared Transport (session cookie, Origin, CSRF and key). */
export async function exportCall<K extends ExportOperation>(
  client: Transport,
  operation: K,
  body: Operations[K][0],
  key?: string,
): Promise<Operations[K][1]> {
  const value = await client.post<unknown>(`/api/v2/c09/${operation}`, body, key);
  return checkedResponse(operation, value);
}

/** The SWR key of the owner's connection, bound to the Transport's authority generation
so a response for one owner can never be shown to the next. */
export const connectionKey = (client: Transport) =>
  ['u6-export-connection', client, client.generation] as const;

/** The owner's connection, or null when none is visible (absent or still being checked). */
export async function readConnection(client: Transport): Promise<Connection | null> {
  try {
    return await exportCall(client, 'read-notion-connection', {});
  } catch (failure) {
    if (failure instanceof ApiError && failure.envelope.code === 'NOT_FOUND') return null;
    throw failure;
  }
}

/** The shell's export capability, when the catalog offers it at all. */
export function findExportCapability(
  catalog: W.WorkspaceCapabilityCatalog | null | undefined,
): Capability | undefined {
  return catalog?.capabilities.find(
    (item) => item.id === EXPORT_CAPABILITY_ID && ['available', 'degraded'].includes(item.state),
  );
}

/** The request form of a listed destination: frozen identity fields only. The server
derives the title, context and permissions itself and ignores any it is sent (A1). */
export function destinationRequest(entry: DestinationEntry): DestinationRequest {
  return {
    connectionId: entry.connectionId,
    workspaceId: entry.workspaceId,
    parentPageId: entry.parentPageId,
    formatRevision: entry.formatRevision,
    destinationId: entry.destinationId,
  };
}

export type ListingState = 'complete' | 'partial' | 'unavailable' | 'empty';

/** Decision S2: completeness and entries together give the listing's state. */
export function listingState(listing: Destinations): ListingState {
  const complete = listing.listingComplete !== false;
  const hasEntries = listing.destinations.length > 0;
  if (complete) return hasEntries ? 'complete' : 'empty';
  return hasEntries ? 'partial' : 'unavailable';
}

export type UnusableReason = 'not-allowed' | 'unreadable' | 'creation-refused';

/** Why a listed page cannot be chosen, or null when it can (BR1.5, BR8.2). */
export function unusableReason(
  entry: DestinationEntry,
  connection: Connection,
): UnusableReason | null {
  const scope = connection.destinationScopeIds;
  if (scope.length > 0 && !scope.includes(entry.destinationId)) return 'not-allowed';
  if (entry.readable === false) return 'unreadable';
  if (entry.creationCapability === 'refused' || entry.writable === false) return 'creation-refused';
  return null;
}

/** The preselected destination: the last one used, only while listed and readable. */
export function preselection(
  listing: Destinations,
  connection: Connection,
): { entry: DestinationEntry | null; dropped: boolean } {
  const last = listing.lastDestinationId;
  if (!last) return { entry: null, dropped: false };
  const entry = listing.destinations.find((item) => item.destinationId === last);
  if (entry && entry.readable === true && unusableReason(entry, connection) === null)
    return { entry, dropped: false };
  return { entry: null, dropped: true };
}

export const effectEnded = (state: EffectState): boolean => ENDED_EFFECT_STATES.includes(state);

/** BR1.2's minimal shape check, mirrored from the trusted side; never echoes the value. */
export type TokenProblem = 'blank' | 'unprintable' | 'too-long';
export function tokenProblem(value: string): TokenProblem | null {
  const token = value.trim();
  if (!token) return 'blank';
  if (token.length > TOKEN_MAX_LENGTH) return 'too-long';
  // Printable means no control characters anywhere in the value.
  if (/\p{Cc}/u.test(token)) return 'unprintable';
  return null;
}

const NOTION_HOSTS = ['notion.so', 'www.notion.so'];
/** BR4.7: an owner-supplied link is accepted only as a Notion page link. */
export function isNotionPageLink(value: string): boolean {
  if (!value || value.length > 2048) return false;
  let parts: URL;
  try {
    parts = new URL(value);
  } catch {
    return false;
  }
  const host = parts.hostname.toLowerCase();
  const segment = parts.pathname.replace(/\/+$/, '').split('/').pop() ?? '';
  return (
    parts.protocol === 'https:' &&
    !parts.username &&
    !parts.password &&
    (parts.port === '' || parts.port === '443') &&
    (NOTION_HOSTS.includes(host) || host.endsWith('.notion.site')) &&
    /(?:^|-)[0-9a-f]{32}$/.test(segment)
  );
}
