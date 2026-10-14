import React, { useEffect, useRef, useState } from 'react';
import type {
  WorkspaceAccessProfile as Profile,
  WorkspaceAccessConsentPage as Consents,
  WorkspaceAccessIdentityPage as Links,
  WorkspaceAccessMfaEnrollment as Enrollment,
  WorkspaceAccessMfaMaterial as Material,
} from '../types/wire/dtos';
import QRCode from 'qrcode';
import { PolicyRef, Transport } from './api';
import { Panel, StatusLine } from './ui';
import { Disclosure, Field, OperationStatus, useOperation, useRead } from './control-ui';
import { SessionStatus } from './auth';

type Lifecycle = {
  lifecycleRequestId: string;
  state: 'accepted' | 'running' | 'complete' | 'blocked' | 'failed';
  revocation: string;
  participants: { participantId: string; state: string }[];
};

export function AccountControls({
  client,
  policy,
  onAuthorityChange,
  onLifecycle,
}: {
  client: Transport;
  policy: PolicyRef;
  onAuthorityChange: () => Promise<unknown>;
  onLifecycle: (id: string) => void;
}) {
  const profile = useRead<Profile>(client, '/api/v2/c02/access-read-profile');
  const [fields, setFields] = useState<Record<string, string>>({});
  const operation = useOperation();
  useEffect(() => {
    if (profile.value)
      setFields(
        Object.fromEntries(
          profile.value.fields.map((field) => [field.fieldId, String(field.value ?? '')]),
        ),
      );
  }, [profile.value]);
  return (
    <Panel title="계정 설정" testId="account-controls">
      <StatusLine value={profile.error} />
      <OperationStatus operation={operation} />
      <button
        type="button"
        onClick={() =>
          void profile.load().then((value) => {
            if (value)
              setFields(
                Object.fromEntries(
                  value.fields.map((field) => [field.fieldId, String(field.value ?? '')]),
                ),
              );
          })
        }
      >
        서버 값 다시 읽기
      </button>
      {profile.loading ? <p role="status">계정을 읽고 있어요</p> : null}
      {profile.value ? (
        <>
          <p>{profile.value.email} · 이메일 인증됨</p>
          <form
            className="stack"
            onSubmit={(event) => {
              event.preventDefault();
              void operation.run(async (key) => {
                const current = profile.value!;
                const result = await client.post<Profile>(
                  '/api/v2/c02/access-update-profile',
                  {
                    expectedRevision: current.revision,
                    fieldVocabularyRevision: current.fieldVocabularyRevision,
                    policyRef: policy,
                    changes: current.definitions
                      .filter((definition) => definition.mutable)
                      .map((definition) => ({
                        fieldId: definition.fieldId,
                        value: fields[definition.fieldId] ?? '',
                      })),
                  },
                  key,
                );
                profile.setValue(result);
              });
            }}
          >
            <fieldset disabled={operation.busy || operation.unknown}>
              {profile.value.definitions
                .filter((definition) => definition.mutable)
                .map((definition) => (
                  <Field
                    key={definition.fieldId}
                    id={`profile-${definition.fieldId}`}
                    label={
                      (
                        {
                          displayName: '표시 이름',
                          affiliation: '소속',
                          biography: '소개',
                        } as Record<string, string>
                      )[definition.fieldId] ?? definition.labelKey
                    }
                    value={fields[definition.fieldId] ?? ''}
                    onChange={(value) => setFields({ ...fields, [definition.fieldId]: value })}
                  />
                ))}
              <button type="submit">프로필 저장</button>
            </fieldset>
          </form>
          <p className="muted">
            충돌 시 입력을 유지해요. 서버 값을 다시 읽으면 작성 중인 입력을 바꿔요.
          </p>
          <Credentials client={client} policy={policy} onAuthorityChange={onAuthorityChange} />
          <LinkedIdentities client={client} policy={policy} />
          <MfaControls client={client} policy={policy} />
          <ConsentControls client={client} policy={policy} />
          <LifecycleControls
            client={client}
            policy={policy}
            revision={profile.value.lifecycleRevision}
            onLifecycle={onLifecycle}
            onAuthorityChange={onAuthorityChange}
          />
        </>
      ) : null}
    </Panel>
  );
}
function Credentials({
  client,
  policy,
  onAuthorityChange,
}: {
  client: Transport;
  policy: PolicyRef;
  onAuthorityChange: () => Promise<unknown>;
}) {
  const [proof, setProof] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const operation = useOperation();
  return (
    <Disclosure title="비밀번호와 이메일">
      <OperationStatus operation={operation} />
      <fieldset disabled={operation.busy || operation.unknown}>
        <Field
          id="current-password"
          label="현재 비밀번호"
          secret
          value={proof}
          onChange={setProof}
          autoComplete="current-password"
        />
        <Field
          id="new-password"
          label="새 비밀번호"
          secret
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
        />
        <button
          type="button"
          onClick={() =>
            void operation.run(async (key) => {
              await client.post(
                '/api/v2/c02/access-change-password',
                { currentPassword: proof, newPassword: password },
                key,
              );
              setProof('');
              setPassword('');
              await onAuthorityChange();
            })
          }
        >
          비밀번호 변경 후 다시 로그인
        </button>
        <Field
          id="new-email"
          label="새 이메일"
          type="email"
          value={email}
          onChange={setEmail}
          autoComplete="email"
        />
        <button
          type="button"
          onClick={() =>
            void operation.run(async (key) => {
              await client.post(
                '/api/v2/c02/access-request-email-change',
                { currentProof: proof, newEmail: email, policyRef: policy },
                key,
              );
              setProof('');
            })
          }
        >
          이메일 변경 인증 요청
        </button>
        <p>이메일은 전달받은 인증을 완료한 뒤 변경돼요. 실제 이메일 발송은 아직 제공되지 않아요.</p>
      </fieldset>
    </Disclosure>
  );
}
export function ConsentControls({ client, policy }: { client: Transport; policy: PolicyRef }) {
  const data = useRead<Consents>(client, '/api/v2/c02/access-list-consents', {
    page: { limit: 25 },
  });
  const operation = useOperation();
  return (
    <Disclosure title="개인정보와 처리 동의">
      <StatusLine value={data.error} />
      <OperationStatus operation={operation} />
      <p>동의 철회는 앞으로의 처리를 중지해요. 기존 데이터 삭제와 처리 완료 여부는 별도예요.</p>
      {data.value?.items.map((record) => (
        <div key={record.consentId} className="control-row">
          <span>
            {record.purposeId} · {record.decision === 'granted' ? '동의함' : '철회함'}
          </span>
          <button
            type="button"
            disabled={operation.busy || operation.unknown}
            onClick={() =>
              void operation.run(async (key) => {
                await client.post(
                  '/api/v2/c02/access-update-consent',
                  {
                    purposeId: record.purposeId,
                    decision: record.decision === 'granted' ? 'revoked' : 'granted',
                    expectedRevision: record.revision,
                    policyRef: policy,
                  },
                  key,
                );
                await data.load();
              })
            }
          >
            {record.decision === 'granted' ? '동의 철회' : '처리 동의'}
          </button>
        </div>
      ))}
      <button type="button" onClick={() => void data.load()}>
        현재 동의 다시 읽기
      </button>
    </Disclosure>
  );
}
function LinkedIdentities({ client, policy }: { client: Transport; policy: PolicyRef }) {
  const links = useRead<Links>(client, '/api/v2/c02/access-list-identity-links', {
    page: { limit: 25 },
  });
  const operation = useOperation();
  const [coverage, setCoverage] = useState('');
  return (
    <Disclosure title="Google · ORCID 연결">
      <StatusLine value={links.error} />
      <OperationStatus operation={operation} />
      <p>로컬 시험용 제공자예요. 실제 Google·ORCID 연결은 아직 사용할 수 없어요.</p>
      {(['google', 'orcid'] as const).map((provider) => (
        <button
          key={provider}
          type="button"
          disabled={operation.busy || operation.unknown}
          onClick={() =>
            void operation.run(async (key) => {
              const result = await client.post<{ authorizationUrl: string }>(
                '/api/v2/c02/access-begin-identity-flow',
                { provider, intent: 'link', returnRouteId: 'account', policyRef: policy },
                key,
              );
              const url = new URL(result.authorizationUrl, window.location.origin);
              if (
                url.origin !== window.location.origin ||
                url.pathname !== `/api/v2/identity/callback/${provider}`
              )
                throw new Error('unapproved identity return');
              await client.get(url.pathname + url.search);
              await links.load();
            })
          }
        >
          {provider} 시험 연결
        </button>
      ))}
      {links.value?.items.map((link) => (
        <div key={link.identityLinkId} className="control-row">
          <span>{link.provider}</span>
          <button
            type="button"
            disabled={operation.busy || operation.unknown}
            onClick={() =>
              void operation.run(async (key) => {
                await client.post(
                  '/api/v2/c02/access-unlink-identity',
                  { identityLinkId: link.identityLinkId, expectedRevision: link.revision },
                  key,
                );
                await links.load();
              })
            }
          >
            연결 해제
          </button>
          {link.provider === 'orcid' ? (
            <button
              type="button"
              onClick={() =>
                void operation.run(async () => {
                  const value = await client.read<{ coverage: string }>(
                    '/api/v2/c02/access-read-orcid-profile',
                    { identityLinkId: link.identityLinkId },
                  );
                  setCoverage(`ORCID 시험 자료 범위: ${value.coverage}`);
                })
              }
            >
              ORCID 자료 확인
            </button>
          ) : null}
        </div>
      ))}
      <p role="status">{coverage}</p>
    </Disclosure>
  );
}
function LocalQr({ uri }: { uri: string }) {
  const canvas = useRef<HTMLCanvasElement | null>(null);
  useEffect(() => {
    const current = canvas.current;
    if (current)
      void QRCode.toCanvas(current, uri, {
        width: 232,
        margin: 4,
        errorCorrectionLevel: 'M',
      }).catch(() => {
        if (current) current.width = 0;
      });
    return () => {
      if (current) {
        current.getContext('2d')?.clearRect(0, 0, current.width, current.height);
        current.width = 0;
      }
    };
  }, [uri]);
  return <canvas ref={canvas} aria-label="인증 앱에서 스캔할 일회성 QR 코드" role="img" />;
}
export function MfaControls({ client, policy }: { client: Transport; policy: PolicyRef }) {
  const [proof, setProof] = useState('');
  const [factor, setFactor] = useState('');
  const [enrollment, setEnrollment] = useState<Enrollment | null>(null);
  const [material, setMaterial] = useState<Material | null>(null);
  const operation = useOperation();
  const clear = () => {
    setMaterial(null);
    setProof('');
    setFactor('');
  };
  useEffect(() => {
    if (!material) return;
    const timer = window.setTimeout(
      clear,
      Math.max(0, Math.min(60_000, Date.parse(material.expiresAt) - Date.now())),
    );
    const hide = () => {
      if (document.hidden) clear();
    };
    document.addEventListener('visibilitychange', hide);
    window.addEventListener('pagehide', clear);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', hide);
      window.removeEventListener('pagehide', clear);
    };
  }, [material]);
  return (
    <details
      className="control-group"
      onToggle={(event) => {
        if (!event.currentTarget.open) clear();
      }}
    >
      <summary>추가 인증(MFA)</summary>
      <div className="control-body">
        <OperationStatus operation={operation} />
        <p>
          설정 키와 복구 코드는 한 번만 표시해요. 닫거나 시간이 지나면 지워져요. 복구 절차는 아직
          사용할 수 없어요.
        </p>
        <Field
          id="mfa-current-proof"
          label="MFA 설정용 현재 비밀번호"
          secret
          value={proof}
          onChange={setProof}
          autoComplete="current-password"
        />
        <button
          type="button"
          disabled={operation.busy || operation.unknown}
          onClick={() =>
            void operation.run(async (key) => {
              clear();
              const value = await client.post<Enrollment>(
                '/api/v2/c02/access-begin-mfa-enrollment',
                { currentProof: proof, policyRef: policy },
                key,
              );
              setEnrollment(value);
            })
          }
        >
          새 MFA 등록 준비
        </button>
        {enrollment && !material ? (
          <button
            type="button"
            disabled={operation.busy || operation.unknown}
            onClick={() =>
              void operation.run(async () => {
                const value = await client.post<Material>(
                  '/api/v2/c02/access-retrieve-mfa-enrollment-material',
                  {
                    enrollmentId: enrollment.enrollmentId,
                    deliveryReference: enrollment.deliveryReference,
                    currentProof: proof,
                  },
                );
                setMaterial(value);
                setProof('');
              })
            }
          >
            설정 키 한 번 보기
          </button>
        ) : null}
        {material ? (
          <div className="protected-material" aria-label="일회성 MFA 설정 자료">
            <LocalQr uri={material.provisioningUri} />
            <p>QR 코드를 스캔하거나 인증 앱에 수동 설정 키를 입력하세요.</p>
            <code>{material.seed}</code>
            <p>복구 코드</p>
            <ul>
              {material.recoveryCodes.map((code) => (
                <li key={code}>
                  <code>{code}</code>
                </li>
              ))}
            </ul>
            <button type="button" onClick={clear}>
              설정 자료 숨기기
            </button>
          </div>
        ) : null}
        {enrollment ? (
          <>
            <Field
              id="enrollment-factor"
              label="등록 확인 코드"
              value={factor}
              onChange={setFactor}
              autoComplete="one-time-code"
            />
            <button
              type="button"
              disabled={operation.busy || operation.unknown}
              onClick={() =>
                void operation.run(async (key) => {
                  const status = await client.read<SessionStatus>(
                    '/api/v2/c02/access-inspect-session',
                    {},
                  );
                  if (status.state !== 'authenticated') throw new Error('full session required');
                  await client.post(
                    '/api/v2/c02/access-confirm-mfa-enrollment',
                    {
                      enrollmentId: enrollment.enrollmentId,
                      verification: {
                        challengeId: enrollment.enrollmentId,
                        flowBinding: status.session.sessionId,
                        proof: factor,
                      },
                    },
                    key,
                  );
                  clear();
                  setEnrollment(null);
                })
              }
            >
              MFA 등록 확인
            </button>
          </>
        ) : null}
      </div>
    </details>
  );
}
function LifecycleControls({
  client,
  policy,
  revision,
  onLifecycle,
  onAuthorityChange,
}: {
  client: Transport;
  policy: PolicyRef;
  revision: string;
  onLifecycle: (id: string) => void;
  onAuthorityChange: () => Promise<unknown>;
}) {
  const [action, setAction] = useState<'withdraw' | 'erase'>('withdraw');
  const [proof, setProof] = useState('');
  const [confirmation, setConfirmation] = useState<{
    confirmationRef: string;
    action: string;
  } | null>(null);
  const operation = useOperation();
  return (
    <Disclosure title="탈퇴와 데이터 삭제">
      <OperationStatus operation={operation} />
      <p>
        탈퇴는 접근을 중지하고 허용된 보관 데이터를 남겨요. 삭제는 정해진 범위의 데이터를 제거하며
        되돌릴 수 없어요. 접수와 전체 정리 완료는 달라요.
      </p>
      <label>
        처리 범위
        <select
          value={action}
          disabled={!!confirmation}
          onChange={(event) => setAction(event.target.value as typeof action)}
        >
          <option value="withdraw">탈퇴</option>
          <option value="erase">계정 데이터 삭제</option>
        </select>
      </label>
      <Field
        id="lifecycle-proof"
        label="계정 처리용 현재 비밀번호"
        secret
        value={proof}
        onChange={setProof}
        autoComplete="current-password"
      />
      {!confirmation ? (
        <button
          type="button"
          disabled={operation.busy || operation.unknown}
          onClick={() =>
            void operation.run(async (key) => {
              setConfirmation(
                await client.post(
                  '/api/v2/c02/access-prepare-lifecycle',
                  { action, currentProof: proof, expectedRevision: revision, policyRef: policy },
                  key,
                ),
              );
              setProof('');
            })
          }
        >
          처리 범위 확인 준비
        </button>
      ) : (
        <div role="group" aria-label="계정 처리 최종 확인">
          <p>{action === 'erase' ? '계정 데이터 삭제' : '탈퇴'}를 접수할까요?</p>
          <button type="button" onClick={() => setConfirmation(null)}>
            취소
          </button>
          <button
            type="button"
            disabled={operation.busy || operation.unknown}
            onClick={() =>
              void operation.run(async (key) => {
                const result = await client.post<Lifecycle>(
                  '/api/v2/c02/lifecycle-request',
                  { action, confirmationRef: confirmation.confirmationRef, policyRef: policy },
                  key,
                );
                onLifecycle(result.lifecycleRequestId);
                await onAuthorityChange();
              })
            }
          >
            확인하고 접수
          </button>
        </div>
      )}
    </Disclosure>
  );
}
export function LifecycleProgress({ client, id }: { client: Transport; id: string }) {
  const result = useRead<Lifecycle>(client, '/api/v2/c02/lifecycle-inspect', {
    lifecycleRequestId: id,
  });
  return (
    <Panel title="계정 처리 현황">
      <StatusLine value={result.error} />
      <button type="button" onClick={() => void result.load()}>
        처리 현황 다시 읽기
      </button>
      {result.value ? (
        <>
          <p role="status">
            {result.value.state === 'complete'
              ? '모든 필수 범위의 처리가 완료됐어요'
              : '접수된 요청의 처리가 아직 완료되지 않았어요'}{' '}
            · {result.value.state}
          </p>
          <p>접근 중지: {result.value.revocation}</p>
          <ul>
            {result.value.participants.map((item, index) => (
              <li key={index}>
                {item.participantId}: {item.state}
              </li>
            ))}
          </ul>
        </>
      ) : null}
    </Panel>
  );
}
