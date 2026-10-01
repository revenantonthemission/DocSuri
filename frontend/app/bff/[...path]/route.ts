import { createHash } from 'node:crypto';
import { NextResponse, type NextRequest } from 'next/server';
import { HttpTransport } from '@/lib/api/httpTransport';
import { MockTransport } from '@/lib/api/mockTransport';
import {
  binaryBody,
  type Transport,
  type TransportMethod,
  type TransportResponse,
} from '@/lib/api/transport';

// BFF (Backend-for-Frontend) — the server-side seam between the browser and the
// U6 gateway (LC-2, P-S1, SEC-3/12).
//
// Client components call the same-origin RouteHandlerTransport (`/bff/*`), which
// reaches this catch-all. Here — and ONLY here — the gateway URL is known and the
// inbound httpOnly session cookie is forwarded to the gateway. The token never
// enters client JS. Transport is chosen by DOCSURI_GATEWAY_URL: set => the real
// gateway (HttpTransport), unset => mock (so previews work without infra). The
// gateway's Set-Cookie (e.g. the login session) is relayed back to the browser.
//
// NOTE: the assembled backend must resolve the session cookie into an authenticated
// principal (request.state.principal) for /library/* and /api/search; that gateway
// auth-injection is tracked separately (backend coordination zone, system-infra step).

const SSE_PROXY_TIMEOUT_MS = 15000;
// asset image relay(REM-2 F07): 개당 수십~수백 KB webp라 기본값으로 충분하고,
// 게이트웨이가 응답하면 로컬로 끝나므로(외부 S3로 나가는 홉이 아님) 더 길게 잡을 이유가 없다.
const ASSET_IMAGE_TIMEOUT_MS = 10000;
// evidence 턴(OpenSearch 검색 + 다건 S3 DocModel 로드 + Bedrock 추출)은 동기로 30~90초
// 걸린다 — HttpTransport 기본 10초로는 백엔드가 정상 완료돼도 이 서버->게이트웨이 홉이
// 먼저 끊겨 504로 보인다(ApiClient의 90초 타임아웃과는 별개 레이어, PR #338 후속 발견).
const EVIDENCE_GATEWAY_TIMEOUT_MS = 90000;
// 검색 콜드 패스(첫 질의: Bedrock embed + OpenSearch k-NN 그래프 첫 로드 + rerank)는 정상
// 완료가 9~12초까지 걸린다 — 기본 10초 홉이 백엔드 완료 직전에 끊어 504를 만들던 것이
// QA 2026-07-10 F1 (evidence 경로의 PR #338과 같은 클래스). 백엔드는 자체 단계별 예산으로
// fail-closed/soft 하므로, 이 홉은 그보다 길게 잡아 완료된 응답을 버리지 않는다.
// (CloudFront origin 타임아웃 30초가 실질 상한이라 그 이상은 의미 없음.)
const SEARCH_GATEWAY_TIMEOUT_MS = 30000;
// SQ3 mitigation (serverless-plan Phase 1-①): dev Aurora Serverless v2 pauses at 0 ACU, and
// the first request during resume can die at the gateway (network error or 502/503/504).
// GETs are safe to replay, so they retry ONCE after this pause; non-GET never retries.
const DB_RESUME_RETRY_DELAY_MS = 1500;
const DB_RESUME_RETRYABLE_STATUSES = new Set([502, 503, 504]);

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isEvidenceHeavyPath(upstreamPath: string): boolean {
  return (
    upstreamPath.startsWith('/api/research/jobs') || upstreamPath.startsWith('/api/evidence/turns')
  );
}

function isSearchPath(upstreamPath: string): boolean {
  return upstreamPath.startsWith('/api/search');
}

function gatewayTimeoutMs(upstreamPath: string): number | undefined {
  if (isEvidenceHeavyPath(upstreamPath)) return EVIDENCE_GATEWAY_TIMEOUT_MS;
  if (isSearchPath(upstreamPath)) return SEARCH_GATEWAY_TIMEOUT_MS;
  return undefined;
}

