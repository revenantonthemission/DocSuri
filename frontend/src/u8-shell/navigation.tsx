/**
 * WorkspaceNavigation (frontend-components.md; A1, BR5.1–BR5.5, BR5.8).
 *
 * The complete assembly's navigation answer carries placements: the component renders
 * exactly the entries the server resolved, by BR5.2's table. An answer without
 * placements comes from an earlier assembly, which keeps its built navigation unchanged
 * (`LegacyNavigation`): its owner-bound filter and its search-only fallback stay theirs.
 */
import React, { useEffect, useId, useRef, useState } from 'react';
import styles from './shell.module.css';
import { cx } from './classes';
import {
  hidden,
  needsSignIn,
  reasonText,
  resolvedByRegistry,
  routeLabel,
  type NavItem,
} from './reasons';

export type NavigationStatus = 'loading' | 'resolved' | 'error';

type Props = {
  items: readonly NavItem[];
  status: NavigationStatus;
  current: string;
  signedIn: boolean;
  catalogReady: boolean;
  /** Whether this is the complete assembly (its capability list is the registry's). */
  complete: boolean;
  onSelect: (routeId: string) => void;
  onRequireSignIn: () => void;
  onRetry: () => void;
};

// The navigation earlier assemblies render (U1–U6), unchanged.
const LEGACY_COPY: Readonly<Record<string, string>> = {
  search: '검색',
  paper: '논문',
  library: '내 서재',
  settings: '설정',
  usage: '사용량',
  jobs: '작업',
  account: '계정',
  research: '연구',
  novelty: '참신성 분석',
  topics: '주제 구독',
  export: '내보내기',
};
const LEGACY_OWNER_BOUND = new Set([
  'library',
  'settings',
  'usage',
  'jobs',
  'account',
  'research',
  'novelty',
  'topics',
  'export',
]);
// With no confirmed entry, only these may be listed, and never enabled (BR5.1).
const PUBLIC_ROUTES = ['search'];

export function WorkspaceNavigation(props: Props) {
  if (!props.complete && !resolvedByRegistry(props.items)) return <LegacyNavigation {...props} />;
  return <ResolvedNavigation {...props} />;
}

function LegacyNavigation({ items, current, signedIn, catalogReady, onSelect }: Props) {
  const shown = items.length
    ? items
    : Object.keys(LEGACY_COPY).map((routeId) => ({
        routeId,
        titleKey: routeId,
        capabilityId: '',
        available: routeId === 'search',
      }));
  return (
    <nav aria-label="주요 이동" data-testid="navigation">
      {shown
        .filter(
          (item) =>
            !LEGACY_OWNER_BOUND.has(item.routeId) || (signedIn && catalogReady && items.length > 0),
        )
        .map((item) => (
          <button
            key={item.routeId}
            type="button"
            className={current === item.routeId ? 'nav active' : 'nav'}
            aria-current={current === item.routeId ? 'page' : undefined}
            aria-disabled={!item.available}
            disabled={!item.available}
            onClick={() => onSelect(item.routeId)}
            data-testid={`nav-${item.routeId}`}
          >
            {LEGACY_COPY[item.routeId] ?? item.titleKey}
          </button>
        ))}
    </nav>
  );
}

function Entry({
  item,
  current,
  onSelect,
  onRequireSignIn,
}: {
  item: NavItem;
  current: string;
  onSelect: (routeId: string) => void;
  onRequireSignIn: () => void;
}) {
  const reasonId = useId();
  const prompt = needsSignIn(item);
  const enabled = item.available || prompt;
  const reason = reasonText(item.reasonKey);
  return (
    <li className={styles.entry}>
      <button
        type="button"
        className={cx('nav', styles.button, current === item.routeId && 'active')}
        aria-current={current === item.routeId ? 'page' : undefined}
        aria-disabled={enabled ? undefined : true}
        aria-describedby={reason ? reasonId : undefined}
        onClick={() => {
          if (prompt) onRequireSignIn();
          else if (item.available) onSelect(item.routeId);
        }}
        data-testid={`nav-${item.routeId}`}
      >
        {routeLabel(item)}
      </button>
      {reason ? (
        <span id={reasonId} className={styles.reason} data-testid={`nav-reason-${item.routeId}`}>
          {reason}
        </span>
      ) : null}
    </li>
  );
}

