/** OutcomeStep (BR2.2, BR3.3, BR3.6, BR4.4, BR4.7): polling read-effect until the
export ends, one announcement per change, the success link and "직접 확인됨". */

import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { OutcomeStep } from '../../src/u6-export/outcome-step';
import { SIGN_OUT_NOTE } from '../../src/u6-export/copy';
import type { Effect } from '../../src/u6-export/api';
import { approval, effect, envelope, ExportDouble, mount, PAGE_URL } from './fixtures';

function outcome(api: ExportDouble, initial: Effect, onFreshPreview = vi.fn()) {
  const announce = vi.fn();
  mount(
    <OutcomeStep
      client={api.client()}
      initial={initial}
      pageTitle="읽은 범위의 연구 비교"
      announce={announce}
      onFreshPreview={onFreshPreview}
      pollMs={15}
    />,
  );
  return { announce, onFreshPreview };
}

describe('polling', () => {
  it('announces each change once and stops polling when the export ends', async () => {
    const sequence: Effect[] = [
      effect({ state: 'executing', revision: '2' }),
      effect({ state: 'executing', revision: '2' }),
      effect({
        state: 'succeeded',
        revision: '3',
        remoteReference: 'f'.repeat(32),
        remoteUrl: PAGE_URL,
        settledBy: 'provider',
      }),
    ];
    const api = new ExportDouble().on(
      'read-export-effect',
      () =>
        sequence.shift() ??
        effect({
          state: 'succeeded',
          revision: '3',
          remoteReference: 'f'.repeat(32),
          remoteUrl: PAGE_URL,
          settledBy: 'provider',
        }),
    );
    const { announce } = outcome(api, effect());
    expect(screen.getByTestId('outcome-signout-note').textContent).toBe(SIGN_OUT_NOTE);
    await screen.findByTestId('outcome-page-link');
    const reads = api.named('read-export-effect').length;
    await new Promise((resolve) => setTimeout(resolve, 80));
    expect(api.named('read-export-effect')).toHaveLength(reads);
    expect(announce.mock.calls.map(([text]) => text)).toEqual([
      '내보내기 상태: 내보내는 중',
      '내보내기 상태: 내보냈습니다',
    ]);
    expect(api.mutations()).toEqual([]);
    expect(api.named('read-export-effect')[0]!.body).toEqual({ effectId: effect().effectId });
  });

  it('names the success link by the page title', async () => {
    const api = new ExportDouble();
    outcome(
      api,
      effect({ state: 'succeeded', remoteReference: 'f'.repeat(32), remoteUrl: PAGE_URL }),
    );
    const link = screen.getByTestId('outcome-page-link');
    expect(link.textContent).toContain('읽은 범위의 연구 비교');
    expect(link.getAttribute('href')).toBe(PAGE_URL);
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    expect(screen.getByTestId('outcome-status').textContent).toContain('✓');
  });
});

describe('an owner-settled success', () => {
  it('shows the owner link labelled 직접 확인됨 when one was supplied', () => {
    outcome(
      new ExportDouble(),
      effect({
        state: 'succeeded',
        remoteReference: 'f'.repeat(32),
        remoteUrl: PAGE_URL,
        settledBy: 'owner',
        outcomeReason: 'owner-settled-delivered',
      }),
    );
    expect(screen.getByTestId('outcome-owner-confirmed').textContent).toBe('직접 확인됨');
    expect(screen.getByTestId('outcome-page-link').textContent).toContain('직접 확인됨');
  });

  it('shows no link when the owner supplied none', () => {
    outcome(
      new ExportDouble(),
      effect({
        state: 'succeeded',
        settledBy: 'owner',
        outcomeReason: 'owner-settled-delivered',
      }),
    );
    expect(screen.getByTestId('outcome-owner-confirmed').textContent).toBe('직접 확인됨');
    expect(screen.queryByTestId('outcome-page-link')).toBeNull();
  });
});

