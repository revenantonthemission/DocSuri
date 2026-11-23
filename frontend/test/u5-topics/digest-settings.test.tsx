/** U5 digest settings form (src/u5-topics/digest-settings.tsx): opened from the topics
 * view (prefill, revision-safe save, stale offer, retryable failure, field validation),
 * and the dialog itself: honest inherited/unconfigured preference readouts, weekly
 * validation, in-dialog unsubscribe confirmation, keyboard handling,
 * preference-propagation refresh, delivery-path copy and Korean accessible names.
 *
 * Moved from topics.test.tsx ('digest settings form') and settings-dialog.test.tsx
 * (plan Step 35, decision L3-1), then merged by rule to eight tests (plan Step 38): each
 * merged test runs its original tests as named cases (eachCase), every body and
 * assertion unchanged, each case rendered on its own. */

import React from 'react';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SWRConfig } from 'swr';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api';
import { DigestSettingsForm } from '../../src/u5-topics/digest-settings';
import { TopicsView } from '../../src/u5-topics/topics-view';
import { eachCase } from './cases';
import { listing, saveResult, settings, topic, TopicsDouble } from './fixtures';

const TOPIC_ID = '11111111-1111-4111-8111-111111111111';
const SETTINGS_ROUTE = `GET /api/v2/topics/${TOPIC_ID}/settings`;
const SAVE_ROUTE = `PUT /api/v2/topics/${TOPIC_ID}/settings`;
const READ_PREFERENCES = 'POST /api/v2/c03/settings-read';
const WRITE_PREFERENCES = 'POST /api/v2/c03/settings-update';

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

const preferenceSnapshot = (languageId: string, timeZone: string, revision: string) => ({
  revision,
  timeZone,
  assistanceDefaults: {
    actionId: 'summary',
    vocabularyRevision: 'synthetic-paper-options-1',
    languageId,
    presentationLevelId: 'standard',
  },
});

const effective = (changes: Record<string, unknown> = {}) => ({
  languageId: 'en',
  presentationLevelId: 'standard',
  timeZone: 'America/New_York',
  effectiveAt: '2026-10-18T00:00:00Z',
  sourceRevision: 'rev-1',
  usesDefaults: false,
  ...changes,
});

function mountForm(api: TopicsDouble, value = topic(), overrides: Record<string, unknown> = {}) {
  const handlers = {
    onClose: vi.fn(),
    onSaved: vi.fn(),
    onUnsubscribe: vi.fn(),
    onError: vi.fn(),
    ...overrides,
  };
  render(<DigestSettingsForm client={api.client()} topic={value} busy={false} {...handlers} />);
  return handlers;
}

afterEach(() => {
  window.localStorage.clear();
});

