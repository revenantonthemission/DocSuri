import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PersonalControls, ResetHistory } from '../../src/personal-controls';
import { Administration, UsageControls } from '../../src/usage-controls';
import {
  fakeClient,
  failed,
  page,
  policy,
  profile,
  reset,
  settings,
  settingsPolicy,
} from './fixtures';
const open = (text: string) => fireEvent.click(screen.getByText(text));
const input = (label: string, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
function personal(overrides = {}) {
  const client = fakeClient(overrides);
  const appearance = vi.fn();
  render(<PersonalControls client={client.transport} policy={policy} onAppearance={appearance} />);
  return { client, appearance };
}
describe('U2 personal controls', () => {
  it('waits for both usage recovery reads before inspecting an administrator session', async () => {
    let measures!: (value: unknown) => void;
    let records!: (value: unknown) => void;
    const client = fakeClient({
      '/api/v2/c02/access-read-profile': {
        ...profile,
        fields: [{ fieldId: 'role', value: 'administrator' }],
      },
    });
    const ordinary = client.read.getMockImplementation()!;
    client.read.mockImplementation((path) =>
      path === '/api/v2/c03/usage-inspect'
        ? new Promise((resolve) => {
            measures = resolve;
          })
        : path === '/api/v2/c03/usage-list-records'
          ? new Promise((resolve) => {
              records = resolve;
            })
          : ordinary(path),
    );
    render(<UsageControls client={client.transport} policy={policy} />);
    await screen.findByText('사용량을 읽은 뒤 관리자 인증을 확인해요');
    expect(
      client.read.mock.calls.some(([path]) => path === '/api/v2/c02/access-inspect-session'),
    ).toBe(false);
    await act(async () => measures(page()));
    expect(
      client.read.mock.calls.some(([path]) => path === '/api/v2/c02/access-inspect-session'),
    ).toBe(false);
    await act(async () => records(page()));
    await screen.findByRole('button', { name: '관리자 인증 다시 읽기' });
    expect(
      client.read.mock.calls.filter(([path]) => path === '/api/v2/c02/access-inspect-session'),
    ).toHaveLength(1);
  });
  it('lets an administrator recover a refused session read without repeating a mutation', async () => {
    const client = fakeClient({
      '/api/v2/c02/access-read-profile': {
        ...profile,
        fields: [{ fieldId: 'role', value: 'administrator' }],
      },
    });
    const ordinary = client.read.getMockImplementation()!;
    let attempts = 0;
    client.read.mockImplementation((path) =>
      path === '/api/v2/c02/access-inspect-session' && attempts++ === 0
        ? Promise.reject(failed('NOT_READY'))
        : ordinary(path),
    );
    render(<UsageControls client={client.transport} policy={policy} />);
    await screen.findByRole('alert');
    open('관리자 인증 다시 읽기');
    await waitFor(() => expect(screen.queryByRole('alert')).toBeNull());
    expect(client.post).not.toHaveBeenCalled();
  });

  it('drops an older reset-list response after changing the view', async () => {
    const client = fakeClient();
    let finish!: (value: unknown) => void;
    client.get.mockImplementation((path) =>
      path.includes('view=outstanding')
        ? new Promise((resolve) => {
            finish = resolve;
          })
        : Promise.resolve(page()),
    );
    render(<ResetHistory client={client.transport} />);
    fireEvent.change(screen.getByLabelText('처리 기록 범위'), { target: { value: 'history' } });
    await screen.findByText(/이 범위에서 확인된 요청이 없어요/);
    await act(async () => finish(page([reset])));
    expect(screen.queryByRole('button', { name: /활동 데이터 삭제 · 정리 진행 중/ })).toBeNull();
    expect(client.post).not.toHaveBeenCalled();
  });

  it('reads acknowledged defaults and does not mutate on opening', async () => {
    const { client } = personal();
    expect(await screen.findByLabelText('저장할 화면 모드')).toHaveValue('system');
    expect(client.post).not.toHaveBeenCalled();
  });
  it('saves actual settings changes with the original shared revision', async () => {
    const { client, appearance } = personal();
    await screen.findByLabelText('저장할 화면 모드');
    input('저장할 화면 모드', 'dark');
    input('기본 정렬', 'newest');
    input('기본 언어', 'ko');
    input('기본 도움 기능', 'translate');
    client.post.mockResolvedValue({ ...settings, appearance: 'dark', revision: 'settings-r2' });
    open('기본 설정 저장');
    await waitFor(() => expect(appearance).toHaveBeenCalledWith('dark'));
    expect(client.post.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        expectedRevision: 'settings-r1',
        policyRef: settingsPolicy,
        appearance: 'dark',
        assistanceDefaults: expect.objectContaining({ languageId: 'ko', actionId: 'translate' }),
      }),
    );
  });
  it('retains local settings on conflict until an explicit reload', async () => {
    const { client } = personal();
    await screen.findByLabelText('기본 검색 방식');
    input('기본 검색 방식', 'semantic');
    client.post.mockRejectedValueOnce(failed('STALE_REVISION'));
    open('기본 설정 저장');
    expect(await screen.findByText('다른 곳에서 변경되었어요')).toBeVisible();
    expect(screen.getByLabelText('기본 검색 방식')).toHaveValue('semantic');
    open('저장된 설정 다시 읽기');
    await waitFor(() => expect(screen.getByLabelText('기본 검색 방식')).toHaveValue('lexical'));
  });
  it.each(['관심 분야 저장', '시작 설정 완료', '선택을 유지하고 건너뛰기'])(
    'persists %s without losing acknowledged interests',
    async (label) => {
      const { client } = personal();
      await screen.findByLabelText('기본 검색 방식');
      open('관심 분야와 시작 설정');
      client.post.mockResolvedValue(settings);
      open(label);
      await waitFor(() => expect(client.post).toHaveBeenCalledOnce());
      expect(client.post.mock.calls[0][1]).toEqual(
        expect.objectContaining({ expectedRevision: 'settings-r1', interestIds: ['1706.03762'] }),
      );
    },
  );
  it('allows manual interest choices when ORCID is absent', async () => {
    const { client } = personal();
    await screen.findByLabelText('기본 검색 방식');
    open('관심 분야와 시작 설정');
    fireEvent.click(screen.getByRole('checkbox', { name: /검색 증강/ }));
    client.post.mockResolvedValue({ ...settings, interestIds: ['1706.03762', '2005.11401'] });
    open('관심 분야 저장');
    await waitFor(() => expect(client.post).toHaveBeenCalledOnce());
    expect(client.post.mock.calls[0][1].interestIds).toEqual(['1706.03762', '2005.11401']);
  });
  it('requires current proof and explicit confirmation before reset acceptance', async () => {
    const { client } = personal();
    await screen.findByLabelText('기본 검색 방식');
    open('활동 삭제와 추천 프로필 초기화');
    input('초기화용 현재 비밀번호', 'secret');
    client.post
      .mockResolvedValueOnce({ confirmationRef: 'confirmation-a', revision: 'settings-r1' })
      .mockResolvedValueOnce({ resetId: 'reset-a' });
    open('초기화 범위 확인 준비');
    expect(await screen.findByText('초기화 접수')).toBeVisible();
    expect(client.post).toHaveBeenCalledTimes(1);
    open('초기화 접수');
    await waitFor(() => expect(client.post).toHaveBeenCalledTimes(2));
    expect(client.post.mock.calls[1][1]).toEqual({
      action: 'delete_behavior',
      confirmationRef: 'confirmation-a',
      expectedRevision: 'settings-r1',
      policyRef: policy,
    });
  });
  it('cancels reset confirmation without submitting the destructive action', async () => {
    const { client } = personal();
    await screen.findByLabelText('기본 검색 방식');
    open('활동 삭제와 추천 프로필 초기화');
    client.post.mockResolvedValue({ confirmationRef: 'confirmation-a', revision: 'settings-r1' });
    input('초기화 범위', 'reset_profile');
    input('초기화용 현재 비밀번호', 'secret');
    open('초기화 범위 확인 준비');
    await screen.findByText('초기화 접수');
    open('취소');
    expect(client.post).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('초기화 접수')).toBeNull();
  });
  it('discovers outstanding resets after a fresh render without issuing writes', async () => {
    const client = fakeClient();
    render(<ResetHistory client={client.transport} />);
    expect(await screen.findByText(/정리 진행 중/)).toBeVisible();
    expect(client.post).not.toHaveBeenCalled();
    open(screen.getByText(/정리 진행 중/).textContent!);
    expect(await screen.findByText(/접수된 경계와 정리 완료는 별도/)).toBeVisible();
    expect(client.get).toHaveBeenCalledWith('/api/v2/c03/settings-resets/reset-a');
  });
  it('keeps empty reset results distinct from unknown acceptance', async () => {
    const client = fakeClient({ '/api/v2/c03/settings-resets?view=outstanding&limit=25': page() });
    render(<ResetHistory client={client.transport} />);
    expect(await screen.findByText(/실패를 뜻하지는 않아요/)).toBeVisible();
  });
  it('shows unavailable reset reads without rendering an empty success', async () => {
    const client = fakeClient({
      '/api/v2/c03/settings-resets?view=outstanding&limit=25': failed(),
    });
    render(<ResetHistory client={client.transport} />);
    expect(await screen.findByRole('alert')).toBeVisible();
    expect(screen.queryByText(/확인된 요청이 없어요/)).toBeNull();
  });
  it('paginates reset history with an encoded owner-bound cursor', async () => {
    const client = fakeClient({
      '/api/v2/c03/settings-resets?view=outstanding&limit=25': page([reset], {
        page: { nextCursor: 'opaque:cursor', snapshotRevision: 's' },
      }),
    });
    render(<ResetHistory client={client.transport} />);
    client.get.mockImplementation(async (path: string) =>
      path.includes('cursor=')
        ? page()
        : page([reset], { page: { nextCursor: 'opaque:cursor', snapshotRevision: 's' } }),
    );
    open(await screen.findByText('다음 처리 기록').then(() => '다음 처리 기록'));
    await waitFor(() =>
      expect(client.get).toHaveBeenCalledWith(
        '/api/v2/c03/settings-resets?view=outstanding&limit=25&cursor=opaque%3Acursor',
      ),
    );
  });
  it('can switch to retained reset history and manually refresh without claims', async () => {
    const client = fakeClient();
    render(<ResetHistory client={client.transport} />);
    await screen.findByText(/정리 진행 중/);
    input('처리 기록 범위', 'history');
    await waitFor(() =>
      expect(client.get).toHaveBeenCalledWith('/api/v2/c03/settings-resets?view=history&limit=25'),
    );
    open('처리 기록 새로 읽기');
    await waitFor(() => expect(client.get).toHaveBeenCalledTimes(3));
    expect(client.post).not.toHaveBeenCalled();
  });
  it('labels mock plans and known server period without billing controls', async () => {
    const client = fakeClient();
    render(<UsageControls client={client.transport} policy={policy} />);
    expect(await screen.findByText(/남은 사용량 2 \/ 4/)).toBeVisible();
    expect(screen.getByText(/시험용 표시/)).toBeVisible();
    expect(screen.queryByRole('button', { name: /구매/ })).toBeNull();
  });
  it('does not turn unknown usage into zero balance', async () => {
    const client = fakeClient({
      '/api/v2/c03/usage-inspect': page([
        { state: 'unknown', metricId: 'paper-assistance', reasonKey: 'unavailable' },
      ]),
    });
    render(<UsageControls client={client.transport} policy={policy} />);
    expect(await screen.findByText(/0으로 간주하지 않아요/)).toBeVisible();
  });
  it('requires current MFA before rendering administrator mutation controls', async () => {
    const client = fakeClient();
    client.read.mockImplementation(async (path: string) =>
      path === '/api/v2/c02/access-read-profile'
        ? { fields: [{ fieldId: 'role', value: 'administrator' }] }
        : path === '/api/v2/c02/access-inspect-session'
          ? { state: 'authenticated', session: { authenticationLevel: 'primary' } }
          : page(),
    );
    render(<UsageControls client={client.transport} policy={policy} />);
    expect(await screen.findByText(/현재 추가 인증이 필요/)).toBeVisible();
    expect(screen.queryByLabelText('대상 계정 ID')).toBeNull();
  });
  it('uses the selected target assignment revision for grants', async () => {
    const client = fakeClient({
      '/api/v2/c03/usage-read-assignment': {
        accountId: 'account-b',
        revision: 'assignment-r1',
        entitlement: null,
      },
    });
    render(<Administration client={client.transport} policy={policy} />);
    open('관리자 할당');
    input('대상 계정 ID', 'account-b');
    open('대상 할당 읽기');
    await screen.findByText('현재 할당 없음');
    input('할당 변경 사유', 'local-proof');
    open('무료 시험 할당 적용');
    await waitFor(() =>
      expect(client.post).toHaveBeenCalledWith(
        '/api/v2/c03/usage-grant-entitlement',
        {
          accountId: 'account-b',
          tierId: 'synthetic-free',
          reasonKey: 'local-proof',
          expectedRevision: 'assignment-r1',
          policyRef: policy,
        },
        expect.any(String),
      ),
    );
  });
  it('clears assignment state when the target changes', async () => {
    const client = fakeClient({
      '/api/v2/c03/usage-read-assignment': {
        accountId: 'account-b',
        revision: 'assignment-r1',
        entitlement: null,
      },
    });
    render(<Administration client={client.transport} policy={policy} />);
    open('관리자 할당');
    input('대상 계정 ID', 'account-b');
    open('대상 할당 읽기');
    await screen.findByText('현재 할당 없음');
    input('대상 계정 ID', 'account-c');
    expect(screen.queryByText('현재 할당 없음')).toBeNull();
    expect(client.post).not.toHaveBeenCalled();
  });
  it('requires confirmation before revoking the observed assignment', async () => {
    const client = fakeClient({
      '/api/v2/c03/usage-read-assignment': {
        accountId: 'account-b',
        revision: 'assignment-r1',
        entitlement: {
          entitlementId: 'entitlement-b',
          tierId: 'synthetic-free',
          disposition: 'active',
        },
      },
    });
    render(<Administration client={client.transport} policy={policy} />);
    open('관리자 할당');
    input('대상 계정 ID', 'account-b');
    open('대상 할당 읽기');
    await screen.findByText(/현재 할당: synthetic/);
    input('할당 변경 사유', 'local-revoke');
    open('할당 철회 준비');
    expect(client.post).not.toHaveBeenCalled();
    open('할당 철회 확인');
    await waitFor(() =>
      expect(client.post).toHaveBeenCalledWith(
        '/api/v2/c03/usage-revoke-entitlement',
        {
          accountId: 'account-b',
          entitlementId: 'entitlement-b',
          reasonKey: 'local-revoke',
          expectedRevision: 'assignment-r1',
          policyRef: policy,
        },
        expect.any(String),
      ),
    );
  });
});
