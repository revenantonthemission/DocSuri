/** ExportHistory (A2, BR3.6, BR3.7, BR4.5, BR4.7): actions by state, continue as the
earlier press, cancel's two expected revisions, settlement through the dialog and the
owner-settled label. */

import React from 'react';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ExportHistory } from '../../src/u6-export/history';
import { FRESH_PREVIEW_GUIDE, IN_FLIGHT, STALE_BINDING } from '../../src/u6-export/copy';
import type { HistoryEntry } from '../../src/u6-export/api';
import {
  approval,
  EFFECT_ID,
  effect,
  envelope,
  ExportDouble,
  historyEntry,
  historyPage,
  mount,
  PAGE_URL,
} from './fixtures';

function history(api: ExportDouble, entries: HistoryEntry[]) {
  const onChanged = vi.fn();
  const announce = vi.fn();
  mount(
    <ExportHistory
      client={api.client()}
      page={historyPage(entries)}
      hasPrevious={false}
      onNext={vi.fn()}
      onPrevious={vi.fn()}
      onChanged={onChanged}
      announce={announce}
    />,
  );
  return { onChanged, announce };
}

const accepted = historyEntry({
  state: 'consumed',
  effect: {
    effectId: EFFECT_ID,
    state: 'accepted',
    revision: '2',
    possibleDuplicates: [],
    settlementOffered: false,
  },
});
const unknownOffered = historyEntry({
  state: 'consumed',
  effect: {
    effectId: EFFECT_ID,
    state: 'unknown',
    revision: '4',
    possibleDuplicates: [{ remoteReference: 'f'.repeat(32), remoteUrl: PAGE_URL }],
    settlementOffered: true,
    nextCheckAt: '2026-10-20T03:00:00+00:00',
  },
});

describe('actions by state', () => {
  it('offers continue and cancel for a continuable approval not yet started', () => {
    history(new ExportDouble(), [historyEntry()]);
    expect(screen.getByTestId('history-continue')).toBeInTheDocument();
    expect(screen.getByTestId('history-cancel')).toBeInTheDocument();
    expect(screen.queryByTestId('history-settle')).toBeNull();
    expect(screen.getByTestId('history-status').textContent).toContain('아직 시작 전');
  });

  it('offers a fresh preview instead of continue when the approving session ended', async () => {
    const { announce } = history(new ExportDouble(), [historyEntry({ continuable: false })]);
    expect(screen.queryByTestId('history-continue')).toBeNull();
    await userEvent.click(screen.getByTestId('history-fresh-preview'));
    expect(screen.getByTestId('history-notice').textContent).toBe(FRESH_PREVIEW_GUIDE);
    expect(announce).toHaveBeenCalledWith(FRESH_PREVIEW_GUIDE);
  });

  it('shows an invalidated approval with its reason and a fresh preview', () => {
    history(new ExportDouble(), [
      historyEntry({ state: 'invalidated', invalidationReason: 'connection-changed' }),
    ]);
    expect(screen.getByTestId('history-reason').textContent).toBe('Notion 연결이 바뀌었습니다');
    expect(screen.getByTestId('history-fresh-preview')).toBeInTheDocument();
    expect(screen.queryByTestId('history-cancel')).toBeNull();
  });

  it('offers settlement only when the entry says it is offered, with duplicates and next check', () => {
    history(new ExportDouble(), [
      unknownOffered,
      historyEntry({
        approvalId: '88888888-8888-4888-8888-888888888888',
        state: 'consumed',
        effect: { ...unknownOffered.effect!, settlementOffered: false },
      }),
    ]);
    const [offered, waiting] = screen.getAllByTestId('history-row');
    expect(within(offered!).getByTestId('history-settle')).toBeInTheDocument();
    expect(within(offered!).getByTestId('history-duplicates').textContent).toContain('중복');
    expect(within(waiting!).queryByTestId('history-settle')).toBeNull();
    expect(within(waiting!).getByTestId('history-next-check').textContent).toContain('다음 확인');
  });

  it('labels an owner-settled success and links only when the owner gave a link', () => {
    history(new ExportDouble(), [
      historyEntry({
        state: 'consumed',
        effect: {
          effectId: EFFECT_ID,
          state: 'succeeded',
          revision: '5',
          possibleDuplicates: [],
          settlementOffered: false,
          settledBy: 'owner',
          remoteUrl: PAGE_URL,
          outcomeReason: 'owner-settled-delivered',
        },
      }),
      historyEntry({
        approvalId: '88888888-8888-4888-8888-888888888888',
        state: 'consumed',
        effect: {
          effectId: '99999999-9999-4999-8999-999999999999',
          state: 'succeeded',
          revision: '5',
          possibleDuplicates: [],
          settlementOffered: false,
          settledBy: 'owner',
          outcomeReason: 'owner-settled-delivered',
        },
      }),
    ]);
    const [linked, unlinked] = screen.getAllByTestId('history-row');
    expect(within(linked!).getByTestId('history-owner-confirmed').textContent).toBe('직접 확인됨');
    expect(within(linked!).getByTestId('history-page-link').getAttribute('href')).toBe(PAGE_URL);
    expect(within(unlinked!).getByTestId('history-owner-confirmed').textContent).toBe(
      '직접 확인됨',
    );
    expect(within(unlinked!).queryByTestId('history-page-link')).toBeNull();
  });

  it('says there is no history yet', () => {
    history(new ExportDouble(), []);
    expect(screen.getByTestId('history-empty')).toBeInTheDocument();
  });
});

