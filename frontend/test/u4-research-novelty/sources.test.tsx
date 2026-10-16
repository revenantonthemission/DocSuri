import React, { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AttachmentControls, SourceControls } from '../../src/u4-research/sources';
import { apiError, Double, policy, scope } from './fixtures';
function Sources({ server }: { server: Double }) {
  const [value, setValue] = useState(scope);
  return <SourceControls client={server.client()} scope={value} onChange={setValue} />;
}
describe('explicit permitted source scope', () => {
  it('stops adding at the bound two-paper and eight-link policy limits', async () => {
    const server = new Double();
    const full = {
      ...scope,
      publicPapers: [1, 2].map((id) => ({
        paperId: `paper-${id}`,
        versionId: 'v1',
        eligibilityRevision: '1',
      })),
      webReferences: Array.from({ length: 8 }, (_, i) => `https://example.org/${i}`),
    };
    render(<SourceControls client={server.client()} scope={full} onChange={vi.fn()} />);
    await userEvent.click(screen.getByText(/근거 범위/));
    await userEvent.type(screen.getByLabelText('논문 주소 또는 식별자'), 'third-paper');
    await userEvent.type(screen.getByLabelText('웹 참고 링크'), 'https://example.org/ninth');
    expect(screen.getByRole('button', { name: '논문 범위에 추가' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '참고 링크 추가' })).toBeDisabled();
    expect(server.calls).toHaveLength(0);
  });
  it('resolves a public paper before adding its authoritative identity and version', async () => {
    const server = new Double().on('resolve-paper', () => ({
      paper: { paperId: 'paper-a', versionId: 'v2', eligibilityRevision: '2' },
      requestedIdentifier: 'paper',
      canonicalDisposition: 'canonical',
      metadataRevision: '1',
      title: 'A paper',
      sourceUrls: [],
      policy,
    }));
    render(<Sources server={server} />);
    await userEvent.click(screen.getByText(/근거 범위/));
    await userEvent.type(screen.getByLabelText('논문 주소 또는 식별자'), 'paper');
    await userEvent.click(screen.getByRole('button', { name: '논문 범위에 추가' }));
    expect(await screen.findByText(/paper-a · v2/)).toBeVisible();
    expect(server.calls[0]!.body).toEqual({ identifier: 'paper' });
    await userEvent.click(screen.getByRole('button', { name: 'paper-a 범위에서 제외' }));
    expect(screen.queryByText(/paper-a · v2/)).toBeNull();
  });
  it('deduplicates the same paper version', async () => {
    const server = new Double().on('resolve-paper', () => ({
      paper: { paperId: 'paper-a', versionId: 'v1', eligibilityRevision: '1' },
    }));
    render(<Sources server={server} />);
    await userEvent.click(screen.getByText(/근거 범위/));
    for (let i = 0; i < 2; i++) {
      await userEvent.type(screen.getByLabelText('논문 주소 또는 식별자'), 'paper');
      await userEvent.click(screen.getByRole('button', { name: '논문 범위에 추가' }));
    }
    expect(screen.getAllByRole('button', { name: 'paper-a 범위에서 제외' })).toHaveLength(1);
  });
  it('keeps the identifier on a failed resolution without claiming the paper was added', async () => {
    const server = new Double().on('resolve-paper', () => {
      throw apiError('SOURCE_INELIGIBLE');
    });
    render(<Sources server={server} />);
    await userEvent.click(screen.getByText(/근거 범위/));
    await userEvent.type(screen.getByLabelText('논문 주소 또는 식별자'), 'withdrawn');
    await userEvent.click(screen.getByRole('button', { name: '논문 범위에 추가' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('논문 주소 또는 식별자')).toHaveValue('withdrawn');
  });
  it('adds and removes a web reference without fetching it or claiming it was read', async () => {
    const server = new Double();
    render(<Sources server={server} />);
    await userEvent.click(screen.getByText(/근거 범위/));
    await userEvent.type(screen.getByLabelText('웹 참고 링크'), 'https://example.org/reference');
    await userEvent.click(screen.getByRole('button', { name: '참고 링크 추가' }));
    expect(screen.getByText(/읽은 근거로 간주하지/)).toBeVisible();
    expect(server.calls).toHaveLength(0);
    await userEvent.click(
      screen.getByRole('button', { name: 'https://example.org/reference 범위에서 제외' }),
    );
    expect(screen.queryByText('https://example.org/reference')).toBeNull();
  });
  it('refuses malformed, executable and credential-bearing references locally', async () => {
    render(<Sources server={new Double()} />);
    await userEvent.click(screen.getByText(/근거 범위/));
    for (const value of ['javascript:alert(1)', 'https://user:secret@example.org/', 'bad-url']) {
      await userEvent.clear(screen.getByLabelText('웹 참고 링크'));
      await userEvent.type(screen.getByLabelText('웹 참고 링크'), value);
      await userEvent.click(screen.getByRole('button', { name: '참고 링크 추가' }));
      expect(screen.getByRole('alert')).toHaveTextContent('HTTP 또는 HTTPS');
    }
  });
  it('policy-suspended attachment controls neither read bytes nor create permits', async () => {
    const server = new Double();
    render(<AttachmentControls client={server.client()} scope={scope} />);
    await userEvent.click(screen.getByText('비공개 첨부 자료'));
    expect(screen.getByLabelText('원고 파일')).toBeDisabled();
    expect(screen.getByText(/파일을 읽거나 전송하지/)).toBeVisible();
    expect(server.calls).toHaveLength(0);
  });
  it('reads an existing attachment using its exact owner context and reports partial extraction', async () => {
    const server = new Double().on('read-private-attachment', () => ({
      attachmentId: 'attachment-a',
      ownerId: 'owner-a',
      contextId: scope.contextId,
      revision: '1',
      contentHash: 'a'.repeat(64),
      state: 'partial',
      assetIds: [],
      limitations: ['일부 페이지는 읽지 못함'],
    }));
    render(
      <AttachmentControls
        client={server.client()}
        scope={{ ...scope, attachmentIds: ['attachment-a'] }}
      />,
    );
    await userEvent.click(screen.getByText('비공개 첨부 자료'));
    await userEvent.click(screen.getByRole('button', { name: '첨부 자료 1 상태 확인' }));
    expect(await screen.findByText('일부 추출됨')).toBeVisible();
    expect(screen.getByText('일부 페이지는 읽지 못함')).toBeVisible();
    expect(server.calls[0]!.body).toEqual({
      contextId: scope.contextId,
      attachmentId: 'attachment-a',
    });
  });
});
