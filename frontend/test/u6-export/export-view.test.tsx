/** ExportView: the five view states, the connection panel and history paging. A record
still being checked answers NOT_FOUND and reads as not connected (cicd §8.1). */

import React from 'react';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { ExportView, exportViewState } from '../../src/u6-export/export-view';
import {
  capability,
  connection,
  envelope,
  ExportDouble,
  historyEntry,
  historyPage,
  mount,
  TOKEN,
} from './fixtures';

const notConnected = () => {
  throw envelope('NOT_FOUND', 404);
};

function view(api: ExportDouble) {
  return mount(<ExportView client={api.client()} capability={capability()} />);
}

const state = () => screen.getByTestId('export-view').getAttribute('data-view-state');

describe('export view states', () => {
  it('starts loading, then shows the empty state with the connect action first', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', notConnected)
      .on('list-export-history', () => historyPage([]));
    view(api);
    expect(screen.getByTestId('export-loading')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: '내보내기' })).toBeInTheDocument();
    await screen.findByTestId('export-empty');
    expect(state()).toBe('empty');
    expect(screen.getByRole('heading', { level: 2, name: 'Notion 연결' })).toBeInTheDocument();
    expect(screen.getByTestId('connection-state').textContent).toContain('연결되지 않음');
    expect(screen.getByTestId('connect-form')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '내보내기 기록' })).toBeNull();
  });

  it('reads a pending record (NOT_FOUND) as not connected, never as a fifth state', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', notConnected)
      .on('list-export-history', () => historyPage([historyEntry()]));
    view(api);
    await screen.findByTestId('history-row');
    expect(state()).toBe('ready');
    expect(screen.getByTestId('connection-state').textContent).toContain('연결되지 않음');
    expect(screen.queryByText(/pending/)).toBeNull();
    expect(api.named('read-notion-connection')[0]!.body).toEqual({});
  });

  it('shows the error state when both reads fail', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      })
      .on('list-export-history', () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      });
    view(api);
    await screen.findByTestId('export-error');
    expect(state()).toBe('error');
  });

  it('shows partial when the connection fails and the history loads', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      })
      .on('list-export-history', () => historyPage([historyEntry()]));
    view(api);
    await screen.findByTestId('export-partial');
    expect(screen.getByTestId('export-partial').textContent).toContain('연결 상태');
    expect(screen.getByTestId('history-row')).toBeInTheDocument();
    expect(screen.queryByTestId('connect-form')).toBeNull();
  });

  it('shows partial when the history fails and the connection loads', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-history', () => {
        throw envelope('DEPENDENCY_UNAVAILABLE', 503);
      });
    view(api);
    await screen.findByTestId('export-partial');
    expect(screen.getByTestId('export-partial').textContent).toContain('기록');
    expect(screen.getByTestId('connection-workspace').textContent).toContain('시험 워크스페이스');
  });

  it('shows ready with the workspace name and the synthetic limitation', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-history', () => historyPage([]));
    view(api);
    await screen.findByTestId('connection-workspace');
    expect(state()).toBe('ready');
    expect(screen.getByTestId('connection-limitations').textContent).toContain('시험 환경');
    expect(screen.getByTestId('history-empty')).toBeInTheDocument();
    expect(document.body.innerHTML).not.toContain(TOKEN);
  });

  it('derives every state from the two reads', () => {
    const base = {
      connectionLoading: false,
      historyLoading: false,
      connectionFailed: false,
      historyFailed: false,
      connected: true,
      historyCount: 0,
    };
    expect(exportViewState({ ...base, historyLoading: true })).toBe('loading');
    expect(exportViewState({ ...base, connectionFailed: true, historyFailed: true })).toBe('error');
    expect(exportViewState({ ...base, historyFailed: true })).toBe('partial');
    expect(exportViewState({ ...base, connected: false })).toBe('empty');
    expect(exportViewState(base)).toBe('ready');
  });
});

