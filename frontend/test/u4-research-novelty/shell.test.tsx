import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../../src/App';
import { context, job, policy, session } from './fixtures';
import { keepJobLink } from '../../src/u4-research/jobs';
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
function server(
  signedIn = true,
  ids = ['account.controls', 'research', 'novelty'],
  researchState = 'available',
) {
  const calls: { path: string; body: unknown }[] = [];
  let signed = signedIn;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, options?: RequestInit) => {
      const path = new URL(String(input), 'https://local.invalid').pathname;
      const body = options?.body ? JSON.parse(String(options.body)) : undefined;
      calls.push({ path, body });
      if (path === '/api/v2/session')
        return json({
          signedIn: signed,
          accountId: signed ? 'owner-a' : null,
          authorityRevision: signed ? '1' : null,
          csrfToken: 'c'.repeat(64),
        });
      if (path === '/api/v2/capabilities')
        return json({
          revision: '1',
          capabilities: ids.map((id) => ({
            id,
            state: ['research', 'novelty'].includes(id) ? researchState : 'available',
            modeIds: researchState === 'degraded' ? ['synthetic-only'] : [],
            languageIds: [],
            levelIds: [],
            formatIds: [],
            policy,
          })),
        });
      if (path === '/api/v2/c01/host-resolve-navigation')
        return json({
          items: ['search', 'research', 'novelty'].map((routeId) => ({
            routeId,
            titleKey: routeId,
            capabilityId: routeId,
            available: true,
          })),
        });
      if (path === '/api/v2/c03/settings-read')
        return json({ revision: '1', appearance: 'system', onboarding: 'complete' });
      if (path === '/api/v2/c03/settings-update')
        return json({ revision: '2', ...(body as object) });
      if (path.endsWith('/list-research-sessions'))
        return json({ sessions: [session], page: { nextCursor: null, snapshotRevision: '1' } });
      if (path.endsWith('/read-research-session')) return json(session);
      if (path.endsWith('/create-research-context'))
        return json({ ...context, purpose: 'novelty' });
      if (path.endsWith('/read-research-job')) return json(job({ kind: 'novelty-analysis' }));
      if (path.endsWith('/access-logout')) {
        signed = false;
        return json({ resourceId: 'session-a', revision: '2', requestId: 'request-a' });
      }
      return json(
        {
          code: 'NOT_FOUND',
          requestId: 'local',
          retryable: false,
          messageKey: 'request.not_found',
        },
        404,
      );
    }),
  );
  return calls;
}
afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
  window.localStorage.clear();
});
describe('shared shell research contribution', () => {
  it('follows a same-document recovery URL through the current owner workspace without creating work', async () => {
    const calls = server();
    render(<App />);
    await screen.findByTestId('logout');
    keepJobLink({ jobId: 'job-a', contextId: 'context-a', kind: 'novelty-analysis' });
    fireEvent(window, new HashChangeEvent('hashchange'));
    await screen.findByText(/접수됨/);
    expect(screen.getByTestId('workspace-novelty')).toBeVisible();
    expect(
      calls.filter((call) => call.path.startsWith('/api/v2/c07/')).map((call) => call.path),
    ).toEqual(['/api/v2/c07/read-research-job']);
  });
  it('mounts degraded research and novelty with explicit capability and synthetic limitations', async () => {
    server(true, ['account.controls', 'research', 'novelty'], 'degraded');
    render(<App />);
    await userEvent.click(await screen.findByTestId('nav-research'));
    expect(screen.getByTestId('workspace-research')).toBeVisible();
    expect(screen.getAllByText(/일부 연구 기능이 제한/)[0]).toBeVisible();
    expect(screen.getAllByText(/현재 합성 자료로 동작을 확인/)[0]).toBeVisible();
    await userEvent.click(screen.getByTestId('nav-novelty'));
    expect(screen.getByTestId('workspace-novelty')).toBeVisible();
    expect(screen.getAllByText(/일부 연구 기능이 제한/)[1]).toBeVisible();
  });
  it('coexists with the installed corpus search surface in the cumulative application', async () => {
    server(true, ['account.controls', 'research', 'novelty', 'corpus.maintenance']);
    render(<App />);
    await screen.findByTestId('corpus-workspace');
    expect(screen.queryByTestId('search-form')).toBeNull();
    await userEvent.click(screen.getByTestId('nav-research'));
    expect(screen.getByTestId('workspace-research')).toBeVisible();
  });
  it('keeps owner routes absent for a guest while public search remains mounted', async () => {
    server(false);
    render(<App />);
    await screen.findByTestId('search-form');
    expect(screen.queryByTestId('nav-research')).toBeNull();
    expect(screen.queryByTestId('workspace-research')).toBeNull();
  });
  it('mounts the contribution only with a current available research capability', async () => {
    server(true, ['account.controls']);
    render(<App />);
    await screen.findByTestId('logout');
    expect(screen.queryByTestId('workspace-research')).toBeNull();
    expect(screen.queryByTestId('workspace-novelty')).toBeNull();
  });
  it('keeps unsent text in memory across workspace navigation and clears it at signout', async () => {
    const calls = server();
    render(<App />);
    await userEvent.click(await screen.findByTestId('nav-research'));
    await userEvent.click(await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' }));
    await userEvent.type(screen.getByLabelText('연구 질문'), '현재 계정만 볼 입력');
    await userEvent.click(screen.getByTestId('nav-novelty'));
    expect(screen.getByTestId('workspace-research')).not.toBeVisible();
    await userEvent.click(screen.getByTestId('nav-research'));
    expect(screen.getByLabelText('연구 질문')).toHaveValue('현재 계정만 볼 입력');
    await userEvent.click(screen.getByTestId('logout'));
    await waitFor(() => expect(screen.queryByLabelText('연구 질문')).toBeNull());
    expect(calls.some((item) => item.path.includes('accept-'))).toBe(false);
  });
  it('restores a novelty recovery URL by reading the job without creating work', async () => {
    keepJobLink({ jobId: 'job-a', contextId: 'context-a', kind: 'novelty-analysis' });
    const calls = server();
    render(<App />);
    await screen.findByText(/접수됨/);
    expect(screen.getByTestId('workspace-novelty')).toBeVisible();
    expect(
      calls.filter((item) => item.path.startsWith('/api/v2/c07/')).map((item) => item.path),
    ).toEqual(['/api/v2/c07/read-research-job']);
    await userEvent.click(screen.getByTestId('logout'));
    expect(window.location.hash).toBe('');
  });
  it('keeps shared light/dark appearance and keyboard navigation available in research', async () => {
    server();
    render(<App />);
    await userEvent.click(await screen.findByTestId('nav-research'));
    await userEvent.selectOptions(screen.getByLabelText('화면 모드'), 'dark');
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('dark'));
    const navigation = screen.getByTestId('nav-novelty');
    navigation.focus();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByTestId('workspace-novelty')).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText('화면 모드'), 'light');
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe('light'));
  });
  it('clears private input immediately when another tab announces an authority change', async () => {
    server();
    render(<App />);
    await userEvent.click(await screen.findByTestId('nav-research'));
    await userEvent.click(await screen.findByRole('button', { name: '연구 1 열기 · 질문 0개' }));
    await userEvent.type(screen.getByLabelText('연구 질문'), '다른 탭 경계의 입력');
    fireEvent(
      window,
      new StorageEvent('storage', {
        key: 'docsuri.authority-boundary',
        newValue: JSON.stringify({
          kind: 'authority-changed',
          nonce: '11111111-1111-4111-8111-111111111111',
        }),
      }),
    );
    await waitFor(() => expect(screen.queryByLabelText('연구 질문')).toBeNull());
    await screen.findByTestId('workspace-research');
    expect(screen.queryByDisplayValue('다른 탭 경계의 입력')).toBeNull();
  });
});
