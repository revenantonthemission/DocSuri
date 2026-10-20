/** The approve-and-export press (BR3.2, BR5.1, BR5.2): one key per press, the same
key on both calls, the same key again on a retry of the same press, and plain
notices for every bind refusal. */

import React from 'react';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { pressRefusal, PreviewStep } from '../../src/u6-export/preview-step';
import { OUTCOME_UNKNOWN_PAIR, PRESS_UNKNOWN, STALE_BINDING } from '../../src/u6-export/copy';
import {
  approval,
  capability,
  connection,
  effect,
  entry,
  envelope,
  ExportDouble,
  mount,
  preview,
  source,
} from './fixtures';

function press(api: ExportDouble) {
  const onExported = vi.fn();
  mount(
    <PreviewStep
      client={api.client()}
      capability={capability()}
      connection={connection()}
      source={source}
      destination={entry()}
      onExported={onExported}
      announce={vi.fn()}
    />,
  );
  return onExported;
}

const button = () => screen.getByTestId('preview-approve');
const keys = (api: ExportDouble, name: string) => api.named(name).map((call) => call.key);

describe('one press', () => {
  it('sends approve then execute under one fresh key', async () => {
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => effect());
    const onExported = press(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(button());
    await waitFor(() => expect(onExported).toHaveBeenCalled());
    const [approveKey] = keys(api, 'approve-export-preview');
    expect(approveKey).toMatch(/^[0-9a-f-]{36}$/);
    expect(keys(api, 'execute-approved-export')).toEqual([approveKey]);
    expect(api.named('approve-export-preview')[0]!.body).toMatchObject({
      explicitApproval: true,
      previewRevision: '1',
    });
  });

  it('is disabled while the press is in flight', async () => {
    let finish: (value: unknown) => void = () => undefined;
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => new Promise((resolve) => (finish = resolve)))
      .on('execute-approved-export', () => effect());
    press(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(button());
    expect(button()).toBeDisabled();
    expect(button().textContent).toBe('승인하는 중…');
    finish(approval());
    await waitFor(() => expect(api.named('execute-approved-export')).toHaveLength(1));
  });
});

describe('a retried press', () => {
  it('reuses its key after a lost DocSuri answer (UNKNOWN_OUTCOME)', async () => {
    let lose = true;
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => {
        if (lose) {
          lose = false;
          throw envelope('UNKNOWN_OUTCOME', 0);
        }
        return effect();
      });
    const onExported = press(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(button());
    expect((await screen.findByTestId('preview-notice')).textContent).toBe(PRESS_UNKNOWN);
    await userEvent.click(button());
    await waitFor(() => expect(onExported).toHaveBeenCalled());
    const all = [...keys(api, 'approve-export-preview'), ...keys(api, 'execute-approved-export')];
    expect(all).toHaveLength(4);
    expect(new Set(all).size).toBe(1);
  });

  it('starts a new press with a new key after a definite approve refusal', async () => {
    let refuse = true;
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => {
        if (refuse) {
          refuse = false;
          throw envelope('DEPENDENCY_UNAVAILABLE', 503);
        }
        return approval();
      })
      .on('execute-approved-export', () => effect());
    const onExported = press(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(button());
    await screen.findByTestId('preview-notice');
    await userEvent.click(button());
    await waitFor(() => expect(onExported).toHaveBeenCalled());
    const [first, second] = keys(api, 'approve-export-preview');
    expect(first).not.toBe(second);
  });
});

describe('bind refusals show plain notices', () => {
  it('names an unknown export of the same pair', async () => {
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => {
        throw envelope('OUTCOME_UNKNOWN');
      });
    press(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(button());
    expect((await screen.findByTestId('preview-notice')).textContent).toBe(OUTCOME_UNKNOWN_PAIR);
  });

  it('turns APPROVAL_REQUIRED into a changed preview', async () => {
    const api = new ExportDouble()
      .on('prepare-export-preview', () => preview())
      .on('approve-export-preview', () => approval())
      .on('execute-approved-export', () => {
        throw envelope('APPROVAL_REQUIRED');
      });
    press(api);
    await screen.findByTestId('preview-rendered');
    await userEvent.click(button());
    expect((await screen.findByTestId('preview-stale')).textContent).toBe(STALE_BINDING);
  });

  it('maps every refusal to words, never raw codes', () => {
    expect(pressRefusal(new Error('x')).text).toBe('문제가 발생했어요');
    expect(pressRefusal(envelope('FORBIDDEN', 403)).text).toBe(
      '이 환경에서는 이 페이지로 내보낼 수 없습니다',
    );
    expect(pressRefusal(envelope('SOURCE_INELIGIBLE', 403)).text).toContain('내보낼 수 없습니다');
    expect(pressRefusal(envelope('CONFLICT')).stale).toBe(true);
    expect(pressRefusal(envelope('NOT_FOUND', 404)).text).toBe('결과를 찾을 수 없습니다');
  });
});
