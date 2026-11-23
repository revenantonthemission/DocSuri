/**
 * C11 for the 운영 view (A5; BR3.8, BR4.1, BR4.9): the dashboard, the incident list,
 * recovery requests and their status, through the shared transport.
 */
import type { PolicyRef, Transport } from '../api';

export type Freshness = 'current' | 'stale';
export type DashboardItem = {
  observationId: string;
  capability: string;
  component: string;
  observedAt: string;
  revision: string;
  status: 'available' | 'degraded' | 'unavailable' | 'unknown';
  evidenceRef: string;
  limitations: string[];
  freshness?: Freshness | null;
  ageSeconds?: number | null;
};
export type DashboardPage = {
  items: DashboardItem[];
  page: { nextCursor: string | null; snapshotRevision: string };
};
export type Incident = {
  incidentId: string;
  revision: string;
  capabilities: string[];
  correlationIds: string[];
  state: 'open' | 'investigating' | 'recovering' | 'resolved';
  evidenceRefs: string[];
  resolutionKind?: string | null;
};
export type IncidentPage = { items: Incident[]; page: { nextCursor: string | null } };
export type RecoveryOperation = 'backup.create' | 'restore.verify' | 'restore.production';
export type RecoveryState =
  | 'requested'
  | 'awaiting-operator'
  | 'running'
  | 'verifying'
  | 'post-restore-pending'
  | 'held'
  | 'succeeded'
  | 'failed'
  | 'unknown'
  | 'cancelled'
  | 'refused'
  | 'expired';
export type Receipt = { jobId: string; revision: string; state: string };

export const DASHBOARD_REFRESH_MS = 30_000;
// Aggregate items the dashboard adds beside the capabilities (C11 items, `capability`).
export const AGGREGATES = new Set([
  'operations.backup-set',
  'operations.backup-revision',
  'operations.restore-verification',
  'operations.recovery-request',
  'operations.email-allowance',
  'operations.latency',
  'operations.availability',
  'operations.standing-job',
  'operations.lane',
  'operations.isolation-result',
]);

const SEOUL_OFFSET_HOURS = 9;
/** Every time on 운영, in Seoul and the same on every machine (L1-52). */
export const OPERATIONS_TIME = new Intl.DateTimeFormat('ko-KR', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'Asia/Seoul',
});

/** A time as '2026. 11. 1. 오전 10:00', or '알 수 없음' when missing or unparsable. The day
 * period is written from Seoul's hour, because newer ICU data spells it 'AM'/'PM' for ko-KR
 * (as api.ts's seoulMoment does). */
export function operationsTime(iso: string | null | undefined): string {
  if (!iso) return '알 수 없음';
  const moment = new Date(iso);
  if (Number.isNaN(moment.getTime())) return '알 수 없음';
  const hour = (moment.getUTCHours() + SEOUL_OFFSET_HOURS) % 24;
  return OPERATIONS_TIME.formatToParts(moment)
    .map((part) => (part.type === 'dayPeriod' ? (hour < 12 ? '오전' : '오후') : part.value))
    .join('');
}