describe('states before and after the write', () => {
  it('cancels an accepted export by its effect revision', async () => {
    let cancelled = false;
    const api = new ExportDouble()
      .on('cancel-export-approval', () => {
        cancelled = true;
        return approval({ state: 'consumed' });
      })
      .on('read-export-effect', () =>
        cancelled
          ? effect({ state: 'cancelled', revision: '3', outcomeReason: 'owner-cancelled' })
          : effect({ revision: '2' }),
      );
    outcome(api, effect({ revision: '2' }));
    await userEvent.click(screen.getByTestId('outcome-cancel'));
    await waitFor(() =>
      expect(screen.getByTestId('outcome-status').textContent).toContain('취소했습니다'),
    );
    expect(api.named('cancel-export-approval')[0]!.body).toEqual({
      approvalId: effect().approvalId,
      expectedRevision: '2',
    });
    expect(screen.queryByTestId('outcome-cancel')).toBeNull();
  });

  it('cancels once more at the newer revision while the export is still accepted', async () => {
    // The lane marked the accepted export as waiting, which advanced its revision.
    let cancelled = false;
    const api = new ExportDouble()
      .on('cancel-export-approval', (body) => {
        if ((body as { expectedRevision: string }).expectedRevision !== '3')
          throw envelope('CONFLICT');
        cancelled = true;
        return approval({ state: 'consumed' });
      })
      .on('read-export-effect', () =>
        cancelled
          ? effect({ state: 'cancelled', revision: '4', outcomeReason: 'owner-cancelled' })
          : effect({ revision: '3' }),
      );
    outcome(api, effect({ revision: '2' }));
    await userEvent.click(screen.getByTestId('outcome-cancel'));
    await waitFor(() =>
      expect(screen.getByTestId('outcome-status').textContent).toContain('취소했습니다'),
    );
    expect(
      api.named('cancel-export-approval').map((call) => call.body as { expectedRevision: string }),
    ).toEqual([
      { approvalId: effect().approvalId, expectedRevision: '2' },
      { approvalId: effect().approvalId, expectedRevision: '3' },
    ]);
    expect(screen.queryByTestId('outcome-notice')).toBeNull();
  });

  it('says plainly when the export already started and cannot be cancelled', async () => {
    const api = new ExportDouble()
      .on('cancel-export-approval', () => {
        throw envelope('CONFLICT');
      })
      .on('read-export-effect', () => effect({ state: 'executing', revision: '3' }));
    outcome(api, effect({ revision: '2' }));
    await userEvent.click(screen.getByTestId('outcome-cancel'));
    expect((await screen.findByTestId('outcome-notice')).textContent).toContain(
      '취소할 수 없습니다',
    );
  });

  it('shows the next check time for an unknown export', () => {
    outcome(
      new ExportDouble().on('read-export-effect', () =>
        effect({ state: 'unknown', nextCheckAt: '2026-10-20T03:00:00+00:00' }),
      ),
      effect({ state: 'unknown', nextCheckAt: '2026-10-20T03:00:00+00:00' }),
    );
    const note = screen.getByTestId('outcome-next-check');
    expect(note.textContent).toContain('다음 확인');
    expect(note.textContent).toContain('다시 할 수 없습니다');
    expect(screen.queryByTestId('outcome-cancel')).toBeNull();
  });

  it('offers a fresh preview for an invalidated export with its reason and hint', async () => {
    const { onFreshPreview } = outcome(
      new ExportDouble(),
      effect({ state: 'invalidated', outcomeReason: 'source-changed' }),
    );
    expect(screen.getByTestId('outcome-reason').textContent).toBe('분석 결과가 바뀌었습니다');
    await userEvent.click(screen.getByTestId('outcome-fresh-preview'));
    expect(onFreshPreview).toHaveBeenCalled();
  });

  it('shows the hint for a refused first write', () => {
    outcome(new ExportDouble(), effect({ state: 'failed', outcomeReason: 'no-access' }));
    expect(screen.getByText(/콘텐츠 삽입\(Insert content\) 권한/)).toBeInTheDocument();
  });
});
