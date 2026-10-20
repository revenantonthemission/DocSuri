/** U6's entry on the novelty result screen: offered only with the export capability and
a ready novelty result, it opens the export flow with the exact ResearchArtifactRef, and
opening or closing it makes no C09 mutation (BR2.2). */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SWRConfig } from 'swr';
import { afterEach, describe, expect, it } from 'vitest';
import { ResearchWorkspace } from '../../src/u4-research/research-workspace';
import { keepJobLink } from '../../src/u4-research/jobs';
import { artifact, complete, Double, job, policy, ready } from './fixtures';

const exportCapability = {
  id: 'export',
  state: 'degraded' as const,
  modeIds: ['synthetic-only'],
  languageIds: ['ko'],
  levelIds: [],
  formatIds: ['notion'],
  policy: { policyId: 'u6-synthetic-export', revision: '1' },
};
const connection = {
  connectionId: '22222222-2222-4222-8222-222222222222',
  ownerId: 'owner-a',
  revision: '1',
  provider: 'notion',
  state: 'connected',
  destinationScopeIds: [],
  limitations: ['synthetic-only'],
  workspaceName: '시험 워크스페이스',
};
const page = 'a'.repeat(32);
const listing = {
  connectionId: connection.connectionId,
  connectionRevision: '1',
  destinations: [
    {
      connectionId: connection.connectionId,
      workspaceId: 'workspace-a',
      parentPageId: page,
      formatRevision: '1',
      destinationId: page,
      title: '연구 노트',
      readable: true,
      creationCapability: 'unknown',
      writable: true,
    },
  ],
  listingComplete: true,
};
const C09_MUTATIONS = [
  'configure-notion-connection',
  'disconnect-notion',
  'prepare-export-preview',
  'approve-export-preview',
  'execute-approved-export',
  'cancel-export-approval',
  'settle-export-effect',
];

function server(readyResult = true) {
  return new Double()
    .on('read-research-job', () =>
      readyResult ? complete({ kind: 'novelty-analysis' }) : job({ kind: 'novelty-analysis' }),
    )
    .on('read-research-artifact', () => ready())
    .on('read-notion-connection', () => connection)
    .on('list-export-destinations', () => listing)
    .on('prepare-export-preview', (body) => ({
      previewId: '33333333-3333-4333-8333-333333333333',
      ownerId: 'owner-a',
      revision: '1',
      source: (body as { source: unknown }).source,
      sourceEligibilityRevision: '1',
      connectionRevision: '1',
      destination: listing.destinations[0],
      renderedText: '미리보기',
      renderedContentHash: 'd'.repeat(64),
      bindingHash: 'e'.repeat(64),
      renderPolicy: exportCapability.policy,
      earlierExports: [],
    }));
}

function workspace(api: Double, withCapability = true) {
  keepJobLink({ jobId: 'job-a', contextId: 'context-a', kind: 'novelty-analysis' });
  return render(
    <SWRConfig value={{ provider: () => new Map() }}>
      <ResearchWorkspace
        client={api.client()}
        purpose="novelty"
        policy={policy}
        exportCapability={withCapability ? exportCapability : undefined}
      />
    </SWRConfig>,
  );
}

const c09Mutations = (api: Double) =>
  api.calls.filter((call) => C09_MUTATIONS.includes(call.name)).map((call) => call.name);

afterEach(() => {
  window.history.replaceState(null, '', '/');
  window.localStorage.clear();
});

describe('the novelty export entry', () => {
  it('is absent without the export capability', async () => {
    const api = server();
    workspace(api, false);
    await userEvent.click(await screen.findByRole('button', { name: '준비된 결과 열기' }));
    await screen.findByText('읽은 범위의 연구 비교');
    expect(screen.queryByTestId('novelty-export-open')).toBeNull();
  });

  it('is absent until a novelty result is ready', async () => {
    const api = server(false);
    workspace(api);
    await screen.findByText(/접수됨/);
    expect(screen.queryByTestId('novelty-export-open')).toBeNull();
  });

  it('opens and closes the flow without any C09 mutation and returns focus', async () => {
    const api = server();
    workspace(api);
    await userEvent.click(await screen.findByRole('button', { name: '준비된 결과 열기' }));
    const entry = await screen.findByTestId('novelty-export-open');
    expect(entry.textContent).toBe('Notion으로 내보내기');
    await userEvent.click(entry);
    await screen.findByTestId('destination-step');
    expect(screen.getByTestId('export-flow')).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('flow-close'));
    const reopened = await screen.findByTestId('novelty-export-open');
    await waitFor(() => expect(document.activeElement).toBe(reopened));
    expect(screen.queryByTestId('export-flow')).toBeNull();
    expect(c09Mutations(api)).toEqual([]);
  });

  // WCAG 2.4.3: pressing a job control must not drop keyboard focus to the document while
  // its read runs. A disabled focused button loses focus, and Tab then restarts at the top
  // of the page; the control stays focusable and inert (aria-disabled) instead.
  it('keeps keyboard focus on the result button while it reads, so Tab reaches the entry', async () => {
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const api = server().on('read-research-artifact', async () => {
      await gate;
      return ready();
    });
    workspace(api);
    const open = await screen.findByRole('button', { name: '준비된 결과 열기' });
    open.focus();
    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(open).toHaveAttribute('aria-disabled', 'true'));
    expect(open).not.toHaveAttribute('disabled');
    expect(document.activeElement).toBe(open);
    await userEvent.keyboard('{Enter}');
    expect(api.calls.filter((call) => call.name === 'read-research-artifact')).toHaveLength(1);
    release();
    const entry = await screen.findByTestId('novelty-export-open');
    expect(open).toHaveAttribute('aria-disabled', 'false');
    expect(document.activeElement).toBe(open);
    for (let step = 0; step < 20 && document.activeElement !== entry; step += 1)
      await userEvent.tab();
    expect(document.activeElement).toBe(entry);
    expect(c09Mutations(api)).toEqual([]);
  });

  it('keeps keyboard focus on the status refresh while it reads', async () => {
    let gated = false;
    let release = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const api = server().on('read-research-job', async () => {
      if (gated) await gate;
      return complete({ kind: 'novelty-analysis' });
    });
    workspace(api);
    await screen.findByRole('button', { name: '준비된 결과 열기' });
    const refresh = screen.getByRole('button', { name: '진행 상태 새로고침' });
    gated = true;
    refresh.focus();
    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(refresh).toHaveAttribute('aria-disabled', 'true'));
    expect(refresh).not.toHaveAttribute('disabled');
    expect(document.activeElement).toBe(refresh);
    await userEvent.keyboard('{Enter}');
    expect(api.calls.filter((call) => call.name === 'read-research-job')).toHaveLength(2);
    release();
    await waitFor(() => expect(refresh).toHaveAttribute('aria-disabled', 'false'));
    expect(document.activeElement).toBe(refresh);
  });

  it('passes the exact ResearchArtifactRef to the preview', async () => {
    const api = server();
    workspace(api);
    await userEvent.click(await screen.findByRole('button', { name: '준비된 결과 열기' }));
    await userEvent.click(await screen.findByTestId('novelty-export-open'));
    await screen.findByTestId('destination-step');
    await userEvent.click(screen.getByTestId('destination-radio'));
    await userEvent.click(screen.getByTestId('destination-next'));
    await screen.findByTestId('preview-rendered');
    const [prepare] = api.calls.filter((call) => call.name === 'prepare-export-preview');
    expect((prepare!.body as { source: unknown }).source).toEqual(artifact.artifact);
    expect(c09Mutations(api)).toEqual(['prepare-export-preview']);
  });
});