describe('continue (BR3.7)', () => {
  it('executes the existing approval with a key it keeps for a retry', async () => {
    let lose = true;
    const api = new ExportDouble().on('execute-approved-export', () => {
      if (lose) {
        lose = false;
        throw envelope('UNKNOWN_OUTCOME', 0);
      }
      return effect();
    });
    const { onChanged } = history(api, [historyEntry()]);
    await userEvent.click(screen.getByTestId('history-continue'));
    await screen.findByTestId('history-notice');
    await userEvent.click(screen.getByTestId('history-continue'));
    await waitFor(() =>
      expect(screen.getByTestId('history-notice').textContent).toContain('이어서 시작했습니다'),
    );
    const [first, second] = api.named('execute-approved-export');
    expect(first!.key).toBe(second!.key);
    expect(first!.body).toEqual({
      approvalId: historyEntry().approvalId,
      bindingHash: historyEntry().bindingHash,
    });
    expect(api.named('approve-export-preview')).toHaveLength(0);
    expect(onChanged).toHaveBeenCalled();
  });

  it('shows continue refusals in plain words', async () => {
    const answers = [
      envelope('CAPACITY_EXHAUSTED', 429),
      envelope('CAPACITY_EXHAUSTED', 429, { retryAfterSeconds: 120 }),
      envelope('APPROVAL_REQUIRED'),
      envelope('OUTCOME_UNKNOWN'),
      envelope('SOURCE_INELIGIBLE', 403),
    ];
    const api = new ExportDouble().on('execute-approved-export', () => {
      throw answers.shift();
    });
    history(api, [historyEntry()]);
    const texts: string[] = [];
    for (let index = 0; index < 5; index += 1) {
      await userEvent.click(screen.getByTestId('history-continue'));
      await waitFor(() => expect(api.named('execute-approved-export')).toHaveLength(index + 1));
      await waitFor(() => expect(screen.getByTestId('history-continue')).not.toBeDisabled());
      texts.push(screen.getByTestId('history-notice').textContent ?? '');
    }
    expect(texts[0]).toBe(IN_FLIGHT);
    expect(texts[1]).toContain('부터 다시 내보낼 수 있습니다');
    expect(texts[2]).toBe(STALE_BINDING);
    expect(texts[3]).toContain('확인 중');
    expect(texts[4]).toBe('이 자료는 이 작업에 사용할 수 없어요');
  });
});