export const STATUS_COPY: Readonly<Record<string, string>> = {
  available: '정상',
  degraded: '제한',
  unavailable: '중단',
  unknown: '알 수 없음',
  stale: '오래됨',
};
export const LIMITATION_COPY: Readonly<Record<string, string>> = {
  'runtime-isolation-lapsed': '런타임 격리 확인 실패',
  'model-evidence-mismatch': '모델 검증값 불일치',
  'isolation-programs': '프로그램',
  'isolation-files': '설정 파일',
  'isolation-accounts': '계정',
  'isolation-database': '데이터베이스',
  'isolation-filter': '패킷 필터',
  'isolation-volume': '백업 볼륨',
  'isolation-backups': '백업 제외 설정',
  'isolation-boot': '부팅 시작',
  'observation-stale': '확인이 오래되었습니다',
  'no-observation': '아직 확인하지 않았습니다',
  // The registry's reasons (u8_registry.py).
  'semantic-search-unavailable': '의미 검색을 사용할 수 없음',
  'model-runtime-waiting': '모델 실행 대기 중',
  'digest-delivery-late': '요약 메일 발송 지연',
  'maintainer-address-pending': '관리자 주소 확인 대기',
  'export-effect-late': '내보내기 처리 지연',
  'ledger-damaged': '운영 기록 손상',
  'capacity-approaching': '저장 공간 한도에 가까움',
  'internal-disk-low': '내부 디스크 여유 공간 부족',
  'internal-disk-critical': '내부 디스크 여유 공간 위험',
  'capacity-exhausted': '저장 공간 한도 도달',
  'last-backup-held': '마지막 백업 보류',
  'backup-volume-unavailable': '백업 볼륨을 찾을 수 없음',
  'backup-volume-low': '백업 볼륨 여유 공간 부족',
  'backup-volume-shared-cleanup': '다른 도구의 정리 표시가 있음',
  'backup-catalogue-damaged': '백업 목록 손상',
  'backup-volume-mismatch': '다른 백업 볼륨이 연결됨',
  'lane-behind-deadline': '작업 처리 지연',
  'assistance-readiness-pending': '요약·번역 준비 확인 대기',
  'model-runtime-unavailable': '모델 실행 환경을 사용할 수 없음',
  'cutover-effect-unknown': '전환 작업 결과를 알 수 없음',
  'cutover-route-differs': '전환 경로가 기록과 다름',
  'sign-in-unverified': '실제 로그인 확인 전',
  'provider-unreachable': '외부 서비스에 연결할 수 없음',
  'first-effect-pending': '첫 외부 작업 승인 대기',
  'allowance-exhausted': '이메일 발송 한도 도달',
  'runtime-unreachable': '모델 실행 환경에 연결할 수 없음',
  // The observation store's reasons (observations.py).
  'producer-failed': '상태 확인 실패',
  'store-unavailable': '상태 기록 저장소를 사용할 수 없음',
  'store-denied': '상태 기록 저장이 거부됨',
  'store-busy': '상태 기록 저장소가 바쁨',
  'evidence-unavailable': '상태 기록을 읽을 수 없음',
  'pre-switch-recipient-bound': '전환 전 수신자만 허용',
  // The readiness and contribution reasons (readiness.py; u8_host.py).
  unconfigured: '설정되지 않음',
  'dependency-unavailable': '필요한 구성 요소를 사용할 수 없음',
  missing: '구성 요소 없음',
  incompatible: '구성 요소 버전 불일치',
  'policy-unresolved': '정책을 확인할 수 없음',
  // The backup agent's findings that platform.status takes.
  'backup-volume-ownership': '백업 볼륨 소유권 확인 실패',
  'backup-volume-unencrypted': '백업 볼륨이 암호화되지 않음',
  'backup-volume-unwritable': '백업 볼륨에 쓸 수 없음',
  'backup-volume-unreadable': '백업 볼륨을 읽을 수 없음',
  'backup-agent-unreachable': '백업 에이전트에 연결할 수 없음',
  // The scheduler's, the standing job's, the isolation result's and the lanes' keys.
  'scheduler-pass-unrecorded': '스케줄러 실행 기록 없음',
  'standing-job-unrecorded': '실행 기록이 아직 없습니다',
  'standing-job-late': '상시 작업 지연',
  'availability-record-unreadable': '가용성 기록을 읽을 수 없음',
  'isolation-result-unreadable': '격리 확인 결과를 읽을 수 없음',
  'lane-count-unavailable': '작업 수를 읽을 수 없음',
};
export const RECOVERY_STATE_COPY: Readonly<Record<RecoveryState, string>> = {
  requested: '요청됨',
  'awaiting-operator': '운영자 대기',
  running: '실행 중',
  verifying: '검증 중',
  'post-restore-pending': '복원 후 백업 대기',
  held: '복원 보류',
  succeeded: '완료',
  failed: '실패',
  unknown: '확인 중',
  cancelled: '취소됨',
  refused: '거절됨',
  expired: '만료됨',
};
export const OPERATION_COPY: Readonly<Record<RecoveryOperation, string>> = {
  'backup.create': '백업 만들기',
  'restore.verify': '복원 검증',
  'restore.production': '운영 데이터 복원 요청',
};

