import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../src/api';
import { OwnerPreferences } from '../../src/u5-topics/owner-preferences';
import { DigestSettingsForm } from '../../src/u5-topics/digest-settings';
import { topic, TopicsDouble } from './fixtures';

const snapshot = {
  revision: 'rev-1',
  timeZone: 'America/New_York',
  assistanceDefaults: {
    actionId: 'summary',
    vocabularyRevision: 'synthetic-paper-options-1',
    languageId: 'en',
    presentationLevelId: 'standard',
  },
};
const failure = (code: string) =>
  new ApiError(409, { code, requestId: 'test', retryable: false, messageKey: 'test' });
const readRoute = 'POST /api/v2/c03/settings-read';
const writeRoute = 'POST /api/v2/c03/settings-update';

describe('owner digest preferences', () => {
  it('loads authoritative settings and acknowledges the persisted language and zone', async () => {
    const api = new TopicsDouble()
      .on(readRoute, () => snapshot)
      .on(writeRoute, () => ({
        ...snapshot,
        revision: 'rev-2',
        timeZone: 'Asia/Seoul',
        assistanceDefaults: { ...snapshot.assistanceDefaults, languageId: 'ko' },
      }));
    const saved = vi.fn();
    render(<OwnerPreferences client={api.client()} onSaved={saved} />);
    await userEvent.selectOptions(await screen.findByTestId('digest-language'), 'ko');
    await userEvent.clear(screen.getByTestId('digest-timezone'));
    await userEvent.type(screen.getByTestId('digest-timezone'), 'Asia/Seoul');
    await userEvent.click(screen.getByTestId('preferences-save'));
    await screen.findByText('계정 환경설정을 저장했어요');
    expect(api.calls.at(-1)?.body).toMatchObject({
      expectedRevision: 'rev-1',
      timeZone: 'Asia/Seoul',
      assistanceDefaults: {
        languageId: 'ko',
        presentationLevelId: 'standard',
        actionId: 'summary',
      },
    });
    expect(saved).toHaveBeenCalledOnce();
    expect(screen.getByTestId('digest-timezone')).toHaveValue('Asia/Seoul');
  });

  it('requires explicit zone confirmation instead of guessing the browser zone', async () => {
    const api = new TopicsDouble().on(readRoute, () => ({ ...snapshot, timeZone: null }));
    render(<OwnerPreferences client={api.client()} onSaved={vi.fn()} />);
    expect(await screen.findByTestId('digest-timezone')).toHaveValue('');
    expect(screen.getByTestId('preferences-save')).toBeDisabled();
    expect(screen.getByText(/시간대를 확인하고 저장해야/)).toBeVisible();
  });

  it('reloads a stale revision before another save, preserving other C03 fields', async () => {
    let revision = 'rev-1';
    const api = new TopicsDouble()
      .on(readRoute, () => ({ ...snapshot, revision }))
      .on(writeRoute, () => {
        throw failure('STALE_REVISION');
      });
    render(<OwnerPreferences client={api.client()} onSaved={vi.fn()} />);
    await userEvent.click(await screen.findByTestId('preferences-save'));
    expect(screen.getByTestId('preferences-save')).toBeDisabled();
    revision = 'rev-2';
    await userEvent.click(await screen.findByTestId('preferences-reload'));
    await userEvent.click(screen.getByTestId('preferences-save'));
    expect(api.calls.at(-1)?.body).toMatchObject({ expectedRevision: 'rev-2' });
  });

  it('retains the same operation identity and body after a lost acknowledgement', async () => {
    let attempts = 0;
    const api = new TopicsDouble()
      .on(readRoute, () => snapshot)
      .on(writeRoute, () => {
        if (++attempts === 1) throw failure('UNKNOWN_OUTCOME');
        return { ...snapshot, revision: 'rev-2' };
      });
    render(<OwnerPreferences client={api.client()} onSaved={vi.fn()} />);
    await userEvent.click(await screen.findByTestId('preferences-save'));
    expect(await screen.findByText('저장 결과 확인')).toBeVisible();
    expect(screen.getByTestId('digest-timezone')).toBeDisabled();
    expect(attempts).toBe(1);
    await userEvent.click(screen.getByTestId('preferences-save'));
    await screen.findByText('계정 환경설정을 저장했어요');
    expect(api.operationKeys[0]).toBe(api.operationKeys[1]);
  });

  it('keeps an invalid zone and displays the refused save without success', async () => {
    const saved = vi.fn();
    const api = new TopicsDouble()
      .on(readRoute, () => snapshot)
      .on(writeRoute, () => {
        throw failure('INVALID_ARGUMENT');
      });
    render(<OwnerPreferences client={api.client()} onSaved={saved} />);
    await userEvent.clear(await screen.findByTestId('digest-timezone'));
    await userEvent.type(screen.getByTestId('digest-timezone'), 'Invalid/Zone');
    await userEvent.click(screen.getByTestId('preferences-save'));
    await screen.findByRole('alert');
    expect(screen.getByTestId('digest-timezone')).toHaveValue('Invalid/Zone');
    expect(saved).not.toHaveBeenCalled();
  });

  it('offers an explicit retry after a settings read fails', async () => {
    let attempts = 0;
    const api = new TopicsDouble().on(readRoute, () => {
      if (++attempts === 1) throw failure('DEPENDENCY_UNAVAILABLE');
      return snapshot;
    });
    render(<OwnerPreferences client={api.client()} onSaved={vi.fn()} />);
    await userEvent.click(await screen.findByTestId('preferences-reload'));
    expect(await screen.findByTestId('digest-language')).toHaveValue('en');
  });

  it('ignores late save acknowledgements after the account generation changes', async () => {
    let resolve!: (value: unknown) => void;
    const saved = vi.fn();
    const api = new TopicsDouble()
      .on(readRoute, () => snapshot)
      .on(
        writeRoute,
        () =>
          new Promise((done) => {
            resolve = done;
          }),
      );
    const view = render(<OwnerPreferences client={api.client()} onSaved={saved} />);
    await userEvent.click(await screen.findByTestId('preferences-save'));
    api.generation += 1;
    view.unmount();
    resolve(snapshot);
    await waitFor(() => expect(saved).not.toHaveBeenCalled());
  });
});

it('shows actual inherited preferences, recorded empty no-send state and editor inside the dialog', async () => {
  const value = topic({
    runs: [{ state: 'empty', presentation: { emptyLabel: 'No new papers' }, sendLog: null }],
  });
  const api = new TopicsDouble()
    .on(`GET /api/v2/topics/${value.topicId}/settings`, () => value)
    .on(readRoute, () => snapshot);
  render(
    <DigestSettingsForm
      client={api.client()}
      topic={value}
      busy={false}
      onClose={vi.fn()}
      onSaved={vi.fn()}
      onUnsubscribe={vi.fn()}
      onError={vi.fn()}
    />,
  );
  expect(await screen.findByTestId('inherited-note')).toHaveTextContent(
    'English · 표준 (standard) · America/New_York',
  );
  expect(screen.getByTestId('inherited-note')).toHaveTextContent('기본값');
  expect(screen.getByTestId('digest-empty')).toHaveTextContent('메일을 보내지 않았어요');
  expect(screen.getByTestId('digest-preview')).toHaveTextContent('발송 기록 없음');
  await userEvent.click(screen.getByTestId('preferences-toggle'));
  expect(await screen.findByTestId('digest-language')).toHaveValue('en');
  await userEvent.click(screen.getByTestId('preferences-toggle'));
  expect(screen.queryByTestId('owner-preferences')).toBeNull();
});
