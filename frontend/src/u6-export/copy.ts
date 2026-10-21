/** Korean copy for the approved Notion export.

Every state and reason a screen shows is keyed by a fixed wire value, never by
server text. Each status pairs its words with an icon so meaning never rests on
color alone (WCAG 1.4.1). Result and page titles keep their original language. */

import type {
  ApprovalState,
  ConnectionState,
  CreationCapability,
  EffectState,
  InvalidationReason,
  OutcomeReason,
  TokenProblem,
  UnusableReason,
} from './api';

export type StatusCopy = { icon: string; text: string };

/** "Not connected" covers both an absent record and one still being checked. */
export const NOT_CONNECTED: StatusCopy = { icon: '○', text: '연결되지 않음' };

export const CONNECTION_STATE_COPY: Record<ConnectionState, StatusCopy> = {
  connected: { icon: '✓', text: '연결됨' },
  disconnected: { icon: '○', text: '연결 해제됨' },
  revoked: { icon: '⚠', text: 'Notion에서 연결이 해제되었습니다. 다시 연결하세요' },
  unavailable: { icon: '⚠', text: '보호된 토큰을 지금 열 수 없습니다' },
};

export const EFFECT_STATE_COPY: Record<EffectState, StatusCopy> = {
  accepted: { icon: '…', text: '내보내는 중' },
  executing: { icon: '…', text: '내보내는 중' },
  succeeded: { icon: '✓', text: '내보냈습니다' },
  failed: { icon: '✕', text: '실패했습니다' },
  unknown: { icon: '?', text: '확인 중' },
  cancelled: { icon: '⊘', text: '취소했습니다' },
  invalidated: { icon: '⚠', text: '변경되어 내보내지 않았습니다' },
};

/** History rows for an approval that has no bound effect. */
export const APPROVAL_STATE_COPY: Record<ApprovalState, StatusCopy> = {
  approved: { icon: '◔', text: '승인됨 · 아직 시작 전' },
  consumed: { icon: '…', text: '내보내기 시작됨' },
  cancelled: { icon: '⊘', text: '취소했습니다' },
  invalidated: { icon: '⚠', text: '변경되어 승인이 무효가 되었습니다' },
  expired: { icon: '⊘', text: '승인이 만료되었습니다' },
};

/** Why an export ended, or that the owner settled it (the 18 reasons of entities.md). */
export const OUTCOME_REASON_COPY: Record<OutcomeReason, string> = {
  'token-invalid': 'Notion이 토큰을 거부했습니다',
  'no-access': '이 연결에 페이지를 만들 권한이 없습니다',
  'destination-missing': '대상 페이지를 찾을 수 없거나 공유되지 않았습니다',
  'content-rejected': 'Notion이 내용을 받아들이지 않았습니다',
  'workspace-block-limit': '무료 워크스페이스의 블록 한도에 도달했습니다',
  'provider-blocked': 'Notion이 요청을 막았습니다',
  'rate-limit-budget-spent': 'Notion 요청 한도로 재시도 기회를 모두 썼습니다',
  'not-found-after-checks': 'Notion에서 찾지 못했습니다',
  'owner-settled-delivered': '직접 확인해 내보낸 것으로 기록했습니다',
  'owner-settled-not-delivered': '직접 확인해 내보내지 않은 것으로 기록했습니다',
  'dependency-unavailable': '확인할 수 없는 상태가 너무 오래 이어졌습니다',
  'policy-unresolved': '내보내기 정책을 확인할 수 없습니다',
  'source-changed': '분석 결과가 바뀌었습니다',
  'destination-changed': '대상 페이지가 바뀌었거나 읽을 수 없습니다',
  'connection-changed': 'Notion 연결이 바뀌었습니다',
  'authority-revoked': '승인한 로그인 세션이 끝났습니다',
  'account-withdrawn': '계정 사용이 중지되었습니다',
  'owner-cancelled': '직접 취소했습니다',
};

