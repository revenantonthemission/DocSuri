// U8 plan Step 18 (your decision of 2026-10-22, BR2.5): the account page's progress view
// lists each part kept by policy, with the date it is gone when the participant gave one.
import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SWRConfig } from 'swr';
import { LifecycleProgress } from '../../src/account-controls';
import type { Transport } from '../../src/api';

const RETAINED_UNTIL = '2026-11-05T03:00:00Z';
const formatted = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'long' }).format(
  new Date(RETAINED_UNTIL),
);

function status(scopes: Record<string, unknown>[]) {
  return {
    lifecycleRequestId: 'life-erase',
    accountId: 'account-a',
    action: 'erase',
    state: 'accepted',
    revocation: 'effective',
    participants: [
      {
        participantId: 'Library',
        state: 'acknowledged',
        scopes: [
          {
            scope: 'live_records',
            disposition: 'erased',
            reasonKey: 'erased',
            evidenceReference: 'evidence-library',
          },
        ],
      },
      { participantId: 'ServiceOperations', state: 'pending', scopes },
    ],
  };
}

function client(value: unknown) {
  const read = vi.fn().mockResolvedValue(value);
  const post = vi.fn();
  return { transport: { read, post } as unknown as Transport, read, post };
}

function mount(value: unknown) {
  const fake = client(value);
  render(
    <SWRConfig value={{ provider: () => new Map() }}>
      <LifecycleProgress client={fake.transport} id="life-erase" />
    </SWRConfig>,
  );
  return fake;
}

const backups = {
  scope: 'backups',
  disposition: 'retained_by_policy',
  reasonKey: 'backups-retained-until-disposal',
  evidenceReference: 'evidence-backups',
  retainedUntil: RETAINED_UNTIL,
};
const enforcement = {
  scope: 'restore_enforcement',
  disposition: 'blocked',
  reasonKey: 'restore-verification-pending',
};

describe('the progress view lists each part kept by policy', () => {
  it('shows the backups part as kept by policy until its date', async () => {
    const fake = mount(status([backups, enforcement]));
    const list = await screen.findByRole('list', { name: '정책에 따라 보관되는 부분이 있어요' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(1);
    expect(items[0]).toHaveTextContent(`ServiceOperations · 백업: ${formatted}까지 보관돼요`);
    expect(fake.read).toHaveBeenCalledWith('/api/v2/c02/lifecycle-inspect', {
      lifecycleRequestId: 'life-erase',
    });
    expect(fake.post).not.toHaveBeenCalled();
  });

  it('shows a part kept by policy without a date as kept for its set period', async () => {
    const copies = {
      scope: 'external_copies',
      disposition: 'retained_by_policy',
      reasonKey: 'external-copies-retained-by-owner',
      evidenceReference: 'evidence-copies',
    };
    mount(status([backups, copies]));
    const list = await screen.findByRole('list', { name: '정책에 따라 보관되는 부분이 있어요' });
    const items = within(list).getAllByRole('listitem');
    expect(items.map((item) => item.textContent)).toEqual([
      `ServiceOperations · 백업: ${formatted}까지 보관돼요`,
      'ServiceOperations · 외부로 내보낸 사본: 정해진 보관 기간 동안 보관돼요',
    ]);
  });

  it('lists nothing kept by policy when no part is, or when scopes are absent', async () => {
    mount({ ...status([enforcement]), participants: [{ participantId: 'Library', state: 'x' }] });
    expect(await screen.findByText(/아직 완료되지/)).toBeVisible();
    expect(screen.queryByText('정책에 따라 보관되는 부분이 있어요')).toBeNull();
  });

  it('names an unlisted scope by its identifier', async () => {
    mount(status([{ ...backups, scope: 'future_scope', retainedUntil: undefined }]));
    const list = await screen.findByRole('list', { name: '정책에 따라 보관되는 부분이 있어요' });
    expect(within(list).getByRole('listitem')).toHaveTextContent(
      'ServiceOperations · future_scope: 정해진 보관 기간 동안 보관돼요',
    );
  });
});
