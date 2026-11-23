// U8 plan Step 42, navigation (BR5.1–BR5.5, BR5.8): WorkspaceNavigation's states, its
// error fallback, the ARIA attributes, Escape, the owner boundary and route focus.
import React, { useEffect, useRef } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import useSWR, { SWRConfig, useSWRConfig } from 'swr';
import { unstable_serialize } from 'swr/infinite';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceNavigation, type NavigationStatus } from '../../src/u8-shell/navigation';
import {
  dropPrivateSession,
  PRIVATE_PREFIX,
  useOwnerBoundary,
} from '../../src/u8-shell/owner-boundary';
import {
  captureReturn,
  claimRouteFocus,
  restoreReturn,
  useRouteFocus,
  type FocusRequest,
} from '../../src/u8-shell/focus';
import {
  hidden,
  needsSignIn,
  reasonText,
  routeLabel,
  type NavItem,
} from '../../src/u8-shell/reasons';
import { cx } from '../../src/u8-shell/classes';

const RESOLVED: NavItem[] = [
  {
    routeId: 'search',
    titleKey: 'nav.search',
    capabilityId: 'discovery.search',
    available: true,
    placement: 'primary',
  },
  {
    routeId: 'library',
    titleKey: 'nav.library',
    capabilityId: 'library',
    available: false,
    reasonKey: 'nav.authenticationRequired',
    placement: 'primary',
  },
  {
    routeId: 'research',
    titleKey: 'nav.research',
    capabilityId: 'research',
    available: false,
    reasonKey: 'nav.capabilityPending',
    placement: 'primary',
  },
  {
    routeId: 'operations',
    titleKey: 'nav.operations',
    capabilityId: 'operations.ledger',
    available: false,
    reasonKey: 'nav.administratorOnly',
    placement: 'primary',
  },
  {
    routeId: 'privacy',
    titleKey: 'nav.privacy',
    capabilityId: 'public.static',
    available: true,
    placement: 'footer',
  },
];

function mount(status: NavigationStatus, items: NavItem[] = RESOLVED, complete = true) {
  const handlers = { onSelect: vi.fn(), onRequireSignIn: vi.fn(), onRetry: vi.fn() };
  render(
    <WorkspaceNavigation
      items={items}
      status={status}
      current="search"
      signedIn={false}
      catalogReady
      complete={complete}
      {...handlers}
    />,
  );
  return handlers;
}

afterEach(() => vi.restoreAllMocks());

describe('each state of the navigation', () => {
  it('shows a loading status while the answer is pending', () => {
    mount('loading');
    expect(screen.getByTestId('nav-loading')).toHaveTextContent('메뉴를 불러오고 있습니다');
    expect(screen.getByTestId('navigation')).toHaveAttribute('aria-busy', 'true');
    expect(screen.queryByTestId('nav-search')).toBeNull();
  });

  it('renders only the primary entries the server resolved, hiding administrator-only ones', () => {
    mount('resolved');
    expect(screen.getByTestId('nav-search')).toHaveTextContent('검색');
    expect(screen.getByTestId('nav-library')).toBeInTheDocument();
    expect(screen.getByTestId('nav-research')).toBeInTheDocument();
    expect(screen.queryByTestId('nav-operations')).toBeNull();
    expect(screen.queryByTestId('nav-privacy')).toBeNull();
  });

  it('selects an available entry and asks a signed-out person to sign in for a member entry', () => {
    const handlers = mount('resolved');
    fireEvent.click(screen.getByTestId('nav-search'));
    expect(handlers.onSelect).toHaveBeenCalledWith('search');
    fireEvent.click(screen.getByTestId('nav-library'));
    expect(handlers.onRequireSignIn).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByTestId('nav-research'));
    expect(handlers.onSelect).toHaveBeenCalledTimes(1);
  });
});

