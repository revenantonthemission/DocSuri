/** PreviewStep (BR2.1–BR2.5, BR3.1, BR5.1): the frozen preview, the earlier-export
notice, a changed binding leading to a fresh preview, and the 20-per-hour and in-flight
refusals. */

import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { PreviewStep } from '../../src/u6-export/preview-step';
import { IN_FLIGHT, PREVIEW_REFUSAL_COPY, STALE_BINDING } from '../../src/u6-export/copy';
import type { Connection, DestinationEntry } from '../../src/u6-export/api';
import {
  approval,
  capability,
  connection,
  EFFECT_ID,
  effect,
  entry,
  envelope,
  ExportDouble,
  mount,
  PAGE_URL,
  POLICY,
  preview,
  source,
} from './fixtures';

function step(
  api: ExportDouble,
  destination: DestinationEntry = entry(),
  current: Connection = connection(),
) {
  const onExported = vi.fn();
  const announce = vi.fn();
  mount(
    <PreviewStep
      client={api.client()}
      capability={capability()}
      connection={current}
      source={source}
      destination={destination}
      onExported={onExported}
      announce={announce}
    />,
  );
  return { onExported, announce };
}

const approve = () => screen.getByTestId('preview-approve');

describe('the prepared preview', () => {
  it('prepares from identity fields only and shows source, destination and the page with its marker', async () => {
    const api = new ExportDouble().on('prepare-export-preview', () => preview());
    step(api);
    expect(screen.getByTestId('preview-preparing')).toBeInTheDocument();
    expect(approve()).toBeDisabled();
    const rendered = await screen.findByTestId('preview-rendered');
    expect(rendered.textContent).toContain('DocSuri export marker: m-1');
    expect(rendered.getAttribute('tabindex')).toBe('0');
    expect(screen.getByTestId('preview-source').textContent).toContain('읽은 범위의 연구 비교');
    expect(screen.getByTestId('preview-destination').textContent).toContain('연구 노트');
    expect(approve()).not.toBeDisabled();
    expect(approve().tagName).toBe('BUTTON');
    expect(api.named('prepare-export-preview')[0]!.body).toEqual({
      source,
      destination: {
        connectionId: entry().connectionId,
        workspaceId: entry().workspaceId,
        parentPageId: entry().parentPageId,
        formatRevision: '1',
        destinationId: entry().destinationId,
      },
      renderPolicy: POLICY,
    });
    expect(api.mutations().map((call) => call.name)).toEqual(['prepare-export-preview']);
  });

  it('lists earlier exports of the same pair, exported and possibly present', async () => {
    const api = new ExportDouble().on('prepare-export-preview', () =>
      preview({
        earlierExports: [
          {
            effectId: EFFECT_ID,
            disposition: 'exported',
            endedAt: '2026-10-19T03:00:00+00:00',
            remoteUrl: PAGE_URL,
          },
          {
            effectId: '99999999-9999-4999-8999-999999999999',
            disposition: 'may-exist',
            endedAt: '2026-10-18T03:00:00+00:00',
            outcomeReason: 'owner-settled-not-delivered',
          },
        ],
      }),
    );
    step(api);
    const earlier = await screen.findByTestId('preview-earlier');
    expect(earlier.textContent).toContain('내보냄');
    expect(earlier.textContent).toContain('Notion에 있을 수 있음');
    expect(earlier.querySelector('a')!.getAttribute('href')).toBe(PAGE_URL);
  });

  it('shows a refused preview with its reason, disables the press and can prepare again', async () => {
    let refuse = true;
    const api = new ExportDouble().on('prepare-export-preview', () => {
      if (refuse) throw envelope('SOURCE_INELIGIBLE', 403);
      return preview();
    });
    step(api);
    expect((await screen.findByTestId('preview-notice')).textContent).toBe(
      PREVIEW_REFUSAL_COPY.SOURCE_INELIGIBLE,
    );
    expect(approve()).toBeDisabled();
    expect(screen.getByTestId('preview-disabled-reason').textContent).toContain('다시 만드세요');
    refuse = false;
    await userEvent.click(screen.getByTestId('preview-refresh'));
    await screen.findByTestId('preview-rendered');
    expect(approve()).not.toBeDisabled();
  });

  it('disables the press with a textual reason for an unusable destination', async () => {
    const api = new ExportDouble().on('prepare-export-preview', () => preview());
    step(api, entry({ creationCapability: 'refused', writable: false }));
    await screen.findByTestId('preview-rendered');
    expect(approve()).toBeDisabled();
    expect(screen.getByTestId('preview-disabled-reason').textContent).toContain('권한이 없습니다');
  });
});

describe('a changed binding', () => {
  it('shows a focused notice and leads to a fresh preview with a new revision', async () => {
    let revision = 1;
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview({ revision: String(revision) }))
      .on('approve-export-preview', () => {
        throw envelope('CONFLICT');
      });
    step(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(approve());
    const stale = await screen.findByTestId('preview-stale');
    expect(stale.textContent).toBe(STALE_BINDING);
    await waitFor(() => expect(document.activeElement).toBe(stale));
    revision = 2;
    await userEvent.click(screen.getByTestId('preview-refresh'));
    await waitFor(() =>
      expect(screen.getByTestId('preview-step').getAttribute('data-preview-state')).toBe('ready'),
    );
    expect(api.named('prepare-export-preview')).toHaveLength(2);
    expect(api.named('execute-approved-export')).toHaveLength(0);
  });
});

describe('bind refusals', () => {
  it('shows when exporting is possible again for the 20-per-hour refusal', async () => {
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => {
        throw envelope('CAPACITY_EXHAUSTED', 429, { retryAfterSeconds: 600 });
      });
    const { onExported } = step(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(approve());
    const notice = await screen.findByTestId('preview-notice');
    expect(notice.textContent).toContain('부터 다시 내보낼 수 있습니다');
    expect(notice.textContent).toContain('내보내기 기록에 남아');
    expect(onExported).not.toHaveBeenCalled();
  });

  it('says another export is in flight when the refusal carries no wait', async () => {
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => {
        throw envelope('CAPACITY_EXHAUSTED', 429);
      });
    step(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(approve());
    expect((await screen.findByTestId('preview-notice')).textContent).toBe(IN_FLIGHT);
  });

  it('hands the bound effect on after one press', async () => {
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => effect());
    const { onExported } = step(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(approve());
    await waitFor(() => expect(onExported).toHaveBeenCalledWith(effect(), preview()));
    expect(api.violations).toEqual([]);
  });
});
