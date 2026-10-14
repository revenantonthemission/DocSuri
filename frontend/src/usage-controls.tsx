import React, { useState } from 'react';
import type {
  WorkspaceUsagePlanPresentation as Plan,
  WorkspaceUsageMeasurePage as Measures,
  WorkspaceUsageRecordsPage as Records,
  WorkspaceUsageAssignmentSnapshot as Assignment,
  WorkspaceAccessProfile as Profile,
} from '../types/wire/dtos';
import { PolicyRef, Transport } from './api';
import { Panel, StatusLine } from './ui';
import { Disclosure, Field, OperationStatus, useOperation, useRead } from './control-ui';
import { SessionStatus } from './auth';
export function UsageControls({ client, policy }: { client: Transport; policy: PolicyRef }) {
  const plan = useRead<Plan>(client, '/api/v2/c03/usage-read-plan');
  const measures = useRead<Measures>(client, '/api/v2/c03/usage-inspect', { page: { limit: 25 } });
  const records = useRead<Records>(client, '/api/v2/c03/usage-list-records', {
    page: { limit: 25 },
  });
  const profile = useRead<Profile>(client, '/api/v2/c02/access-read-profile');
  const admin = profile.value?.fields.some(
    (field) => field.fieldId === 'role' && field.value === 'administrator',
  );
  return (
    <Panel title="사용량과 할당" testId="usage-controls">
      <p>무료 로컬 시험 할당이에요. 결제나 구매가 발생하지 않아요.</p>
      <StatusLine value={plan.error ?? measures.error ?? records.error} />
      {plan.value ? (
        <p>
          계획: {plan.value.tierId} · {plan.value.source === 'mock' ? '시험용 표시' : '관리자 할당'}
        </p>
      ) : (
        <p>계획을 확인하고 있어요</p>
      )}
      {measures.value?.items.map((item) => (
        <p key={item.metricId}>
          {item.state === 'known'
            ? `남은 사용량 ${item.remaining} / ${item.allocated} · 사용 ${item.used} · 예약 ${item.reserved} · 기간 ${item.periodId}`
            : '사용량을 확인할 수 없어요. 0으로 간주하지 않아요.'}
        </p>
      ))}
      <button
        type="button"
        onClick={() => {
          void plan.load();
          void measures.load();
          void records.load();
        }}
      >
        사용량 새로 읽기
      </button>
      <h3>사용 기록</h3>
      {records.value && !records.value.items.length ? <p>확인된 사용 기록이 없어요</p> : null}
      <ul>
        {records.value?.items.map((record) => (
          <li key={record.usageRecordId}>
            {record.operation.operationOwner} · {record.disposition} · {record.periodId}
          </li>
        ))}
      </ul>
      {records.value?.page.nextCursor ? (
        <button
          type="button"
          onClick={async () =>
            records.setValue(
              await client.read('/api/v2/c03/usage-list-records', {
                page: { limit: 25, cursor: records.value?.page.nextCursor },
              }),
            )
          }
        >
          다음 사용 기록
        </button>
      ) : null}
      {admin ? (
        measures.loading || records.loading ? (
          <p role="status">사용량을 읽은 뒤 관리자 인증을 확인해요</p>
        ) : (
          <AdministrationAccess client={client} policy={policy} />
        )
      ) : null}
    </Panel>
  );
}
function AdministrationAccess({ client, policy }: { client: Transport; policy: PolicyRef }) {
  // The two usage reads share the two-slot recovery lane. Inspect the session
  // only after they settle, so opening this page does not overload its own lane.
  const session = useRead<SessionStatus>(client, '/api/v2/c02/access-inspect-session');
  return (
    <>
      <StatusLine value={session.error} />
      {session.loading ? (
        <p role="status">관리자 인증을 확인하고 있어요</p>
      ) : session.value?.state === 'authenticated' &&
        session.value.session.authenticationLevel === 'mfa' ? (
        <Administration client={client} policy={policy} />
      ) : (
        <p>관리자 할당에는 현재 추가 인증이 필요해요. MFA 인증으로 다시 로그인해 주세요.</p>
      )}
      <button type="button" disabled={session.loading} onClick={() => void session.load()}>
        관리자 인증 다시 읽기
      </button>
    </>
  );
}
export function Administration({ client, policy }: { client: Transport; policy: PolicyRef }) {
  const [target, setTarget] = useState('');
  const [reason, setReason] = useState('');
  const [assignment, setAssignment] = useState<Assignment | null>(null);
  const [confirming, setConfirming] = useState(false);
  const operation = useOperation();
  return (
    <Disclosure title="관리자 할당">
      <p>
        현재 추가 인증과 대상 계정 권한을 서버에서 다시 확인해요. 운영자 도구 권한을 부여하지
        않아요.
      </p>
      <OperationStatus operation={operation} />
      <Field
        id="assignment-target"
        label="대상 계정 ID"
        value={target}
        onChange={(value) => {
          setTarget(value);
          setAssignment(null);
          setConfirming(false);
        }}
      />
      <button
        type="button"
        disabled={operation.busy || operation.unknown || !target}
        onClick={() =>
          void operation.run(async () =>
            setAssignment(
              await client.read<Assignment>('/api/v2/c03/usage-read-assignment', {
                accountId: target,
              }),
            ),
          )
        }
      >
        대상 할당 읽기
      </button>
      {assignment ? (
        <>
          <p>
            {assignment.entitlement
              ? `현재 할당: ${assignment.entitlement.tierId} / ${assignment.entitlement.disposition}`
              : '현재 할당 없음'}
          </p>
          <Field
            id="assignment-reason"
            label="할당 변경 사유"
            value={reason}
            onChange={setReason}
          />
          <button
            type="button"
            disabled={operation.busy || operation.unknown || !reason}
            onClick={() =>
              void operation.run(async (key) => {
                await client.post(
                  '/api/v2/c03/usage-grant-entitlement',
                  {
                    accountId: assignment.accountId,
                    tierId: 'synthetic-free',
                    reasonKey: reason,
                    expectedRevision: assignment.revision,
                    policyRef: policy,
                  },
                  key,
                );
                setAssignment(
                  await client.read('/api/v2/c03/usage-read-assignment', {
                    accountId: assignment.accountId,
                  }),
                );
              })
            }
          >
            무료 시험 할당 적용
          </button>
          {assignment.entitlement ? (
            <button type="button" onClick={() => setConfirming(true)}>
              할당 철회 준비
            </button>
          ) : null}
          {confirming ? (
            <div role="group" aria-label="할당 철회 확인">
              <p>
                이 계정의 앞으로의 할당을 철회해요. 이미 접수된 작업은 기록된 정책에 따라 처리돼요.
              </p>
              <button type="button" onClick={() => setConfirming(false)}>
                취소
              </button>
              <button
                type="button"
                disabled={operation.busy || operation.unknown || !reason}
                onClick={() =>
                  void operation.run(async (key) => {
                    await client.post(
                      '/api/v2/c03/usage-revoke-entitlement',
                      {
                        accountId: assignment.accountId,
                        entitlementId: assignment.entitlement!.entitlementId,
                        reasonKey: reason,
                        expectedRevision: assignment.revision,
                        policyRef: policy,
                      },
                      key,
                    );
                    setAssignment(
                      await client.read('/api/v2/c03/usage-read-assignment', {
                        accountId: assignment.accountId,
                      }),
                    );
                    setConfirming(false);
                  })
                }
              >
                할당 철회 확인
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </Disclosure>
  );
}