describe('connection panel', () => {
  it('disconnects only after the dialog names the consequences', async () => {
    let current = connection();
    const api = new ExportDouble()
      .on('read-notion-connection', () => current)
      .on('list-export-history', () => historyPage([]))
      .on('disconnect-notion', () => {
        current = { ...connection({ state: 'disconnected', revision: '2' }), limitations: [] };
        return current;
      });
    view(api);
    await userEvent.click(await screen.findByTestId('connection-disconnect'));
    const dialog = screen.getByTestId('disconnect-dialog');
    expect(dialog.textContent).toContain('아직 시작하지 않은 승인은 무효가 됩니다');
    expect(dialog.textContent).toContain('Notion에 그대로 남습니다');
    expect(api.named('disconnect-notion')).toHaveLength(0);
    await userEvent.click(within(dialog).getByTestId('disconnect-confirm'));
    await screen.findByTestId('connection-notice');
    expect(api.named('disconnect-notion')[0]!.body).toEqual({});
    await waitFor(() =>
      expect(screen.getByTestId('connection-state').textContent).toContain('연결 해제됨'),
    );
    expect(screen.getByTestId('connect-form')).toBeInTheDocument();
  });

  it('keeps the connection when the dialog is dismissed', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-history', () => historyPage([]));
    view(api);
    await userEvent.click(await screen.findByTestId('connection-disconnect'));
    await userEvent.click(screen.getByTestId('disconnect-keep'));
    expect(screen.queryByTestId('disconnect-dialog')).toBeNull();
    expect(api.named('disconnect-notion')).toHaveLength(0);
  });

  it('reports a refused disconnect in plain words', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-history', () => historyPage([]))
      .on('disconnect-notion', () => {
        throw envelope('NOT_FOUND', 404);
      });
    view(api);
    await userEvent.click(await screen.findByTestId('connection-disconnect'));
    await userEvent.click(screen.getByTestId('disconnect-confirm'));
    expect((await screen.findByTestId('connection-notice')).textContent).toBe('찾을 수 없어요');
  });

  it('opens and closes the replace form for a connected record', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-history', () => historyPage([]))
      .on('configure-notion-connection', () => connection({ revision: '2' }));
    view(api);
    await userEvent.click(await screen.findByTestId('connection-replace'));
    expect(screen.getByTestId('connect-form')).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('connection-replace-cancel'));
    expect(screen.queryByTestId('connect-form')).toBeNull();
    await userEvent.click(screen.getByTestId('connection-replace'));
    await userEvent.type(screen.getByTestId('connect-token'), TOKEN);
    await userEvent.click(screen.getByTestId('connect-submit'));
    await waitFor(() => expect(screen.queryByTestId('connect-form')).toBeNull());
    expect(api.named('configure-notion-connection')[0]!.body).toMatchObject({
      expectedRevision: '1',
    });
  });

  it('offers only disconnect from unavailable', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection({ state: 'unavailable' }))
      .on('list-export-history', () => historyPage([]));
    view(api);
    await screen.findByTestId('connection-unavailable-note');
    expect(screen.queryByTestId('connect-form')).toBeNull();
    expect(screen.queryByTestId('connection-replace')).toBeNull();
    expect(screen.getByTestId('connection-disconnect')).toBeInTheDocument();
  });

  it('offers a reconnect for a revoked record', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection({ state: 'revoked', revision: '3' }))
      .on('list-export-history', () => historyPage([]));
    view(api);
    await screen.findByTestId('connect-form');
    expect(screen.getByTestId('connection-state').textContent).toContain('다시 연결하세요');
  });
});

describe('history paging', () => {
  it('pages forward by cursor and back', async () => {
    const second = historyEntry({
      approvalId: '77777777-7777-4777-8777-777777777777',
      sourceTitle: '두 번째 결과',
    });
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-history', (body) =>
        (body as { cursor: string | null }).cursor === 'cursor-2'
          ? historyPage([second])
          : historyPage([historyEntry()], 'cursor-2'),
      );
    view(api);
    await userEvent.click(await screen.findByTestId('history-next'));
    await screen.findByText('두 번째 결과');
    expect(api.named('list-export-history').at(-1)!.body).toEqual({
      limit: 20,
      cursor: 'cursor-2',
    });
    await userEvent.click(screen.getByTestId('history-previous'));
    await waitFor(() => expect(screen.queryByText('두 번째 결과')).toBeNull());
    expect(api.violations).toEqual([]);
  });
});
