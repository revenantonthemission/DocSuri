/**
 * The owner's job list (A2) and a job's snapshot, through the shared transport.
 */
import type { Transport } from '../api';

export type JobKind = 'research' | 'novelty';
export type JobState =
  | 'accepted'
  | 'running'
  | 'cancel_requested'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'unknown';

export type JobListItem = {
  jobId: string;
  kind: JobKind;
  label: string;
  state: JobState;
  createdAt: string;
  updatedAt: string;
  resultAvailable: boolean;
};
export type JobListPage = { items: JobListItem[]; nextCursor: string | null };
export type JobSnapshot = {
  jobId: string;
  kind: string;
  state: JobState;
  seq: number;
  revision: string;
  acceptedAt: string;
};

export const LIST_PATH = '/api/v2/c07/list-research-jobs';
export const PAGE_SIZE = 20;
export const LIST_REFRESH_MS = 5_000;
export const POLL_MS = 2_000;

export const STATE_COPY: Readonly<Record<JobState, string>> = {
  accepted: '대기 중',
  running: '진행 중',
  cancel_requested: '진행 중',
  succeeded: '완료',
  failed: '실패',
  cancelled: '취소됨',
  unknown: '확인 중',
};
export const KIND_COPY: Readonly<Record<JobKind, string>> = {
  research: '연구',
  novelty: '참신성 분석',
};

const FINISHED: ReadonlySet<JobState> = new Set(['succeeded', 'failed', 'cancelled']);

export function finished(state: JobState): boolean {
  return FINISHED.has(state);
}

export function listJobs(
  client: Transport,
  kind: JobKind | null,
  cursor: string | null,
): Promise<JobListPage> {
  return client.read<JobListPage>(LIST_PATH, {
    limit: PAGE_SIZE,
    ...(kind ? { kind } : {}),
    ...(cursor ? { cursor } : {}),
  });
}

export function readJob(client: Transport, jobId: string): Promise<JobSnapshot> {
  return client.get<JobSnapshot>(`/api/v2/jobs/${encodeURIComponent(jobId)}`);
}

const UPDATED = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short' });

export function updatedText(iso: string): string {
  const moment = new Date(iso);
  return Number.isNaN(moment.getTime()) ? '' : UPDATED.format(moment);
}
