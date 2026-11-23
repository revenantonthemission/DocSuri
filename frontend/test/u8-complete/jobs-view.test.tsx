// U8 plan Step 42, JobsView (A2; frontend-components.md "JobsView"): the list, the filter
// and paging; the refresh while a job is unfinished; the pause toggle; the empty, error
// and partial states; and no start, cancel or retry control on a job. Step 94(f): the 5 s
// refresh in literal times, only for the jobs the list shows (L1-14), keyboard parity and the
// retry's focus.
import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { JobsView } from '../../src/u8-jobs/jobs-view';
import {
  LIST_PATH,
  LIST_REFRESH_MS,
  PAGE_SIZE,
  updatedText,
  type JobListItem,
} from '../../src/u8-jobs/api';
import type { EventSourceLike } from '../../src/u8-jobs/job-live-status';
import { advance, apiError, fakeClient, Fresh } from './helpers';

const UPDATED = '2026-10-23T02:00:00Z';

function job(jobId: string, overrides: Partial<JobListItem> = {}): JobListItem {
  return {
    jobId,
    kind: 'research',
    label: `질문 ${jobId}`,
    state: 'succeeded',
    createdAt: UPDATED,
    updatedAt: UPDATED,
    resultAvailable: true,
    ...overrides,
  };
}

const quietSource = (): EventSourceLike => ({
  readyState: 1,
  addEventListener: () => undefined,
  close: () => undefined,
});

function mount(answer: (body: { kind?: string; cursor?: string }) => unknown) {
  const fake = fakeClient((path, body) =>
    path === LIST_PATH
      ? answer(body as { kind?: string; cursor?: string })
      : apiError(404, 'NOT_FOUND'),
  );
  const handlers = { onOpenResearch: vi.fn(), onOpenView: vi.fn() };
  render(
    <Fresh>
      <JobsView client={fake.transport} createSource={quietSource} {...handlers} />
    </Fresh>,
  );
  return { ...fake, ...handlers };
}

afterEach(() => vi.useRealTimers());

/** Step 94: timing tests count reads per path, here the list's. */
function listReads(fake: { read: { mock: { calls: unknown[][] } } }): number {
  return fake.read.mock.calls.filter(([path]) => path === LIST_PATH).length;
}

describe('the list', () => {
  it('shows each job with its kind, state, last update and one link', async () => {
    const fake = mount(() => ({
      items: [job('a'), job('b', { kind: 'novelty', state: 'running', resultAvailable: false })],
      nextCursor: null,
    }));
    const items = await screen.findAllByTestId('jobs-item');
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent('질문 a · 연구 · 완료');
    expect(items[0]).toHaveTextContent(`마지막 변경 ${updatedText(UPDATED)}`);
    expect(within(items[0]!).getByTestId('jobs-item-open')).toHaveTextContent('결과 보기');
    expect(items[1]).toHaveTextContent('질문 b · 참신성 분석 · 진행 중');
    expect(within(items[1]!).getByTestId('jobs-item-open')).toHaveTextContent('진행 상황 보기');
    expect(fake.read).toHaveBeenCalledWith(LIST_PATH, { limit: PAGE_SIZE });
    expect(updatedText('not a date')).toBe('');
  });

  it('filters by kind and pages by cursor', async () => {
    const fake = mount((body) => {
      if (body.kind === 'novelty')
        return { items: [job('n', { kind: 'novelty' })], nextCursor: null };
      if (body.cursor === 'c2') return { items: [job('second')], nextCursor: null };
      return { items: [job('first')], nextCursor: 'c2' };
    });
    await screen.findByText(/질문 first/);
    fireEvent.click(screen.getByTestId('jobs-more'));
    await screen.findByText(/질문 second/);
    expect(fake.read).toHaveBeenCalledWith(LIST_PATH, { limit: PAGE_SIZE, cursor: 'c2' });
    expect(screen.queryByTestId('jobs-more')).toBeNull();
    fireEvent.click(screen.getByTestId('jobs-filter-novelty'));
    await screen.findByText(/질문 n/);
    expect(screen.getByTestId('jobs-filter-novelty')).toHaveAttribute('aria-pressed', 'true');
    expect(fake.read).toHaveBeenCalledWith(LIST_PATH, { limit: PAGE_SIZE, kind: 'novelty' });
  });

  it('opens the selected job and its own view, without start, cancel or retry controls', async () => {
    const fake = mount(() => ({ items: [job('a', { kind: 'novelty' })], nextCursor: null }));
    fireEvent.click(await screen.findByTestId('jobs-item-open'));
    expect(screen.getByTestId('jobs-selected')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('jobs-open-view'));
    expect(fake.onOpenView).toHaveBeenCalledWith('novelty');
    for (const name of [/시작/, /취소/, /재시도/]) {
      expect(screen.queryByRole('button', { name })).toBeNull();
    }
  });
});

