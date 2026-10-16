import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { checkedJob } from '../../src/u4-research/api';
import { ResearchJob, keepJobLink, readJobLink } from '../../src/u4-research/jobs';
import { apiError, artifact, complete, Double, job, ready } from './fixtures';
const reference = { jobId: 'job-a', contextId: 'context-a', kind: 'research-turn' as const };
afterEach(() => window.history.replaceState(null, '', '/'));

describe('progress, recovery and result reads', () => {
  it.each(['status', 'artifact', 'deleted'] as const)(
    'clears a previously displayed result and discussion source when a later %s read is refused',
    async (path) => {
      let denied = false;
      const onResult = vi.fn();
      const server = new Double()
        .on('read-research-job', () => {
          if (denied && path === 'status') throw apiError('FORBIDDEN');
          if (denied && path === 'deleted') throw apiError('NOT_FOUND');
          return complete({ kind: 'novelty-analysis' });
        })
        .on('read-research-artifact', () => {
          if (denied) throw apiError('SOURCE_INELIGIBLE');
          return ready();
        });
      render(
        <ResearchJob
          client={server.client()}
          reference={{ ...reference, kind: 'novelty-analysis' }}
          onNoveltyResult={onResult}
        />,
      );
      await userEvent.click(await screen.findByRole('button', { name: '준비된 결과 열기' }));
      await screen.findByText('읽은 범위의 연구 비교');
      denied = true;
      await userEvent.click(
        screen.getByRole('button', {
          name: path === 'artifact' ? '준비된 결과 열기' : '진행 상태 새로고침',
        }),
      );
      await screen.findByRole('alert');
      expect(screen.queryByText('읽은 범위의 연구 비교')).toBeNull();
      expect(onResult).toHaveBeenLastCalledWith(null);
      expect(server.calls.some((call) => call.name.startsWith('accept-'))).toBe(false);
    },
  );
  it('opening and refreshing accepted work only reads, with no synthetic completion', async () => {
    const server = new Double().on('read-research-job', () => job());
    render(<ResearchJob client={server.client()} reference={reference} />);
    await screen.findByText(/접수됨/);
    expect(screen.queryByRole('button', { name: '준비된 결과 열기' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: '진행 상태 새로고침' }));
    expect(server.calls.map((item) => item.name)).toEqual([
      'read-research-job',
      'read-research-job',
    ]);
  });
  it('renders determinate running work, refuses an older snapshot and preserves latest state', async () => {
    let next = job({
      state: 'running',
      seq: 4,
      progress: { mode: 'determinate', current: 2, total: 5 },
    });
    const server = new Double().on('read-research-job', () => next);
    render(<ResearchJob client={server.client()} reference={reference} />);
    await screen.findByText('실행 중이에요');
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '2');
    next = job({ seq: 1 });
    await userEvent.click(screen.getByRole('button', { name: '진행 상태 새로고침' }));
    expect(screen.getByText('실행 중이에요')).toBeVisible();
  });
  it('reads an immutable prepared result only after an explicit open action', async () => {
    const onResult = vi.fn();
    const server = new Double()
      .on('read-research-job', () => complete({ kind: 'novelty-analysis' }))
      .on('read-research-artifact', () => ready());
    render(
      <ResearchJob
        client={server.client()}
        reference={{ ...reference, kind: 'novelty-analysis' }}
        onNoveltyResult={onResult}
      />,
    );
    await screen.findByText(/완료됐어요/);
    expect(server.calls).toHaveLength(1);
    await userEvent.click(screen.getByRole('button', { name: '준비된 결과 열기' }));
    await screen.findByText('읽은 범위의 연구 비교');
    expect(server.calls[1]!.body).toEqual({ artifact: artifact.artifact });
    expect(onResult).toHaveBeenCalledWith(artifact);
  });
  it('does not publish a result with a different context or immutable tuple', async () => {
    const server = new Double()
      .on('read-research-job', () => complete())
      .on('read-research-artifact', () => ready({ ...artifact, contextId: 'context-b' }));
    render(<ResearchJob client={server.client()} reference={reference} />);
    await screen.findByText(/완료됐어요/);
    await userEvent.click(screen.getByRole('button', { name: '준비된 결과 열기' }));
    await screen.findByRole('alert');
    expect(screen.queryByText('읽은 범위의 연구 비교')).toBeNull();
  });
  it('requires cancellation confirmation and reports request separately from completion', async () => {
    const server = new Double()
      .on('read-research-job', () => job({ kind: 'novelty-analysis' }))
      .on('cancel-novelty-analysis', () =>
        job({ kind: 'novelty-analysis', seq: 2, state: 'cancel_requested' }),
      );
    render(
      <ResearchJob
        client={server.client()}
        reference={{ ...reference, kind: 'novelty-analysis' }}
      />,
    );
    await screen.findByText(/접수됨/);
    expect(screen.getByRole('button', { name: '분석 취소 요청' })).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: '분석 취소 요청' }));
    await screen.findByText(/아직 취소 완료가 아니에요/);
    expect(screen.queryByText('취소가 완료됐어요')).toBeNull();
  });
  it('keeps completed result when completion wins a cancellation race', async () => {
    const server = new Double()
      .on('read-research-job', () => job({ kind: 'novelty-analysis' }))
      .on('cancel-novelty-analysis', () => complete({ kind: 'novelty-analysis' }));
    render(
      <ResearchJob
        client={server.client()}
        reference={{ ...reference, kind: 'novelty-analysis' }}
      />,
    );
    await screen.findByText(/접수됨/);
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: '분석 취소 요청' }));
    expect(await screen.findByRole('button', { name: '준비된 결과 열기' })).toBeEnabled();
  });
  it('recovers from a failed status read without submitting work', async () => {
    let failed = true;
    const server = new Double().on('read-research-job', () => {
      if (failed) throw apiError('DEPENDENCY_UNAVAILABLE');
      return job({ state: 'cancelled', kind: 'novelty-analysis' });
    });
    render(
      <ResearchJob
        client={server.client()}
        reference={{ ...reference, kind: 'novelty-analysis' }}
      />,
    );
    await screen.findByRole('alert');
    failed = false;
    await userEvent.click(screen.getByRole('button', { name: '진행 상태 새로고침' }));
    await screen.findByText('취소가 완료됐어요');
  });
  it('rejects malformed success and cross-job snapshots before UI publication', () => {
    expect(() => checkedJob(job({ state: 'succeeded' }), reference)).toThrow();
    expect(() => checkedJob(job({ jobId: 'job-b' }), reference)).toThrow();
    expect(() => checkedJob(job({ seq: -1 }), reference)).toThrow();
  });
  it('stores only opaque recovery references and rejects malformed extra fields', () => {
    keepJobLink(reference);
    expect(readJobLink()).toEqual(reference);
    expect(window.location.hash).not.toContain('owner');
    expect(
      readJobLink('#research-job?jobId=a&contextId=b&kind=research-turn&text=private'),
    ).toBeNull();
    expect(readJobLink('#research-job?jobId=a&contextId=b&kind=wrong')).toBeNull();
    expect(readJobLink('#other')).toBeNull();
  });
  it('does not update an unmounted status view from a late response', async () => {
    let resolve!: (value: unknown) => void;
    const server = new Double().on(
      'read-research-job',
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    const rendered = render(<ResearchJob client={server.client()} reference={reference} />);
    rendered.unmount();
    resolve(job());
    await waitFor(() => expect(screen.queryByText(/접수됨/)).toBeNull());
  });
});
