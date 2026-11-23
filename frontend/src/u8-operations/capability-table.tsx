/**
 * CapabilityTable (frontend-components.md "OperationsView"; BR3.2, BR6.11, BR6.12, O01):
 * every capability with its state, age, limitations and related incidents, problems
 * first, as a real table. A measured zero, an estimate and unknown read differently. The
 * summaries below it show each database incarnation's newest backup (L1-52), the restore
 * verifications against the bound, the isolation stop records, the standing job and the
 * failed jobs per lane (L1-41).
 */
import React from 'react';
import {
  AGGREGATES,
  ageText,
  LIMITATION_COPY,
  operationsTime,
  STATUS_COPY,
  valueOf,
  type DashboardItem,
  type Incident,
} from './api';

const ORDER: Readonly<Record<string, number>> = {
  unavailable: 0,
  stale: 1,
  unknown: 1,
  degraded: 2,
  available: 3,
};
const ICON: Readonly<Record<string, string>> = {
  available: '●',
  degraded: '◐',
  unavailable: '✕',
  unknown: '?',
  stale: '…',
};
const UNKNOWN = '알 수 없음';
const SECONDS_PER_MINUTE = 60;
const INTEGRITY_COPY: Readonly<Record<string, string>> = {
  available: '무결성 확인 통과',
  unavailable: '무결성 확인 실패',
};
const VERIFICATION_COPY: Readonly<Record<string, string>> = {
  available: '검증 통과',
  unavailable: '검증 실패',
};

export function shownState(item: DashboardItem): string {
  return item.freshness === 'stale' ? 'stale' : item.status;
}

export function limitationText(entry: string): string {
  if (entry.startsWith('error-rate-permille:')) {
    const value = Number(entry.split(':')[1]);
    return value === 0 ? '오류 0건 (측정값)' : `오류율 ${value / 10}% (측정값)`;
  }
  if (entry.startsWith('missing-observations:')) {
    return `저장하지 못한 확인 기록 ${entry.slice('missing-observations:'.length)}건`;
  }
  if (entry === 'available') return '';
  return LIMITATION_COPY[entry] ?? entry;
}

export function sortProblemsFirst(items: readonly DashboardItem[]): DashboardItem[] {
  return [...items].sort(
    (left, right) =>
      (ORDER[shownState(left)] ?? 1) - (ORDER[shownState(right)] ?? 1) ||
      left.capability.localeCompare(right.capability),
  );
}

