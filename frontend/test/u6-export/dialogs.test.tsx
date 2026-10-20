/** The export dialogs: focus moves in, Tab is trapped, Escape closes, focus returns to
the trigger; the settle dialog shows its assumption and accepts only a Notion page link. */

import React, { useState } from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DisconnectDialog, SettleDialog } from '../../src/u6-export/dialogs';
import { SETTLE_ASSUMPTION_COPY } from '../../src/u6-export/copy';
import { historyEntry, PAGE_URL } from './fixtures';

function Harness({ onConfirm }: { onConfirm: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        연결 해제 열기
      </button>
      {open ? (
        <DisconnectDialog busy={false} onConfirm={onConfirm} onClose={() => setOpen(false)} />
      ) : null}
    </>
  );
}

describe('dialog shell', () => {
  it('moves focus in, traps Tab both ways, closes on Escape and returns focus', async () => {
    const onConfirm = vi.fn();
    render(<Harness onConfirm={onConfirm} />);
    const trigger = screen.getByRole('button', { name: '연결 해제 열기' });
    await userEvent.click(trigger);
    const dialog = screen.getByRole('dialog', { name: 'Notion 연결 해제' });
    expect(dialog.getAttribute('aria-modal')).toBe('true');
    const keep = screen.getByTestId('disconnect-keep');
    const confirm = screen.getByTestId('disconnect-confirm');
    expect(document.activeElement).toBe(keep);
    await userEvent.tab();
    expect(document.activeElement).toBe(confirm);
    await userEvent.tab();
    expect(document.activeElement).toBe(keep);
    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(confirm);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).toBeNull();
    await waitFor(() => expect(document.activeElement).toBe(trigger));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  function SettleHarness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          직접 확인 열기
        </button>
        {open ? (
          <SettleDialog
            entry={historyEntry()}
            busy={false}
            onSubmit={vi.fn()}
            onClose={() => setOpen(false)}
          />
        ) : null}
      </>
    );
  }

  async function openSettle() {
    render(<SettleHarness />);
    const trigger = screen.getByRole('button', { name: '직접 확인 열기' });
    await userEvent.click(trigger);
    return trigger;
  }

  it('cycles Tab and Shift+Tab over its own stops, an unchecked radio group being one', async () => {
    await openSettle();
    const delivered = screen.getByTestId('settle-delivered');
    const cancel = screen.getByTestId('settle-cancel');
    expect(document.activeElement).toBe(delivered);
    for (const expected of [cancel, delivered, cancel]) {
      await userEvent.tab();
      expect(document.activeElement).toBe(expected);
    }
    for (const expected of [delivered, cancel, delivered, cancel]) {
      await userEvent.tab({ shift: true });
      expect(document.activeElement).toBe(expected);
    }
  });

  it('makes the checked radio its group stop once a choice is made', async () => {
    await openSettle();
    const notDelivered = screen.getByTestId('settle-not-delivered');
    await userEvent.click(notDelivered);
    const cancel = screen.getByTestId('settle-cancel');
    const confirm = screen.getByTestId('settle-confirm');
    for (const expected of [cancel, confirm, notDelivered]) {
      await userEvent.tab();
      expect(document.activeElement).toBe(expected);
    }
    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(confirm);
  });

  it('takes focus back to where it was when the page moves it out while open', async () => {
    const trigger = await openSettle();
    const cancel = screen.getByTestId('settle-cancel');
    await userEvent.tab();
    expect(document.activeElement).toBe(cancel);
    act(() => trigger.focus());
    expect(document.activeElement).toBe(cancel);
  });

  it('keeps a Tab inside after focus dropped to the page body', async () => {
    await openSettle();
    act(() => (document.activeElement as HTMLElement).blur());
    expect(document.activeElement).toBe(document.body);
    await userEvent.tab();
    expect(screen.getByRole('dialog').contains(document.activeElement)).toBe(true);
  });
});

describe('settle dialog', () => {
  function settle() {
    const onSubmit = vi.fn();
    const onClose = vi.fn();
    render(
      <SettleDialog
        entry={historyEntry({ destinationTitle: '연구 노트', sourceTitle: '비교 결과' })}
        busy={false}
        onSubmit={onSubmit}
        onClose={onClose}
      />,
    );
    return { onSubmit, onClose };
  }

  it('names the destination and title and shows the assumption of the chosen answer', async () => {
    const { onSubmit } = settle();
    const dialog = screen.getByRole('dialog', { name: 'Notion에서 직접 확인' });
    expect(dialog.textContent).toContain('연구 노트');
    expect(dialog.textContent).toContain('비교 결과');
    expect(screen.getByTestId('settle-confirm')).toBeDisabled();
    expect(screen.queryByTestId('settle-assumption')).toBeNull();
    await userEvent.click(screen.getByTestId('settle-not-delivered'));
    expect(screen.getByTestId('settle-assumption').textContent).toBe(
      SETTLE_ASSUMPTION_COPY['not-delivered'],
    );
    await userEvent.click(screen.getByTestId('settle-delivered'));
    expect(screen.getByTestId('settle-assumption').textContent).toBe(
      SETTLE_ASSUMPTION_COPY.delivered,
    );
    await userEvent.click(screen.getByTestId('settle-confirm'));
    expect(onSubmit).toHaveBeenCalledWith({ disposition: 'delivered' });
  });

  it('refuses a link that is not a Notion page link and keeps what was typed', async () => {
    const { onSubmit } = settle();
    await userEvent.click(screen.getByTestId('settle-delivered'));
    const link = screen.getByTestId('settle-link') as HTMLInputElement;
    for (const bad of ['https://example.com/page', 'http://www.notion.so/x-' + 'a'.repeat(32)]) {
      await userEvent.clear(link);
      await userEvent.type(link, bad);
      await userEvent.click(screen.getByTestId('settle-confirm'));
      expect(screen.getByTestId('settle-link-error').textContent).toContain('Notion 페이지 링크');
      expect(link.getAttribute('aria-invalid')).toBe('true');
      expect(link.value).toBe(bad);
    }
    expect(onSubmit).not.toHaveBeenCalled();
    await userEvent.clear(link);
    await userEvent.type(link, PAGE_URL);
    await userEvent.click(screen.getByTestId('settle-confirm'));
    expect(onSubmit).toHaveBeenCalledWith({ disposition: 'delivered', remoteUrl: PAGE_URL });
  });

  it('closes with Escape and the close button', async () => {
    const { onClose } = settle();
    await userEvent.keyboard('{Escape}');
    await userEvent.click(screen.getByTestId('settle-cancel'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