describe('the refresh', () => {
  it('runs every 5 s while a job is unfinished, stops when all finish, and pauses', async () => {
    vi.useFakeTimers();
    let state: JobListItem['state'] = 'running';
    const fake = mount(() => ({ items: [job('a', { state })], nextCursor: null }));
    await advance(0);
    expect(screen.getByTestId('jobs-refreshing')).toBeInTheDocument();
    expect(LIST_REFRESH_MS).toBe(5_000);
    const reads = () => listReads(fake);
    expect(reads()).toBe(1);
    await advance(4_900);
    expect(reads()).toBe(1);
    await advance(200);
    expect(reads()).toBe(2);
    await advance(5_000);
    expect(reads()).toBe(3);
    state = 'succeeded';
    await advance(5_000);
    expect(reads()).toBe(4);
    expect(screen.queryByTestId('jobs-refreshing')).toBeNull();
    await advance(15_000);
    expect(reads()).toBe(4);
  });

  it('the pause toggle stops the automatic refresh', async () => {
    vi.useFakeTimers();
    const fake = mount(() => ({ items: [job('a', { state: 'running' })], nextCursor: null }));
    await advance(0);
    expect(screen.getByTestId('jobs-refreshing')).toBeInTheDocument();
    const pause = screen.getByTestId('jobs-pause');
    fireEvent.click(pause);
    expect(pause).toHaveAttribute('aria-pressed', 'true');
    expect(pause).toHaveTextContent('자동 새로 고침 다시 시작');
    expect(screen.queryByTestId('jobs-refreshing')).toBeNull();
    const paused = listReads(fake);
    await advance(15_000);
    expect(listReads(fake)).toBe(paused);
  });

  it('refreshes only for the jobs the list shows', async () => {
    vi.useFakeTimers();
    const fake = mount((body) =>
      body.kind === 'novelty'
        ? { items: [job('n', { kind: 'novelty', state: 'succeeded' })], nextCursor: null }
        : {
            items: [
              job('r', { state: 'running', resultAvailable: false }),
              job('n', { kind: 'novelty' }),
            ],
            nextCursor: null,
          },
    );
    await advance(0);
    expect(screen.getByTestId('jobs-refreshing')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('jobs-filter-novelty'));
    await advance(0);
    expect(screen.getAllByTestId('jobs-item')).toHaveLength(1);
    expect(screen.queryByTestId('jobs-refreshing')).toBeNull();
    const shown = listReads(fake);
    expect(fake.read).toHaveBeenLastCalledWith(LIST_PATH, { limit: PAGE_SIZE, kind: 'novelty' });
    await advance(15_000);
    expect(listReads(fake)).toBe(shown);
  });
});

describe('keyboard parity for every jobs control', () => {
  it('acts by Enter and by Space, as a click does', async () => {
    const user = userEvent.setup();
    // The second page has a further page, so jobs-more is pressed by Enter and then by Space.
    const fake = mount((body) =>
      body.cursor === 'c3'
        ? { items: [job('third')], nextCursor: null }
        : body.cursor === 'c2'
          ? { items: [job('second', { kind: 'novelty' })], nextCursor: 'c3' }
          : { items: [job('first')], nextCursor: 'c2' },
    );
    await screen.findByText(/질문 first/);
    for (const [value, key] of [
      ['novelty', '{Enter}'],
      ['research', ' '],
      ['all', '{Enter}'],
      ['novelty', ' '],
      ['all', ' '],
    ] as const) {
      const filter = screen.getByTestId(`jobs-filter-${value}`);
      filter.focus();
      await user.keyboard(key);
      expect(filter).toHaveAttribute('aria-pressed', 'true');
    }
    await screen.findByText(/질문 first/);
    const pause = screen.getByTestId('jobs-pause');
    pause.focus();
    await user.keyboard('{Enter}');
    expect(pause).toHaveAttribute('aria-pressed', 'true');
    await user.keyboard(' ');
    expect(pause).toHaveAttribute('aria-pressed', 'false');
    screen.getByTestId('jobs-more').focus();
    await user.keyboard('{Enter}');
    await screen.findByText(/질문 second/);
    expect(fake.read).toHaveBeenCalledWith(LIST_PATH, { limit: PAGE_SIZE, cursor: 'c2' });
    screen.getByTestId('jobs-more').focus();
    await user.keyboard(' ');
    await screen.findByText(/질문 third/);
    expect(fake.read).toHaveBeenCalledWith(LIST_PATH, { limit: PAGE_SIZE, cursor: 'c3' });
    expect(screen.queryByTestId('jobs-more')).toBeNull();
    const [firstOpen, secondOpen] = screen.getAllByTestId('jobs-item-open');
    firstOpen!.focus();
    await user.keyboard('{Enter}');
    expect(screen.getByTestId('jobs-selected')).toHaveAccessibleName('질문 first 상태');
    secondOpen!.focus();
    await user.keyboard(' ');
    expect(screen.getByTestId('jobs-selected')).toHaveAccessibleName('질문 second 상태');
    const openView = screen.getByTestId('jobs-open-view');
    openView.focus();
    await user.keyboard('{Enter}');
    await user.keyboard(' ');
    expect(fake.onOpenView.mock.calls).toEqual([['novelty'], ['novelty']]);
  });

  it('opens research from the empty state and retries a failed read by Enter and by Space', async () => {
    const user = userEvent.setup();
    const empty = mount(() => ({ items: [], nextCursor: null }));
    const research = await screen.findByTestId('jobs-empty-research');
    research.focus();
    await user.keyboard('{Enter}');
    await user.keyboard(' ');
    expect(empty.onOpenResearch).toHaveBeenCalledTimes(2);
    cleanup();
    let failures = 2;
    const failing = mount(() =>
      failures > 0 ? apiError(503, 'UNAVAILABLE') : { items: [job('a')], nextCursor: null },
    );
    const answer = () => {
      failures -= 1;
    };
    (await screen.findByTestId('jobs-retry')).focus();
    answer();
    await user.keyboard('{Enter}');
    await waitFor(() => expect(failing.read).toHaveBeenCalledTimes(2));
    (await screen.findByTestId('jobs-retry')).focus();
    answer();
    await user.keyboard(' ');
    await screen.findByText(/질문 a/);
    expect(failing.read).toHaveBeenCalledTimes(3);
  });
});

