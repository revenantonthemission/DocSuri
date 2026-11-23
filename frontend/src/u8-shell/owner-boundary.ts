/**
 * The owner boundary (BR5.5): on sign-in, sign-out, an account switch or expiry, every
 * private view, cached response and live-region message is cleared before navigation is
 * resolved again, so nothing of the prior owner's can appear for the next one.
 */
import { useEffect, useRef } from 'react';
import { useSWRConfig } from 'swr';

/** Session-scoped keys the complete workspace keeps; all are dropped at a boundary. */
export const PRIVATE_PREFIX = 'docsuri.private.';

export function dropPrivateSession(storage: Pick<Storage, 'length' | 'key' | 'removeItem'>) {
  const keys: string[] = [];
  for (let index = 0; index < storage.length; index += 1) {
    const key = storage.key(index);
    if (key?.startsWith(PRIVATE_PREFIX)) keys.push(key);
  }
  keys.forEach((key) => storage.removeItem(key));
}

/** Clear the SWR cache, session-scoped private keys and `onClear` when `owner` changes.
 *
 * SWR's `unload` deletes every entry, the `$inf$` and `$sub$` keys a key filter cannot
 * match included, and discards in-flight requests and mutations, so a late answer for
 * the prior owner cannot write back (L1-39). Its default revalidation reads again for the
 * hooks the new owner has just mounted. Nothing here runs on a timer. */
export function useOwnerBoundary(owner: string, onClear: () => void): void {
  const { unload } = useSWRConfig();
  const current = useRef(owner);
  useEffect(() => {
    if (current.current === owner) return;
    current.current = owner;
    unload();
    try {
      dropPrivateSession(window.sessionStorage);
    } catch {
      // Restricted storage holds nothing of ours to drop.
    }
    onClear();
  }, [owner, unload, onClear]);
}