function buildTransport(req: NextRequest, upstreamPath: string): Transport | null {
  const baseUrl = process.env.DOCSURI_GATEWAY_URL;
  if (baseUrl) {
    return new HttpTransport({
      baseUrl,
      cookieHeader: req.headers.get('cookie') ?? undefined,
      timeoutMs: gatewayTimeoutMs(upstreamPath),
    });
  }
  if (process.env.NODE_ENV === 'production' && process.env.DOCSURI_BFF_ALLOW_MOCK !== '1') {
    return null;
  }
  return new MockTransport();
}

function forwardedHeaders(req: NextRequest): Record<string, string> | undefined {
  const recaptchaToken = req.headers.get('x-recaptcha-token');
  return recaptchaToken ? { 'X-Recaptcha-Token': recaptchaToken } : undefined;
}

function isNoveltyEventStream(method: TransportMethod, path: string[]): boolean {
  return (
    method === 'GET' &&
    path.length === 5 &&
    path[0] === 'api' &&
    path[1] === 'novelty' &&
    path[2] === 'jobs' &&
    path[4] === 'events'
  );
}

// US-EV2/NFR-P6 — 동기 evidence 턴의 SSE 표면(POST + Accept: text/event-stream).
// research(에이전트 채팅의 evidence 모드)와 U11 canonical 엔드포인트 둘 다 지원한다.
// 게이트웨이 미구성(mock) 시에는 일반 proxy로 흘려 JSON 폴백이 그대로 동작한다.
function isAgentTurnStream(req: NextRequest, method: TransportMethod, path: string[]): boolean {
  if (method !== 'POST') return false;
  if (!req.headers.get('accept')?.includes('text/event-stream')) return false;
  const upstream = `/${path.join('/')}`;
  return (
    upstream === '/api/evidence/turns' ||
    upstream === '/api/research/jobs' ||
    (path.length === 5 &&
      path[0] === 'api' &&
      path[1] === 'research' &&
      path[2] === 'jobs' &&
      path[4] === 'messages')
  );
}

function isPdfBody(req: NextRequest): boolean {
  return (
    req.headers.get('content-type')?.split(';', 1)[0].trim().toLowerCase() === 'application/pdf'
  );
}