describe('the retry keeps focus', () => {
  it('a retried job list keeps focus in the view', async () => {
    const user = userEvent.setup();
    let release: (value: unknown) => void = () => undefined;
    let calls = 0;
    mount(() => {
      calls += 1;
      if (calls === 1) return apiError(503, 'UNAVAILABLE');
      return new Promise((resolve) => {
        release = resolve;
      });
    });
    const heading = screen.getByRole('heading', { name: '작업' });
    const retry = await screen.findByTestId('jobs-retry');
    retry.focus();
    const seen: Element[] = [];
    const watch = () => seen.push(document.activeElement ?? document.body);
    const afterBlur = () => queueMicrotask(watch);
    document.addEventListener('focusin', watch);
    document.addEventListener('focusout', afterBlur);
    await user.keyboard('{Enter}');
    expect(heading).toHaveFocus();
    expect(screen.getByTestId('jobs-loading')).toBeInTheDocument();
    expect(heading).toHaveFocus();
    await act(async () => {
      release({ items: [job('a')], nextCursor: null });
    });
    await screen.findByText(/질문 a/);
    expect(heading).toHaveFocus();
    expect(document.activeElement).not.toBe(document.body);
    expect(seen).not.toContain(document.body);
    document.removeEventListener('focusin', watch);
    document.removeEventListener('focusout', afterBlur);
  });
});

describe('the empty, error and partial states', () => {
  it('shows the empty state with a way to research', async () => {
    const fake = mount(() => ({ items: [], nextCursor: null }));
    expect(await screen.findByTestId('jobs-empty')).toHaveTextContent('아직 작업이 없습니다');
    fireEvent.click(screen.getByTestId('jobs-empty-research'));
    expect(fake.onOpenResearch).toHaveBeenCalledTimes(1);
  });

  it('shows the error state with a retry that reads again', async () => {
    let fail = true;
    const fake = mount(() =>
      fail ? apiError(503, 'UNAVAILABLE') : { items: [job('a')], nextCursor: null },
    );
    expect(await screen.findByTestId('jobs-error')).toHaveTextContent(
      '작업 목록을 불러오지 못했습니다.',
    );
    fail = false;
    fireEvent.click(screen.getByTestId('jobs-retry'));
    await screen.findByText(/질문 a/);
    expect(fake.read.mock.calls.length).toBeGreaterThanOrEqual(2);
  });

  it('keeps the loaded page when a later page fails (partial)', async () => {
    mount((body) =>
      body.cursor ? apiError(503, 'UNAVAILABLE') : { items: [job('first')], nextCursor: 'c2' },
    );
    await screen.findByText(/질문 first/);
    fireEvent.click(screen.getByTestId('jobs-more'));
    await screen.findByTestId('jobs-error');
    expect(screen.getByText(/질문 first/)).toBeInTheDocument();
  });

  it('shows the loading state first', () => {
    mount(() => new Promise(() => undefined));
    expect(screen.getByTestId('jobs-loading')).toBeInTheDocument();
  });
});
