import React, { useRef, useState } from 'react';
import type { Transport } from '../api';
import { ActionStatus, useResearchAction } from './action';
import {
  researchCall,
  type DraftKind,
  type DraftRef,
  type DraftRevision,
  type Policy,
} from './api';

/** A provisioned identity is required: the browser never invents a draft allocation contract. */
export function DraftControls({
  client,
  contextId,
  identity,
  policy,
  kind,
  text,
  onText,
  onAcknowledged,
}: {
  client: Transport;
  contextId: string;
  identity?: string;
  policy: Policy;
  kind: DraftKind;
  text: string;
  onText: (value: string) => void;
  onAcknowledged: (value: DraftRef | null) => void;
}) {
  const action = useResearchAction(client);
  const [acknowledged, setAcknowledged] = useState<DraftRevision | null>(null);
  const [conflict, setConflict] = useState<DraftRevision | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [state, setState] = useState('아직 저장하지 않았어요');
  const currentText = useRef(text);
  currentText.current = text;
  const accept = (value: DraftRevision) => {
    if (value.contextId !== contextId || value.kind !== kind || value.draft.draftId !== identity)
      throw new Error('draft binding mismatch');
    setAcknowledged(value);
    onAcknowledged(value.text === currentText.current ? value.draft : null);
  };
  if (!identity)
    return (
      <section className="control-group" aria-label="초안 저장">
        <h4>초안 저장</h4>
        <p role="status">
          초안 보관·삭제·공유 기기 정책을 확인 중이에요. 지금 입력은 이 화면에만 있으며, 브라우저를
          닫거나 계정을 바꾸면 복구되지 않아요.
        </p>
        <button type="button" disabled>
          초안 저장 사용 대기
        </button>
      </section>
    );
  return (
    <section className="control-group" aria-label="초안 저장">
      <h4>초안 저장</h4>
      <p role="status">
        {action.busy ? '저장 여부를 확인하고 있어요. 아직 복구를 보장하지 않아요' : state}
      </p>
      {acknowledged && acknowledged.text !== text ? (
        <p>마지막으로 확인한 저장 이후의 수정은 저장되지 않았어요.</p>
      ) : null}
      <div className="row">
        <button
          type="button"
          disabled={action.busy || action.unknown || !!conflict}
          onClick={() =>
            void action.run(async (key) => {
              const result = await researchCall(
                client,
                'save-draft',
                {
                  contextId,
                  draftId: identity,
                  kind,
                  baseRevision: acknowledged?.draft.revision ?? null,
                  text,
                  policy,
                },
                key,
              );
              if (result.outcome === 'saved') {
                accept(result.acknowledged);
                setState('서버에서 저장을 확인했어요. 이 버전만 복구할 수 있어요');
              } else {
                setConflict(result.current);
                onAcknowledged(null);
                setState('다른 저장본과 충돌했어요. 현재 입력을 덮어쓰지 않았어요');
              }
            })
          }
        >
          초안 저장
        </button>
        <button
          type="button"
          disabled={action.busy || action.unknown}
          onClick={() =>
            void action.run(async () => {
              const result = await researchCall(client, 'restore-draft', {
                contextId,
                draftId: identity,
              });
              if (result.state === 'recoverable') {
                accept(result.acknowledged);
                if (text && text !== result.acknowledged.text) {
                  setConflict(result.acknowledged);
                  setState('복구할 저장본이 있어요. 현재 입력은 유지했어요');
                } else {
                  onText(result.acknowledged.text);
                  onAcknowledged(result.acknowledged.draft);
                  setState('확인된 저장본을 복구했어요. 질문을 전송하지 않았어요');
                }
              } else {
                setAcknowledged(null);
                onAcknowledged(null);
                setState('현재 복구할 저장본이 없어요');
              }
            })
          }
        >
          저장본 확인
        </button>
      </div>
      {conflict ? (
        <div className="control-confirmation">
          <h5>확인된 다른 저장본</h5>
          <p className="research-text">{conflict.text}</p>
          <button
            type="button"
            onClick={() => {
              accept(conflict);
              onText(conflict.text);
              onAcknowledged(conflict.draft);
              setConflict(null);
              setState('선택한 저장본을 불러왔어요');
            }}
          >
            이 저장본 사용
          </button>
          <button
            type="button"
            onClick={() => {
              accept(conflict);
              onAcknowledged(null);
              setConflict(null);
              setState('현재 입력을 유지했어요. 다시 저장해야 복구할 수 있어요');
            }}
          >
            현재 입력 유지
          </button>
        </div>
      ) : null}
      {acknowledged ? (
        <div className="control-confirmation">
          <label className="check-row">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            확인된 초안 버전만 폐기합니다. 전송한 질문과 새 저장본은 삭제하지 않습니다.
          </label>
          <button
            type="button"
            disabled={!confirmed || action.busy || action.unknown}
            onClick={() =>
              void action.run(async (key) => {
                await researchCall(
                  client,
                  'discard-draft',
                  { contextId, draft: acknowledged.draft, confirmed: true, policy },
                  key,
                );
                setAcknowledged(null);
                setConflict(null);
                setConfirmed(false);
                onAcknowledged(null);
                setState('확인된 초안 버전을 폐기했어요. 현재 입력은 화면에 남아 있어요');
              })
            }
          >
            확인한 초안 폐기
          </button>
        </div>
      ) : null}
      <ActionStatus action={action} />
    </section>
  );
}