function ResolvedNavigation({ items, status, current, onSelect, onRequireSignIn, onRetry }: Props) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const loadingLine = useRef<HTMLParagraphElement | null>(null);
  // Where a retry's press left focus, so it never falls to the page body as the retry
  // control unmounts (Step 91(g)).
  const retried = useRef<'toggle' | 'loading' | null>(null);
  const listId = useId();
  useEffect(() => {
    const landing = retried.current;
    if (landing === null) return;
    const active = document.activeElement;
    const held =
      landing === 'toggle'
        ? active === trigger.current
        : active === loadingLine.current || active === null || active === document.body;
    if (status === 'loading') {
      if (landing === 'loading') loadingLine.current?.focus();
      return;
    }
    retried.current = null;
    if (!held) return;
    if (status === 'error') {
      document.querySelector<HTMLElement>('[data-testid="nav-retry"]')?.focus();
    } else if (landing === 'loading') {
      document.getElementById(listId)?.querySelector<HTMLElement>('button')?.focus();
    }
  }, [status, listId]);
  const retry = () => {
    const toggle = trigger.current;
    if (toggle && window.getComputedStyle(toggle).display !== 'none') {
      toggle.focus();
      retried.current = 'toggle';
    } else {
      retried.current = 'loading';
    }
    onRetry();
  };
  useEffect(() => {
    if (!open) return;
    const close = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      trigger.current?.focus();
    };
    document.addEventListener('keydown', close);
    return () => document.removeEventListener('keydown', close);
  }, [open]);
  const primary = items.filter(
    (item) => (item.placement ?? 'primary') === 'primary' && !hidden(item),
  );
  const shown: NavItem[] =
    status === 'error'
      ? PUBLIC_ROUTES.map(
          (routeId) =>
            primary.find((item) => item.routeId === routeId) ?? {
              routeId,
              titleKey: routeId,
              capabilityId: '',
              available: false,
            },
        )
      : primary;
  const select = (routeId: string) => {
    setOpen(false);
    onSelect(routeId);
  };
  // At 320 px the open menu fills the sticky header; once focus moves on into the page
  // the menu closes, so the header returns to its height and covers no focused control.
  const closeWhenFocusLeaves = (event: React.FocusEvent<HTMLElement>) => {
    const next = event.relatedTarget;
    if (!open || !(next instanceof Node)) return;
    if (event.currentTarget.contains(next)) return;
    setOpen(false);
  };
  return (
    <nav
      aria-label="주요 이동"
      data-testid="navigation"
      className={styles.navigation}
      aria-busy={status === 'loading' ? true : undefined}
      onBlur={closeWhenFocusLeaves}
    >
      <button
        ref={trigger}
        type="button"
        className={styles.toggle}
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((value) => !value)}
        data-testid="nav-menu-toggle"
      >
        메뉴
      </button>
      {status === 'loading' ? (
        <p role="status" tabIndex={-1} ref={loadingLine} data-testid="nav-loading">
          메뉴를 불러오고 있습니다
        </p>
      ) : (
        <ul id={listId} className={cx(styles.list, !open && styles.collapsed)}>
          {shown.map((item) => (
            <Entry
              key={item.routeId}
              item={item}
              current={current}
              onSelect={select}
              onRequireSignIn={() => {
                setOpen(false);
                onRequireSignIn();
              }}
            />
          ))}
        </ul>
      )}
      {status === 'error' ? (
        <div className={styles.error} role="alert" data-testid="nav-error">
          <p>다른 메뉴를 확인하지 못했습니다</p>
          <button type="button" onClick={retry} data-testid="nav-retry">
            다시 시도
          </button>
        </div>
      ) : null}
    </nav>
  );
}
