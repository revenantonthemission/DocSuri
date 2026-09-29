/** Library wire aliases; meta is an explicit domain view over the schema's opaque snapshot. */
import type { LibraryLibraryItemDTO, LibraryLibraryItemCreateDTO, LibraryLibraryPageDTO } from '../wire/dtos';
export type {
  LibraryPageParams as PageParams,
  LibrarySavedSearchCreateDTO as SavedSearchCreateDTO,
  LibrarySavedSearchDTO as SavedSearchDTO,
  LibrarySavedSearchPageDTO as SavedSearchPageDTO,
  LibraryHistoryEntry as HistoryEntry,
  LibraryHistoryPageDTO as HistoryPageDTO,
  LibrarySearchResultSetDTO as SearchResultSetDTO,
} from '../wire/dtos';

/** U4 snapshot view, validated by library schemas and consumed by cardFromMeta. */
export interface LibraryItemMeta {
  title: string;
  authors: string[];
  year?: number | null;
  arxivId: string;
  abstractSnippet?: string | null;
  arxivUrl?: string | null;
}
export type LibraryItemCreateDTO = Omit<LibraryLibraryItemCreateDTO, 'meta'> & { meta: LibraryItemMeta };
export type LibraryItemDTO = Omit<LibraryLibraryItemDTO, 'meta'> & { meta: LibraryItemMeta };
export type LibraryPageDTO = Omit<LibraryLibraryPageDTO, 'items'> & { items: LibraryItemDTO[] };
