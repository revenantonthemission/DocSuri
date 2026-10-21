/** DestinationStep (BR1.5, BR8.2, decision S2): listing notices, placeholders and
context, unusable pages with reasons, creation capability as far as known, and the
preselection of the last used page. */

import React from 'react';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DestinationStep } from '../../src/u6-export/destination-step';
import type { Connection, Destinations } from '../../src/u6-export/api';
import {
  connection,
  destinations,
  entry,
  envelope,
  ExportDouble,
  mount,
  PAGE_A,
  PAGE_B,
  PAGE_C,
} from './fixtures';

function step(listing: Destinations | (() => Destinations), current: Connection = connection()) {
  const api = new ExportDouble().on('list-export-destinations', () =>
    typeof listing === 'function' ? listing() : listing,
  );
  const onChoose = vi.fn();
  mount(
    <DestinationStep
      client={api.client()}
      connection={current}
      initial={null}
      onChoose={onChoose}
    />,
  );
  return { api, onChoose };
}

const options = () => screen.getAllByTestId('destination-option');
const radios = () => screen.getAllByTestId('destination-radio') as HTMLInputElement[];

describe('listing notices', () => {
  it('says a listing is partial when incomplete with entries', async () => {
    step(destinations([entry()], { listingComplete: false }));
    expect((await screen.findByTestId('destination-partial')).textContent).toContain('새로고침');
    expect(options()).toHaveLength(1);
  });

  it('says a listing is unavailable when incomplete without entries', async () => {
    step(destinations([], { listingComplete: false }));
    await screen.findByTestId('destination-unavailable');
    expect(screen.queryByTestId('destination-list')).toBeNull();
    expect(screen.getByTestId('destination-next')).toBeDisabled();
  });

  it('explains how to share a page when the listing is complete and empty', async () => {
    step(destinations([]));
    const notice = await screen.findByTestId('destination-empty');
    expect(notice.textContent).toContain('연결(Connections)');
    expect(notice.textContent).toContain('통합을 추가');
  });

  it('refreshes the listing on request', async () => {
    let complete = false;
    const { api } = step(() => destinations([entry()], { listingComplete: complete }));
    await screen.findByTestId('destination-partial');
    complete = true;
    await userEvent.click(screen.getByTestId('destination-refresh'));
    await waitFor(() => expect(screen.queryByTestId('destination-partial')).toBeNull());
    expect(api.named('list-export-destinations')).toHaveLength(2);
    expect(api.named('list-export-destinations')[0]!.body).toEqual({});
  });

  it('shows a refused listing in plain words', async () => {
    const api = new ExportDouble().on('list-export-destinations', () => {
      throw envelope('POLICY_UNRESOLVED', 503);
    });
    mount(
      <DestinationStep
        client={api.client()}
        connection={connection()}
        initial={null}
        onChoose={vi.fn()}
      />,
    );
    expect((await screen.findByTestId('destination-error')).textContent).toBe(
      '현재 이 작업을 사용할 수 없어요',
    );
  });
});

