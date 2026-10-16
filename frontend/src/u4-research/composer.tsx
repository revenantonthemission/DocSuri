import React, { useId, useState } from 'react';
import type { Transport } from '../api';
import { ActionStatus, useResearchAction } from './action';
import {
  researchCall,
  RESEARCH_LIMITS,
  utf8Bytes,
  type Artifact,
  type DraftRef,
  type Policy,
  type Scope,
  type Session,
} from './api';
import { DraftControls } from './drafts';
import { AttachmentControls, SourceControls } from './sources';
import type { JobLink } from './jobs';

export function ResearchComposer({
  client,
  scope: initialScope,
  session,
  purpose,
  policy,
  onAccepted,
}: {
  client: Transport;
  scope: Scope;
  session?: Session;
  purpose: 'research' | 'novelty';
  policy: Policy;
  onAccepted: (value: JobLink) => void;
}) {
  const [scope, setScope] = useState(initialScope);
  const [text, setText] = useState('');
  const [mode, setMode] = useState<'question' | 'compare' | 'quote'>('question');
  const [inputMode, setInputMode] = useState<'topic' | 'manuscript'>('topic');
  const [draft, setDraft] = useState<DraftRef | null>(null);
  const action = useResearchAction(client);
  const locked = action.busy || action.unknown;
  const isResearch = purpose === 'research';
  const budgetId = useId();
  const bytes = utf8Bytes(text);
  const overLimit = bytes > RESEARCH_LIMITS.textBytes;
  const edit = (value: string) => {
    setText(value);
    setDraft(null);
  };
  return (
    <section aria-label={isResearch ? '연구 질문 작성' : '참신성 분석 작성'}>
      <h3>{isResearch ? '근거를 확인하며 질문하기' : '연구의 참신성 살펴보기'}</h3>
      <SourceControls client={client} scope={scope} onChange={setScope} disabled={locked} />
      <AttachmentControls client={client} scope={scope} />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!text.trim() || overLimit || (isResearch && !session)) return;
          const captured = text;
          void action.run(async (key) => {
            const receipt = isResearch
              ? await researchCall(
                  client,
                  'accept-research-turn',
                  {
                    sessionId: session!.sessionId,
                    scope,
                    mode,
                    text: captured,
                    policy,
                    ...(draft ? { submittedDraft: draft } : {}),
                  },
                  key,
                )
              : await researchCall(
                  client,
                  'accept-novelty-analysis',
                  {
                    scope,
                    inputMode,
                    text: captured,
                    policy,
                    ...(draft ? { submittedDraft: draft } : {}),
                  },
                  key,
                );
            onAccepted({
              jobId: receipt.jobId,
              contextId: scope.contextId,
              kind: isResearch ? 'research-turn' : 'novelty-analysis',
            });
            setText((current) => (current === captured ? '' : current));
            setDraft(null);
          });
        }}
      >
        <fieldset disabled={locked}>
          {isResearch ? (
            <label>
              질문 방식
              <select
                aria-label="질문 방식"
                value={mode}
                onChange={(event) => setMode(event.target.value as typeof mode)}
              >
                <option value="question">질문</option>
                <option value="compare">비교</option>
                <option value="quote">인용 확인</option>
              </select>
            </label>
          ) : (
            <label>
              분석 대상
              <select
                aria-label="분석 대상"
                value={inputMode}
                onChange={(event) => setInputMode(event.target.value as typeof inputMode)}
              >
                <option value="topic">연구 주제</option>
                <option value="manuscript" disabled={!scope.attachmentIds.length}>
                  원고 (읽을 수 있는 첨부 필요)
                </option>
              </select>
            </label>
          )}
          <label>
            {isResearch ? '연구 질문' : '분석할 주제 또는 원고 설명'}
            <textarea
              aria-label={isResearch ? '연구 질문' : '분석할 주제 또는 원고 설명'}
              value={text}
              onChange={(event) => edit(event.target.value)}
              rows={6}
              maxLength={RESEARCH_LIMITS.textBytes}
              aria-invalid={overLimit}
              aria-describedby={budgetId}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <p id={budgetId} role={overLimit ? 'alert' : undefined}>
            입력 용량 {bytes} / {RESEARCH_LIMITS.textBytes} UTF-8 바이트
            {overLimit ? ' · 한도를 초과했어요. 입력을 줄여 주세요.' : ''}
          </p>
          <p className="muted">
            읽은 근거가 부족하면 판단을 보류해요. 입력 내용으로 외부 내보내기를 승인하지 않아요.
          </p>
          <button type="submit" disabled={!text.trim() || overLimit || (isResearch && !session)}>
            {isResearch ? '질문 보내기' : '참신성 분석 시작'}
          </button>
        </fieldset>
      </form>
      <ActionStatus action={action} />
      <DraftControls
        client={client}
        contextId={scope.contextId}
        policy={policy}
        kind={
          isResearch
            ? 'research-question'
            : inputMode === 'topic'
              ? 'novelty-topic'
              : 'novelty-manuscript'
        }
        text={text}
        onText={edit}
        onAcknowledged={setDraft}
      />
    </section>
  );
}

export function NoveltyDiscussion({
  client,
  source,
  policy,
  onAccepted,
}: {
  client: Transport;
  source: Artifact;
  policy: Policy;
  onAccepted: (value: JobLink) => void;
}) {
  const [text, setText] = useState('');
  const action = useResearchAction(client);
  const budgetId = useId();
  const bytes = utf8Bytes(text);
  const overLimit = bytes > RESEARCH_LIMITS.textBytes;
  return (
    <section aria-label="분석 결과 토론">
      <h3>이 결과에 이어 질문하기</h3>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (!text.trim() || overLimit) return;
          const captured = text;
          void action.run(async (key) => {
            const receipt = await researchCall(
              client,
              'accept-novelty-discussion',
              { source: source.artifact, text: captured, policy },
              key,
            );
            onAccepted({
              jobId: receipt.jobId,
              contextId: source.contextId,
              kind: 'novelty-discussion',
            });
            setText((current) => (current === captured ? '' : current));
          });
        }}
      >
        <fieldset disabled={action.busy || action.unknown}>
          <label>
            결과에 대한 질문
            <textarea
              aria-label="결과에 대한 질문"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={4}
              maxLength={RESEARCH_LIMITS.textBytes}
              aria-invalid={overLimit}
              aria-describedby={budgetId}
              autoComplete="off"
              spellCheck={false}
            />
          </label>
          <p id={budgetId} role={overLimit ? 'alert' : undefined}>
            입력 용량 {bytes} / {RESEARCH_LIMITS.textBytes} UTF-8 바이트
            {overLimit ? ' · 한도를 초과했어요. 입력을 줄여 주세요.' : ''}
          </p>
          <button type="submit" disabled={!text.trim() || overLimit}>
            결과에 대해 질문 보내기
          </button>
        </fieldset>
      </form>
      <p>확인한 결과 버전에 대한 별도 질문이에요. 분석을 다시 실행하거나 내보내지 않아요.</p>
      <DraftControls
        client={client}
        contextId={source.contextId}
        policy={policy}
        kind="novelty-discussion"
        text={text}
        onText={setText}
        onAcknowledged={() => undefined}
      />
      <ActionStatus action={action} />
    </section>
  );
}
