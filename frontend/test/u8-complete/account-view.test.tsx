// U8 plan Step 92(l) (L1-58, your answer of 2026-11-02, "Complete-app texts for both"): U2's
// 계정 view keeps its texts without the switch, and with `isCompleteApp` says what the
// complete app does; the switch changes no request.
import React from 'react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { AccountControls } from '../../src/account-controls';
import type { Transport } from '../../src/api';

vi.mock('qrcode', () => ({ default: { toCanvas: vi.fn().mockResolvedValue(undefined) } }));

const POLICY = { policyId: 'u8-account-view-test', revision: '1' };
const PROFILE = {
  accountId: 'account-member',
  email: 'member@example.test',
  emailVerified: true,
  revision: 'p1',
  lifecycleRevision: 'l1',
  fieldVocabularyRevision: 'v1',
  definitions: [],
  fields: [],
};
const EMPTY = { items: [], page: { snapshotRevision: 's' } };
const ORCID_LINK = {
  items: [{ identityLinkId: 'link-a', provider: 'orcid', revision: 'link-r1' }],
  page: { snapshotRevision: 's' },
};

const U2_EMAIL =
  '이메일은 전달받은 인증을 완료한 뒤 변경돼요. 실제 이메일 발송은 아직 제공되지 않아요.';
const U2_LINKS = '로컬 시험용 제공자예요. 실제 Google·ORCID 연결은 아직 사용할 수 없어요.';
const COMPLETE_EMAIL =
  '이메일은 전달받은 인증을 완료한 뒤 변경돼요. 메일의 링크는 이 브라우저에서 로그인한 상태에서 열어 주세요.';
const COMPLETE_LINKS = '새 Google·ORCID 연결은 아직 이 화면에서 할 수 없어요.';

// A fake client of its own, built as lifecycle-retained.test.tsx builds one.
function client(links: unknown = EMPTY) {
  const read = vi.fn(async (path: string) => {
    if (path === '/api/v2/c02/access-read-profile') return PROFILE;
    if (path === '/api/v2/c02/access-list-consents') return EMPTY;
    if (path === '/api/v2/c02/access-list-identity-links') return links;
    if (path === '/api/v2/c02/access-inspect-session') return { state: 'anonymous' };
    return EMPTY;
  });
  const post = vi
    .fn<(path: string, body?: unknown, key?: string) => Promise<unknown>>()
    .mockResolvedValue({});
  const get = vi.fn(async () => ({}));
  return { transport: { read, post, get } as unknown as Transport, read, post, get };
}

async function mount(isCompleteApp: boolean | undefined, links: unknown = EMPTY) {
  const fake = client(links);
  render(
    <AccountControls
      client={fake.transport}
      policy={POLICY}
      onAuthorityChange={vi.fn().mockResolvedValue({})}
      onLifecycle={vi.fn()}
      {...(isCompleteApp !== undefined ? { isCompleteApp } : {})}
    />,
  );
  await screen.findByText(/member@example\.test/);
  fireEvent.click(screen.getByText('비밀번호와 이메일'));
  fireEvent.click(screen.getByText('Google · ORCID 연결'));
  return fake;
}

describe("the 계정 view's texts", () => {
  it("keeps U2's 계정 view without the switch", async () => {
    await mount(undefined);
    const view = screen.getByTestId('account-controls');
    expect(view).toHaveTextContent(U2_EMAIL);
    expect(view).toHaveTextContent(U2_LINKS);
    expect(screen.getByRole('button', { name: 'google 시험 연결' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'orcid 시험 연결' })).toBeInTheDocument();
  });

  it("the complete app's 계정 says what it does", async () => {
    const fake = await mount(true, ORCID_LINK);
    const view = screen.getByTestId('account-controls');
    expect(view).toHaveTextContent(COMPLETE_EMAIL);
    expect(view).toHaveTextContent(COMPLETE_LINKS);
    expect(view).not.toHaveTextContent('실제 이메일 발송은 아직 제공되지 않아요');
    expect(view).not.toHaveTextContent('로컬 시험용 제공자예요');
    expect(screen.queryAllByRole('button', { name: /시험 연결/ })).toHaveLength(0);
    const unlink = await screen.findByRole('button', { name: '연결 해제' });
    expect(screen.getByRole('button', { name: 'ORCID 자료 확인' })).toBeInTheDocument();
    fireEvent.click(unlink);
    await waitFor(() =>
      expect(fake.post).toHaveBeenCalledWith(
        '/api/v2/c02/access-unlink-identity',
        { identityLinkId: 'link-a', expectedRevision: 'link-r1' },
        expect.any(String),
      ),
    );
    expect(
      fake.post.mock.calls.some(([path]) => path === '/api/v2/c02/access-begin-identity-flow'),
    ).toBe(false);
  });

  it('the switch changes no request', async () => {
    const fake = await mount(true);
    const proof = crypto.randomUUID();
    fireEvent.change(screen.getByLabelText('현재 비밀번호'), { target: { value: proof } });
    fireEvent.change(screen.getByLabelText('새 이메일'), {
      target: { value: 'next@example.test' },
    });
    fireEvent.click(screen.getByText('이메일 변경 인증 요청'));
    await waitFor(() =>
      expect(fake.post).toHaveBeenCalledWith(
        '/api/v2/c02/access-request-email-change',
        { currentProof: proof, newEmail: 'next@example.test', policyRef: POLICY },
        expect.any(String),
      ),
    );
  });

  it('imports no U8 module', () => {
    const source = readFileSync(join(__dirname, '..', '..', 'src', 'account-controls.tsx'), 'utf8');
    const specifiers = [...source.matchAll(/(?:from|import)\s*['"]([^'"]+)['"]/g)].map(
      (match) => match[1]!,
    );
    expect(specifiers.length).toBeGreaterThan(0);
    expect(specifiers.filter((specifier) => specifier.startsWith('./u8-'))).toEqual([]);
  });
});
