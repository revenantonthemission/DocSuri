import 'server-only';
import { createHash } from 'node:crypto';
import {
  isBinaryTransportBody,
  type Transport,
  type TransportRequest,
  type TransportResponse,
} from './transport';

// SHA-256 of an empty payload — 본문 없는 비-GET 요청에 동봉한다.
const EMPTY_PAYLOAD_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

// HttpTransport (LC-2, P-S1) — SERVER-ONLY.
//
// `import 'server-only'` makes a client-side import a build error: the gateway
// base URL and the httpOnly session cookie never reach the browser bundle
// (SEC-3/12). Forwards the incoming session cookie to the U6 gateway; the token
// lives only in the server<->gateway hop.
//
// Inert until the U6 gateway is deployed — the app runs on MockTransport today.
// Swapping mock -> http is a configuration change (see lib/api/index.ts).

export interface HttpTransportConfig {
  baseUrl: string;
  /** The raw Cookie header captured server-side from the inbound request. */
  cookieHeader?: string;
  /** Server->gateway hop timeout (ms). Defaults to 10000. */
  timeoutMs?: number;
}

export class HttpTransport implements Transport {
  constructor(private readonly config: HttpTransportConfig) {}

  async send(req: TransportRequest): Promise<TransportResponse> {
    const requestBody = req.body;
    const binary = isBinaryTransportBody(requestBody);
    // 전송 바이트를 한 번 확정해 해시와 body가 항상 같은 바이트를 가리키게 한다.
    // (Blob은 미리 Uint8Array로 변환 — fetch에 그대로 전달해도 동일 바이트.)
    let payload: string | Uint8Array | undefined;
    if (requestBody !== undefined) {
      if (binary) {
        const data = requestBody.data;
        payload =
          data instanceof Uint8Array
            ? data
            : data instanceof ArrayBuffer
              ? new Uint8Array(data)
              : new Uint8Array(await data.arrayBuffer());
      } else {
        payload = JSON.stringify(requestBody);
      }
    }
    const headers: Record<string, string> = {
      ...(requestBody !== undefined
        ? { 'content-type': binary ? requestBody.contentType : 'application/json' }
        : {}),
      ...(req.headers ?? {}),
    };
    if (req.method !== 'GET') {
      // OAC(Lambda Function URL) 오리진은 본문 있는 요청에 클라이언트가 계산한
      // x-amz-content-sha256을 요구한다 — 미동봉 POST는 403 signature mismatch
      // (serverless 1-③ 카나리 실측, 2026-08-05). ALB 오리진은 이 헤더를 무시하므로
      // 상시 동봉이 안전하고, 오리진 스위치와 독립적으로 선반영할 수 있다.
      headers['x-amz-content-sha256'] =
        payload === undefined
          ? EMPTY_PAYLOAD_SHA256
          : createHash('sha256').update(payload).digest('hex');
    }
    if (this.config.cookieHeader) headers['cookie'] = this.config.cookieHeader;

    const res = await fetch(`${this.config.baseUrl}${req.path}`, {
      method: req.method,
      headers,
      body: payload,
      // Never cache personalized/authenticated responses (P-P3).
      cache: 'no-store',
      // The BFF (app/bff/[...path]/route.ts) is the sole caller and never sets req.signal, so
      // this server->gateway hop needs its own timeout: ApiClient's timeout only covers the
      // browser->BFF hop, and without this a gateway hang would pin BFF sockets for ~300s and
      // take down the whole FE (BR-U5-10, NFR-U5-R2).
      signal: AbortSignal.timeout(this.config.timeoutMs ?? 10000),
    });

    let body: unknown = null;
    const text = await res.text();
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = null;
      }
    }
    // Capture Set-Cookie (e.g. the login session cookie) so the BFF can relay it
    // to the browser. getSetCookie() is the spec way to read multiple values.
    const setCookies =
      typeof res.headers.getSetCookie === 'function' ? res.headers.getSetCookie() : [];
    return { status: res.status, body, setCookies };
  }
}
