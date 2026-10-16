import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { ResearchWorkspace } from '../../src/u4-research/research-workspace';
import { keepJobLink } from '../../src/u4-research/jobs';
import {
  apiError,
  complete,
  context,
  Double,
  job,
  policy,
  ready,
  receipt,
  session,
} from './fixtures';
const listing = { sessions: [session], page: { nextCursor: null, snapshotRevision: '1' } };
function server() {
  return new Double()
    .on('list-research-sessions', () => listing)
    .on('read-research-session', () => session);
}
afterEach(() => window.history.replaceState(null, '', '/'));
describe('private research workspace', () => {
  it('reauthorizes a same-document job link and displays refusal without restoring prior private content', async () => {
    keepJobLink({ jobId: 'job-a', contextId: 'context-a', kind: 'novelty-analysis' });
    const api = server()
      .on('read-research-job', (body) => {
        if ((body as { jobId: string }).jobId === 'prior-owner-job') throw apiError('FORBIDDEN');
        return complete({ kind: 'novelty-analysis' });
      })
      .on('read-research-artifact', () => ready());
    render(<ResearchWorkspace client={api.client()} purpose="novelty" policy={policy} />);
    await userEvent.click(await screen.findByRole('button', { name: '준비된 결과 열기' }));
    await screen.findByText('읽은 범위의 연구 비교');
    await screen.findByLabelText('결과에 대한 질문');
    keepJobLink({
      jobId: 'prior-owner-job',
      contextId: 'prior-owner-context',
      kind: 'novelty-analysis',
    });
    fireEvent(window, new HashChangeEvent('hashchange'));
    await screen.findByRole('alert');
    expect(api.calls.at(-1)).toMatchObject({
      name: 'read-research-job',
      body: {
        jobId: 'prior-owner-job',
        contextId: 'prior-owner-context',
        kind: 'novelty-analysis',
      },
    });
    expect(screen.queryByRole('button', { name: '준비된 결과 열기' })).toBeNull();
    expect(screen.queryByText('읽은 범위의 연구 비교')).toBeNull();
    expect(screen.queryByLabelText('결과에 대한 질문')).toBeNull();
    expect(api.calls.some((call) => call.name.startsWith('accept-'))).toBe(false);
  });
  it('accepts an explicitly selected per-turn source scope without mutating the session default or prior submission', async () => {
    const paper = {
      paperId: 'u4-paper-alpha',
      versionId: 'u4-paper-alpha/v1',
      eligibilityRevision: '1',
    };
    let committedScope = session.scope;
    const api = server()
      .on('create-research-context', () => context)
      .on('resolve-paper', () => ({
        paper,
        requestedIdentifier: paper.paperId,
        canonicalDisposition: 'canonical',
        metadataRevision: '1',
        title: 'Synthetic paper',
        sourceUrls: [],
        policy,
      }))
      .on('create-research-session', (body) => {
        committedScope = (body as { scope: typeof session.scope }).scope;
        return { ...session, scope: committedScope };
      })
      .on('accept-research-turn', () => receipt)
      .on('read-research-job', () => job());
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await userEvent.type(screen.getByLabelText('새 연구 이름'), '질문별 근거 선택');
    await userEvent.click(screen.getByRole('button', { name: '새 연구 시작' }));
    await userEvent.click(screen.getByText(/근거 범위 · 논문/));
    await userEvent.type(screen.getByLabelText('논문 주소 또는 식별자'), paper.paperId);
    await userEvent.click(screen.getByRole('button', { name: '논문 범위에 추가' }));
    await screen.findByRole('button', { name: 'u4-paper-alpha 범위에서 제외' });
    await userEvent.type(screen.getByLabelText('연구 질문'), '확정한 근거로 질문');
    await userEvent.click(screen.getByRole('button', { name: '질문 보내기' }));
    await screen.findByText(/접수됨/);
    expect(committedScope.publicPapers).toEqual([]);
    const submitted = api.calls.find((call) => call.name === 'accept-research-turn')!.body;
    expect(submitted).toMatchObject({ scope: { ...committedScope, publicPapers: [paper] } });
    await userEvent.click(screen.getByRole('button', { name: 'u4-paper-alpha 범위에서 제외' }));
    expect(submitted).toMatchObject({ scope: { publicPapers: [paper] } });
    expect(committedScope.publicPapers).toEqual([]);
    expect(api.calls.filter((call) => call.name === 'accept-research-turn')).toHaveLength(1);
  });
  it('requires an explicit all-session confirmation and binds deletion to the owner-list snapshot', async () => {
    keepJobLink({ jobId: 'job-a', contextId: 'context-a', kind: 'research-turn' });
    const api = server()
      .on('read-research-job', () => job())
      .on('delete-research-sessions', () => ({
        requestId: 'delete-all',
        revision: '2',
        state: 'limited',
        tombstoneBoundary: '2',
        policy,
        remainingJobIds: [],
        limitations: ['백업 처리는 확인 중이에요'],
      }));
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' });
    await userEvent.click(screen.getByText('모든 연구 삭제', { selector: 'summary' }));
    expect(screen.getByRole('button', { name: '모든 연구 삭제 확인' })).toBeDisabled();
    await userEvent.click(
      screen.getByRole('checkbox', { name: '현재 계정의 모든 연구 삭제 범위를 확인했습니다' }),
    );
    await userEvent.click(screen.getByRole('button', { name: '모든 연구 삭제 확인' }));
    await screen.findByText(/모든 연구 삭제 경계를 확인했어요/);
    expect(api.calls.find((call) => call.name === 'delete-research-sessions')!.body).toEqual({
      scope: 'all-sessions',
      expectedRevision: listing.page.snapshotRevision,
      confirmed: true,
      policy,
    });
    expect(screen.getByText(/백업 처리는 확인 중이에요/)).toBeVisible();
    expect(screen.queryByText('모든 연구 정리가 완료됐어요')).toBeNull();
    expect(window.location.hash).toBe('');
  });
  it('keeps current input on an all-session snapshot conflict and resets confirmation on list refresh', async () => {
    const api = server().on('delete-research-sessions', () => {
      throw apiError('CONFLICT');
    });
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await userEvent.click(await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' }));
    await userEvent.type(screen.getByLabelText('연구 질문'), '보존할 입력');
    await userEvent.click(screen.getByText('모든 연구 삭제', { selector: 'summary' }));
    await userEvent.click(
      screen.getByRole('checkbox', { name: '현재 계정의 모든 연구 삭제 범위를 확인했습니다' }),
    );
    await userEvent.click(screen.getByRole('button', { name: '모든 연구 삭제 확인' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('연구 질문')).toHaveValue('보존할 입력');
    await userEvent.click(screen.getByRole('button', { name: '연구 목록 새로고침' }));
    expect(
      screen.getByRole('checkbox', { name: '현재 계정의 모든 연구 삭제 범위를 확인했습니다' }),
    ).not.toBeChecked();
  });
  it('enforces the title byte boundary while preserving an oversized Korean name for correction', async () => {
    const api = server()
      .on('create-research-context', () => context)
      .on('create-research-session', () => session);
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' });
    const title = screen.getByLabelText('새 연구 이름');
    const oversized = '한'.repeat(342);
    fireEvent.change(title, { target: { value: oversized } });
    expect(title).toHaveValue(oversized);
    expect(screen.getByRole('alert')).toHaveTextContent('1026 / 1024 UTF-8');
    expect(screen.getByRole('button', { name: '새 연구 시작' })).toBeDisabled();
    fireEvent.submit(title.closest('form')!);
    expect(api.calls.filter((item) => item.name.startsWith('create-'))).toHaveLength(0);
    const exact = '한'.repeat(341) + 'a';
    fireEvent.change(title, { target: { value: exact } });
    await userEvent.click(screen.getByRole('button', { name: '새 연구 시작' }));
    await screen.findByLabelText('연구 질문');
    expect(api.calls.find((item) => item.name === 'create-research-session')!.body).toMatchObject({
      title: exact,
    });
  });
  it('lists and reopens owned sessions without starting a context, job or export', async () => {
    keepJobLink({ jobId: 'job-a', contextId: 'context-a', kind: 'research-turn' });
    const api = server();
    api.on('read-research-job', () => job());
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await userEvent.click(await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' }));
    await screen.findByRole('region', { name: '연구 질문 작성' });
    expect(api.calls.map((item) => item.name)).toEqual([
      'read-research-job',
      'list-research-sessions',
      'read-research-session',
    ]);
    expect(window.location.hash).toBe('');
  });
  it('starts a new session with a server-allocated context and separate stable request keys', async () => {
    const api = server()
      .on('create-research-context', () => context)
      .on('create-research-session', () => session);
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' });
    await userEvent.type(screen.getByLabelText('새 연구 이름'), '논문 비교');
    await userEvent.click(screen.getByRole('button', { name: '새 연구 시작' }));
    await screen.findByLabelText('연구 질문');
    const create = api.calls.filter((item) => item.name.startsWith('create-'));
    expect(create[0]!.body).toEqual({ purpose: 'research', policy });
    expect(create[1]!.body).toEqual({ title: '논문 비교', scope: session.scope });
    expect(create[0]!.key).not.toBe(create[1]!.key);
  });
  it('lost session acknowledgement retries the same session operation without allocating another context', async () => {
    let attempts = 0;
    const api = server()
      .on('create-research-context', () => context)
      .on('create-research-session', () => {
        if (++attempts === 1) throw apiError('UNKNOWN_OUTCOME');
        return session;
      });
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await userEvent.type(screen.getByLabelText('새 연구 이름'), '이름');
    await userEvent.click(screen.getByRole('button', { name: '새 연구 시작' }));
    await userEvent.click(await screen.findByRole('button', { name: '같은 요청의 결과 확인' }));
    await screen.findByLabelText('연구 질문');
    expect(api.calls.filter((item) => item.name === 'create-research-context')).toHaveLength(1);
    const calls = api.calls.filter((item) => item.name === 'create-research-session');
    expect(calls[0]!.key).toBe(calls[1]!.key);
  });
  it('confirms current-session deletion and keeps limited cleanup visibly incomplete', async () => {
    const api = server().on('delete-research-sessions', () => ({
      requestId: 'delete-a',
      revision: '2',
      state: 'limited',
      tombstoneBoundary: '2',
      policy,
      remainingJobIds: ['job-a'],
      limitations: ['백업 정리 정책 대기'],
    }));
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await userEvent.click(await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' }));
    await userEvent.click(screen.getByText('현재 연구 삭제', { selector: 'summary' }));
    expect(screen.getByRole('button', { name: '현재 연구 삭제 확인' })).toBeDisabled();
    await userEvent.click(
      screen.getByRole('checkbox', { name: '현재 연구 삭제 범위를 확인했습니다' }),
    );
    await userEvent.click(screen.getByRole('button', { name: '현재 연구 삭제 확인' }));
    await screen.findByText(/남은 작업 1개/);
    expect(screen.queryByLabelText('연구 질문')).toBeNull();
    expect(api.calls.find((item) => item.name === 'delete-research-sessions')!.body).toEqual({
      scope: 'one-session',
      sessionId: session.sessionId,
      expectedRevision: session.revision,
      confirmed: true,
      policy,
    });
  });
  it('does not clear committed context or text after a stale deletion refusal', async () => {
    const api = server().on('delete-research-sessions', () => {
      throw apiError('CONFLICT');
    });
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await userEvent.click(await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' }));
    await userEvent.type(screen.getByLabelText('연구 질문'), '유지할 입력');
    await userEvent.click(screen.getByText('현재 연구 삭제', { selector: 'summary' }));
    await userEvent.click(
      screen.getByRole('checkbox', { name: '현재 연구 삭제 범위를 확인했습니다' }),
    );
    await userEvent.click(screen.getByRole('button', { name: '현재 연구 삭제 확인' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('연구 질문')).toHaveValue('유지할 입력');
  });
  it('discloses failed/empty/snapshot paging states and allows explicit list recovery', async () => {
    let fail = true;
    const api = new Double().on('list-research-sessions', (body) => {
      if (fail) throw apiError('SNAPSHOT_EXPIRED');
      const cursor = (body as { page: { cursor?: string } }).page.cursor;
      return {
        sessions: [],
        page: { nextCursor: cursor ? null : 'next-page', snapshotRevision: '1' },
      };
    });
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await screen.findByRole('alert');
    fail = false;
    await userEvent.click(screen.getByRole('button', { name: '연구 목록 새로고침' }));
    await screen.findByText(/저장된 연구가 없어요/);
    await userEvent.click(screen.getByRole('button', { name: '다음 연구 목록' }));
    expect(api.calls.at(-1)!.body).toEqual({ page: { limit: 10, cursor: 'next-page' } });
  });
  it('opens a recovery URL using an authorized job read and never re-accepts work', async () => {
    keepJobLink({ jobId: 'job-a', contextId: 'context-a', kind: 'novelty-analysis' });
    const api = new Double().on('read-research-job', () => job({ kind: 'novelty-analysis' }));
    render(<ResearchWorkspace client={api.client()} purpose="novelty" policy={policy} />);
    await screen.findByText(/접수됨/);
    expect(api.calls.map((item) => item.name)).toEqual(['read-research-job']);
  });
  it('prepares novelty only by explicit action and submits a job from its allocated context', async () => {
    const api = new Double()
      .on('create-research-context', () => ({ ...context, purpose: 'novelty' }))
      .on('accept-novelty-analysis', () => receipt)
      .on('read-research-job', () => job({ kind: 'novelty-analysis' }));
    render(<ResearchWorkspace client={api.client()} purpose="novelty" policy={policy} />);
    expect(api.calls).toHaveLength(0);
    await userEvent.click(screen.getByRole('button', { name: '새 분석 준비' }));
    await screen.findByLabelText('분석할 주제 또는 원고 설명');
    await userEvent.type(screen.getByLabelText('분석할 주제 또는 원고 설명'), '주제');
    await userEvent.click(screen.getByRole('button', { name: '참신성 분석 시작' }));
    await screen.findByText(/접수됨/);
    expect(window.location.hash).toContain('kind=novelty-analysis');
  });
  it('rediscovers a committed turn and reads its existing accepted work', async () => {
    const api = server()
      .on('read-research-session', () => ({
        ...session,
        turnIds: ['turn-a'],
        pendingJobIds: ['job-a'],
      }))
      .on('read-research-turn', () => ({
        turnId: 'turn-a',
        sessionId: session.sessionId,
        ownerId: session.ownerId,
        revision: '1',
        inputMode: 'question',
        committedText: '기존 질문',
        submittedDraft: null,
        job: job(),
        artifact: null,
      }))
      .on('read-research-job', () => job());
    render(<ResearchWorkspace client={api.client()} purpose="research" policy={policy} />);
    await userEvent.click(await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' }));
    await userEvent.click(screen.getByRole('button', { name: '질문 1 진행 및 결과 보기' }));
    await screen.findByText(/접수됨/);
    expect(api.calls.map((item) => item.name)).toEqual([
      'list-research-sessions',
      'read-research-session',
      'read-research-turn',
      'read-research-job',
    ]);
  });
});
