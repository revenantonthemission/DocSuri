import type { LibraryItemMeta, ResultCardVM } from '@/types/generated';

// Map a preserved library meta snapshot (BR-L5) onto the shared ResultCardVM so
// the library reuses ResultCard — WITHOUT the live index (availability isolation,
// NFR-R1). relevance is intentionally absent (a saved card has no live ranking,
// SEC-9). Missing optional fields are normalized so ResultCard can guard them.
export function cardFromMeta(meta: LibraryItemMeta): ResultCardVM {
  if (!meta || typeof meta.title !== 'string' || typeof meta.arxivId !== 'string' ||
      !Array.isArray(meta.authors) || !meta.authors.every((author) => typeof author === 'string') ||
      (meta.year != null && (typeof meta.year !== 'number' || !Number.isFinite(meta.year)))) {
    throw new TypeError('Invalid library snapshot');
  }
  return {
    title: meta.title,
    authors: meta.authors ?? [],
    year: meta.year ?? 0,
    arxivId: meta.arxivId,
    abstractSnippet: meta.abstractSnippet ?? '',
    relevance: null,
    arxivUrl: meta.arxivUrl ?? '',
  };
}
