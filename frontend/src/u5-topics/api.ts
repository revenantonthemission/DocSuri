/** U5 topics browser bindings; authority is always server-derived. */

import type { Transport } from '../api';

export const TOPICS_POLICY = { policyId: 'u5-synthetic-topics', revision: '1' } as const;

export type Cadence = 'daily' | 'weekly';
export type DeliveryDay = 'mon' | 'tue' | 'wed' | 'thu' | 'fri' | 'sat' | 'sun';
export type ContentWindow = 7 | 30;

export type DigestPreferences = {
  languageId: 'en' | 'ko';
  presentationLevelId: 'standard';
  timeZone: string | null;
  effectiveAt: string | null;
  sourceRevision: string | null;
  usesDefaults: boolean;
};

export type DigestSettings = {
  cadence: Cadence;
  deliveryTimeLocal: string | null;
  deliveryDay: DeliveryDay | null;
  contentWindowDays: ContentWindow;
  revision: number;
};

export type DigestItem = {
  versionId: string;
  paperId: string;
  title: string;
  publishedOn: string;
};

export type DigestRun = {
  preferenceSnapshot?: DigestPreferences;
  presentation?: {
    subject: string;
    text: string;
    html: string;
    languageId: string;
    presentationLevelId: string;
    emptyLabel: string;
  };
  runId: string;
  topicId: string;
  windowStart: string;
  windowEnd: string;
  state: string;
  settingsRevision: number;
  digestContent: DigestItem[];
  createdAt: string | null;
  outcome: {
    observedState: string;
    observedAt: string | null;
    reconciledState: string | null;
    reconciledAt: string | null;
    failureReason: string | null;
  } | null;
  sendLog: {
    pathKind: string;
    transportReceipt: string | null;
    acknowledgedAt: string | null;
  } | null;
};

export type LastRun = {
  runId: string | null;
  state: string | null;
  windowEnd: string | null;
  observedState: string | null;
};

export type Topic = {
  effectivePreferences?: DigestPreferences;
  topicId: string;
  topicKey: string;
  displayName: string;
  status: 'active' | 'unsubscribed';
  followedAt: string | null;
  settings: DigestSettings | null;
  lastRun?: LastRun;
  runs?: DigestRun[];
};

export type TopicList = { topics: Topic[] };
export type FollowResult = { topicId: string; status: string; reactivated: boolean };
export type UnsubscribeResult = {
  topicId: string;
  status: string;
  discardedRunIds: string[];
  unchanged: boolean;
};
export type SettingsSaveResult = {
  settings: DigestSettings;
  discardedRunIds: string[];
  unchanged: boolean;
};
export type ResolveResult = { runId: string; state: string; decision: string; assumption: string };

/** The resolve control names the assumption its choice makes (BR3.2). */
export const RESOLVE_ASSUMPTIONS = {
  delivered: '보낸 메일이 도착했다고 가정합니다',
  'not-delivered': '보낸 메일이 도착하지 않았다고 가정합니다',
} as const;
export type ResolveDecision = keyof typeof RESOLVE_ASSUMPTIONS;

export const DELIVERY_DAYS: { value: DeliveryDay; label: string }[] = [
  { value: 'mon', label: '월요일' },
  { value: 'tue', label: '화요일' },
  { value: 'wed', label: '수요일' },
  { value: 'thu', label: '목요일' },
  { value: 'fri', label: '금요일' },
  { value: 'sat', label: '토요일' },
  { value: 'sun', label: '일요일' },
];

export const CADENCE_LABELS: Record<Cadence, string> = {
  daily: '매일',
  weekly: '매주',
};

export async function listTopics(client: Transport): Promise<TopicList> {
  return client.get<TopicList>('/api/v2/topics');
}

export async function followTopic(
  client: Transport,
  topicKey: string,
  displayName: string,
): Promise<FollowResult> {
  return client.post<FollowResult>('/api/v2/topics', { topicKey, displayName });
}

export async function unsubscribeTopic(
  client: Transport,
  topicId: string,
): Promise<UnsubscribeResult> {
  return client.del<UnsubscribeResult>(`/api/v2/topics/${topicId}`);
}

export async function readTopic(client: Transport, topicId: string): Promise<Topic> {
  return client.get<Topic>(`/api/v2/topics/${topicId}/settings`);
}

export async function saveSettings(
  client: Transport,
  topicId: string,
  body: {
    revision: number;
    cadence: Cadence;
    deliveryTimeLocal: string;
    deliveryDay: DeliveryDay | null;
    contentWindowDays: ContentWindow;
  },
): Promise<SettingsSaveResult> {
  return client.put<SettingsSaveResult>(`/api/v2/topics/${topicId}/settings`, body);
}

export async function resolveRun(
  client: Transport,
  topicId: string,
  runId: string,
  decision: ResolveDecision,
): Promise<ResolveResult> {
  return client.post<ResolveResult>(`/api/v2/topics/${topicId}/runs/${runId}/resolve`, {
    decision,
    assumption: RESOLVE_ASSUMPTIONS[decision],
  });
}

export const isValidTime = (value: string): boolean => /^([01]\d|2[0-3]):[0-5]\d$/.test(value);

export const isUnresolvedUnknown = (topic: Topic): boolean =>
  topic.lastRun?.state === 'unknown' && topic.lastRun.observedState === 'unknown';
