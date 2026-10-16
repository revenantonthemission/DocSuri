import React, { useState } from 'react';
import type { Transport } from '../api';
import { api as corpusApi } from '../u3-corpus/api';
import { ActionStatus, useResearchAction } from './action';
import { researchCall, RESEARCH_LIMITS, type Scope } from './api';
import type { WorkspaceResearchAttachment } from '../../types/wire/dtos';

export function SourceControls({
  client,
  scope,
  onChange,
  disabled = false,
}: {
  client: Transport;
  scope: Scope;
  onChange: (value: Scope) => void;
  disabled?: boolean;
}) {
  const [identifier, setIdentifier] = useState('');
  const [web, setWeb] = useState('');
  const [invalid, setInvalid] = useState(false);
  const action = useResearchAction(client);
  return (
    <details className="control-group">
      <summary>
        근거 범위 · 논문 {scope.publicPapers.length}개 / 참고 링크 {scope.webReferences.length}개
      </summary>
      <fieldset disabled={disabled || action.busy || action.unknown} className="control-body">
        <p>
          현재 범위는 논문 {RESEARCH_LIMITS.papers}개, 참고 링크 {RESEARCH_LIMITS.links}개까지예요.
        </p>
        <label>
          논문 주소 또는 식별자
          <input
            aria-label="논문 주소 또는 식별자"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            maxLength={2048}
          />
        </label>
        <button
          type="button"
          disabled={!identifier.trim() || scope.publicPapers.length >= RESEARCH_LIMITS.papers}
          onClick={() =>
            void action.run(async () => {
              const value = await corpusApi.resolve(client, identifier.trim());
              if (
                !scope.publicPapers.some(
                  (paper) =>
                    paper.paperId === value.paper.paperId &&
                    paper.versionId === value.paper.versionId,
                )
              )
                onChange({ ...scope, publicPapers: [...scope.publicPapers, value.paper] });
              setIdentifier('');
            })
          }
        >
          논문 범위에 추가
        </button>
        <ul>
          {scope.publicPapers.map((paper) => (
            <li key={`${paper.paperId}:${paper.versionId}`}>
              {paper.paperId} · {paper.versionId}{' '}
              <button
                type="button"
                aria-label={`${paper.paperId} 범위에서 제외`}
                onClick={() =>
                  onChange({
                    ...scope,
                    publicPapers: scope.publicPapers.filter((item) => item !== paper),
                  })
                }
              >
                범위에서 제외
              </button>
            </li>
          ))}
        </ul>
        <label>
          웹 참고 링크
          <input
            aria-label="웹 참고 링크"
            type="url"
            value={web}
            onChange={(e) => {
              setWeb(e.target.value);
              setInvalid(false);
            }}
            maxLength={2048}
          />
        </label>
        <p>링크를 추가해도 읽은 근거로 간주하지 않아요. 실제 읽기 여부는 결과에 표시해요.</p>
        <button
          type="button"
          disabled={!web.trim() || scope.webReferences.length >= RESEARCH_LIMITS.links}
          onClick={() => {
            try {
              const url = new URL(web);
              if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password)
                throw new Error('unsafe');
              onChange({
                ...scope,
                webReferences: [...new Set([...scope.webReferences, url.href])],
              });
              setWeb('');
            } catch {
              setInvalid(true);
            }
          }}
        >
          참고 링크 추가
        </button>
        {invalid ? (
          <p role="alert">사용자 정보가 없는 HTTP 또는 HTTPS 주소를 입력해 주세요</p>
        ) : null}
        <ul>
          {scope.webReferences.map((url) => (
            <li key={url}>
              {url}{' '}
              <button
                type="button"
                aria-label={`${url} 범위에서 제외`}
                onClick={() =>
                  onChange({
                    ...scope,
                    webReferences: scope.webReferences.filter((item) => item !== url),
                  })
                }
              >
                범위에서 제외
              </button>
            </li>
          ))}
        </ul>
      </fieldset>
      <ActionStatus action={action} />
    </details>
  );
}

export function AttachmentControls({ client, scope }: { client: Transport; scope: Scope }) {
  const action = useResearchAction(client);
  const [attachment, setAttachment] = useState<WorkspaceResearchAttachment | null>(null);
  return (
    <details className="control-group">
      <summary>비공개 첨부 자료</summary>
      <p>
        파일 보관·삭제 정책과 업로드 연결을 확인 중이에요. 현재 파일 업로드를 사용할 수 없으며
        파일을 읽거나 전송하지 않아요.
      </p>
      <label>
        원고 파일
        <input type="file" accept="application/pdf,text/plain" disabled />
      </label>
      {scope.attachmentIds.map((id, index) => (
        <button
          key={id}
          type="button"
          disabled={action.busy}
          onClick={() =>
            void action.run(async () =>
              setAttachment(
                await researchCall(client, 'read-private-attachment', {
                  contextId: scope.contextId,
                  attachmentId: id,
                }),
              ),
            )
          }
        >
          첨부 자료 {index + 1} 상태 확인
        </button>
      ))}
      {attachment ? (
        <div role="status">
          <p>
            {
              {
                processing: '추출 중',
                ready: '읽기 준비됨',
                partial: '일부 추출됨',
                unsupported: '지원하지 않는 형식',
                failed: '추출 실패',
                deleted: '삭제됨',
              }[attachment.state]
            }
          </p>
          <ul>
            {attachment.limitations.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <ActionStatus action={action} />
    </details>
  );
}