describe('the error state', () => {
  it('shows only the public entries, disabled, with a retry', () => {
    const handlers = mount('error', []);
    const search = screen.getByTestId('nav-search');
    expect(search).toHaveAttribute('aria-disabled', 'true');
    fireEvent.click(search);
    expect(handlers.onSelect).not.toHaveBeenCalled();
    expect(screen.queryByTestId('nav-library')).toBeNull();
    expect(screen.getByTestId('nav-error')).toHaveTextContent('다른 메뉴를 확인하지 못했습니다');
    fireEvent.click(screen.getByTestId('nav-retry'));
    expect(handlers.onRetry).toHaveBeenCalledTimes(1);
  });

  it('never enables an entry the server did not confirm, even one it listed before', () => {
    mount('error', RESOLVED);
    expect(screen.getAllByRole('button', { name: /검색|내 서재|연구/ })).toHaveLength(1);
    expect(screen.getByTestId('nav-search')).not.toHaveAttribute('aria-disabled');
  });
});

describe('the ARIA attributes', () => {
  it('names the navigation, marks the current entry and describes disabled ones', () => {
    mount('resolved');
    expect(screen.getByRole('navigation', { name: '주요 이동' })).toBeInTheDocument();
    expect(screen.getByTestId('nav-search')).toHaveAttribute('aria-current', 'page');
    const research = screen.getByTestId('nav-research');
    expect(research).toHaveAttribute('aria-disabled', 'true');
    const reason = document.getElementById(research.getAttribute('aria-describedby') ?? '');
    expect(reason).toHaveTextContent('준비 중입니다');
    expect(screen.getByTestId('nav-library')).not.toHaveAttribute('aria-disabled');
  });
});

describe('the disclosure menu', () => {
  it('closes on Escape and returns focus to its trigger', () => {
    const handlers = mount('resolved');
    const trigger = screen.getByTestId('nav-menu-toggle');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    screen.getByTestId('nav-search').focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveFocus();
    fireEvent.click(trigger);
    fireEvent.click(screen.getByTestId('nav-library'));
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(handlers.onRequireSignIn).toHaveBeenCalled();
  });
});

// Your answer of 2026-11-13, "Close it when focus leaves": at 320 px the open menu fills
// the sticky header, so it closes once keyboard focus moves on into the page.
function mountInPage() {
  const handlers = { onSelect: vi.fn(), onRequireSignIn: vi.fn(), onRetry: vi.fn() };
  render(
    <>
      <header>
        <WorkspaceNavigation
          items={RESOLVED}
          status="resolved"
          current="search"
          signedIn={false}
          catalogReady
          complete
          {...handlers}
        />
      </header>
      <main id="main">
        <button type="button">페이지의 첫 컨트롤</button>
      </main>
    </>,
  );
  return handlers;
}