describe('saving the digest settings', () => {
  it('saves with the loaded revision and reports each acknowledged outcome truthfully', async () => {
    await eachCase({
      'prefills, saves with the loaded revision, and reports the acknowledged state': async () => {
        const api = new TopicsDouble()
          .on('GET /api/v2/topics', () => listing([topic()]))
          .on(`GET /api/v2/topics/${TOPIC_ID}/settings`, () =>
            topic({ settings: settings({ revision: 3, cadence: 'weekly', deliveryDay: 'tue' }) }),
          )
          .on(`PUT /api/v2/topics/${TOPIC_ID}/settings`, () => saveResult());
        mount(<TopicsView client={api.client()} />);
        await userEvent.click(await screen.findByTestId('settings-link'));
        const form = await screen.findByTestId('settings-form');
        expect(
          (form.querySelector('[data-testid="cadence-select"]') as HTMLSelectElement).value,
        ).toBe('weekly');
        expect(
          (form.querySelector('[data-testid="delivery-day"]') as HTMLSelectElement).value,
        ).toBe('tue');
        await userEvent.click(screen.getByTestId('save-button'));
        await screen.findByText(/발송 설정을 저장했어요/);
        const sent = api.calls.find((call) => call.method === 'PUT')?.body;
        expect(sent).toMatchObject({ revision: 3, cadence: 'weekly', deliveryDay: 'tue' });
      },
      'reports an unchanged acknowledged save truthfully': async () => {
        const api = new TopicsDouble()
          .on(SETTINGS_ROUTE, () => topic())
          .on(SAVE_ROUTE, () => saveResult({ unchanged: true }));
        const handlers = mountForm(api);
        await userEvent.click(await screen.findByTestId('save-button'));
        await waitFor(() => expect(handlers.onSaved).toHaveBeenCalledWith('변경된 내용이 없어요'));
      },
    });
  });

  it('validates the delivery fields: the time on blur, a weekly day, no stale weekday', async () => {
    await eachCase({
      'validates the delivery time on blur and shows the weekly-only day select': async () => {
        const api = new TopicsDouble()
          .on('GET /api/v2/topics', () => listing([topic()]))
          .on(`GET /api/v2/topics/${TOPIC_ID}/settings`, () => topic());
        mount(<TopicsView client={api.client()} />);
        await userEvent.click(await screen.findByTestId('settings-link'));
        await screen.findByTestId('settings-form');
        // Daily cadence hides the day select.
        expect(screen.queryByTestId('delivery-day')).toBeNull();
        const time = screen.getByTestId('delivery-time') as HTMLInputElement;
        await userEvent.clear(time);
        await userEvent.tab();
        await screen.findByTestId('delivery-time-error');
        // A native time input can never hold an out-of-range value; the empty
        // field is the invalid case the blur validation catches.
        expect((screen.getByTestId('delivery-time') as HTMLInputElement).value).toBe('');
      },
      'blocks a weekly save until a day is chosen, then sends day and window': async () => {
        const api = new TopicsDouble()
          .on(SETTINGS_ROUTE, () => topic())
          .on(SAVE_ROUTE, () => saveResult());
        const handlers = mountForm(api);
        await userEvent.selectOptions(await screen.findByTestId('cadence-select'), 'weekly');
        expect(screen.getByTestId('save-button')).toBeDisabled();
        screen.getByTestId('delivery-day').focus();
        await userEvent.tab();
        expect(await screen.findByTestId('delivery-day-error')).toHaveTextContent(
          '요일이 필요해요',
        );
        await userEvent.selectOptions(screen.getByTestId('delivery-day'), 'fri');
        await userEvent.selectOptions(screen.getByTestId('window-select'), '30');
        await userEvent.click(screen.getByTestId('save-button'));
        await waitFor(() => expect(handlers.onSaved).toHaveBeenCalledOnce());
        expect(api.calls.find((call) => call.method === 'PUT')?.body).toMatchObject({
          revision: 1,
          cadence: 'weekly',
          deliveryDay: 'fri',
          contentWindowDays: 30,
        });
      },
      'drops a stale weekday when the cadence returns to daily': async () => {
        const api = new TopicsDouble()
          .on(SETTINGS_ROUTE, () =>
            topic({ settings: settings({ cadence: 'weekly', deliveryDay: 'wed' }) }),
          )
          .on(SAVE_ROUTE, () => saveResult());
        mountForm(api);
        await userEvent.selectOptions(await screen.findByTestId('cadence-select'), 'daily');
        expect(screen.queryByTestId('delivery-day')).toBeNull();
        await userEvent.click(screen.getByTestId('save-button'));
        await waitFor(() => expect(api.calls.some((call) => call.method === 'PUT')).toBe(true));
        expect(api.calls.find((call) => call.method === 'PUT')?.body).toMatchObject({
          cadence: 'daily',
          deliveryDay: null,
        });
      },
    });
  });

  it('meets failed reads and saves without overwriting or claiming success', async () => {
    await eachCase({
      'offers a reload on a stale revision instead of an overwriting retry': async () => {
        let loaded = 0;
        const api = new TopicsDouble()
          .on('GET /api/v2/topics', () => listing([topic()]))
          .on(`GET /api/v2/topics/${TOPIC_ID}/settings`, () => {
            loaded += 1;
            return topic({ settings: settings({ revision: loaded }) });
          })
          .on(`PUT /api/v2/topics/${TOPIC_ID}/settings`, () => {
            throw envelope('STALE_REVISION', 409);
          });
        mount(<TopicsView client={api.client()} />);
        await userEvent.click(await screen.findByTestId('settings-link'));
        await screen.findByTestId('settings-form');
        await userEvent.click(screen.getByTestId('save-button'));
        await screen.findByTestId('stale-offer');
        // No second PUT fired on its own: the retry is only via the explicit reload.
        expect(api.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
        await userEvent.click(screen.getByTestId('stale-reload'));
        await screen.findByText(/다시 불러왔어요/);
      },
      'shows a reload failure instead of claiming the refresh succeeded': async () => {
        let reads = 0;
        const api = new TopicsDouble()
          .on(SETTINGS_ROUTE, () => {
            reads += 1;
            if (reads > 1) throw new Error('network');
            return topic();
          })
          .on(SAVE_ROUTE, () => {
            throw new ApiError(409, {
              code: 'STALE_REVISION',
              requestId: 'request-2',
              retryable: false,
              messageKey: 'request.error',
            });
          });
        mountForm(api);
        await userEvent.click(await screen.findByTestId('save-button'));
        await userEvent.click(await screen.findByTestId('stale-reload'));
        await waitFor(() => expect(reads).toBe(2));
        expect(await screen.findByTestId('status-line')).toHaveTextContent('문제가 발생했어요');
        expect(screen.queryByText(/다시 불러왔어요/)).toBeNull();
      },
      'keeps the form open with values intact on a retryable save failure': async () => {
        const api = new TopicsDouble()
          .on('GET /api/v2/topics', () => listing([topic()]))
          .on(`GET /api/v2/topics/${TOPIC_ID}/settings`, () => topic())
          .on(`PUT /api/v2/topics/${TOPIC_ID}/settings`, () => {
            throw envelope('RATE_LIMITED', 429);
          });
        mount(<TopicsView client={api.client()} />);
        await userEvent.click(await screen.findByTestId('settings-link'));
        await screen.findByTestId('settings-form');
        await userEvent.click(screen.getByTestId('save-button'));
        await screen.findByRole('alert');
        expect(screen.getByTestId('settings-form')).toBeDefined();
        expect(api.calls.filter((call) => call.method === 'PUT')).toHaveLength(1);
      },
      'surfaces an initial read failure to the owner and stays in loading': async () => {
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => {
          throw new ApiError(404, {
            code: 'NOT_FOUND',
            requestId: 'request-1',
            retryable: false,
            messageKey: 'request.error',
          });
        });
        const handlers = mountForm(api);
        await waitFor(() => expect(handlers.onError).toHaveBeenCalledOnce());
        expect(screen.getByTestId('settings-loading')).toBeInTheDocument();
        expect(screen.queryByTestId('save-button')).toBeNull();
      },
    });
  });
});

