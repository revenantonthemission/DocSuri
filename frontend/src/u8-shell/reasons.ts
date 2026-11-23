/**
 * The reason-key copy and destination labels of the complete workspace (A1, BR5.2,
 * frontend-components.md "WorkspaceNavigation").
 */

export type Placement = 'primary' | 'contextual' | 'footer';

/** One entry as `host-resolve-navigation` resolves it (C01 2.1.0). */
export type NavItem = {
  routeId: string;
  titleKey: string;
  path?: string;
  capabilityId: string;
  available: boolean;
  reasonKey?: string;
  placement?: Placement;
};

export const REASON_COPY: Readonly<Record<string, string>> = {
  'nav.authenticationRequired': '로그인 후 이용할 수 있습니다',
  'nav.capabilityPending': '준비 중입니다',
  'nav.capabilityDegraded': '일부 기능이 제한되어 있습니다',
  'nav.capabilityUnavailable': '일시적으로 사용할 수 없습니다',
  'nav.capabilityStale': '상태 정보가 오래되어 다시 확인하는 중입니다',
  'nav.capabilityUnknown': '상태를 확인할 수 없습니다',
};

export const ROUTE_LABELS: Readonly<Record<string, string>> = {
  search: '검색',
  library: '내 서재',
  research: '연구',
  novelty: '참신성 분석',
  jobs: '작업',
  topics: '주제 구독',
  export: '내보내기',
  settings: '설정',
  usage: '사용량',
  account: '계정',
  operations: '운영',
  paper: '논문',
  privacy: '개인정보 처리방침',
  terms: '이용약관',
};

/** The visible text of a reason key, or null when it has none. */
export function reasonText(key: string | undefined): string | null {
  if (!key) return null;
  return REASON_COPY[key] ?? REASON_COPY['nav.capabilityUnknown'] ?? null;
}

export function routeLabel(item: Pick<NavItem, 'routeId' | 'titleKey'>): string {
  return ROUTE_LABELS[item.routeId] ?? item.titleKey;
}

/** An entry the caller may activate even though it is not available: a sign-in prompt. */
export function needsSignIn(item: NavItem): boolean {
  return !item.available && item.reasonKey === 'nav.authenticationRequired';
}

/** BR5.2: an administrator-only entry for anyone else is not shown at all. */
export function hidden(item: NavItem): boolean {
  return item.reasonKey === 'nav.administratorOnly';
}

/** Whether a navigation answer is the registry's (A1): its items carry placements. */
export function resolvedByRegistry(items: readonly NavItem[]): boolean {
  return items.some((item) => item.placement !== undefined);
}
