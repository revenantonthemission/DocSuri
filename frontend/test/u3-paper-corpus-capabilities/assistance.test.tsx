/** U3 assistance states: options, acceptance, ordered progress and results. */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AssistanceSection } from '../../src/u3-corpus/assistance';
import { ContractDouble, jobSnapshot, paper, readyContent } from './helpers';

const content = readyContent() as { content: { contentRevision: string; contentHash: string } };
const optionsPayload = {
  revision: 'options-r1',
  options: [
    {
      optionId: 'u3-key-sections-summary',
      operation: 'summary',
      sourceLanguageId: 'en',
      targetLanguageId: 'en',
      presentationLevelId: 'selected-source',
      labelKey: '핵심 구간 요약',
    },
    {
      optionId: 'u3-key-sections-translation',
      operation: 'translation',
      sourceLanguageId: 'en',
      targetLanguageId: 'ko',
      presentationLevelId: 'selected-source',
      labelKey: '핵심 구간 한국어 번역',
    },
  ],
  policy: { policyId: 'local-research', revision: '1' },
  limitations: ['선택한 원문 부분만 처리합니다.', '이 환경은 합성(synthetic) 실행기를 사용합니다.'],
};

function renderAssistance(extra: (client: ContractDouble) => ContractDouble = (c) => c) {
  let client = new ContractDouble()
    .on('/api/v2/c06/read-assistance-options', () => optionsPayload)
    .on('/api/v2/c06/read-glossary', () => ({
      ownerId: 'owner-a',
      revision: 'empty:owner-a:u3-owner-glossary-v1',
      normalizationPolicy: { policyId: 'u3-owner-glossary', revision: '1' },
      terms: [],
    }))
    .on('/api/v2/c06/accept-assistance', () => ({
      jobId: '44444444-4444-4444-4444-444444444444',
      revision: 'job-r1',
      seq: 1,
      state: 'accepted',
      requestId: 'op-1',
      acceptedAt: '2026-10-15T00:00:00+00:00',
    }))
    .on('/api/v2/jobs/44444444-4444-4444-4444-444444444444', () =>
      jobSnapshot({ state: 'succeeded', seq: 5, progress: { mode: 'determinate', current: 1, total: 1 } }),
    )
    .on('/api/v2/jobs/44444444-4444-4444-4444-444444444444/result', () => ({
      availability: 'ready',
      prepared: {
        result: { resultId: 'r1', revision: 'rr1', contentHash: 'd'.repeat(64) },
        ownerId: 'owner-a',
        jobId: '44444444-4444-4444-4444-444444444444',
        paper,
        sourceContentHash: 'b'.repeat(64),
        operation: 'summary',
        optionId: 'u3-key-sections-summary',
        glossaryRevision: 'empty:owner-a:u3-owner-glossary-v1',
        sections: [
          { sectionId: 's1', heading: 'Introduction', text: '요약 문장입니다.', anchor: 'p1' },
        ],
        coverage: 'partial',
        limitations: ['선택한 원문 구간에 대한 결과입니다.'],
        methodRevision: 'options-r1',
      },
    }));
  client = extra(client);
  render(
    <AssistanceSection
      client={client.asTransport()}
      paper={paper}
      contentRevision={content.content.contentRevision}
      contentHash={content.content.contentHash}
      signedIn
    />,
  );
  return client;
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
});