describe('listed pages', () => {
  it('shows a placeholder for an untitled page and context for same-titled pages', async () => {
    step(
      destinations([
        entry({
          destinationId: PAGE_A,
          parentPageId: PAGE_A,
          title: '제목 없음',
          context: '팀 공간',
        }),
        entry({
          destinationId: PAGE_B,
          parentPageId: PAGE_B,
          title: '회의록',
          context: '팀 공간 / 2025',
        }),
        entry({
          destinationId: PAGE_C,
          parentPageId: PAGE_C,
          title: '회의록',
          context: '개인 / 메모',
        }),
      ]),
    );
    await screen.findByTestId('destination-list');
    const [untitled, first, second] = options();
    expect(untitled!.textContent).toContain('(제목 없음)');
    expect(first!.textContent).toContain('팀 공간 / 2025');
    expect(second!.textContent).toContain('개인 / 메모');
  });

  it('shows an unreadable page as unusable with its reason', async () => {
    step(destinations([entry({ readable: false, writable: false })]));
    await screen.findByTestId('destination-list');
    expect(radios()[0]).toBeDisabled();
    expect(screen.getByTestId('destination-reason').textContent).toContain('읽을 수 없습니다');
  });

  it('shows creation capability only as far as Notion has shown it', async () => {
    step(
      destinations([
        entry({ destinationId: PAGE_A, parentPageId: PAGE_A }),
        entry({ destinationId: PAGE_B, parentPageId: PAGE_B, creationCapability: 'confirmed' }),
        entry({
          destinationId: PAGE_C,
          parentPageId: PAGE_C,
          creationCapability: 'refused',
          writable: false,
        }),
      ]),
    );
    await screen.findByTestId('destination-list');
    const [unknown, confirmed, refused] = options();
    expect(unknown!.textContent).toContain('페이지 만들기 권한: 확인 전');
    expect(confirmed!.textContent).toContain('페이지 만들기 권한: 확인됨');
    expect(refused!.textContent).toContain('페이지 만들기 권한: 거부됨');
    expect(within(refused!).getByTestId('destination-radio')).toBeDisabled();
  });

  it('shows pages other than the activation destination as not allowed in the real composition', async () => {
    step(
      destinations([
        entry({ destinationId: PAGE_A, parentPageId: PAGE_A, title: '허용된 페이지' }),
        entry({ destinationId: PAGE_B, parentPageId: PAGE_B, title: '다른 페이지' }),
      ]),
      connection({ destinationScopeIds: [PAGE_A], limitations: [] }),
    );
    await screen.findByTestId('destination-list');
    expect(radios()[0]).not.toBeDisabled();
    expect(radios()[1]).toBeDisabled();
    expect(within(options()[1]!).getByTestId('destination-reason').textContent).toContain(
      '허용된 페이지가 아니어서',
    );
  });
});

describe('preselection', () => {
  it('preselects the last destination when it is listed and readable', async () => {
    const { onChoose } = step(
      destinations(
        [
          entry({ destinationId: PAGE_A, parentPageId: PAGE_A }),
          entry({ destinationId: PAGE_B, parentPageId: PAGE_B, title: '지난 위치' }),
        ],
        { lastDestinationId: PAGE_B },
      ),
    );
    await screen.findByTestId('destination-list');
    expect(radios()[1]!.checked).toBe(true);
    expect(screen.queryByTestId('destination-stale')).toBeNull();
    await userEvent.click(screen.getByTestId('destination-next'));
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ destinationId: PAGE_B }));
  });

  it('drops a stale preselection with a notice', async () => {
    step(
      destinations([entry({ destinationId: PAGE_A, parentPageId: PAGE_A })], {
        lastDestinationId: PAGE_C,
      }),
    );
    await screen.findByTestId('destination-stale');
    expect(radios()[0]!.checked).toBe(false);
    expect(screen.getByTestId('destination-next')).toBeDisabled();
  });

  it('drops a listed but unreadable preselection with a notice', async () => {
    step(destinations([entry({ readable: false })], { lastDestinationId: PAGE_A }));
    await screen.findByTestId('destination-stale');
  });

  it('lets the owner choose another page, which is what the step hands on', async () => {
    const { onChoose } = step(
      destinations(
        [
          entry({ destinationId: PAGE_A, parentPageId: PAGE_A, title: '첫 페이지' }),
          entry({ destinationId: PAGE_B, parentPageId: PAGE_B, title: '둘째 페이지' }),
        ],
        { lastDestinationId: PAGE_A },
      ),
    );
    await screen.findByTestId('destination-list');
    await userEvent.click(screen.getByLabelText('둘째 페이지'));
    await userEvent.click(screen.getByTestId('destination-next'));
    expect(onChoose).toHaveBeenCalledWith(expect.objectContaining({ destinationId: PAGE_B }));
  });
});