export function CapabilityTable({
  items,
  incidents,
  paused,
  onTogglePause,
  onRefresh,
}: {
  items: readonly DashboardItem[];
  incidents: readonly Incident[];
  paused: boolean;
  onTogglePause: () => void;
  onRefresh: () => void;
}) {
  const rows = sortProblemsFirst(items.filter((item) => !AGGREGATES.has(item.capability)));
  const open = (capability: string) =>
    incidents.filter(
      (incident) => incident.state !== 'resolved' && incident.capabilities.includes(capability),
    ).length;
  return (
    <section aria-labelledby="capability-table-title" data-testid="capability-table">
      <h3 id="capability-table-title">기능 상태</h3>
      <div className="row">
        <button type="button" onClick={onRefresh} data-testid="capability-refresh">
          지금 새로 고침
        </button>
        <button
          type="button"
          aria-pressed={paused}
          onClick={onTogglePause}
          data-testid="capability-pause"
        >
          {paused ? '자동 새로 고침 다시 시작' : '자동 새로 고침 일시 중지'}
        </button>
      </div>
      <table>
        <thead>
          <tr>
            <th scope="col">기능</th>
            <th scope="col">상태</th>
            <th scope="col">마지막 확인</th>
            <th scope="col">제한 사항</th>
            <th scope="col">관련 사고</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => {
            const state = shownState(item);
            const limitations = item.limitations.map(limitationText).filter(Boolean);
            return (
              <tr key={item.capability} data-testid={`capability-row-${item.capability}`}>
                <th scope="row">{item.capability}</th>
                <td>
                  <span aria-hidden="true">{ICON[state] ?? '?'}</span> {STATUS_COPY[state] ?? state}
                </td>
                <td>{ageText(item.ageSeconds)}</td>
                <td>{limitations.length ? limitations.join(', ') : '없음'}</td>
                <td>{open(item.capability) || '없음'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Summaries items={items} />
    </section>
  );
}

const minutes = (seconds: string): number => Math.round(Number(seconds) / SECONDS_PER_MINUTE);

/** `<database>:<oid>` as '<database> (<oid>)'; a component without ':' is shown whole. */
function incarnationText(component: string): string {
  const at = component.lastIndexOf(':');
  return at < 0 ? component : `${component.slice(0, at)} (${component.slice(at + 1)})`;
}

/** Each database incarnation's newest set, failed sets included, newest first (L1-52). */
export function newestSets(items: readonly DashboardItem[]): DashboardItem[] {
  const newest = new Map<string, DashboardItem>();
  for (const item of items) {
    if (item.capability !== 'operations.backup-set') continue;
    const kept = newest.get(item.component);
    if (!kept || Date.parse(item.observedAt) > Date.parse(kept.observedAt)) {
      newest.set(item.component, item);
    }
  }
  const time = (item: DashboardItem) => Date.parse(item.observedAt) || 0;
  // A stable sort keeps the dashboard's order for equal times.
  return [...newest.values()].sort((left, right) => time(right) - time(left));
}

export function backupText(item: DashboardItem): string {
  return [
    incarnationText(item.component),
    operationsTime(item.observedAt),
    INTEGRITY_COPY[item.status] ?? '무결성 확인 전',
    `보관 기한 ${operationsTime(valueOf(item, 'retain-until'))}`,
  ].join(' · ');
}

export function verificationText(item: DashboardItem): { text: string; overBound: boolean } {
  const head = `${operationsTime(item.observedAt)} · ${VERIFICATION_COPY[item.status] ?? '확인 중'}`;
  const rebuild = valueOf(item, 'hnsw-rebuild-seconds');
  if (rebuild === null) return { text: `${head} · HNSW 재구성 기록 없음`, overBound: false };
  const projected = valueOf(item, 'hnsw-projected-seconds');
  const bound = valueOf(item, 'restore-bound-seconds');
  const overBound = projected !== null && bound !== null && Number(projected) > Number(bound);
  const projection = projected === null ? UNKNOWN : `${minutes(projected)}분`;
  const limit = bound === null ? UNKNOWN : `${minutes(bound)}분`;
  return {
    text: `${head} · HNSW 재구성 ${minutes(rebuild)}분 · 8 GiB 기준 예상 ${projection} · 복원 한도 ${limit}${overBound ? ' 초과' : ''}`,
    overBound,
  };
}

/** The isolation result's stop records, or null when the result is missing or unreadable. */
export function stopRecords(
  items: readonly DashboardItem[],
): { label: string; expiresAt: string }[] | null {
  const result = items.find((item) => item.capability === 'operations.isolation-result');
  if (!result || result.limitations.includes('isolation-result-unreadable')) return null;
  return result.limitations
    .filter((entry) => entry.startsWith('stop:'))
    .map((entry) => {
      const rest = entry.slice('stop:'.length);
      const at = rest.indexOf(':');
      return at < 0
        ? { label: rest, expiresAt: '' }
        : { label: rest.slice(0, at), expiresAt: rest.slice(at + 1) };
    });
}

export function standingJobText(items: readonly DashboardItem[]): string {
  const job = items.find((item) => item.capability === 'operations.standing-job');
  if (!job) return UNKNOWN;
  if (job.limitations.includes('standing-job-unrecorded')) return '실행 기록이 아직 없습니다';
  const age = job.limitations.includes('availability-record-unreadable')
    ? `마지막 실행 ${UNKNOWN}`
    : `마지막 실행 ${ageText(job.ageSeconds)}`;
  const late = job.limitations.includes('standing-job-late') ? ' · 지연' : '';
  const count = (prefix: string) => {
    const value = valueOf(job, prefix);
    return value === null ? UNKNOWN : `${value}건`;
  };
  return `${age}${late} · 최근 24시간 실패한 백업 ${count('failed-backups')} · 실패한 검증 ${count(
    'failed-verifications',
  )} · 끝내지 못한 폐기 ${count('failed-disposals')} (측정값)`;
}

export function laneText(items: readonly DashboardItem[]): string {
  const lanes = items
    .filter((item) => item.capability === 'operations.lane')
    .sort((left, right) => left.component.localeCompare(right.component));
  if (!lanes.length) return UNKNOWN;
  const parts = lanes.map((lane) => {
    const failed = valueOf(lane, 'failed');
    const terminal = valueOf(lane, 'terminal');
    return failed === null || terminal === null
      ? `${lane.component} ${UNKNOWN}`
      : `${lane.component} 실패 ${failed}건 / 종료 ${terminal}건`;
  });
  return `${parts.join(' · ')} (측정값)`;
}

export function latencyText(items: readonly DashboardItem[]): string {
  const latency = items.filter((item) => item.capability === 'operations.latency');
  if (!latency.length) return UNKNOWN;
  return latency
    .map((item) => {
      const p95 = valueOf(item, 'p95-ms');
      const shown = p95 === 'unknown' || p95 === null ? UNKNOWN : `${p95}ms`;
      const rate = item.limitations.find((entry) => entry.startsWith('error-rate-permille:'));
      return `${item.component} ${shown}${rate ? `, 최근 5분 ${limitationText(rate)}` : ''}`;
    })
    .join(' · ');
}

function Summaries({ items }: { items: readonly DashboardItem[] }) {
  const allowance = items.find((item) => item.capability === 'operations.email-allowance');
  const availability = items.find((item) => item.capability === 'operations.availability');
  const sets = newestSets(items);
  const verifications = items.filter(
    (item) => item.capability === 'operations.restore-verification',
  );
  const stops = stopRecords(items);
  return (
    <dl data-testid="operations-summaries">
      <dt>이메일 발송</dt>
      <dd data-testid="summary-allowance">
        {allowance
          ? `오늘 ${valueOf(allowance, 'daily')}건 · 이번 달 ${valueOf(allowance, 'monthly')}건 (측정값)`
          : UNKNOWN}
      </dd>
      <dt>이번 달 가용성</dt>
      <dd data-testid="summary-availability">
        {availability
          ? `${Number(valueOf(availability, 'availability-permille')) / 10}% · 남은 허용 중단 ${Math.round(
              Number(valueOf(availability, 'budget-left-seconds')) / SECONDS_PER_MINUTE,
            )}분`
          : UNKNOWN}
      </dd>
      <dt>응답 시간(95번째 백분위)</dt>
      <dd data-testid="summary-latency">{latencyText(items)}</dd>
      <dt>최근 백업</dt>
      <dd data-testid="summary-backups">
        {sets.length ? (
          <ul>
            {sets.map((item) => (
              <li key={item.evidenceRef} data-testid="summary-backup">
                {backupText(item)}
              </li>
            ))}
          </ul>
        ) : (
          '백업이 없습니다'
        )}
      </dd>
      <dt>복원 검증</dt>
      <dd data-testid="summary-verifications">
        {verifications.length ? (
          <ul>
            {verifications.map((item) => {
              const { text, overBound } = verificationText(item);
              return (
                <li
                  key={item.evidenceRef}
                  data-testid="summary-verification"
                  {...(overBound ? { 'data-over-bound': 'true' } : {})}
                >
                  {text}
                </li>
              );
            })}
          </ul>
        ) : (
          UNKNOWN
        )}
      </dd>
      <dt>격리 확인 중지 기록</dt>
      <dd data-testid="summary-stops">
        {stops === null ? (
          UNKNOWN
        ) : stops.length ? (
          <ul>
            {stops.map((stop) => (
              <li key={`${stop.label}:${stop.expiresAt}`} data-testid="summary-stop">
                {stop.label} · 만료 {operationsTime(stop.expiresAt)}
              </li>
            ))}
          </ul>
        ) : (
          '중지 기록 없음'
        )}
      </dd>
      <dt>상시 작업</dt>
      <dd data-testid="summary-standing-job">{standingJobText(items)}</dd>
      <dt>작업 실패(24시간)</dt>
      <dd data-testid="summary-lanes">{laneText(items)}</dd>
    </dl>
  );
}
