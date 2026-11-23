/**
 * IncidentList (frontend-components.md "OperationsView"; BR3.7, BR9.7, BR9.14): unresolved
 * incidents first, each with its capabilities, opening time, state, diagnosis, linked
 * recovery requests and opaque evidence references. 복구 요청 opens the recovery panel
 * prefilled. A 복구 요청 begins the incident's investigation and links its request (L1-19);
 * 해결 처리 is left to the operator tool, and an abort's and a rollback copy's incident say so
 * in their own words.
 */
import React, { useId } from 'react';
import { evidenceOf, operationsTime, type Incident } from './api';

export const INCIDENT_STATE_COPY: Readonly<Record<Incident['state'], string>> = {
  open: '열림',
  investigating: '조사 중',
  recovering: '복구 중',
  resolved: '해결됨',
};
export const RESOLUTION_COPY: Readonly<Record<string, string>> = {
  'capability-available': '기능 복구됨',
  'abort-reviewed': '중단 검토 완료',
  'rollback-copy-settled': '롤백 사본 처리 완료',
  'environment-stopped': '환경 중지',
};
/** The diagnosis keys the product writes; a key without copy shows as written. */
export const DIAGNOSIS_COPY: Readonly<Record<string, string>> = {
  'recovery-requested': '복구 요청됨',
};
export const INVESTIGATE_DESCRIPTION = '조사는 복구 요청과 함께 시작됩니다';
const PREFIXES = ['opened', 'role', 'diagnosis', 'recovery'];

export function resolveDescription(incident: Incident): string {
  const [role] = evidenceOf(incident, 'role');
  if (role === 'abort') return '관리자 도구에서 전환 중단 검토가 기록되어야 합니다';
  if (role === 'rollback-copy') return '관리자 도구에서 롤백 사본이 처리되어야 합니다';
  return '증거가 확인되면 관리자 도구에서 해결을 기록합니다';
}

function opened(incident: Incident): string {
  const [value] = evidenceOf(incident, 'opened');
  return operationsTime(value);
}

function IncidentItem({ incident, onRecover }: { incident: Incident; onRecover: () => void }) {
  const investigateId = useId();
  const resolveId = useId();
  const opaque = incident.evidenceRefs.filter(
    (entry) => !PREFIXES.some((prefix) => entry.startsWith(`${prefix}:`)),
  );
  const [diagnosis] = evidenceOf(incident, 'diagnosis');
  const requests = evidenceOf(incident, 'recovery');
  const resolved = incident.state === 'resolved';
  return (
    <li data-testid="incident-item">
      <p>
        <strong>{incident.capabilities.join(', ')}</strong> · {INCIDENT_STATE_COPY[incident.state]}{' '}
        · 열린 시각 {opened(incident)}
      </p>
      {diagnosis ? <p>진단: {DIAGNOSIS_COPY[diagnosis] ?? diagnosis}</p> : null}
      {requests.length ? <p>연결된 복구 요청: {requests.join(', ')}</p> : null}
      {opaque.length ? <p className="muted">증거: {opaque.join(', ')}</p> : null}
      {resolved ? (
        <p data-testid="incident-resolution">
          {RESOLUTION_COPY[incident.resolutionKind ?? ''] ?? incident.resolutionKind}
        </p>
      ) : (
        <div className="row">
          <button
            type="button"
            aria-disabled="true"
            aria-describedby={investigateId}
            data-testid="incident-investigate"
          >
            조사 시작
          </button>
          <span id={investigateId} className="muted">
            {INVESTIGATE_DESCRIPTION}
          </span>
          <button type="button" onClick={onRecover} data-testid="incident-recover">
            복구 요청
          </button>
          <button
            type="button"
            aria-disabled="true"
            aria-describedby={resolveId}
            data-testid="incident-resolve"
          >
            해결 처리
          </button>
          <span id={resolveId} className="muted" data-testid="incident-resolve-reason">
            {resolveDescription(incident)}
          </span>
        </div>
      )}
    </li>
  );
}

export function IncidentList({
  incidents,
  onRecover,
}: {
  incidents: readonly Incident[];
  onRecover: (incident: Incident) => void;
}) {
  const ordered = [
    ...incidents.filter((incident) => incident.state !== 'resolved'),
    ...incidents.filter((incident) => incident.state === 'resolved'),
  ];
  return (
    <section aria-labelledby="incident-list-title" data-testid="incident-list">
      <h3 id="incident-list-title">사고</h3>
      {ordered.length === 0 ? <p>열린 사고가 없습니다</p> : null}
      <ul>
        {ordered.map((incident) => (
          <IncidentItem
            key={incident.incidentId}
            incident={incident}
            onRecover={() => onRecover(incident)}
          />
        ))}
      </ul>
    </section>
  );
}