describe('cancel (BR3.6, A10)', () => {
  it('expects the preview revision for an approval not yet started', async () => {
    const api = new ExportDouble().on('cancel-export-approval', () =>
      approval({ state: 'cancelled' }),
    );
    history(api, [historyEntry({ previewRevision: '3' })]);
    await userEvent.click(screen.getByTestId('history-cancel'));
    await screen.findByText(/취소했습니다/, { selector: '[data-testid="history-notice"]' });
    expect(api.named('cancel-export-approval')[0]!.body).toEqual({
      approvalId: historyEntry().approvalId,
      expectedRevision: '3',
    });
  });

  it('expects the effect revision for an accepted export and reports a moved state', async () => {
    const api = new ExportDouble()
      .on('cancel-export-approval', () => {
        throw envelope('CONFLICT');
      })
      .on('read-export-effect', () => effect({ state: 'executing', revision: '3' }));
    history(api, [accepted]);
    await userEvent.click(screen.getByTestId('history-cancel'));
    expect((await screen.findByTestId('history-notice')).textContent).toContain(
      '이미 상태가 바뀌었습니다',
    );
    expect(api.named('cancel-export-approval')).toHaveLength(1);
    expect(api.named('cancel-export-approval')[0]!.body).toMatchObject({ expectedRevision: '2' });
  });

  it('cancels once more at the newer revision while the export is still accepted', async () => {
    // The lane marked the accepted export as waiting, which advanced its revision.
    const api = new ExportDouble()
      .on('cancel-export-approval', (body) => {
        if ((body as { expectedRevision: string }).expectedRevision !== '3')
          throw envelope('CONFLICT');
        return approval({ state: 'consumed' });
      })
      .on('read-export-effect', () => effect({ revision: '3' }));
    const { onChanged } = history(api, [accepted]);
    await userEvent.click(screen.getByTestId('history-cancel'));
    expect((await screen.findByTestId('history-notice')).textContent).toContain('취소했습니다');
    expect(
      api.named('cancel-export-approval').map((call) => call.body as { expectedRevision: string }),
    ).toEqual([
      { approvalId: accepted.approvalId, expectedRevision: '2' },
      { approvalId: accepted.approvalId, expectedRevision: '3' },
    ]);
    expect(api.named('read-export-effect')[0]!.body).toEqual({ effectId: EFFECT_ID });
    expect(onChanged).toHaveBeenCalled();
    expect(api.violations).toEqual([]);
  });

  it('does not re-read for an approval not yet started that answers CONFLICT', async () => {
    const api = new ExportDouble().on('cancel-export-approval', () => {
      throw envelope('CONFLICT');
    });
    history(api, [historyEntry({ previewRevision: '3' })]);
    await userEvent.click(screen.getByTestId('history-cancel'));
    expect((await screen.findByTestId('history-notice')).textContent).toContain(
      '이미 상태가 바뀌었습니다',
    );
    expect(api.named('read-export-effect')).toHaveLength(0);
    expect(api.named('cancel-export-approval')).toHaveLength(1);
  });
});

describe('settle (BR4.5)', () => {
  it('records a delivered settlement with the owner link and its assumption', async () => {
    const api = new ExportDouble().on('settle-export-effect', () =>
      effect({ state: 'succeeded', revision: '5', settledBy: 'owner', remoteUrl: PAGE_URL }),
    );
    history(api, [unknownOffered]);
    await userEvent.click(screen.getByTestId('history-settle'));
    const dialog = screen.getByTestId('settle-dialog');
    await userEvent.click(within(dialog).getByTestId('settle-delivered'));
    await userEvent.type(within(dialog).getByTestId('settle-link'), PAGE_URL);
    await userEvent.click(within(dialog).getByTestId('settle-confirm'));
    await waitFor(() => expect(screen.queryByTestId('settle-dialog')).toBeNull());
    const [call] = api.named('settle-export-effect');
    expect(call!.body).toEqual({
      effectId: EFFECT_ID,
      expectedRevision: '4',
      disposition: 'delivered',
      assumptionAccepted: true,
      remoteUrl: PAGE_URL,
    });
    expect(call!.key).toMatch(/^[0-9a-f-]{36}$/);
    expect(screen.getByTestId('history-notice').textContent).toContain('내보낸 것으로');
  });

  it('records a not-delivered settlement without a link', async () => {
    const api = new ExportDouble().on('settle-export-effect', () =>
      effect({ state: 'failed', revision: '5', settledBy: 'owner' }),
    );
    history(api, [unknownOffered]);
    await userEvent.click(screen.getByTestId('history-settle'));
    await userEvent.click(screen.getByTestId('settle-not-delivered'));
    await userEvent.click(screen.getByTestId('settle-confirm'));
    await waitFor(() => expect(api.named('settle-export-effect')).toHaveLength(1));
    expect(api.named('settle-export-effect')[0]!.body).not.toHaveProperty('remoteUrl');
  });

  it('closes the dialog and reports a moved state on CONFLICT', async () => {
    const api = new ExportDouble().on('settle-export-effect', () => {
      throw envelope('CONFLICT');
    });
    history(api, [unknownOffered]);
    await userEvent.click(screen.getByTestId('history-settle'));
    await userEvent.click(screen.getByTestId('settle-not-delivered'));
    await userEvent.click(screen.getByTestId('settle-confirm'));
    await waitFor(() => expect(screen.queryByTestId('settle-dialog')).toBeNull());
    expect(screen.getByTestId('history-notice').textContent).toContain('이미 상태가 바뀌었습니다');
    expect(api.violations).toEqual([]);
  });
});