export function readDashboard(client: Transport): Promise<DashboardPage> {
  return client.read<DashboardPage>('/api/v2/c11/read-dashboard', { page: { limit: 200 } });
}

export function listIncidents(client: Transport): Promise<IncidentPage> {
  return client.read<IncidentPage>('/api/v2/c11/list-incidents', { page: { limit: 50 } });
}

/** A limitation's value after its `prefix:`, as the dashboard writes it. */
export function valueOf(item: Pick<DashboardItem, 'limitations'>, prefix: string): string | null {
  const found = item.limitations.find((entry) => entry.startsWith(`${prefix}:`));
  return found === undefined ? null : found.slice(prefix.length + 1);
}

/** An incident's prefixed evidence reference (`opened:`, `role:`, `diagnosis:`, …). */
export function evidenceOf(incident: Incident, prefix: string): string[] {
  return incident.evidenceRefs
    .filter((entry) => entry.startsWith(`${prefix}:`))
    .map((entry) => entry.slice(prefix.length + 1));
}

export type Submission = {
  operation: RecoveryOperation;
  targetId: string;
  expectedRevision: string;
  origin: 'administrator';
  submissionId: string;
  policy: PolicyRef;
  incidentId?: string;
};

function hex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

/** A SHA-256 digest's first 128 bits as a UUID (version 8, RFC 9562's custom form): the
 * `Idempotency-Key` header every body-carrying route reads as a UUID (`local_browser`). */
export function digestUuid(digestHex: string): string {
  const bits = digestHex.slice(0, 32).split('');
  bits[12] = '8';
  bits[16] = ((parseInt(bits[16]!, 16) & 0x3) | 0x8).toString(16);
  const value = bits.join('');
  return [
    value.slice(0, 8),
    value.slice(8, 12),
    value.slice(12, 16),
    value.slice(16, 20),
    value.slice(20, 32),
  ].join('-');
}

/** BR4.9's idempotency key: SHA-256 (the browser's crypto API) of the origin (관리자),
 * the account, the operation, the target, the expected revision and the submission, sent
 * in the UUID form the boundary accepts (the browser journeys found the bare digest
 * refused with 400). */
export async function idempotencyKey(account: string, submission: Submission): Promise<string> {
  const facts = [
    '관리자',
    account,
    submission.operation,
    submission.targetId,
    submission.expectedRevision,
    submission.submissionId,
  ];
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(facts.join('\n')));
  return digestUuid(hex(digest));
}

export async function requestRecovery(
  client: Transport,
  account: string,
  submission: Submission,
): Promise<Receipt> {
  return client.post<Receipt>(
    '/api/v2/c11/request-recovery',
    submission,
    await idempotencyKey(account, submission),
  );
}

const RELATIVE = new Intl.RelativeTimeFormat('ko', { numeric: 'auto' });

/** An age as people read it: "3분 전". */
export function ageText(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '확인한 적 없음';
  if (seconds < 60) return RELATIVE.format(-Math.max(0, Math.round(seconds)), 'second');
  if (seconds < 3600) return RELATIVE.format(-Math.round(seconds / 60), 'minute');
  if (seconds < 86_400) return RELATIVE.format(-Math.round(seconds / 3600), 'hour');
  return RELATIVE.format(-Math.round(seconds / 86_400), 'day');
}
