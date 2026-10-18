// U5 topics test doubles: a Transport-compatible fake recording every call.
import type { Transport } from '../../src/api';
import type {
  Cadence,
  DeliveryDay,
  FollowResult,
  SettingsSaveResult,
  Topic,
  TopicList,
  UnsubscribeResult,
} from '../../src/u5-topics/api';

export const settings = (changes: Record<string, unknown> = {}) =>
  ({
    cadence: 'daily',
    deliveryTimeLocal: '08:00',
    deliveryDay: null,
    contentWindowDays: 7,
    revision: 1,
    ...changes,
  }) as {
    cadence: Cadence;
    deliveryTimeLocal: string;
    deliveryDay: DeliveryDay | null;
    contentWindowDays: 7 | 30;
    revision: number;
  };

export const topic = (changes: Record<string, unknown> = {}): Topic => ({
  topicId: '11111111-1111-4111-8111-111111111111',
  topicKey: 'quantum-error-correction',
  displayName: '양자 오류 정정',
  status: 'active',
  followedAt: '2026-10-18T00:00:00+00:00',
  settings: settings(),
  lastRun: { runId: null, state: null, windowEnd: null, observedState: null },
  ...changes,
});

export const listing = (topics: Topic[]): TopicList => ({ topics });

export class TopicsDouble {
  generation = 1;
  calls: { method: string; path: string; body: unknown }[] = [];
  private routes = new Map<string, (path: string, body: unknown) => unknown>();

  on(route: string, handler: (path: string, body: unknown) => unknown) {
    this.routes.set(route, handler);
    return this;
  }

  private async dispatch<T>(method: string, path: string, body: unknown): Promise<T> {
    this.calls.push({ method, path, body });
    const handler = this.routes.get(`${method} ${path}`);
    if (!handler) throw new Error(`Unexpected call ${method} ${path}`);
    return (await handler(path, body)) as T;
  }

  get<T>(path: string): Promise<T> {
    return this.dispatch<T>('GET', path, undefined);
  }
  post<T>(path: string, body: unknown): Promise<T> {
    return this.dispatch<T>('POST', path, body);
  }
  put<T>(path: string, body: unknown): Promise<T> {
    return this.dispatch<T>('PUT', path, body);
  }
  del<T>(path: string): Promise<T> {
    return this.dispatch<T>('DELETE', path, undefined);
  }
  client(): Transport {
    return this as unknown as Transport;
  }
}

export const followResult = (changes: Record<string, unknown> = {}): FollowResult => ({
  topicId: '22222222-2222-4222-8222-222222222222',
  status: 'active',
  reactivated: false,
  ...changes,
});

export const unsubscribeResult = (changes: Record<string, unknown> = {}): UnsubscribeResult => ({
  topicId: '11111111-1111-4111-8111-111111111111',
  status: 'unsubscribed',
  discardedRunIds: [],
  unchanged: false,
  ...changes,
});

export const saveResult = (changes: Record<string, unknown> = {}): SettingsSaveResult => ({
  settings: settings({ revision: 2, cadence: 'weekly', deliveryDay: 'mon' }),
  discardedRunIds: [],
  unchanged: false,
  ...changes,
});
