/** NFR5.1 component checks: every status shows text and an icon (1.4.1), and each view
announces changes through exactly one polite live region (4.1.3). */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import {
  APPROVAL_STATE_COPY,
  CONNECTION_STATE_COPY,
  EFFECT_STATE_COPY,
  NOT_CONNECTED,
} from '../../src/u6-export/copy';
import { LiveRegion, StatusBadge } from '../../src/u6-export/status';
import { ExportView } from '../../src/u6-export/export-view';
import { ExportFlow } from '../../src/u6-export/export-flow';
import {
  capability,
  connection,
  envelope,
  ExportDouble,
  historyEntry,
  historyPage,
  mount,
  source,
} from './fixtures';

const everyStatus = [
  NOT_CONNECTED,
  ...Object.values(CONNECTION_STATE_COPY),
  ...Object.values(EFFECT_STATE_COPY),
  ...Object.values(APPROVAL_STATE_COPY),
];

const politeRegions = () =>
  Array.from(document.querySelectorAll('[aria-live], [role="status"], [role="alert"]'));

describe('status badges', () => {
  it('pair words with a decorative icon for every state', () => {
    for (const status of everyStatus) {
      const { container, unmount } = render(<StatusBadge status={status} />);
      const icon = container.querySelector('[aria-hidden="true"]');
      expect(icon?.textContent?.trim().length).toBeGreaterThan(0);
      expect(container.textContent).toContain(status.text);
      expect(status.text.trim().length).toBeGreaterThan(1);
      unmount();
    }
  });
});

describe('one polite live region', () => {
  it('is always mounted, and renders each announcement as text', () => {
    const { rerender } = render(<LiveRegion message={null} testId="live" />);
    const region = screen.getByTestId('live');
    expect(region.getAttribute('aria-live')).toBe('polite');
    expect(region.getAttribute('role')).toBe('status');
    rerender(<LiveRegion message={{ id: 1, text: '내보냈습니다' }} testId="live" />);
    expect(screen.getByTestId('live').textContent).toBe('내보냈습니다');
  });

  it('is the only live region of the export view, including refusals', async () => {
    const api = new ExportDouble()
      .on('read-notion-connection', () => connection())
      .on('list-export-history', () =>
        historyPage([
          historyEntry(),
          historyEntry({
            approvalId: '77777777-7777-4777-8777-777777777777',
            state: 'invalidated',
            invalidationReason: 'source-changed',
          }),
        ]),
      );
    mount(<ExportView client={api.client()} capability={capability()} />);
    await screen.findAllByTestId('history-row');
    const regions = politeRegions();
    expect(regions).toHaveLength(1);
    expect(regions[0]!.getAttribute('aria-live')).toBe('polite');
    for (const status of screen.getAllByTestId('history-status'))
      expect(status.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });

  it('is the only live region of the export flow', async () => {
    const api = new ExportDouble().on('read-notion-connection', () => {
      throw envelope('NOT_FOUND', 404);
    });
    mount(
      <ExportFlow
        client={api.client()}
        capability={capability()}
        source={source}
        onClose={() => {}}
      />,
    );
    await screen.findByTestId('connection-step');
    expect(politeRegions()).toHaveLength(1);
  });
});
