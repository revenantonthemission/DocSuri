/** ConnectForm (BR1.1–BR1.3, D7, R-03, NFR5.1): the write-only token field, its
validation, the "확인 중" state and the two CONFLICT cases told apart by re-reading. */

import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ConnectForm } from '../../src/u6-export/connect-form';
import {
  CONFLICT_CHANGED,
  CONFLICT_STILL_CHECKING,
  CONFLICT_UNAVAILABLE,
  CONNECT_REFUSAL_COPY,
} from '../../src/u6-export/copy';
import { connection, envelope, ExportDouble, POLICY, TOKEN } from './fixtures';

function setup(api: ExportDouble, current: ReturnType<typeof connection> | null = null) {
  const onSaved = vi.fn();
  const onReload = vi.fn();
  const announce = vi.fn();
  const view = render(
    <ConnectForm
      client={api.client()}
      policy={POLICY}
      connection={current}
      onSaved={onSaved}
      onReload={onReload}
      announce={announce}
    />,
  );
  return { ...view, onSaved, onReload, announce };
}

const field = () => screen.getByTestId('connect-token') as HTMLInputElement;

async function submitToken(value = TOKEN) {
  await userEvent.type(field(), value);
  await userEvent.click(screen.getByTestId('connect-submit'));
}

afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  vi.restoreAllMocks();
});