/** Why an unconsumed approval was invalidated (the 5 reasons, A9). */
export const INVALIDATION_REASON_COPY: Record<InvalidationReason, string> = {
  'source-changed': '분석 결과가 바뀌었습니다',
  'destination-changed': '대상 페이지가 바뀌었거나 읽을 수 없습니다',
  'connection-changed': 'Notion 연결이 바뀌었습니다',
  'authority-revoked': '승인한 로그인 세션이 끝났습니다',
  'account-withdrawn': '계정 사용이 중지되었습니다',
};

/** Specific next steps for refusals at the first export (BR4.2). */
export const REFUSAL_HINTS: Partial<Record<OutcomeReason, string>> = {
  'destination-missing': '대상 페이지의 공유 메뉴에서 이 통합을 연결(공유)해 주세요.',
  'no-access': 'Notion 통합 설정에서 콘텐츠 삽입(Insert content) 권한을 켜 주세요.',
  'workspace-block-limit':
    '여러 명이 쓰는 무료 워크스페이스는 통합이 만들 수 있는 블록 수에 한도가 있습니다. 워크스페이스 요금제를 확인해 주세요.',
  'token-invalid': '연결 화면에서 새 토큰으로 다시 연결해 주세요.',
};

/** Limitation keys the connection and effect records may carry. */
export const LIMITATION_COPY: Record<string, string> = {
  'synthetic-only': '시험 환경입니다. 실제 Notion이 아니라 로컬 시험용 Notion에만 연결됩니다',
  'orphaned-attempt': '응답을 끝까지 확인하지 못한 시도가 있었습니다',
};

export const limitationText = (key: string): string =>
  LIMITATION_COPY[key] ?? '이 기능에 알려진 제한이 있습니다';

export const CREATION_CAPABILITY_COPY: Record<CreationCapability, string> = {
  unknown: '페이지 만들기 권한: 확인 전',
  confirmed: '페이지 만들기 권한: 확인됨',
  refused: '페이지 만들기 권한: 거부됨',
};

export const UNUSABLE_REASON_COPY: Record<UnusableReason, string> = {
  'not-allowed': '이 환경에서는 허용된 페이지가 아니어서 선택할 수 없습니다',
  unreadable: '이 연결로 페이지를 읽을 수 없습니다. 통합과 공유되어 있는지 확인하세요',
  'creation-refused': '이 연결에는 페이지를 만들 권한이 없습니다',
};

export const TOKEN_PROBLEM_COPY: Record<TokenProblem, string> = {
  blank: '토큰을 입력해 주세요',
  unprintable: '토큰에 쓸 수 없는 문자(줄바꿈이나 제어 문자)가 들어 있습니다',
  'too-long': '토큰이 너무 깁니다. 복사한 내용을 확인해 주세요',
};

/** D7: the help asks for read content and insert content only; everything else stays off. */
export const CONNECT_HELP = {
  intro: 'Notion에서 내부 통합(internal integration)을 만들고, 다음 권한만 켜 주세요.',
  requested: ['콘텐츠 읽기(Read content)', '콘텐츠 삽입(Insert content)'],
  rest: '그 밖의 권한은 모두 꺼 두고, 내보낼 페이지만 이 통합과 공유하세요. 토큰은 통합 설정의 비밀 키입니다.',
} as const;

/** Refusal copy for configure (Workflow 1). */
export const CONNECT_REFUSAL_COPY: Record<string, string> = {
  INVALID_TOKEN: '토큰을 확인할 수 없습니다',
  INVALID_ARGUMENT: '토큰 형식을 확인해 주세요',
  DEPENDENCY_UNAVAILABLE: 'Notion에 연결할 수 없습니다. 잠시 후 다시 시도하세요',
  POLICY_UNRESOLVED: '지금은 토큰을 안전하게 보관할 수 없어 연결할 수 없습니다',
  UNKNOWN_OUTCOME: '연결 결과를 확인하지 못했습니다. 연결 상태를 다시 확인하세요',
};