describe('inherited preference readout', () => {
  it('states each source of the inherited preferences honestly', async () => {
    await eachCase({
      'states an unconfigured owner zone instead of assuming a location': async () => {
        const value = topic({ effectivePreferences: effective({ timeZone: null }) });
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
        mountForm(api, value);
        expect(await screen.findByTestId('inherited-note')).toHaveTextContent('시간대 미설정');
        expect(screen.getByText(/계정 시간대 미설정 기준/)).toBeInTheDocument();
        expect(screen.getByRole('status')).toHaveTextContent('시간대를 확인하고 저장해야');
      },
      'shows Korean explicitly chosen settings without a defaults label': async () => {
        const value = topic({
          effectivePreferences: effective({ languageId: 'ko', timeZone: 'Asia/Seoul' }),
        });
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
        mountForm(api, value);
        const note = await screen.findByTestId('inherited-note');
        expect(note).toHaveTextContent('한국어 · 표준 (standard) · Asia/Seoul');
        expect(note).not.toHaveTextContent('기본값');
        expect(screen.queryByText(/시간대를 확인하고 저장해야/)).toBeNull();
      },
      'admits when effective preferences cannot be read': async () => {
        const value = topic({ effectivePreferences: undefined });
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
        mountForm(api, value);
        expect(await screen.findByTestId('inherited-note')).toHaveTextContent(
          '계정 환경설정을 확인할 수 없어요',
        );
      },
    });
  });

  it('refreshes the readout after an acknowledged owner-preference save', async () => {
    let reads = 0;
    const value = topic({ effectivePreferences: effective() });
    const api = new TopicsDouble()
      .on(SETTINGS_ROUTE, () => {
        reads += 1;
        return reads === 1
          ? value
          : topic({
              effectivePreferences: effective({ languageId: 'ko', timeZone: 'Asia/Seoul' }),
            });
      })
      .on(READ_PREFERENCES, () => preferenceSnapshot('en', 'America/New_York', 'rev-1'))
      .on(WRITE_PREFERENCES, () => preferenceSnapshot('ko', 'Asia/Seoul', 'rev-2'));
    mountForm(api, value);
    await screen.findByTestId('inherited-note');
    await userEvent.click(screen.getByTestId('preferences-toggle'));
    await userEvent.selectOptions(await screen.findByTestId('digest-language'), 'ko');
    await userEvent.clear(screen.getByTestId('digest-timezone'));
    await userEvent.type(screen.getByTestId('digest-timezone'), 'Asia/Seoul');
    await userEvent.click(screen.getByTestId('preferences-save'));
    await waitFor(() =>
      expect(screen.getByTestId('inherited-note')).toHaveTextContent(
        '한국어 · 표준 (standard) · Asia/Seoul',
      ),
    );
    expect(reads).toBe(2);
  });
});