describe('the token field', () => {
  it('is a plain text field without autocomplete or spellcheck', () => {
    setup(new ExportDouble());
    const input = field();
    expect(input.type).toBe('text');
    expect(input.getAttribute('autocomplete')).toBe('off');
    expect(input.getAttribute('spellcheck')).toBe('false');
    expect(screen.getByLabelText('Notion 통합 토큰')).toBe(input);
  });

  it('clears the field after a successful submit and reports the workspace, not the token', async () => {
    const api = new ExportDouble().on('configure-notion-connection', () => connection());
    const { onSaved, announce, container } = setup(api);
    await submitToken();
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(connection()));
    expect(field().value).toBe('');
    expect(api.named('configure-notion-connection')[0]!.body).toEqual({
      token: TOKEN,
      expectedRevision: null,
      credentialPolicy: POLICY,
    });
    expect(announce).toHaveBeenLastCalledWith(
      'Notion 워크스페이스 ‘시험 워크스페이스’에 연결했습니다',
    );
    expect(container.innerHTML).not.toContain(TOKEN);
  });

  it('clears the field after a refused submit and names the refusal without echoing the token', async () => {
    const api = new ExportDouble().on('configure-notion-connection', () => {
      throw envelope('INVALID_TOKEN', 422);
    });
    const { container, onSaved } = setup(api);
    await submitToken();
    const refusal = await screen.findByTestId('connect-refusal');
    expect(refusal.textContent).toBe(CONNECT_REFUSAL_COPY.INVALID_TOKEN);
    expect(field().value).toBe('');
    expect(container.innerHTML).not.toContain(TOKEN);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it('names a blank or unprintable token without echoing it and sends nothing', async () => {
    const api = new ExportDouble();
    const { container } = setup(api);
    await userEvent.type(field(), '   ');
    await userEvent.click(screen.getByTestId('connect-submit'));
    expect(screen.getByTestId('connect-field-error').textContent).toBe('토큰을 입력해 주세요');
    expect(field().getAttribute('aria-invalid')).toBe('true');
    fireEvent.change(field(), { target: { value: 'secret_bad\u0007value' } });
    fireEvent.submit(screen.getByTestId('connect-form'));
    expect(screen.getByTestId('connect-field-error').textContent).toContain('쓸 수 없는 문자');
    expect(container.innerHTML).not.toContain('secret_bad');
    fireEvent.change(field(), { target: { value: 'x'.repeat(513) } });
    fireEvent.submit(screen.getByTestId('connect-form'));
    expect(screen.getByTestId('connect-field-error').textContent).toContain('너무 깁니다');
    expect(api.calls).toEqual([]);
  });

  it('never puts the token in storage, the URL, a cookie or a log', async () => {
    const logs = [
      vi.spyOn(console, 'log'),
      vi.spyOn(console, 'info'),
      vi.spyOn(console, 'warn'),
      vi.spyOn(console, 'error'),
      vi.spyOn(console, 'debug'),
    ];
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const api = new ExportDouble().on('configure-notion-connection', () => connection());
    const { onSaved } = setup(api);
    await submitToken();
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const stored = JSON.stringify({ ...window.localStorage, ...window.sessionStorage });
    expect(stored).not.toContain(TOKEN);
    expect(setItem.mock.calls.flat().join(' ')).not.toContain(TOKEN);
    expect(window.location.href).not.toContain(TOKEN);
    expect(document.cookie).not.toContain(TOKEN);
    for (const log of logs) expect(JSON.stringify(log.mock.calls)).not.toContain(TOKEN);
  });
});

describe('while configure is in flight', () => {
  it('shows 확인 중 and disables a second submit', async () => {
    let finish: (value: unknown) => void = () => undefined;
    const api = new ExportDouble().on(
      'configure-notion-connection',
      () => new Promise((resolve) => (finish = resolve)),
    );
    const { onSaved } = setup(api);
    await submitToken();
    expect(screen.getByTestId('connect-submit').textContent).toBe('확인 중');
    expect(screen.getByTestId('connect-checking').textContent).toContain('확인 중');
    expect(screen.getByTestId('connect-submit')).toBeDisabled();
    expect(field()).toBeDisabled();
    finish(connection());
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(screen.queryByTestId('connect-checking')).toBeNull();
  });
});

describe('the connect help (D7)', () => {
  it('asks for read content and insert content only', () => {
    setup(new ExportDouble());
    const help = screen.getByTestId('connect-help');
    const text = help.textContent ?? '';
    expect(text).toContain('콘텐츠 읽기(Read content)');
    expect(text).toContain('콘텐츠 삽입(Insert content)');
    expect(help.querySelectorAll('li')).toHaveLength(2);
    for (const forbidden of [
      '업데이트',
      'Update',
      '댓글',
      'Comment',
      '사용자 정보',
      'user information',
    ])
      expect(text).not.toContain(forbidden);
  });
});

describe('a configure CONFLICT (R-03)', () => {
  it('says another window is checking when the connection still reads as not connected', async () => {
    const api = new ExportDouble()
      .on('configure-notion-connection', () => {
        throw envelope('CONFLICT');
      })
      .on('read-notion-connection', () => {
        throw envelope('NOT_FOUND', 404);
      });
    const { onReload } = setup(api);
    await submitToken();
    const refusal = await screen.findByTestId('connect-refusal');
    expect(refusal.textContent).toBe(CONFLICT_STILL_CHECKING);
    expect(api.named('read-notion-connection')).toHaveLength(1);
    expect(onReload).not.toHaveBeenCalled();
  });

  it('says the connection changed and reloads it when another place connected it', async () => {
    const newer = connection({ revision: '2' });
    const api = new ExportDouble()
      .on('configure-notion-connection', () => {
        throw envelope('CONFLICT');
      })
      .on('read-notion-connection', () => newer);
    const { onReload } = setup(api);
    await submitToken();
    expect((await screen.findByTestId('connect-refusal')).textContent).toBe(CONFLICT_CHANGED);
    expect(onReload).toHaveBeenCalledWith(newer);
  });

  it('reloads a stale revision on replace', async () => {
    const newer = connection({ revision: '3' });
    const api = new ExportDouble()
      .on('configure-notion-connection', () => {
        throw envelope('CONFLICT');
      })
      .on('read-notion-connection', () => newer);
    const { onReload } = setup(api, connection({ revision: '2' }));
    expect(screen.getByTestId('connect-submit').textContent).toBe('토큰 교체');
    await submitToken();
    expect((await screen.findByTestId('connect-refusal')).textContent).toBe(CONFLICT_CHANGED);
    expect(api.named('configure-notion-connection')[0]!.body).toMatchObject({
      expectedRevision: '2',
    });
    expect(onReload).toHaveBeenCalledWith(newer);
    expect(field().value).toBe('');
  });

  it('points to disconnecting first when the connection is unavailable', async () => {
    const unavailable = connection({ state: 'unavailable', revision: '2' });
    const api = new ExportDouble()
      .on('configure-notion-connection', () => {
        throw envelope('CONFLICT');
      })
      .on('read-notion-connection', () => unavailable);
    const { onReload } = setup(api, connection({ state: 'revoked', revision: '2' }));
    await submitToken();
    expect((await screen.findByTestId('connect-refusal')).textContent).toBe(CONFLICT_UNAVAILABLE);
    expect(onReload).toHaveBeenCalledWith(unavailable);
  });

  it('shows the read failure itself when the re-read fails', async () => {
    const api = new ExportDouble()
      .on('configure-notion-connection', () => {
        throw envelope('CONFLICT');
      })
      .on('read-notion-connection', () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      });
    setup(api);
    await submitToken();
    expect((await screen.findByTestId('connect-refusal')).textContent).toBe(
      '일시적으로 사용할 수 없어요',
    );
  });
});

describe('a reconnect after disconnect', () => {
  it('sends the disconnected record revision as expected', async () => {
    const api = new ExportDouble().on('configure-notion-connection', () =>
      connection({ revision: '5' }),
    );
    const { onSaved } = setup(api, connection({ state: 'disconnected', revision: '4' }));
    expect(screen.getByTestId('connect-submit').textContent).toBe('연결');
    await submitToken();
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(api.named('configure-notion-connection')[0]!.body).toMatchObject({
      expectedRevision: '4',
    });
    expect(api.violations).toEqual([]);
  });
});