describe('U3 assistance surface', () => {
  it('offers only reconciled options with the synthetic disclosure', async () => {
    renderAssistance();
    await waitFor(() => expect(screen.getByTestId('assistance-options')).toBeInTheDocument());
    expect(screen.getByTestId('start-summary')).toHaveTextContent('핵심 구간 요약');
    expect(screen.getByTestId('start-translation')).toBeInTheDocument();
    expect(screen.getByTestId('assistance-panel')).toHaveTextContent('합성(synthetic)');
  });

  it('runs acceptance, ordered progress and a bound result', async () => {
    // No EventSource in this test: the polling fallback recovers the snapshot.
    vi.stubGlobal('EventSource', undefined as unknown as typeof EventSource);
    const client = renderAssistance();
    await waitFor(() => expect(screen.getByTestId('start-summary')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('start-summary'));
    await waitFor(() => expect(screen.getByTestId('job-progress')).toBeInTheDocument(), {
      timeout: 5000,
    });
    await waitFor(() => expect(screen.getByTestId('prepared-result')).toBeInTheDocument(), {
      timeout: 5000,
    });
    expect(screen.getByTestId('prepared-result')).toHaveTextContent('요약 문장입니다.');
    expect(client.calls.some((call) => call.path.endsWith('/accept-assistance'))).toBe(true);
  });

  it('reuses one operation key for the same intended submission', async () => {
    vi.stubGlobal('EventSource', undefined as unknown as typeof EventSource);
    const client = renderAssistance();
    await waitFor(() => expect(screen.getByTestId('start-summary')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('start-summary'));
    await waitFor(() =>
      expect(client.calls.some((call) => call.path.endsWith('/accept-assistance'))).toBe(true),
    );
    const keys = client.calls
      .filter((call) => call.path.endsWith('/accept-assistance'))
      .map((call) => call.operationKey);
    expect(keys[0]).toBeTruthy();
    expect(window.localStorage.getItem('docsuri.u3.operation.paper-alpha.summary')).toBe(keys[0]);
  });

  it('shows an expired result without regenerating work', async () => {
    vi.stubGlobal('EventSource', undefined as unknown as typeof EventSource);
    renderAssistance((client) =>
      client.on('/api/v2/jobs/44444444-4444-4444-4444-444444444444/result', () => ({
        availability: 'expired',
        jobId: '44444444-4444-4444-4444-444444444444',
        reasonKey: 'result.expired',
      })),
    );
    await waitFor(() => expect(screen.getByTestId('start-summary')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('start-summary'));
    await waitFor(() => expect(screen.getByTestId('result-expired')).toBeInTheDocument(), {
      timeout: 5000,
    });
    expect(screen.getByTestId('result-expired')).toHaveTextContent('보관 기간이 지난 결과예요');
  });

  it('marks assistance unavailable for guests', () => {
    render(
      <AssistanceSection
        client={new ContractDouble().asTransport()}
        paper={paper}
        contentRevision="r"
        contentHash="h"
        signedIn={false}
      />,
    );
    expect(screen.getByTestId('assistance-unavailable')).toBeInTheDocument();
  });

  it('ignores stale progress frames and keeps the newest snapshot', async () => {
    const frames: string[] = [];
    class FakeEventSource {
      static instances: FakeEventSource[] = [];
      listeners = new Map<string, ((event: MessageEvent) => void)[]>();
      closed = false;
      constructor(public url: string) {
        FakeEventSource.instances.push(this);
      }
      addEventListener(name: string, handler: (event: MessageEvent) => void) {
        this.listeners.set(name, [...(this.listeners.get(name) ?? []), handler]);
      }
      onerror: (() => void) | null = null;
      close() {
        this.closed = true;
      }
      emit(name: string, data: unknown) {
        frames.push(JSON.stringify(data));
        for (const handler of this.listeners.get(name) ?? []) {
          handler({ data: JSON.stringify(data) } as MessageEvent);
        }
      }
    }
    vi.stubGlobal('EventSource', FakeEventSource as unknown as typeof EventSource);
    const jobId = '44444444-4444-4444-4444-444444444444';
    renderAssistance((client) =>
      client.on(`/api/v2/jobs/${jobId}`, () =>
        jobSnapshot({ state: 'running', seq: 1 }),
      ),
    );
    await waitFor(() => expect(screen.getByTestId('start-summary')).toBeInTheDocument());
    await userEvent.click(screen.getByTestId('start-summary'));
    await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0));
    const source = FakeEventSource.instances[0];
    source.emit('snapshot', jobSnapshot({ seq: 4, state: 'running' }));
    source.emit('snapshot', jobSnapshot({ seq: 2, state: 'running' }));
    await waitFor(() =>
      expect(screen.getByTestId('activity-card')).toHaveTextContent('순서 4'),
    );
    expect(frames).toHaveLength(2);
  });
});
