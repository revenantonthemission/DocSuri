/** NFR5.1 on the topics list and the resolve control: every acknowledged change is
 * announced in the polite status line (role="status"), every failed request in an
 * alert (role="alert"), and every control carries its Korean accessible name.
 * Assertions read the live region itself, not only the text on the page. */

import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SWRConfig } from 'swr';
import { afterEach, describe, expect, it } from 'vitest';
import { ApiError } from '../../src/api';
import { TopicsView } from '../../src/u5-topics/topics-view';
import { eachCase } from './cases';
import {
  followResult,
  listing,
  saveResult,
  settings,
  topic,
  TopicsDouble,
  unsubscribeResult,
} from './fixtures';

const TOPIC_ID = '11111111-1111-4111-8111-111111111111';
const RUN_ID = '33333333-3333-4333-8333-333333333333';
const RESOLVE_PATH = `/api/v2/topics/${TOPIC_ID}/runs/${RUN_ID}/resolve`;

type Resolution = { name: string; decision: 'delivered' | 'not-delivered'; message: RegExp };

const RESOLUTIONS: Resolution[] = [
  { name: '배달됨으로 해결', decision: 'delivered', message: /배달됨으로 표시했어요/ },
  { name: '미전달로 해결', decision: 'not-delivered', message: /미전달로 표시했어요/ },
];

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

const unresolved = () =>
  topic({
    lastRun: {
      runId: RUN_ID,
      state: 'unknown',
      windowEnd: '2026-10-18',
      observedState: 'unknown',
    },
  });

function regionsWith(role: 'status' | 'alert', text: RegExp): HTMLElement[] {
  return screen.queryAllByRole(role).filter((node) => text.test(node.textContent ?? ''));
}

/** The polite live region holding `text`; fails when the text is only elsewhere. */
async function politeRegion(text: RegExp): Promise<HTMLElement> {
  const region = await waitFor(() => {
    const [found] = regionsWith('status', text);
    expect(found).toBeDefined();
    return found as HTMLElement;
  });
  expect(region.getAttribute('role')).toBe('status');
  expect(region.getAttribute('aria-live')).not.toBe('assertive');
  // The acknowledgement is never raised as an alert.
  expect(regionsWith('alert', text)).toHaveLength(0);
  return region;
}

afterEach(() => {
  window.localStorage.clear();
});

describe('polite announcements of acknowledged changes', () => {
  it('announces a followed topic in the status line', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([]))
      .on('POST /api/v2/topics', () => followResult());
    mount(<TopicsView client={api.client()} />);
    const input = await screen.findByRole('textbox', { name: '새 주제' });
    await userEvent.type(input, '양자 오류 정정');
    await userEvent.click(screen.getByRole('button', { name: '주제 팔로우' }));
    const region = await politeRegion(/주제를 팔로우했어요/);
    expect(region.textContent).toContain('양자 오류 정정');
  });

  it('announces an unsubscribe in the status line', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([topic()]))
      .on(`DELETE /api/v2/topics/${TOPIC_ID}`, () => unsubscribeResult());
    mount(<TopicsView client={api.client()} />);
    await userEvent.click(await screen.findByRole('button', { name: '구독 해지' }));
    await userEvent.click(screen.getByTestId('confirm-dialog-confirm'));
    const region = await politeRegion(/구독을 해지했어요/);
    expect(region.textContent).toContain('양자 오류 정정');
  });

  it('announces saved digest settings in the status line', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([topic()]))
      .on(`GET /api/v2/topics/${TOPIC_ID}/settings`, () =>
        topic({ settings: settings({ revision: 3 }) }),
      )
      .on(`PUT /api/v2/topics/${TOPIC_ID}/settings`, () => saveResult());
    mount(<TopicsView client={api.client()} />);
    await userEvent.click(await screen.findByRole('button', { name: '발송 설정' }));
    await screen.findByTestId('settings-form');
    await userEvent.click(screen.getByTestId('save-button'));
    await politeRegion(/발송 설정을 저장했어요/);
    expect(screen.queryByTestId('settings-form')).toBeNull();
  });

  // Plan Step 38 (decision L3-1): the two resolutions ran one body from one loop; they
  // are merged into one test that runs that body for each, unchanged.
  it('announces each resolution in the status line', async () => {
    await eachCase(
      Object.fromEntries(
        RESOLUTIONS.map(({ name, decision, message }) => [
          `announces the ${decision} resolution in the status line`,
          async () => {
            const api = new TopicsDouble()
              .on('GET /api/v2/topics', () => listing([unresolved()]))
              .on(`POST ${RESOLVE_PATH}`, () => ({
                runId: RUN_ID,
                state: decision === 'delivered' ? 'sent' : 'failed',
                decision,
                assumption: '가정',
              }));
            mount(<TopicsView client={api.client()} />);
            await userEvent.click(await screen.findByRole('button', { name }));
            await politeRegion(message);
            expect(api.calls.filter((call) => call.method === 'POST')).toHaveLength(1);
          },
        ]),
      ),
    );
  });
});

