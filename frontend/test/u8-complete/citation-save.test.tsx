// U3's citation save in the complete workspace (the person's decision of 2026-10-23, "U2's
// controls for all usage"): it sends the app's own library policy, the one the reading
// page's save uses, and every earlier realm keeps U3's built synthetic library policy.
import { afterEach, describe, expect, it } from 'vitest';
import { api, BUILT_LIBRARY_POLICY, setLibraryPolicy } from '../../src/u3-corpus/api';
import { fakeClient } from './helpers';

const PAPER = { paperId: 'p1', versionId: 'v1', eligibilityRevision: 'e1' };
const COMPLETE = { policyId: 'u8-synthetic-v1', revision: '1' };

describe('the citation save policy', () => {
  afterEach(() => setLibraryPolicy(undefined));

  it('sends the complete workspace library policy once the shell sets it', async () => {
    const fake = fakeClient(() => ({}));
    setLibraryPolicy(COMPLETE);
    await api.savePaper(fake.transport, PAPER);
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c03/library-save-paper', {
      paper: PAPER,
      policyRef: COMPLETE,
    });
  });

  it('keeps the built synthetic library policy everywhere else', async () => {
    const fake = fakeClient(() => ({}));
    setLibraryPolicy(undefined);
    await api.savePaper(fake.transport, PAPER);
    expect(fake.post).toHaveBeenCalledWith('/api/v2/c03/library-save-paper', {
      paper: PAPER,
      policyRef: BUILT_LIBRARY_POLICY,
    });
    expect(BUILT_LIBRARY_POLICY).toEqual({ policyId: 'synthetic-local-library', revision: '1' });
  });
});