describe('dialog keyboard and unsubscribe confirmation', () => {
  it('keeps the keyboard inside the dialog and confirms before unsubscribing', async () => {
    await eachCase({
      'closes on Escape and keeps Tab focus inside the dialog': async () => {
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => topic());
        const handlers = mountForm(api);
        await screen.findByTestId('save-button');
        screen.getByTestId('save-button').focus();
        await userEvent.tab();
        expect(screen.getByTestId('settings-form')).toContainElement(
          document.activeElement as HTMLElement,
        );
        expect(document.activeElement).toBe(screen.getByTestId('cadence-select'));
        await userEvent.tab({ shift: true });
        expect(document.activeElement).toBe(screen.getByTestId('save-button'));
        await userEvent.keyboard('{Escape}');
        expect(handlers.onClose).toHaveBeenCalledOnce();
      },
      'requires confirmation before unsubscribing and honours cancel': async () => {
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => topic());
        const handlers = mountForm(api);
        await userEvent.click(await screen.findByTestId('settings-unsubscribe'));
        expect(screen.getByTestId('settings-confirm-dialog')).toHaveTextContent('양자 오류 정정');
        await userEvent.click(screen.getByTestId('settings-confirm-dialog-cancel'));
        expect(handlers.onUnsubscribe).not.toHaveBeenCalled();
        await userEvent.click(screen.getByTestId('settings-unsubscribe'));
        await userEvent.click(screen.getByTestId('settings-confirm-dialog-confirm'));
        expect(handlers.onUnsubscribe).toHaveBeenCalledOnce();
        expect(screen.queryByTestId('settings-confirm-dialog')).toBeNull();
      },
    });
  });
});

describe('Korean accessible names (NFR5.1)', () => {
  it('names the dialog and every control of the settings form in Korean', async () => {
    const api = new TopicsDouble().on(SETTINGS_ROUTE, () => topic());
    mountForm(api);
    const form = await screen.findByRole('dialog', { name: "'양자 오류 정정' 발송 설정" });
    expect(form).toBe(screen.getByTestId('settings-form'));
    const named = (role: string, name: string | RegExp) => within(form).getByRole(role, { name });
    expect(named('combobox', '발송 주기')).toBe(screen.getByTestId('cadence-select'));
    expect(named('combobox', '불러올 기간')).toBe(screen.getByTestId('window-select'));
    // A time field has no ARIA role in jsdom, so it is found by its Korean label.
    expect(within(form).getByLabelText(/^발송 시각 \(.+ 기준\)$/)).toBe(
      screen.getByTestId('delivery-time'),
    );
    expect(named('button', '계정 환경설정 변경')).toBe(screen.getByTestId('preferences-toggle'));
    expect(named('button', '닫기')).toBe(screen.getByTestId('settings-close'));
    expect(named('button', '구독 해지')).toBe(screen.getByTestId('settings-unsubscribe'));
    expect(named('button', '저장')).toBe(screen.getByTestId('save-button'));
    // The weekly-only day select carries its own Korean name once it is shown.
    await userEvent.selectOptions(named('combobox', '발송 주기'), 'weekly');
    expect(named('combobox', '발송 요일')).toBe(screen.getByTestId('delivery-day'));
  });
});

describe('recorded digest presentation', () => {
  it('labels the delivery path truthfully and admits a missing presentation', async () => {
    await eachCase({
      'labels a local-sink send as local, never as email delivery': async () => {
        const value = topic({
          runs: [
            {
              state: 'sent',
              presentation: { text: 'Quantum digest body', emptyLabel: 'No new papers' },
              sendLog: {
                pathKind: 'local-sink',
                transportReceipt: 'local-1',
                acknowledgedAt: null,
              },
            },
          ],
        });
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
        mountForm(api, value);
        const preview = await screen.findByTestId('digest-preview');
        expect(preview).toHaveTextContent('Quantum digest body');
        expect(preview).toHaveTextContent('로컬 시험 저장소');
        expect(preview).not.toHaveTextContent('이메일 전송 경로');
      },
      'labels a real path and admits a missing stored presentation': async () => {
        const value = topic({
          runs: [
            {
              state: 'sent',
              sendLog: { pathKind: 'real', transportReceipt: 'r', acknowledgedAt: null },
            },
          ],
        });
        const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
        mountForm(api, value);
        const preview = await screen.findByTestId('digest-preview');
        expect(preview).toHaveTextContent('이메일 전송 경로');
        expect(preview).toHaveTextContent('저장된 표시 내용을 확인할 수 없어요');
      },
    });
  });
});
