import React from 'react';
import type { ArtifactResponse, Evidence } from './api';

function safeSource(value: string | null): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}

function Source({ evidence }: { evidence: Evidence }) {
  const unread = evidence.readCoverage === 'not-read' || evidence.sourceKind === 'unread-reference';
  const href = safeSource(evidence.sourceUrl);
  return (
    <li className="research-evidence">
      <p>
        <strong>
          {unread
            ? '읽지 않은 참고 링크 · 근거에서 제외'
            : {
                supports: '뒷받침하는 근거',
                contradicts: '상반되는 근거',
                uncertain: '불확실한 근거',
              }[evidence.stance]}
        </strong>
      </p>
      <p>{evidence.claim}</p>
      {!unread && evidence.quote ? <blockquote>{evidence.quote}</blockquote> : null}
      <p className="muted">
        {evidence.sourceId} · 버전 {evidence.sourceVersion} · {evidence.location}
        {evidence.readCoverage === 'partial' ? ' · 일부만 읽음' : ''}
      </p>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer">
          출처 열기 (새 창)
        </a>
      ) : null}
    </li>
  );
}

export function EvidenceResult({ value }: { value: ArtifactResponse }) {
  if (value.availability !== 'ready')
    return (
      <p role="status">
        {
          {
            pending: '결과 준비 중이에요',
            failed: '결과를 준비하지 못했어요',
            expired: '결과 보관 기간이 지났어요',
            deleted: '삭제된 결과예요',
            restricted: '현재 이 결과를 열 수 없어요',
          }[value.availability]
        }{' '}
        · 열람으로 새 작업을 시작하지 않아요.
      </p>
    );
  const { output } = value.prepared;
  const eligible = new Set(
    output.evidence
      .filter((item) => item.readCoverage !== 'not-read' && item.sourceKind !== 'unread-reference')
      .map((item) => item.evidenceId),
  );
  return (
    <section className="research-result" aria-label="준비된 연구 결과">
      <h3>{value.prepared.kind === 'novelty-result' ? '참신성 분석 결과' : '연구 답변'}</h3>
      <p role="status">
        {
          {
            complete: '확인한 범위의 결과예요',
            partial: '일부 근거만으로 작성한 결과예요',
            abstained: '근거가 부족해 판단을 보류했어요',
          }[output.coverage]
        }
      </p>
      <p className="research-text">{output.summary}</p>
      {output.limitations.length ? (
        <ul aria-label="결과의 한계">
          {output.limitations.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ul>
      ) : null}
      <ul className="research-sources" aria-label="근거와 출처">
        {output.evidence.map((evidence) => (
          <Source key={evidence.evidenceId} evidence={evidence} />
        ))}
      </ul>
      {(output.assessments ?? []).map((assessment) => {
        const valid =
          Number.isFinite(assessment.score) &&
          Number.isFinite(assessment.scaleMinimum) &&
          Number.isFinite(assessment.scaleMaximum) &&
          assessment.scaleMinimum! <= assessment.score! &&
          assessment.score! <= assessment.scaleMaximum! &&
          assessment.evidenceIds.length > 0 &&
          assessment.evidenceIds.every((id) => eligible.has(id));
        return (
          <section key={assessment.criterionId} aria-label={assessment.label}>
            <h4>{assessment.label}</h4>
            {valid ? (
              <p>
                {assessment.score} (척도 {assessment.scaleMinimum}–{assessment.scaleMaximum}) · 방법{' '}
                {output.methodRevision}
              </p>
            ) : (
              <p>척도 또는 근거를 확인할 수 없어 점수를 표시하지 않아요</p>
            )}
            <p>이 평가는 과학적 참신성의 증명이 아니에요.</p>
            <ul>
              {assessment.limitations.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </section>
        );
      })}
      <p className="muted">결과를 읽는 것만으로 분석이나 외부 내보내기를 실행하지 않아요.</p>
    </section>
  );
}