describe('the disclosure menu when focus leaves it', () => {
  it('closes when Tab moves focus out of the menu into the page', async () => {
    const user = userEvent.setup();
    mountInPage();
    const trigger = screen.getByTestId('nav-menu-toggle');
    await user.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    screen.getByTestId('nav-research').focus();
    await user.tab();
    expect(screen.getByRole('button', { name: '페이지의 첫 컨트롤' })).toHaveFocus();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('stays open while focus moves within the menu, by Tab and Shift+Tab', async () => {
    const user = userEvent.setup();
    mountInPage();
    const trigger = screen.getByTestId('nav-menu-toggle');
    await user.click(trigger);
    await user.tab();
    expect(screen.getByTestId('nav-search')).toHaveFocus();
    await user.tab();
    expect(screen.getByTestId('nav-library')).toHaveFocus();
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await user.tab({ shift: true });
    await user.tab({ shift: true });
    expect(trigger).toHaveFocus();
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('stays open when focus leaves for no element, and Escape still closes it onto the toggle', async () => {
    const user = userEvent.setup();
    mountInPage();
    const trigger = screen.getByTestId('nav-menu-toggle');
    await user.click(trigger);
    const library = screen.getByTestId('nav-library');
    library.focus();
    act(() => library.blur());
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    library.focus();
    await user.keyboard('{Escape}');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveFocus();
  });

  it('a closed menu stays closed as focus passes through it', async () => {
    const user = userEvent.setup();
    mountInPage();
    const trigger = screen.getByTestId('nav-menu-toggle');
    screen.getByTestId('nav-research').focus();
    await user.tab();
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });
});

const AVAILABLE: NavItem[] = [
  RESOLVED[0]!,
  {
    routeId: 'library',
    titleKey: 'nav.library',
    capabilityId: 'library',
    available: true,
    placement: 'primary',
  },
  RESOLVED[2]!,
];

function retryTree(status: NavigationStatus, handlers: Record<string, () => void>) {
  return (
    <WorkspaceNavigation
      items={AVAILABLE}
      status={status}
      current="search"
      signedIn
      catalogReady
      complete
      onSelect={handlers.onSelect!}
      onRequireSignIn={handlers.onRequireSignIn!}
      onRetry={handlers.onRetry!}
    />
  );
}

describe('a retried navigation keeps focus in the navigation', () => {
  it('lands on the menu toggle while it shows, then on the new retry after a failure', async () => {
    const user = userEvent.setup();
    const handlers = { onSelect: vi.fn(), onRequireSignIn: vi.fn(), onRetry: vi.fn() };
    const view = render(retryTree('error', handlers));
    screen.getByTestId('nav-retry').focus();
    await user.keyboard('{Enter}');
    expect(handlers.onRetry).toHaveBeenCalledTimes(1);
    const toggle = screen.getByTestId('nav-menu-toggle');
    expect(toggle).toHaveFocus();
    view.rerender(retryTree('loading', handlers));
    expect(toggle).toHaveFocus();
    view.rerender(retryTree('resolved', handlers));
    expect(toggle).toHaveFocus();
    expect(document.activeElement).not.toBe(document.body);
    // A retry that fails again lands on the new retry control.
    view.rerender(retryTree('error', handlers));
    screen.getByTestId('nav-retry').focus();
    await user.keyboard('{Enter}');
    view.rerender(retryTree('loading', handlers));
    view.rerender(retryTree('error', handlers));
    expect(screen.getByTestId('nav-retry')).toHaveFocus();
  });

  it('lands on the loading line, then on the first entry, when the toggle is hidden', async () => {
    const user = userEvent.setup();
    const handlers = { onSelect: vi.fn(), onRequireSignIn: vi.fn(), onRetry: vi.fn() };
    const view = render(retryTree('error', handlers));
    screen.getByTestId('nav-menu-toggle').style.display = 'none';
    screen.getByTestId('nav-retry').focus();
    await user.keyboard('{Enter}');
    expect(document.activeElement).not.toBe(document.body);
    view.rerender(retryTree('loading', handlers));
    expect(screen.getByTestId('nav-loading')).toHaveFocus();
    view.rerender(retryTree('resolved', handlers));
    expect(screen.getByTestId('nav-search')).toHaveFocus();
    expect(document.activeElement).not.toBe(document.body);
  });
});

describe('keyboard parity for navigation', () => {
  it('opens the menu, retries and selects by keyboard, and describes a disabled entry', async () => {
    const user = userEvent.setup();
    const handlers = { onSelect: vi.fn(), onRequireSignIn: vi.fn(), onRetry: vi.fn() };
    const view = render(retryTree('resolved', handlers));
    const toggle = screen.getByTestId('nav-menu-toggle');
    toggle.focus();
    await user.keyboard('{Enter}');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard('{Enter}');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await user.keyboard(' ');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await user.keyboard(' ');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    for (const routeId of ['search', 'library']) {
      screen.getByTestId(`nav-${routeId}`).focus();
      await user.keyboard('{Enter}');
    }
    expect(handlers.onSelect.mock.calls).toEqual([['search'], ['library']]);
    // A disabled entry is reached by Tab and described by its reason.
    screen.getByTestId('nav-library').focus();
    await user.tab();
    const research = screen.getByTestId('nav-research');
    expect(research).toHaveFocus();
    expect(research).toHaveAttribute('aria-disabled', 'true');
    expect(research.getAttribute('aria-describedby')).toBe(
      screen.getByTestId('nav-reason-research').id,
    );
    view.rerender(retryTree('error', handlers));
    screen.getByTestId('nav-retry').focus();
    await user.keyboard('{Enter}');
    expect(handlers.onRetry).toHaveBeenCalledTimes(1);
  });
});

describe('earlier assemblies', () => {
  it('keep their built navigation when the answer carries no placements', () => {
    const handlers = mount('resolved', [], false);
    expect(screen.getByTestId('nav-search')).not.toBeDisabled();
    expect(screen.queryByTestId('nav-library')).toBeNull();
    fireEvent.click(screen.getByTestId('nav-search'));
    expect(handlers.onSelect).toHaveBeenCalledWith('search');
  });
});

function Owner({ owner, onClear }: { owner: string; onClear: () => void }) {
  useOwnerBoundary(owner, onClear);
  const { cache } = useSWRConfig();
  return <p data-testid="cached">{cache.get('private-key') ? 'kept' : 'cleared'}</p>;
}

// A reader keyed by the owner: it remounts in the boundary's commit and reads with useSWR.
function OwnerReader({ owner }: { owner: string }) {
  const { data } = useSWR(['owner-reader', owner], async ([, who]: [string, string]) => {
    return `answer for ${who}`;
  });
  return <p data-testid="owner-reader">{data ?? 'reading'}</p>;
}

describe('the owner boundary', () => {
  it('clears cached responses, private keys and views before resolving again', async () => {
    // A's page list under its `$inf$` key, which a key filter cannot match (Step 91(a)).
    const pageListKey = unstable_serialize(() => ['u8-jobs', 0, null, null]);
    expect(pageListKey).toBe('$inf$@"u8-jobs",0,null,null,');
    const cache = new Map<string, unknown>([
      ['private-key', { data: 'account-a' }],
      [pageListKey, { data: [{ items: [{ jobId: 'job-a1' }] }] }],
    ]);
    window.sessionStorage.setItem(`${PRIVATE_PREFIX}identity-flow`, 'x');
    window.sessionStorage.setItem('other', 'y');
    const onClear = vi.fn();
    const tree = (owner: string) => (
      <SWRConfig value={{ provider: () => cache as never, dedupingInterval: 0 }}>
        <Owner owner={owner} onClear={onClear} />
        <OwnerReader key={owner} owner={owner} />
      </SWRConfig>
    );
    const view = render(tree('account-a'));
    expect(await screen.findByText('answer for account-a')).toBeInTheDocument();
    expect(onClear).not.toHaveBeenCalled();
    await act(async () => view.rerender(tree('account-b')));
    expect(cache.has('private-key')).toBe(false);
    expect(cache.has(pageListKey)).toBe(false);
    expect(onClear).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem(`${PRIVATE_PREFIX}identity-flow`)).toBeNull();
    expect(window.sessionStorage.getItem('other')).toBe('y');
    expect(await screen.findByText('answer for account-b')).toBeInTheDocument();
    expect(screen.queryByText('answer for account-a')).toBeNull();
    window.sessionStorage.clear();
  });

  it('drops only private keys from a storage', () => {
    const removed: string[] = [];
    const keys = [`${PRIVATE_PREFIX}a`, 'b', null];
    dropPrivateSession({
      length: keys.length,
      key: (index) => keys[index] ?? null,
      removeItem: (key) => removed.push(key),
    });
    expect(removed).toEqual([`${PRIVATE_PREFIX}a`]);
  });
});

// A destination that focuses its own heading as it mounts, as SearchWorkspace does.
function SelfFocusing({ title }: { title: string }) {
  const heading = useRef<HTMLHeadingElement | null>(null);
  useEffect(() => heading.current?.focus(), []);
  return (
    <h2 tabIndex={-1} ref={heading}>
      {title}
    </h2>
  );
}

type Harness = {
  route: string;
  request?: FocusRequest | null;
  withHeading?: boolean;
  skipped?: boolean;
  selfFocusing?: boolean;
};

// Step 92(b)'s harness: `<main id="main">` with the entry's section and a
// `.workspace-content` holding a hidden section, then a plain h2 named after the route.
function Routed({
  route,
  request = null,
  withHeading = true,
  skipped = false,
  selfFocusing = false,
}: Harness) {
  useRouteFocus(route, request);
  return (
    <>
      <main id="main" tabIndex={-1}>
        <section data-testid="complete-entry">
          <h2>로그인</h2>
        </section>
        <div className="workspace-content">
          <section hidden>
            <h2>숨은 제목</h2>
          </section>
          {skipped ? (
            <section data-route-focus="skip" data-testid="email-change-proof">
              <h2 tabIndex={-1}>이메일 변경 확인</h2>
            </section>
          ) : null}
          {withHeading ? <h2>{route}</h2> : null}
          {selfFocusing ? <SelfFocusing key={route} title={`${route} 자체`} /> : null}
        </div>
      </main>
      <button type="button" data-testid="claimed">
        claimed
      </button>
    </>
  );
}

function immediateFrames() {
  vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
    callback(0);
    return 1;
  });
}

describe('route focus', () => {
  it('focuses the destination heading on a route change, never the hidden or the entry heading', async () => {
    immediateFrames();
    const view = render(<Routed route="search" />);
    // The first render moves nothing.
    expect(document.activeElement).toBe(document.body);
    await act(async () => view.rerender(<Routed route="library" />));
    const heading = screen.getByRole('heading', { name: 'library' });
    expect(heading).toHaveFocus();
    expect(heading).toHaveAttribute('tabindex', '-1');
  });

  it('focuses #main when the destination has no heading', async () => {
    immediateFrames();
    const view = render(<Routed route="search" />);
    await act(async () => view.rerender(<Routed route="library" withHeading={false} />));
    expect(document.getElementById('main')).toHaveFocus();
  });

  it("keeps the destination's own focused heading", async () => {
    immediateFrames();
    const view = render(<Routed route="search" />);
    await act(async () => view.rerender(<Routed route="library" selfFocusing />));
    expect(screen.getByRole('heading', { name: 'library 자체' })).toHaveFocus();
  });

  it('lands on a claimed target once', async () => {
    immediateFrames();
    const view = render(<Routed route="search" />);
    claimRouteFocus(() => screen.getByTestId('claimed'));
    await act(async () => view.rerender(<Routed route="library" />));
    expect(screen.getByTestId('claimed')).toHaveFocus();
    await act(async () => view.rerender(<Routed route="search" />));
    expect(screen.getByRole('heading', { name: 'search' })).toHaveFocus();
  });

  it('passes over a skipped section on a route change, and a request naming it focuses it', async () => {
    immediateFrames();
    const view = render(<Routed route="search" skipped />);
    const skippedHeading = screen.getByRole('heading', { name: '이메일 변경 확인' });
    skippedHeading.focus();
    await act(async () => view.rerender(<Routed route="library" skipped />));
    expect(screen.getByRole('heading', { name: 'library' })).toHaveFocus();
    await act(async () =>
      view.rerender(
        <Routed route="library" skipped request={{ id: 1, testId: 'email-change-proof' }} />,
      ),
    );
    expect(skippedHeading).toHaveFocus();
    await act(async () =>
      view.rerender(
        <Routed route="library" skipped request={{ id: 2, testId: 'complete-entry' }} />,
      ),
    );
    expect(screen.getByRole('heading', { name: '로그인' })).toHaveFocus();
  });

  it('restores a return point: scroll position and the focused control', () => {
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback) => {
      callback(0);
      return 1;
    });
    const scroll = vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined);
    render(
      <>
        <button type="button" data-testid="result-open">
          open
        </button>
        <button type="button" id="other">
          other
        </button>
      </>,
    );
    screen.getByTestId('result-open').focus();
    const point = captureReturn('search');
    expect(point).toEqual({ view: 'search', scrollY: window.scrollY, focus: 'result-open' });
    screen.getByText('other').focus();
    expect(captureReturn('library').focus).toBe('#other');
    restoreReturn(point);
    expect(scroll).toHaveBeenCalledWith(0, point.scrollY);
    expect(screen.getByTestId('result-open')).toHaveFocus();
    scroll.mockImplementation(() => {
      throw new Error('no scroll');
    });
    restoreReturn({ view: 'search', scrollY: 0, focus: '#other' });
    expect(screen.getByText('other')).toHaveFocus();
    (document.activeElement as HTMLElement).blur();
    expect(captureReturn('search').focus).toBeNull();
  });
});

describe('the reason copy', () => {
  it('maps keys, labels and the sign-in prompt', () => {
    expect(reasonText(undefined)).toBeNull();
    expect(reasonText('nav.somethingNew')).toBe('상태를 확인할 수 없습니다');
    expect(routeLabel({ routeId: 'unlisted', titleKey: 'nav.unlisted' })).toBe('nav.unlisted');
    expect(needsSignIn(RESOLVED[1]!)).toBe(true);
    expect(hidden(RESOLVED[3]!)).toBe(true);
    expect(cx('nav', false, 'px-2 px-4')).toBe('nav px-4');
  });
});
