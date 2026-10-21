/** ExportFlow (Workflow 3): the step indicator's accessible state, the connection step
skipped when connected, the whole flow to the outcome, and closing that never exports. */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ExportFlow, StepIndicator } from '../../src/u6-export/export-flow';
import {
  approval,
  capability,
  connection,
  destinations,
  effect,
  entry,
  envelope,
  ExportDouble,
  mount,
  PAGE_URL,
  preview,
  source,
  TOKEN,
} from './fixtures';

function flow(api: ExportDouble) {
  const onClose = vi.fn();
  mount(
    <ExportFlow
      client={api.client()}
      capability={capability()}
      source={source}
      onClose={onClose}
      pollMs={15}
    />,
  );
  return onClose;
}

const current = () => document.querySelector('[aria-current="step"]')?.getAttribute('data-testid');

describe('step indicator', () => {
  it('exposes the current step as state and marks done steps in words', () => {
    render(<StepIndicator current="preview" />);
    expect(screen.getByTestId('flow-step-preview').getAttribute('aria-current')).toBe('step');
    expect(screen.getByTestId('flow-step-preview').textContent).toContain('(현재 단계)');
    expect(screen.getByTestId('flow-step-connection').textContent).toContain('(완료)');
    expect(screen.getByTestId('flow-step-outcome').getAttribute('aria-current')).toBeNull();
  });
});

describe('the export flow', () => {
  it('connects, picks a page, previews, exports and follows the outcome', async () => {
    let connected = false;
    const api = new ExportDouble()
      .on('read-notion-connection', () => {
        if (!connected) throw envelope('NOT_FOUND', 404);
        return connection();
      })
      .on('configure-notion-connection', () => {
        connected = true;
        return connection();
      })
      .on('list-export-destinations', () =>
        destinations([entry()], { lastDestinationId: entry().destinationId }),
      )
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => effect())
      .on('read-export-effect', () =>
        effect({
          state: 'succeeded',
          revision: '3',
          remoteReference: 'f'.repeat(32),
          remoteUrl: PAGE_URL,
        }),
      );
    flow(api);
    await screen.findByTestId('connection-step');
    expect(current()).toBe('flow-step-connection');
    expect(screen.getByRole('heading', { level: 2, name: 'Notion 연결' })).toBeInTheDocument();
    await userEvent.type(screen.getByTestId('connect-token'), TOKEN);
    await userEvent.click(screen.getByTestId('connect-submit'));
    await screen.findByTestId('destination-step');
    expect(current()).toBe('flow-step-destination');
    await waitFor(() => expect(screen.getByTestId('destination-next')).not.toBeDisabled());
    await userEvent.click(screen.getByTestId('destination-next'));
    await screen.findByTestId('preview-rendered');
    expect(current()).toBe('flow-step-preview');
    await userEvent.click(screen.getByTestId('preview-approve'));
    await screen.findByTestId('outcome-step');
    expect(current()).toBe('flow-step-outcome');
    const link = await screen.findByTestId('outcome-page-link');
    expect(link.textContent).toContain('읽은 범위의 연구 비교');
    expect(screen.getByTestId('flow-live').textContent).toContain('내보냈습니다');
    expect(document.body.innerHTML).not.toContain(TOKEN);
    expect(api.violations).toEqual([]);
  });

  it('skips the connection step when connected, and returns to the destination step', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-destinations', () => destinations([entry()]))
      .on('prepare-export-preview', () => preview());
    flow(api);
    await screen.findByTestId('destination-step');
    expect(screen.queryByTestId('connection-step')).toBeNull();
    await userEvent.click(screen.getByTestId('destination-radio'));
    await userEvent.click(screen.getByTestId('destination-next'));
    await screen.findByTestId('preview-rendered');
    await userEvent.click(screen.getByTestId('flow-back-destination'));
    await screen.findByTestId('destination-step');
    expect((screen.getByTestId('destination-radio') as HTMLInputElement).checked).toBe(true);
  });

  it('prepares a fresh preview after an invalidated outcome', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-destinations', () => destinations([entry()]))
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => effect())
      .on('read-export-effect', () =>
        effect({ state: 'invalidated', revision: '2', outcomeReason: 'destination-changed' }),
      );
    flow(api);
    await screen.findByTestId('destination-step');
    await userEvent.click(screen.getByTestId('destination-radio'));
    await userEvent.click(screen.getByTestId('destination-next'));
    await screen.findByTestId('preview-rendered');
    await userEvent.click(screen.getByTestId('preview-approve'));
    await userEvent.click(await screen.findByTestId('outcome-fresh-preview'));
    await screen.findByTestId('preview-rendered');
    expect(api.named('prepare-export-preview')).toHaveLength(2);
  });

  it('closes without any export, and shows an unavailable connection plainly', async () => {
    const api = new ExportDouble().on('read-notion-connection', () =>
      connection({ state: 'unavailable' }),
    );
    const onClose = flow(api);
    await screen.findByTestId('connection-step');
    expect(screen.queryByTestId('connect-form')).toBeNull();
    expect(screen.getByTestId('connection-step').textContent).toContain('연결을 해제한 뒤');
    await userEvent.click(screen.getByTestId('flow-close'));
    expect(onClose).toHaveBeenCalled();
    expect(api.mutations()).toEqual([]);
  });

  it('shows a refused connection read in plain words', async () => {
    const api = new ExportDouble().on('read-notion-connection', () => {
      throw envelope('DEPENDENCY_UNAVAILABLE', 503);
    });
    flow(api);
    expect((await screen.findByTestId('flow-error')).textContent).toBe(
      '일시적으로 사용할 수 없어요',
    );
  });
});
