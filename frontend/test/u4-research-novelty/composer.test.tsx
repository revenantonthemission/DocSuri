import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { NoveltyDiscussion, ResearchComposer } from '../../src/u4-research/composer';
import { apiError, artifact, Double, policy, receipt, scope, session } from './fixtures';
describe('intentful research and novelty submission', () => {
  it.each(['research', 'novelty', 'discussion'] as const)(
    'applies the UTF-8 byte boundary to %s without truncating or transmitting oversized input',
    async (purpose) => {
      const operation =
        purpose === 'research'
          ? 'accept-research-turn'
          : purpose === 'novelty'
            ? 'accept-novelty-analysis'
            : 'accept-novelty-discussion';
      const server = new Double().on(operation, () => receipt);
      const onAccepted = vi.fn();
      render(
        purpose === 'discussion' ? (
          <NoveltyDiscussion
            client={server.client()}
            source={artifact}
            policy={policy}
            onAccepted={onAccepted}
          />
        ) : (
          <ResearchComposer
            client={server.client()}
            purpose={purpose}
            scope={scope}
            session={session}
            policy={policy}
            onAccepted={onAccepted}
          />
        ),
      );
      const input = screen.getByRole('textbox', {
        name:
          purpose === 'research'
            ? '연구 질문'
            : purpose === 'novelty'
              ? '분석할 주제 또는 원고 설명'
              : '결과에 대한 질문',
      });
      const button = screen.getByRole('button', {
        name:
          purpose === 'research'
            ? '질문 보내기'
            : purpose === 'novelty'
              ? '참신성 분석 시작'
              : '결과에 대해 질문 보내기',
      });
      const oversized = '한'.repeat(10_923);
      fireEvent.change(input, { target: { value: oversized } });
      expect(input).toHaveValue(oversized);
      expect(input).toHaveAttribute('aria-invalid', 'true');
      expect(screen.getByRole('alert')).toHaveTextContent('32769 / 32768 UTF-8');
      expect(button).toBeDisabled();
      fireEvent.submit(input.closest('form')!);
      expect(server.calls).toHaveLength(0);
      const exact = '한'.repeat(10_922) + 'aa';
      fireEvent.change(input, { target: { value: exact } });
      expect(input).toHaveAttribute('aria-invalid', 'false');
      await userEvent.click(button);
      await waitFor(() => expect(onAccepted).toHaveBeenCalledOnce());
      expect(server.calls[0]!.body).toMatchObject({ text: exact });
    },
  );
  it('does no write while composing; submits exact text/scope only on explicit action', async () => {
    const server = new Double().on('accept-research-turn', () => receipt);
    const onAccepted = vi.fn();
    render(
      <ResearchComposer
        client={server.client()}
        purpose="research"
        scope={scope}
        session={session}
        policy={policy}
        onAccepted={onAccepted}
      />,
    );
    expect(screen.getByRole('button', { name: '질문 보내기' })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('연구 질문'), '근거를 비교해 주세요');
    expect(server.calls).toHaveLength(0);
    await userEvent.selectOptions(screen.getByLabelText('질문 방식'), 'compare');
    await userEvent.click(screen.getByRole('button', { name: '질문 보내기' }));
    await waitFor(() =>
      expect(onAccepted).toHaveBeenCalledWith({
        jobId: receipt.jobId,
        contextId: scope.contextId,
        kind: 'research-turn',
      }),
    );
    expect(server.calls[0]!.body).toEqual({
      sessionId: session.sessionId,
      scope,
      mode: 'compare',
      text: '근거를 비교해 주세요',
      policy,
    });
    expect(screen.getByLabelText('연구 질문')).toHaveValue('');
  });
  it('retains input on refusal and sends quote mode without pretending it succeeded', async () => {
    const server = new Double().on('accept-research-turn', () => {
      throw apiError('POLICY_UNRESOLVED');
    });
    render(
      <ResearchComposer
        client={server.client()}
        purpose="research"
        scope={scope}
        session={session}
        policy={policy}
        onAccepted={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByLabelText('연구 질문'), '인용해 주세요');
    await userEvent.selectOptions(screen.getByLabelText('질문 방식'), 'quote');
    await userEvent.click(screen.getByRole('button', { name: '질문 보내기' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('연구 질문')).toHaveValue('인용해 주세요');
    expect(server.calls[0]!.body).toMatchObject({ mode: 'quote' });
  });
  it('lost acknowledgement never auto-replays; explicit recovery keeps the original key/body', async () => {
    let count = 0;
    const server = new Double().on('accept-research-turn', () => {
      if (++count === 1) throw apiError('UNKNOWN_OUTCOME');
      return receipt;
    });
    const accepted = vi.fn();
    render(
      <ResearchComposer
        client={server.client()}
        purpose="research"
        scope={scope}
        session={session}
        policy={policy}
        onAccepted={accepted}
      />,
    );
    await userEvent.type(screen.getByLabelText('연구 질문'), '유실된 요청');
    await userEvent.click(screen.getByRole('button', { name: '질문 보내기' }));
    await screen.findByRole('button', { name: '같은 요청의 결과 확인' });
    expect(server.calls).toHaveLength(1);
    expect(screen.getByLabelText('연구 질문')).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '같은 요청의 결과 확인' }));
    await waitFor(() => expect(accepted).toHaveBeenCalled());
    expect(server.calls[0]!.key).toBe(server.calls[1]!.key);
    expect(server.calls[0]!.body).toEqual(server.calls[1]!.body);
  });
  it('starts distinct topic analysis with correct action wording, keeping unsupported manuscript explicit', async () => {
    const server = new Double().on('accept-novelty-analysis', () => receipt);
    render(
      <ResearchComposer
        client={server.client()}
        purpose="novelty"
        scope={scope}
        policy={policy}
        onAccepted={vi.fn()}
      />,
    );
    expect(screen.getByRole('option', { name: /원고/ })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('분석할 주제 또는 원고 설명'), '연구 주제');
    await userEvent.click(screen.getByRole('button', { name: '참신성 분석 시작' }));
    await waitFor(() => expect(server.calls).toHaveLength(1));
    expect(server.calls[0]!.body).toMatchObject({ inputMode: 'topic', text: '연구 주제' });
  });
  it('allows manuscript mode only with a bound attachment scope', async () => {
    const server = new Double().on('accept-novelty-analysis', () => receipt);
    render(
      <ResearchComposer
        client={server.client()}
        purpose="novelty"
        scope={{ ...scope, attachmentIds: ['attachment-a'] }}
        policy={policy}
        onAccepted={vi.fn()}
      />,
    );
    await userEvent.selectOptions(screen.getByLabelText('분석 대상'), 'manuscript');
    await userEvent.type(screen.getByLabelText('분석할 주제 또는 원고 설명'), '이 첨부 원고');
    await userEvent.click(screen.getByRole('button', { name: '참신성 분석 시작' }));
    expect(server.calls[0]!.body).toMatchObject({
      inputMode: 'manuscript',
      scope: { attachmentIds: ['attachment-a'] },
    });
  });
  it('discussion binds the exact ready artifact without rerunning analysis or exporting', async () => {
    const server = new Double().on('accept-novelty-discussion', () => receipt);
    const accepted = vi.fn();
    render(
      <NoveltyDiscussion
        client={server.client()}
        source={artifact}
        policy={policy}
        onAccepted={accepted}
      />,
    );
    await userEvent.type(screen.getByLabelText('결과에 대한 질문'), '한계를 설명해 주세요');
    await userEvent.click(screen.getByRole('button', { name: '결과에 대해 질문 보내기' }));
    await waitFor(() =>
      expect(accepted).toHaveBeenCalledWith({
        jobId: receipt.jobId,
        contextId: scope.contextId,
        kind: 'novelty-discussion',
      }),
    );
    expect(server.calls[0]!.body).toEqual({
      source: artifact.artifact,
      text: '한계를 설명해 주세요',
      policy,
    });
    expect(server.calls.map((item) => item.name)).toEqual(['accept-novelty-discussion']);
  });
  it('drops private in-memory text on unmount and never writes browser storage', async () => {
    const server = new Double();
    const local = vi.spyOn(Storage.prototype, 'setItem');
    const { unmount } = render(
      <ResearchComposer
        client={server.client()}
        purpose="novelty"
        scope={scope}
        policy={policy}
        onAccepted={vi.fn()}
      />,
    );
    await userEvent.type(screen.getByLabelText('분석할 주제 또는 원고 설명'), '개인 원고 텍스트');
    unmount();
    render(
      <ResearchComposer
        client={server.client()}
        purpose="novelty"
        scope={{ ...scope, contextId: 'context-b' }}
        policy={policy}
        onAccepted={vi.fn()}
      />,
    );
    expect(screen.getByLabelText('분석할 주제 또는 원고 설명')).toHaveValue('');
    expect(local).not.toHaveBeenCalled();
    local.mockRestore();
  });
});
