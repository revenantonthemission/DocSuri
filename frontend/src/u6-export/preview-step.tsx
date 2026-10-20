/** The preview step and the one publishing control (BR2.1–BR2.5, BR3.1, BR3.2, BR5.1).

Preparing freezes a new preview revision; the owner sees the source, the destination,
earlier exports of the same pair and the read-only page exactly as it will be written,
marker line included. "승인하고 내보내기" is a native button and the only control
that publishes. One press makes two calls under one key (approve, then execute); a
retry of the same press reuses that key, so the server answers with the same approval
and effect. A changed binding shows a notice that takes focus and offers a fresh
preview. */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, type Transport } from '../api';
import {
  destinationRequest,
  exportCall,
  unusableReason,
  UNTITLED_TITLE,
  type ArtifactRef,
  type Capability,
  type Connection,
  type DestinationEntry,
  type EarlierExport,
  type Effect,
  type Preview,
} from './api';
import {
  displayTitle,
  formatTime,
  IN_FLIGHT,
  OUTCOME_UNKNOWN_PAIR,
  PREVIEW_REFUSAL_COPY,
  PRESS_UNKNOWN,
  retryClock,
  STALE_BINDING,
  UNUSABLE_REASON_COPY,
} from './copy';
import { refusalCode, refusalText, type Announce } from './status';

export type PreviewState = 'preparing' | 'ready' | 'refused' | 'stale';
export type PressState = 'idle' | 'approving' | 'binding' | 'done' | 'refused';

/** Codes after which the same press can be retried and is still the same request. */
const SAME_PRESS_CODES = ['UNKNOWN_OUTCOME', 'CAPACITY_EXHAUSTED', 'OUTCOME_UNKNOWN'];

/** A bind or approve refusal in plain words, with when or how to continue (BR5.1, BR5.2). */
export function pressRefusal(failure: unknown): { text: string; stale: boolean } {
  if (!(failure instanceof ApiError)) return { text: refusalText(failure), stale: false };
  const { code, retryAfterSeconds } = failure.envelope;
  if (code === 'UNKNOWN_OUTCOME') return { text: PRESS_UNKNOWN, stale: false };
  if (code === 'CAPACITY_EXHAUSTED')
    return {
      text:
        typeof retryAfterSeconds === 'number'
          ? `한 시간에 내보낼 수 있는 횟수를 모두 썼습니다. ${retryClock(retryAfterSeconds)}부터 다시 내보낼 수 있습니다. 승인은 내보내기 기록에 남아 있습니다`
          : IN_FLIGHT,
      stale: false,
    };
  if (code === 'OUTCOME_UNKNOWN') return { text: OUTCOME_UNKNOWN_PAIR, stale: false };
  if (code === 'CONFLICT' || code === 'APPROVAL_REQUIRED')
    return { text: STALE_BINDING, stale: true };
  return { text: refusalText(failure, PREVIEW_REFUSAL_COPY), stale: false };
}

