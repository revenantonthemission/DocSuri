/** U5 digest settings dialog after implementation: honest inherited/unconfigured
 * preference readouts, weekly validation, in-dialog unsubscribe confirmation,
 * keyboard handling, preference-propagation refresh and delivery-path copy. */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api';
import { DigestSettingsForm } from '../../src/u5-topics/digest-settings';
import { saveResult, settings, topic, TopicsDouble } from './fixtures';

const TOPIC_ID = '11111111-1111-4111-8111-111111111111';
const SETTINGS_ROUTE = `GET /api/v2/topics/${TOPIC_ID}/settings`;
const SAVE_ROUTE = `PUT /api/v2/topics/${TOPIC_ID}/settings`;
const READ_PREFERENCES = 'POST /api/v2/c03/settings-read';
const WRITE_PREFERENCES = 'POST /api/v2/c03/settings-update';

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

describe('inherited preference readout', () => {
  it('states an unconfigured owner zone instead of assuming a location', async () => {
    const value = topic({ effectivePreferences: effective({ timeZone: null }) });
    const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
    mountForm(api, value);
    expect(await screen.findByTestId('inherited-note')).toHaveTextContent('시간대 미설정');
    expect(screen.getByText(/계정 시간대 미설정 기준/)).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('시간대를 확인하고 저장해야');
  });

  it('shows Korean explicitly chosen settings without a defaults label', async () => {
    const value = topic({
      effectivePreferences: effective({ languageId: 'ko', timeZone: 'Asia/Seoul' }),
    });
    const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
    mountForm(api, value);
    const note = await screen.findByTestId('inherited-note');
    expect(note).toHaveTextContent('한국어 · 표준 (standard) · Asia/Seoul');
    expect(note).not.toHaveTextContent('기본값');
    expect(screen.queryByText(/시간대를 확인하고 저장해야/)).toBeNull();
  });

  it('admits when effective preferences cannot be read', async () => {
    const value = topic({ effectivePreferences: undefined });
    const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
    mountForm(api, value);
    expect(await screen.findByTestId('inherited-note')).toHaveTextContent(
      '계정 환경설정을 확인할 수 없어요',
    );
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

describe('weekly settings and save outcomes', () => {
  it('blocks a weekly save until a day is chosen, then sends day and window', async () => {
    const api = new TopicsDouble()
      .on(SETTINGS_ROUTE, () => topic())
      .on(SAVE_ROUTE, () => saveResult());
    const handlers = mountForm(api);
    await userEvent.selectOptions(await screen.findByTestId('cadence-select'), 'weekly');
    expect(screen.getByTestId('save-button')).toBeDisabled();
    screen.getByTestId('delivery-day').focus();
    await userEvent.tab();
    expect(await screen.findByTestId('delivery-day-error')).toHaveTextContent('요일이 필요해요');
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
  });

  it('drops a stale weekday when the cadence returns to daily', async () => {
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
  });

  it('reports an unchanged acknowledged save truthfully', async () => {
    const api = new TopicsDouble()
      .on(SETTINGS_ROUTE, () => topic())
      .on(SAVE_ROUTE, () => saveResult({ unchanged: true }));
    const handlers = mountForm(api);
    await userEvent.click(await screen.findByTestId('save-button'));
    await waitFor(() => expect(handlers.onSaved).toHaveBeenCalledWith('변경된 내용이 없어요'));
  });

  it('surfaces an initial read failure to the owner and stays in loading', async () => {
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
  });

  it('shows a reload failure instead of claiming the refresh succeeded', async () => {
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
  });
});

describe('dialog keyboard and unsubscribe confirmation', () => {
  it('closes on Escape and keeps Tab focus inside the dialog', async () => {
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
  });

  it('requires confirmation before unsubscribing and honours cancel', async () => {
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
  });
});

describe('recorded digest presentation', () => {
  it('labels a local-sink send as local, never as email delivery', async () => {
    const value = topic({
      runs: [
        {
          state: 'sent',
          presentation: { text: 'Quantum digest body', emptyLabel: 'No new papers' },
          sendLog: { pathKind: 'local-sink', transportReceipt: 'local-1', acknowledgedAt: null },
        },
      ],
    });
    const api = new TopicsDouble().on(SETTINGS_ROUTE, () => value);
    mountForm(api, value);
    const preview = await screen.findByTestId('digest-preview');
    expect(preview).toHaveTextContent('Quantum digest body');
    expect(preview).toHaveTextContent('로컬 시험 저장소');
    expect(preview).not.toHaveTextContent('이메일 전송 경로');
  });

  it('labels a real path and admits a missing stored presentation', async () => {
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
  });
});
