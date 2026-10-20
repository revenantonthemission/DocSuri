/** The novelty result's entry into U6's approved export: "Notion으로 내보내기".

It opens the export flow with the exact result reference (`novelty.artifact`).
Opening and closing never export: only the flow's explicit press does (BR2.2).
Closing returns focus to the entry button. */

import React, { useRef, useState } from 'react';
import type { Transport } from '../api';
import { ExportFlow } from '../u6-export/export-flow';
import type { Capability } from '../u6-export/api';
import type { Artifact } from './api';

export function NoveltyExportAction({
  client,
  capability,
  novelty,
}: {
  client: Transport;
  capability: Capability;
  novelty: Artifact;
}) {
  const [open, setOpen] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const close = () => {
    setOpen(false);
    window.requestAnimationFrame(() => trigger.current?.focus());
  };
  return (
    <section className="control-group" aria-label="Notion으로 내보내기">
      {open ? (
        <ExportFlow
          client={client}
          capability={capability}
          source={novelty.artifact}
          onClose={close}
        />
      ) : (
        <button
          type="button"
          ref={trigger}
          onClick={() => setOpen(true)}
          data-testid="novelty-export-open"
        >
          Notion으로 내보내기
        </button>
      )}
    </section>
  );
}
