import React, { useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DraftControls } from '../../src/u4-research/drafts';
import type { DraftRevision } from '../../src/u4-research/api';
import { apiError, Double, policy } from './fixtures';
const saved: DraftRevision = {
  draft: { draftId: 'draft-a', revision: '1', contentHash: 'a'.repeat(64) },
  ownerId: 'owner-a',
  contextId: 'context-a',
  kind: 'research-question',
  parentRevision: null,
  text: '현재 질문',
  acknowledgedAt: '2026-10-16T00:00:00Z',
  policy,
};
function Editor({
  server,
  identity = 'draft-a',
  text: initial = '현재 질문',
  acknowledge = vi.fn(),
}: {
  server: Double;
  identity?: string;
  text?: string;
  acknowledge?: ReturnType<typeof vi.fn>;
}) {
  const [text, setText] = useState(initial);
  return (
    <>
      <textarea aria-label="편집" value={text} onChange={(e) => setText(e.target.value)} />
      <DraftControls
        client={server.client()}
        contextId="context-a"
        identity={identity}
        policy={policy}
        kind="research-question"
        text={text}
        onText={setText}
        onAcknowledged={acknowledge}
      />
    </>
  );
}
describe('acknowledged draft boundary', () => {
  it('suspended draft policy does not promise persistence or allocate identifiers', () => {
    const server = new Double();
    render(
      <DraftControls
        client={server.client()}
        contextId="context-a"
        policy={policy}
        kind="research-question"
        text="private text"
        onText={vi.fn()}
        onAcknowledged={vi.fn()}
      />,
    );
    expect(screen.getByText(/복구되지 않아요/)).toBeVisible();
    expect(screen.getByRole('button')).toBeDisabled();
    expect(server.calls).toHaveLength(0);
  });
  it('claims saved only after the acknowledgement, with exact base revision', async () => {
    let finish!: (value: unknown) => void;
    const acknowledge = vi.fn();
    const server = new Double().on(
      'save-draft',
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    render(<Editor server={server} acknowledge={acknowledge} />);
    await userEvent.click(screen.getByRole('button', { name: '초안 저장' }));
    expect(screen.getByText(/아직 복구를 보장하지/)).toBeVisible();
    expect(acknowledge).not.toHaveBeenCalled();
    finish({ outcome: 'saved', acknowledged: saved });
    await screen.findByText(/서버에서 저장을 확인/);
    expect(acknowledge).toHaveBeenCalledWith(saved.draft);
    expect(server.calls[0]!.body).toMatchObject({ baseRevision: null, text: saved.text });
    await userEvent.type(screen.getByLabelText('편집'), ' 수정');
    expect(screen.getByText(/수정은 저장되지/)).toBeVisible();
  });
  it('preserves proposed text after a conflicting save and lets the owner choose', async () => {
    const other = { ...saved, text: '다른 탭 저장본' };
    const server = new Double().on('save-draft', () => ({
      outcome: 'conflict',
      current: other,
      proposedText: saved.text,
      proposedBaseRevision: null,
    }));
    render(<Editor server={server} />);
    await userEvent.click(screen.getByRole('button', { name: '초안 저장' }));
    await screen.findByText('다른 탭 저장본');
    expect(screen.getByLabelText('편집')).toHaveValue(saved.text);
    await userEvent.click(screen.getByRole('button', { name: '현재 입력 유지' }));
    expect(screen.getByLabelText('편집')).toHaveValue(saved.text);
    expect(screen.queryByText('다른 탭 저장본')).toBeNull();
  });
  it('recovers an acknowledged draft without submitting a question', async () => {
    const server = new Double().on('restore-draft', () => ({
      state: 'recoverable',
      acknowledged: saved,
    }));
    render(<Editor server={server} text="" />);
    await userEvent.click(screen.getByRole('button', { name: '저장본 확인' }));
    await waitFor(() => expect(screen.getByLabelText('편집')).toHaveValue(saved.text));
    expect(server.calls.map((item) => item.name)).toEqual(['restore-draft']);
    expect(screen.getByText(/질문을 전송하지/)).toBeVisible();
  });
  it('does not overwrite local edits with a restored revision until explicitly selected', async () => {
    const server = new Double().on('restore-draft', () => ({
      state: 'recoverable',
      acknowledged: { ...saved, text: '복구된 질문' },
    }));
    render(<Editor server={server} />);
    await userEvent.click(screen.getByRole('button', { name: '저장본 확인' }));
    await screen.findByText('복구된 질문');
    expect(screen.getByLabelText('편집')).toHaveValue(saved.text);
    await userEvent.click(screen.getByRole('button', { name: '이 저장본 사용' }));
    expect(screen.getByLabelText('편집')).toHaveValue('복구된 질문');
  });
  it('discards only the confirmed revision and keeps local input visible', async () => {
    const server = new Double()
      .on('save-draft', () => ({ outcome: 'saved', acknowledged: saved }))
      .on('discard-draft', () => ({
        resourceId: 'draft-a',
        revision: '2',
        requestId: 'request-a',
      }));
    render(<Editor server={server} />);
    await userEvent.click(screen.getByRole('button', { name: '초안 저장' }));
    await screen.findByText(/서버에서 저장을 확인/);
    expect(screen.getByRole('button', { name: '확인한 초안 폐기' })).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: '확인한 초안 폐기' }));
    await screen.findByText(/현재 입력은 화면에 남아/);
    expect(server.calls[1]!.body).toMatchObject({ draft: saved.draft, confirmed: true });
    expect(screen.getByLabelText('편집')).toHaveValue(saved.text);
  });
  it('reports missing and failed recovery honestly without erasing unsent text', async () => {
    let failed = false;
    const server = new Double().on('restore-draft', () => {
      if (failed) throw apiError('POLICY_UNRESOLVED');
      return { state: 'expired', draftId: 'draft-a', reasonKey: 'draft.expired' };
    });
    render(<Editor server={server} />);
    await userEvent.click(screen.getByRole('button', { name: '저장본 확인' }));
    await screen.findByText('현재 복구할 저장본이 없어요');
    failed = true;
    await userEvent.click(screen.getByRole('button', { name: '저장본 확인' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('편집')).toHaveValue(saved.text);
  });
  it('rejects a recovered revision for another context', async () => {
    const server = new Double().on('restore-draft', () => ({
      state: 'recoverable',
      acknowledged: { ...saved, contextId: 'context-b' },
    }));
    const acknowledge = vi.fn();
    render(<Editor server={server} acknowledge={acknowledge} />);
    await userEvent.click(screen.getByRole('button', { name: '저장본 확인' }));
    await screen.findByRole('alert');
    expect(acknowledge).not.toHaveBeenCalled();
  });
  it('does not associate a late save receipt with newer unsent text', async () => {
    let finish!: (value: unknown) => void;
    const acknowledge = vi.fn();
    const server = new Double().on(
      'save-draft',
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    render(<Editor server={server} acknowledge={acknowledge} />);
    await userEvent.click(screen.getByRole('button', { name: '초안 저장' }));
    await userEvent.type(screen.getByLabelText('편집'), ' 새 수정');
    finish({ outcome: 'saved', acknowledged: saved });
    await screen.findByText(/서버에서 저장을 확인/);
    expect(acknowledge).toHaveBeenLastCalledWith(null);
    expect(screen.getByLabelText('편집')).toHaveValue('현재 질문 새 수정');
    expect(screen.getByText(/수정은 저장되지/)).toBeVisible();
  });
});