/** R-03: the two cases a configure CONFLICT can mean, told apart by re-reading. */
export const CONFLICT_STILL_CHECKING =
  '다른 창에서 연결을 확인하고 있습니다. 잠시 후 다시 시도하세요';
export const CONFLICT_CHANGED = '다른 곳에서 연결이 바뀌었습니다';
export const CONFLICT_UNAVAILABLE =
  '보호된 토큰을 열 수 없는 상태에서는 다시 연결할 수 없습니다. 먼저 연결을 해제하세요';

/** Preview refusals (Workflow 3 step 4). */
export const PREVIEW_REFUSAL_COPY: Record<string, string> = {
  NOT_FOUND: '결과를 찾을 수 없습니다',
  CONFLICT: '결과나 대상 페이지가 바뀌었습니다. 대상을 다시 고르거나 미리보기를 다시 만드세요',
  SOURCE_INELIGIBLE:
    '이 결과는 내보낼 수 없습니다 (내보낼 수 없는 결과이거나 한 페이지에 담기에 너무 큽니다)',
  FORBIDDEN: '이 환경에서는 이 페이지로 내보낼 수 없습니다',
  DEPENDENCY_UNAVAILABLE: '잠시 후 다시 시도하세요',
  POLICY_UNRESOLVED: '현재 내보내기 정책을 확인할 수 없어 미리보기를 만들 수 없습니다',
};

export const STALE_BINDING = '내용이 바뀌었습니다. 미리보기를 다시 확인하세요';
export const OUTCOME_UNKNOWN_PAIR =
  '같은 결과를 같은 페이지로 보낸 이전 내보내기가 아직 확인 중입니다. 확인이 끝난 뒤 다시 시도하세요';
export const IN_FLIGHT =
  '다른 내보내기가 진행 중입니다. 끝난 뒤 내보내기 기록에서 이어서 내보내세요';
export const PRESS_UNKNOWN =
  '요청 결과를 확인하지 못했습니다. 다시 누르면 같은 요청의 결과를 확인합니다';
export const SIGN_OUT_NOTE = '내보내기가 시작되기 전에 로그아웃하면 이 내보내기는 멈춥니다.';
export const OWNER_CONFIRMED = '직접 확인됨';
export const FRESH_PREVIEW_GUIDE =
  '참신성 분석 화면에서 이 결과를 열고 ‘Notion으로 내보내기’를 누르면 새 미리보기를 만들 수 있습니다';

/** The assumption each settlement choice records (BR4.5). */
export const SETTLE_ASSUMPTION_COPY = {
  delivered: '페이지가 Notion에 있다고 기록합니다. 이 내보내기는 성공으로 남습니다.',
  'not-delivered':
    '페이지가 없다고 기록합니다. 만약 페이지가 실제로 있다면, 다시 내보낼 때 두 번째 사본이 생깁니다.',
} as const;

const TIME_FORMAT = new Intl.DateTimeFormat('ko-KR', {
  dateStyle: 'medium',
  timeStyle: 'short',
});
const CLOCK_FORMAT = new Intl.DateTimeFormat('ko-KR', { timeStyle: 'short' });

/** A wire time for display; an unreadable one is shown as unknown rather than raw. */
export function formatTime(value: string | undefined | null): string {
  if (!value) return '알 수 없음';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '알 수 없음' : TIME_FORMAT.format(parsed);
}

/** When exporting is possible again, from the 20-per-hour refusal's wait in seconds. */
export function retryClock(retryAfterSeconds: number, now: Date = new Date()): string {
  return CLOCK_FORMAT.format(new Date(now.getTime() + retryAfterSeconds * 1000));
}

/** A page title for display: the server's untitled placeholder reads as a placeholder. */
export function displayTitle(title: string, untitled: string): string {
  return !title.trim() || title === untitled ? `(${untitled})` : title;
}