describe('failed requests announce in an alert', () => {
  it('raises a failed unsubscribe as an alert, not a status', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([topic()]))
      .on(`DELETE /api/v2/topics/${TOPIC_ID}`, () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      });
    mount(<TopicsView client={api.client()} />);
    await userEvent.click(await screen.findByRole('button', { name: '구독 해지' }));
    await userEvent.click(screen.getByTestId('confirm-dialog-confirm'));
    const alert = await screen.findByRole('alert');
    expect(alert.getAttribute('role')).toBe('alert');
    expect(alert.textContent).toBeTruthy();
    expect(regionsWith('status', /해지했어요/)).toHaveLength(0);
  });

  it('raises a failed resolution as an alert and keeps the control', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([unresolved()]))
      .on(`POST ${RESOLVE_PATH}`, () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      });
    mount(<TopicsView client={api.client()} />);
    await userEvent.click(await screen.findByRole('button', { name: '배달됨으로 해결' }));
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toBeTruthy();
    expect(regionsWith('status', /표시했어요/)).toHaveLength(0);
    expect(screen.getByTestId('resolve-control')).toBeDefined();
  });

  it('raises a failed follow as an alert beside the follow control', async () => {
    const api = new TopicsDouble()
      .on('GET /api/v2/topics', () => listing([]))
      .on('POST /api/v2/topics', () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      });
    mount(<TopicsView client={api.client()} />);
    const input = await screen.findByRole('textbox', { name: '새 주제' });
    await userEvent.type(input, '양자 오류 정정');
    await userEvent.click(screen.getByRole('button', { name: '주제 팔로우' }));
    const follow = screen.getByTestId('follow-action');
    const alert = await within(follow).findByRole('alert');
    expect(alert.textContent).toBeTruthy();
    expect(regionsWith('status', /팔로우했어요/)).toHaveLength(0);
  });
});

describe('Korean accessible names', () => {
  // Plan Step 38 (decision L3-1): one rule, Korean accessible names, over the list's and
  // the resolve control's surfaces, merged into one test; each case keeps its body.
  it('names every control of the topic list and the resolve control in Korean', async () => {
    await eachCase({
      'names every control of the topic list in Korean': async () => {
        const api = new TopicsDouble().on('GET /api/v2/topics', () => listing([topic()]));
        mount(<TopicsView client={api.client()} />);
        const list = await screen.findByTestId('topic-list');
        expect(within(list).getByRole('button', { name: '발송 설정' })).toBeDefined();
        expect(within(list).getByRole('button', { name: '구독 해지' })).toBeDefined();
        const follow = screen.getByTestId('follow-action');
        expect(within(follow).getByRole('textbox', { name: '새 주제' }).id).toBe('u5-follow-key');
        expect(within(follow).getByRole('button', { name: '주제 팔로우' })).toBeDefined();
      },
      'names both controls of the resolve control in Korean': async () => {
        const api = new TopicsDouble().on('GET /api/v2/topics', () => listing([unresolved()]));
        mount(<TopicsView client={api.client()} />);
        const control = await screen.findByTestId('resolve-control');
        const buttons = within(control).getAllByRole('button');
        expect(buttons.map((button) => button.textContent)).toEqual([
          '배달됨으로 해결',
          '미전달로 해결',
        ]);
        for (const { name } of RESOLUTIONS) {
          expect(within(control).getByRole('button', { name })).toBeDefined();
        }
      },
    });
  });
});