function EarlierExports({ items }: { items: readonly EarlierExport[] }) {
  if (items.length === 0) return null;
  return (
    <div className="export-earlier" data-testid="preview-earlier">
      <p>이 결과를 같은 페이지로 내보낸 적이 있습니다:</p>
      <ul>
        {items.map((item) => (
          <li key={item.effectId}>
            {item.disposition === 'exported' ? (
              <>
                {formatTime(item.endedAt)} 내보냄
                {item.remoteUrl ? (
                  <>
                    {' · '}
                    <a href={item.remoteUrl} target="_blank" rel="noopener noreferrer">
                      Notion에서 열기
                    </a>
                  </>
                ) : null}
              </>
            ) : (
              <>Notion에 있을 수 있음 ({formatTime(item.endedAt)})</>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PreviewStep({
  client,
  capability,
  connection,
  source,
  destination,
  onExported,
  announce,
}: {
  client: Transport;
  capability: Capability;
  connection: Connection;
  source: ArtifactRef;
  destination: DestinationEntry;
  onExported: (effect: Effect, preview: Preview) => void;
  announce: Announce;
}) {
  const [preview, setPreview] = useState<Preview | null>(null);
  const [previewState, setPreviewState] = useState<PreviewState>('preparing');
  const [pressState, setPressState] = useState<PressState>('idle');
  const [notice, setNotice] = useState<string | null>(null);
  const pressKey = useRef<string | null>(null);
  const staleNotice = useRef<HTMLParagraphElement>(null);
  const alive = useRef(true);

  const prepare = useCallback(async () => {
    setPreviewState('preparing');
    setNotice(null);
    pressKey.current = null;
    setPressState('idle');
    try {
      const value = await exportCall(client, 'prepare-export-preview', {
        source,
        destination: destinationRequest(destination),
        renderPolicy: capability.policy,
      });
      if (!alive.current) return;
      setPreview(value);
      setPreviewState('ready');
      announce('미리보기를 만들었습니다. 내용을 확인한 뒤 승인하세요');
    } catch (failure) {
      if (!alive.current) return;
      const text = refusalText(failure, PREVIEW_REFUSAL_COPY);
      setPreview(null);
      setPreviewState('refused');
      setNotice(text);
      announce(text);
    }
  }, [announce, capability.policy, client, destination, source]);

  useEffect(() => {
    alive.current = true;
    void prepare();
    return () => {
      alive.current = false;
    };
  }, [prepare]);

  useEffect(() => {
    if (previewState === 'stale') staleNotice.current?.focus();
  }, [previewState]);

  const press = async () => {
    if (!preview || pressState === 'approving' || pressState === 'binding') return;
    // One key per press; a retry of the same press keeps it (BR3.2).
    const key = pressKey.current ?? crypto.randomUUID();
    pressKey.current = key;
    setNotice(null);
    try {
      setPressState('approving');
      announce('승인하는 중입니다');
      const approval = await exportCall(
        client,
        'approve-export-preview',
        {
          previewId: preview.previewId,
          previewRevision: preview.revision,
          bindingHash: preview.bindingHash,
          explicitApproval: true,
        },
        key,
      );
      setPressState('binding');
      const effect = await exportCall(
        client,
        'execute-approved-export',
        { approvalId: approval.approvalId, bindingHash: approval.bindingHash },
        key,
      );
      pressKey.current = null;
      setPressState('done');
      onExported(effect, preview);
    } catch (failure) {
      const refusal = pressRefusal(failure);
      if (!SAME_PRESS_CODES.includes(refusalCode(failure) ?? '')) pressKey.current = null;
      setPressState('refused');
      setNotice(refusal.text);
      if (refusal.stale) setPreviewState('stale');
      announce(refusal.text);
    }
  };

  const unusable = unusableReason(destination, connection);
  const busy = pressState === 'approving' || pressState === 'binding';
  const disabledReason =
    previewState === 'preparing'
      ? '미리보기를 만드는 중입니다'
      : previewState !== 'ready'
        ? '현재 미리보기로는 내보낼 수 없습니다. 미리보기를 다시 만드세요'
        : unusable
          ? UNUSABLE_REASON_COPY[unusable]
          : busy
            ? '이 승인을 처리하는 중입니다'
            : null;
  const earlier: readonly EarlierExport[] = preview?.earlierExports ?? [];
  const label =
    pressState === 'approving'
      ? '승인하는 중…'
      : pressState === 'binding'
        ? '내보내기를 시작하는 중…'
        : '승인하고 내보내기';
  return (
    <div className="export-step" data-testid="preview-step" data-preview-state={previewState}>
      <dl className="export-summary">
        <div>
          <dt>내보낼 결과</dt>
          <dd data-testid="preview-source">
            {preview?.sourceTitle ?? '참신성 분석 결과'}
            <span className="export-identity">
              {' '}
              (결과 {source.artifactId.slice(0, 8)} · 판 {source.revision})
            </span>
          </dd>
        </div>
        <div>
          <dt>내보낼 위치</dt>
          <dd data-testid="preview-destination">
            {displayTitle(destination.title, UNTITLED_TITLE)}
            {destination.context ? ` · ${destination.context}` : ''}
          </dd>
        </div>
      </dl>
      {previewState === 'preparing' ? (
        <p data-testid="preview-preparing">미리보기를 만드는 중…</p>
      ) : null}
      {previewState === 'stale' ? (
        <p className="export-notice" tabIndex={-1} ref={staleNotice} data-testid="preview-stale">
          {STALE_BINDING}
        </p>
      ) : null}
      {notice && previewState !== 'stale' ? (
        <p className="export-notice" data-testid="preview-notice">
          {notice}
        </p>
      ) : null}
      <EarlierExports items={earlier} />
      {preview ? (
        <pre
          className="export-rendered"
          tabIndex={0}
          role="region"
          aria-label="Notion에 만들 페이지 미리보기 (읽기 전용)"
          data-testid="preview-rendered"
        >
          {preview.renderedText}
        </pre>
      ) : null}
      <div className="export-actions">
        <button
          type="button"
          className="export-primary"
          onClick={() => void press()}
          disabled={disabledReason !== null}
          aria-describedby={disabledReason ? 'u6-press-reason' : undefined}
          data-testid="preview-approve"
        >
          {label}
        </button>
        {previewState === 'stale' || previewState === 'refused' ? (
          <button type="button" onClick={() => void prepare()} data-testid="preview-refresh">
            미리보기 다시 만들기
          </button>
        ) : null}
      </div>
      {disabledReason ? (
        <p id="u6-press-reason" className="export-note" data-testid="preview-disabled-reason">
          {disabledReason}
        </p>
      ) : null}
      <p className="export-note">
        닫으면 아무것도 내보내지 않습니다. 승인한 뒤에는 닫아도 내보내기가 계속되고, 결과는 내보내기
        기록에 남습니다.
      </p>
    </div>
  );
}