async function proxyEventStream(
  req: NextRequest,
  upstreamPath: string,
  options?: { method?: 'GET' | 'POST'; body?: string; timeoutMs?: number },
): Promise<NextResponse> {
  const baseUrl = process.env.DOCSURI_GATEWAY_URL;
  if (!baseUrl) {
    if (process.env.NODE_ENV === 'production' && process.env.DOCSURI_BFF_ALLOW_MOCK !== '1') {
      return NextResponse.json(
        { message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.' },
        { status: 503 },
      );
    }
    return new NextResponse(null, {
      status: 204,
      headers: {
        'cache-control': 'no-store',
        'content-type': 'text/event-stream',
      },
    });
  }

  const method = options?.method ?? 'GET';
  const headers = new Headers({ accept: 'text/event-stream' });
  if (options?.body !== undefined) {
    headers.set('content-type', 'application/json');
    // OAC(Lambda Function URL) 오리진의 본문 요청 요건 — HttpTransport와 동일 계약
    // (미동봉 POST → 403 signature mismatch, 1-③ 카나리 실측). ALB 오리진은 무시.
    headers.set(
      'x-amz-content-sha256',
      createHash('sha256').update(options.body).digest('hex'),
    );
  }
  const cookie = req.headers.get('cookie');
  if (cookie) headers.set('cookie', cookie);

  const controller = new AbortController();
  // 타이머는 헤더 도착까지만 유효하다(finally에서 해제) — 본문 스트리밍은 끊지 않는다.
  const timer = setTimeout(() => controller.abort(), options?.timeoutMs ?? SSE_PROXY_TIMEOUT_MS);
  try {
    const res = await fetch(`${baseUrl}${upstreamPath}`, {
      method,
      headers,
      body: options?.body,
      cache: 'no-store',
      signal: controller.signal,
    });
    const out = new NextResponse(res.body, {
      status: res.status,
      headers: {
        'cache-control': 'no-store',
        'content-type': res.headers.get('content-type') ?? 'text/event-stream',
      },
    });
    const getSetCookie = (res.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie;
    const cookies = getSetCookie?.call(res.headers) ?? [];
    const fallbackCookie = res.headers.get('set-cookie');
    for (const setCookie of cookies.length ? cookies : fallbackCookie ? [fallbackCookie] : []) {
      out.headers.append('set-cookie', setCookie);
    }
    return out;
  } catch {
    return NextResponse.json(
      { message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.' },
      { status: 502 },
    );
  } finally {
    clearTimeout(timer);
  }
}

// figure/table 원본 이미지(REM-2 F07 / SECURITY-8) — `/api/papers/<id>/assets/<assetId>`.
// Transport는 응답 본문을 항상 JSON으로 파싱하므로(이미지 body면 null이 된다) 이 홉만 직접 fetch한다.
function isAssetImageRequest(method: TransportMethod, path: string[]): boolean {
  return (
    method === 'GET' &&
    path.length === 5 &&
    path[0] === 'api' &&
    path[1] === 'papers' &&
    path[3] === 'assets'
  );
}

function notFoundImage(): NextResponse {
  // 이미지 실패는 404로 접는다 — 뷰어 쪽이 "이미지 없음"으로 자연스럽게 degrade하고,
  // 게이트웨이 주소·본문·Set-Cookie 같은 내부 정보가 5xx 본문으로 새어나가지 않는다.
  return new NextResponse(null, { status: 404, headers: { 'cache-control': 'no-store' } });
}

// U7이 object storage를 **서버에서** 읽어 돌려주는 같은 출처 이미지 relay.
// presigned URL은 더 이상 어디에도 등장하지 않으므로 브라우저는 object store를 알 수 없다.
async function proxyAssetImage(req: NextRequest, upstreamPath: string): Promise<NextResponse> {
  const baseUrl = process.env.DOCSURI_GATEWAY_URL;
  if (!baseUrl) {
    if (process.env.NODE_ENV === 'production' && process.env.DOCSURI_BFF_ALLOW_MOCK !== '1') {
      return NextResponse.json(
        { message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.' },
        { status: 503 },
      );
    }
    return notFoundImage();
  }
  const headers = new Headers({ accept: 'image/*' });
  const cookie = req.headers.get('cookie');
  if (cookie) headers.set('cookie', cookie);

  let res: Response;
  try {
    res = await fetch(`${baseUrl}${upstreamPath}`, {
      method: 'GET',
      headers,
      cache: 'no-store',
      signal: AbortSignal.timeout(ASSET_IMAGE_TIMEOUT_MS),
    });
  } catch {
    // 게이트웨이 응답 실패(네트워크/타임아웃). 이미지는 본체 표시에 부가적이므로
    // throw 대신 404 degrade — SSE 홉과 달리 사용자에게 오류 UI를 띄우지 않는다.
    return notFoundImage();
  }
  // 3xx를 그대로 넘기면 Location이 object store URL이 되어 브라우저가 그 주소를 알게 된다.
  // 리다이렉트를 따라가는 fetch도 마찬가지 — 업스트림이 200 이미지일 때만 통과시킨다.
  if (res.status !== 200) return notFoundImage();
  const contentType = res.headers.get('content-type')?.split(';', 1)[0].trim() ?? '';
  // <img> 컨텍스트에 JSON/HTML이 들어오면 깨진 이미지거나 content-type confusion이 된다.
  if (!contentType.startsWith('image/')) return notFoundImage();

  const out = new NextResponse(res.body, {
    status: 200,
    headers: {
      'content-type': contentType,
      'cache-control': res.headers.get('cache-control') ?? 'private, no-store',
      // 스니핑으로 이미지가 아닌 것이 <img>로 렌더링되는 걸 막는다.
      'x-content-type-options': 'nosniff',
    },
  });
  const getSetCookie = (res.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie;
  const cookies = getSetCookie?.call(res.headers) ?? [];
  const fallbackCookie = res.headers.get('set-cookie');
  for (const setCookie of cookies.length ? cookies : fallbackCookie ? [fallbackCookie] : []) {
    out.headers.append('set-cookie', setCookie);
  }
  return out;
}

async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const method = req.method as TransportMethod;
  const upstreamPath = `/${path.join('/')}${req.nextUrl.search}`;

  if (isAssetImageRequest(method, path)) {
    return proxyAssetImage(req, upstreamPath);
  }

  if (isNoveltyEventStream(method, path)) {
    return proxyEventStream(req, upstreamPath);
  }

  // 동기 evidence 턴 SSE(US-EV2) — novelty와 같은 스트리밍 홉으로 흘린다. 게이트웨이
  // 미구성(mock) 시엔 일반 proxy로 폴스루해 FE가 JSON 응답으로 폴백한다(fail-soft).
  if (isAgentTurnStream(req, method, path) && process.env.DOCSURI_GATEWAY_URL) {
    return proxyEventStream(req, upstreamPath, {
      method: 'POST',
      body: await req.text(),
      timeoutMs: EVIDENCE_GATEWAY_TIMEOUT_MS,
    });
  }

  let body: unknown;
  if (method !== 'GET' && method !== 'DELETE') {
    if (isPdfBody(req)) {
      body = binaryBody(new Uint8Array(await req.arrayBuffer()), 'application/pdf');
    } else {
      const text = await req.text();
      if (text) {
        try {
          body = JSON.parse(text);
        } catch {
          return NextResponse.json({ message: '잘못된 요청 형식입니다.' }, { status: 400 });
        }
      }
    }
  }

  const transport = buildTransport(req, upstreamPath);
  if (!transport) {
    return NextResponse.json(
      { message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.' },
      { status: 503 },
    );
  }

  const sendUpstream = () =>
    transport.send({
      method,
      path: upstreamPath,
      body,
      headers: forwardedHeaders(req),
      idempotent: method === 'GET',
    });
  const gatewayTimeoutResponse = () =>
    NextResponse.json(
      { message: '요청 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.' },
      { status: 504 },
    );

  let res: TransportResponse | null = null;
  try {
    res = await sendUpstream();
  } catch {
    // Gateway hang/timeout (HttpTransport AbortSignal.timeout) — fail fast so a slow
    // upstream can't pin BFF sockets into an FE-wide outage (BR-U5-10, NFR-U5-R2).
    // GET falls through to the single SQ3 resume retry below instead.
    if (method !== 'GET') return gatewayTimeoutResponse();
  }
  // SQ3 mitigation: one replay after the Aurora-resume pause, GET only (safe to repeat).
  if (method === 'GET' && (res === null || DB_RESUME_RETRYABLE_STATUSES.has(res.status))) {
    await delay(DB_RESUME_RETRY_DELAY_MS);
    try {
      res = await sendUpstream();
    } catch {
      return gatewayTimeoutResponse();
    }
  }
  if (res === null) return gatewayTimeoutResponse();

  // 204 No Content / 304 Not Modified must not carry a body — NextResponse.json() always
  // attaches one, and the Response constructor then throws ("Invalid response status code
  // 204"), turning a successful upstream DELETE (un-bookmark, delete saved search, clear
  // history) into a 500. Relay those status-only, still forwarding any Set-Cookie.
  const out =
    res.status === 204 || res.status === 304
      ? new NextResponse(null, { status: res.status })
      : NextResponse.json(res.body ?? null, { status: res.status });
  for (const cookie of res.setCookies ?? []) out.headers.append('set-cookie', cookie);
  return out;
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  return proxy(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  return proxy(req, (await ctx.params).path);
}
export async function PUT(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  return proxy(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  return proxy(req, (await ctx.params).path);
}
export async function DELETE(req: NextRequest, ctx: Ctx): Promise<NextResponse> {
  return proxy(req, (await ctx.params).path);
}
