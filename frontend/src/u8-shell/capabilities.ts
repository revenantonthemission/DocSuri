/**
 * The capability list as the complete assembly answers it (BR5.9): a signed-in caller
 * reads the capability catalog; a caller with no session reads only the public
 * projection, each capability's state and reason key.
 */
import type { WorkspaceCapabilityCatalog } from '../../types/wire/dtos';
import type { CapabilityStateMap } from './provider-notice';

export type PublicCapabilityPage = {
  manifestRevision: string;
  items: { capabilityId: string; state: string; reasonKey: string }[];
};

export function isPublicPage(value: unknown): value is PublicCapabilityPage {
  if (typeof value !== 'object' || value === null) return false;
  const candidate = value as Partial<PublicCapabilityPage>;
  return typeof candidate.manifestRevision === 'string' && Array.isArray(candidate.items);
}

/** Whether the answer is the complete assembly's: the projection, or a catalog with
 * ServiceOperations' own row. */
export function isCompleteAnswer(value: unknown): boolean {
  if (isPublicPage(value)) return true;
  const catalog = value as Partial<WorkspaceCapabilityCatalog> | null;
  return (
    Array.isArray(catalog?.capabilities) &&
    catalog.capabilities.some((row) => row.id === 'operations.ledger')
  );
}

export function statesOf(value: unknown): CapabilityStateMap {
  if (isPublicPage(value)) {
    return Object.fromEntries(
      value.items.map((item) => [
        item.capabilityId,
        { state: item.state, reasonKey: item.reasonKey },
      ]),
    );
  }
  const catalog = value as Partial<WorkspaceCapabilityCatalog> | null;
  return Object.fromEntries(
    (catalog?.capabilities ?? []).map((row) => [row.id, { state: row.state }]),
  );
}
