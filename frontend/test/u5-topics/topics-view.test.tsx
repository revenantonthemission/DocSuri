/** U5 topics view (src/u5-topics/topics-view.tsx) over a recording Transport double:
 * view states, acknowledged follow and unsubscribe, dialog accessibility, the
 * unknown-outcome resolution and the last-digest copy. Moved unchanged from
 * topics.test.tsx (plan Step 35, decision L3-1); its digest settings form tests are in
 * digest-settings.test.tsx. */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SWRConfig } from 'swr';
import { afterEach, describe, expect, it } from 'vitest';
import { ApiError } from '../../src/api';
import { TopicsView, lastDigestView } from '../../src/u5-topics/topics-view';
import { eachCase } from './cases';
import { followResult, listing, topic, TopicsDouble, unsubscribeResult } from './fixtures';

const TOPIC_ID = '11111111-1111-4111-8111-111111111111';
const RUN_ID = '33333333-3333-4333-8333-333333333333';

function mount(ui: React.ReactElement) {
  return render(<SWRConfig value={{ provider: () => new Map() }}>{ui}</SWRConfig>);
}

const envelope = (code: string, status: number) =>
  new ApiError(status, {
    code,
    requestId: 'request-1',
    retryable: false,
    messageKey: 'request.error',
  });

afterEach(() => {
  window.localStorage.clear();
});

describe('topics view states', () => {
  it('shows loading, then ready rows with the last-digest indicator', async () => {
    const api = new TopicsDouble().on('GET /api/v2/topics', () =>
      listing([
        topic({
          lastRun: { runId: RUN_ID, state: 'sent', windowEnd: '2026-10-18', observedState: 'sent' },
        }),
      ]),
    );
    mount(<TopicsView client={api.client()} />);
    await screen.findByText('불러오는 중…');
    await screen.findByTestId('topic-row');
    const digest = await screen.findByTestId('last-digest');
    expect(digest.textContent).toContain('✓');
    expect(digest.textContent).toContain('마지막 발송 완료');
    expect(api.calls.some((call) => call.method === 'GET' && call.path === '/api/v2/topics')).toBe(
      true,
    );
  });

  // Plan Step 38 (decision L3-1): three same-rule cases, each list state's own marker,
  // merged into one test; every case keeps its original body.
  it('marks the empty, read-failure and degraded states each with its own marker', async () => {
    await eachCase({
      'shows the empty state and the follow action for a new account': async () => {
        const api = new TopicsDouble().on('GET /api/v2/topics', () => listing([]));
        mount(<TopicsView client={api.client()} />);
        await screen.findByTestId('topics-empty');
        expect(screen.getByTestId('follow-input')).toBeDefined();
        expect(screen.getByTestId('follow-button')).toBeDefined();
      },
      'surfaces a read failure as a plain refusal': async () => {
        const api = new TopicsDouble().on('GET /api/v2/topics', () => {
          throw envelope('DEPENDENCY_UNAVAILABLE', 503);
        });
        mount(<TopicsView client={api.client()} />);
        await screen.findByTestId('topics-error');
      },
      'marks the partial state when the capability is degraded': async () => {
        const api = new TopicsDouble().on('GET /api/v2/topics', () => listing([topic()]));
        mount(<TopicsView client={api.client()} degraded />);
        await screen.findByTestId('topics-partial');
      },
    });
  });
});

describe('follow and unsubscribe', () => {
  it('follows after acknowledgement, then refreshes the list', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([]))
      .on('POST /api/v2/topics', () => followResult());
    mount(<TopicsView client={api.client()} />);
    await userEvent.type(await screen.findByTestId('follow-input'), '양자 오류 정정');
    await userEvent.click(screen.getByTestId('follow-button'));
    await screen.findByText(/주제를 팔로우했어요/);
    expect(api.calls.find((call) => call.method === 'POST')?.body).toMatchObject({
      topicKey: '양자 오류 정정',
      displayName: '양자 오류 정정',
    });
  });

  it('shows the duplicate notice without changing the existing subscription', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([]))
      .on('POST /api/v2/topics', () => {
        throw envelope('CONFLICT', 409);
      });
    mount(<TopicsView client={api.client()} />);
    await userEvent.type(await screen.findByTestId('follow-input'), '양자 오류 정정');
    await userEvent.click(screen.getByTestId('follow-button'));
    await screen.findByText(/이미 구독 중/);
    expect(api.calls.filter((call) => call.method === 'POST')).toHaveLength(1);
  });

  it('confirms unsubscribe with the topic name and queued-work note, then removes the row', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([topic()]))
      .on(`DELETE /api/v2/topics/${TOPIC_ID}`, () => unsubscribeResult());
    mount(<TopicsView client={api.client()} />);
    await userEvent.click(await screen.findByTestId('unsubscribe-button'));
    const dialog = await screen.findByTestId('confirm-dialog');
    expect(dialog.textContent).toContain('양자 오류 정정');
    expect(dialog.textContent).toContain('폐기');
    await userEvent.click(screen.getByTestId('confirm-dialog-confirm'));
    await screen.findByText(/구독을 해지했어요/);
    expect(api.calls.find((call) => call.method === 'DELETE')?.path).toBe(
      `/api/v2/topics/${TOPIC_ID}`,
    );
  });

  it('returns focus to the trigger after the dialog closes and traps Tab inside', async () => {
    const api = new TopicsDouble().on('GET /api/v2/topics', () => listing([topic()]));
    mount(<TopicsView client={api.client()} />);
    await userEvent.click(await screen.findByTestId('unsubscribe-button'));
    const dialog = await screen.findByTestId('confirm-dialog');
    expect(dialog.contains(document.activeElement)).toBe(true);
    // Tab from the last focusable wraps back into the dialog.
    for (let index = 0; index < 6; index += 1) {
      await userEvent.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
    await userEvent.click(screen.getByTestId('confirm-dialog-cancel'));
    await waitFor(() =>
      expect(document.activeElement?.getAttribute('data-testid')).toBe('unsubscribe-button'),
    );
  });
});

describe('unknown outcome resolution', () => {
  it('offers both resolutions and posts the named assumption', async () => {
    const unresolved = topic({
      lastRun: {
        runId: RUN_ID,
        state: 'unknown',
        windowEnd: '2026-10-18',
        observedState: 'unknown',
      },
    });
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([unresolved]))
      .on(`POST /api/v2/topics/${TOPIC_ID}/runs/${RUN_ID}/resolve`, () => ({
        runId: RUN_ID,
        state: 'sent',
        decision: 'delivered',
        assumption: '보낸 메일이 도착했다고 가정합니다',
      }));
    mount(<TopicsView client={api.client()} />);
    await screen.findByTestId('resolve-control');
    await userEvent.click(screen.getByTestId('resolve-delivered'));
    await screen.findByText(/배달됨으로 표시했어요/);
    const sent = api.calls.find((call) => call.method === 'POST')?.body;
    expect(sent).toMatchObject({
      decision: 'delivered',
      assumption: '보낸 메일이 도착했다고 가정합니다',
    });
  });
});

describe('last-digest copy', () => {
  it('never reports color-only state: every state carries icon and text', () => {
    for (const state of ['sent', 'empty', 'failed', 'unknown', 'prepared', 'sending']) {
      const view = lastDigestView(
        topic({ lastRun: { runId: RUN_ID, state, windowEnd: null, observedState: state } }),
      );
      expect(view).not.toBeNull();
      expect(view!.icon).toBeTruthy();
      expect(view!.text).toBeTruthy();
    }
    expect(lastDigestView(topic())).toBeNull();
  });
});
