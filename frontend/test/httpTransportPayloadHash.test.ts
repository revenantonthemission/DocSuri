// serverless 1-③ 카나리 실측 후속 — OAC(Lambda Function URL) 오리진은 본문 있는
// 요청에 클라이언트 x-amz-content-sha256을 요구한다(미동봉 POST → 403 signature
// mismatch). HttpTransport가 "실제 전송 바이트"의 해시를 상시 동봉하는지 검증한다.
import { createHash } from 'node:crypto';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

import { HttpTransport } from '@/lib/api/httpTransport';
import { binaryBody } from '@/lib/api/transport';

const EMPTY_PAYLOAD_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

function sha256Hex(data: string | Uint8Array): string {
  return createHash('sha256').update(data).digest('hex');
}

describe('HttpTransport x-amz-content-sha256 (OAC payload hash)', () => {
  const captured: { headers?: Headers; body?: unknown } = {};

  beforeEach(() => {
    captured.headers = undefined;
    captured.body = undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        captured.headers = new Headers(init.headers as HeadersInit);
        captured.body = init.body;
        return new Response('{}', { status: 200 });
      }),
    );
  });

  it('POST JSON 본문 — 전송 문자열의 SHA-256을 동봉한다', async () => {
    const transport = new HttpTransport({ baseUrl: 'https://gw.test' });
    const body = { email: 'user@test.dev', password: 'pw' };

    await transport.send({ method: 'POST', path: '/auth/login', body, idempotent: false });

    const sent = captured.body as string;
    expect(sent).toBe(JSON.stringify(body));
    expect(captured.headers?.get('x-amz-content-sha256')).toBe(sha256Hex(sent));
  });

  it('POST 바이너리 본문 — 바이트의 SHA-256을 동봉한다', async () => {
    const transport = new HttpTransport({ baseUrl: 'https://gw.test' });
    const bytes = new Uint8Array([37, 80, 68, 70, 45]); // %PDF-

    await transport.send({
      method: 'POST',
      path: '/api/research/attachments',
      body: binaryBody(bytes, 'application/pdf'),
      idempotent: false,
    });

    expect(captured.headers?.get('x-amz-content-sha256')).toBe(sha256Hex(bytes));
    expect(captured.headers?.get('content-type')).toBe('application/pdf');
  });

  it('본문 없는 비-GET — 빈 페이로드 해시를 동봉한다', async () => {
    const transport = new HttpTransport({ baseUrl: 'https://gw.test' });

    await transport.send({ method: 'DELETE', path: '/api/research/jobs', idempotent: true });

    expect(captured.headers?.get('x-amz-content-sha256')).toBe(EMPTY_PAYLOAD_SHA256);
  });

  it('GET — 헤더를 동봉하지 않는다 (OAC가 빈 페이로드로 서명)', async () => {
    const transport = new HttpTransport({ baseUrl: 'https://gw.test' });

    await transport.send({ method: 'GET', path: '/api/library', idempotent: true });

    expect(captured.headers?.get('x-amz-content-sha256')).toBeNull();
  });
});
