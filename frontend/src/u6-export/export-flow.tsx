/** The stepped export flow, opened from a novelty result (Workflow 3).

연결 → 대상 → 미리보기 → 결과. The current step is exposed as state, never as color.
Opening, reading and closing the flow never export (BR2.2): only the preview step's
press does. Closing after the press does not stop the export; its outcome stays in
the export history. */

import React, { useEffect, useRef, useState } from 'react';
import useSWR from 'swr';
import type { Transport } from '../api';
import {
  connectionKey,
  readConnection,
  type ArtifactRef,
  type Capability,
  type Connection,
  type DestinationEntry,
  type Effect,
} from './api';
import { CONNECTION_STATE_COPY, limitationText, NOT_CONNECTED } from './copy';
import { ConnectForm } from './connect-form';
import { DestinationStep } from './destination-step';
import { OutcomeStep, OUTCOME_POLL_MS } from './outcome-step';
import { PreviewStep } from './preview-step';
import { LiveRegion, refusalText, StatusBadge, useAnnouncer } from './status';
import './export.css';

export type FlowStep = 'connection' | 'destination' | 'preview' | 'outcome';

export const FLOW_STEPS: { id: FlowStep; label: string }[] = [
  { id: 'connection', label: '연결' },
  { id: 'destination', label: '대상' },
  { id: 'preview', label: '미리보기' },
  { id: 'outcome', label: '결과' },
];

const STEP_HEADINGS: Record<FlowStep, string> = {
  connection: 'Notion 연결',
  destination: '내보낼 위치 고르기',
  preview: '미리보기 확인',
  outcome: '내보내기 결과',
};

export function StepIndicator({ current }: { current: FlowStep }) {
  const index = FLOW_STEPS.findIndex((step) => step.id === current);
  return (
    <ol className="export-steps" aria-label="내보내기 단계" data-testid="flow-steps">
      {FLOW_STEPS.map((step, position) => {
        const isCurrent = step.id === current;
        const done = position < index;
        return (
          <li
            key={step.id}
            className={isCurrent ? 'export-step-current' : undefined}
            aria-current={isCurrent ? 'step' : undefined}
            data-testid={`flow-step-${step.id}`}
          >
            <span aria-hidden="true">{isCurrent ? '●' : done ? '✓' : '○'}</span> {step.label}
            <span className="export-visually-hidden">
              {isCurrent ? ' (현재 단계)' : done ? ' (완료)' : ''}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function ConnectionStep({
  client,
  capability,
  connection,
  onConnected,
  onReload,
  announce,
}: {
  client: Transport;
  capability: Capability;
  connection: Connection | null;
  onConnected: (connection: Connection) => void;
  onReload: (connection: Connection | null) => void;
  announce: (text: string) => void;
}) {
  const status = connection ? CONNECTION_STATE_COPY[connection.state] : NOT_CONNECTED;
  return (
    <div className="export-step" data-testid="connection-step">
      <p>
        <StatusBadge status={status} testId="flow-connection-state" />
      </p>
      {connection?.limitations.map((key) => (
        <p key={key} className="export-note">
          {limitationText(key)}
        </p>
      ))}
      {connection?.state === 'unavailable' ? (
        <p className="export-notice">
          보호된 토큰을 지금 열 수 없습니다. ‘내보내기’ 화면에서 연결을 해제한 뒤 다시 연결하세요.
        </p>
      ) : (
        <ConnectForm
          client={client}
          policy={capability.policy}
          connection={connection}
          announce={announce}
          onSaved={onConnected}
          onReload={onReload}
        />
      )}
    </div>
  );
}

export function ExportFlow({
  client,
  capability,
  source,
  onClose,
  pollMs = OUTCOME_POLL_MS,
}: {
  client: Transport;
  capability: Capability;
  source: ArtifactRef;
  onClose: () => void;
  pollMs?: number;
}) {
  const [step, setStep] = useState<FlowStep>('connection');
  const [destination, setDestination] = useState<DestinationEntry | null>(null);
  const [effect, setEffect] = useState<Effect | null>(null);
  const [pageTitle, setPageTitle] = useState('');
  const [previewRun, setPreviewRun] = useState(0);
  const [message, announce] = useAnnouncer();
  const heading = useRef<HTMLHeadingElement>(null);
  const settled = useRef(false);
  const connection = useSWR(connectionKey(client), () => readConnection(client), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  const current = connection.data ?? null;

  // The connection step is skipped when already connected; it is decided once.
  useEffect(() => {
    if (settled.current || connection.isLoading || connection.error) return;
    settled.current = true;
    if (current?.state === 'connected') setStep('destination');
  }, [connection.error, connection.isLoading, current]);

  useEffect(() => {
    heading.current?.focus();
  }, [step]);

  const connected = (value: Connection) => {
    void connection.mutate(value, false);
    setStep('destination');
  };

  return (
    <section className="export-flow" aria-labelledby="u6-flow-heading" data-testid="export-flow">
      <div className="export-flow-head">
        <StepIndicator current={step} />
        <button type="button" onClick={onClose} data-testid="flow-close">
          닫기
        </button>
      </div>
      <h2 id="u6-flow-heading" tabIndex={-1} ref={heading} data-testid="flow-heading">
        {STEP_HEADINGS[step]}
      </h2>
      <LiveRegion message={message} testId="flow-live" />
      {connection.isLoading ? <p data-testid="flow-loading">연결 상태를 확인하는 중…</p> : null}
      {connection.error ? (
        <p className="export-notice" data-testid="flow-error">
          {refusalText(connection.error)}
        </p>
      ) : null}
      {step === 'connection' && !connection.isLoading && !connection.error ? (
        <ConnectionStep
          client={client}
          capability={capability}
          connection={current}
          onConnected={connected}
          onReload={(value) => void connection.mutate(value, false)}
          announce={announce}
        />
      ) : null}
      {step === 'destination' && current ? (
        <DestinationStep
          client={client}
          connection={current}
          initial={destination}
          onChoose={(entry) => {
            setDestination(entry);
            setStep('preview');
          }}
        />
      ) : null}
      {step === 'preview' && current && destination ? (
        <>
          <PreviewStep
            key={`${destination.destinationId}:${previewRun}`}
            client={client}
            capability={capability}
            connection={current}
            source={source}
            destination={destination}
            announce={announce}
            onExported={(value, preview) => {
              setEffect(value);
              setPageTitle(preview.sourceTitle ?? '참신성 분석 결과');
              setStep('outcome');
            }}
          />
          <div className="export-actions">
            <button
              type="button"
              onClick={() => setStep('destination')}
              data-testid="flow-back-destination"
            >
              다른 위치 고르기
            </button>
          </div>
        </>
      ) : null}
      {step === 'outcome' && effect ? (
        <OutcomeStep
          client={client}
          initial={effect}
          pageTitle={pageTitle}
          announce={announce}
          pollMs={pollMs}
          onFreshPreview={() => {
            setPreviewRun((value) => value + 1);
            setStep('preview');
          }}
        />
      ) : null}
    </section>
  );
}
