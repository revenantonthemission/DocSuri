"""SourceSelector — task/scope→source with abstract fallback (BR-S2 / Q1 / D2).

summary → full text; absent → abstract fallback (NFR-R2) with a reason; both absent → None
(→ SourceUnavailableDTO). translate scope=full → full text (abstract fallback); scope=abstract
→ abstract.

(D2) The full-text input is the structured **doc-model** when a reader is wired and the
artifact exists (built lazily by U1); it degrades to the legacy plain-text ``.txt`` and then
the abstract. Selection/fallback/DTO logic is otherwise unchanged — only the input upgrades.
"""

from __future__ import annotations

from collections.abc import Callable

from ..ports.ports import DocModelReadPort, FullTextSourcePort
from .models import Scope, SourceKind, SourceText, SummaryRequest, Task


class SourceSelector:
    """Server-verified source selection (REM-2 F02, FD-Q2, SECURITY-13).

    Content is only ever read from a server-verified store, in a fixed order:

      1. the structured **doc-model** (when a reader is wired),
      2. the legacy plain full text,
      3. the **server-side** abstract lookup.

    The request body is never a source. ``SummaryRequest.abstract`` is still accepted on the
    dataclass for wire/worker compatibility, but it is deliberately ignored here: it was the
    sole/fallback source for abstract-scope translate and for every full-text fallback, while
    the cache key carried no source content — so one caller's crafted body became the artifact
    the owner-agnostic baseline cache served to everyone (F02). Ignoring it makes the key's
    implicit "same key ⇒ same artifact" guarantee true by construction, because the artifact is
    a pure function of the canonical source.
    """

    def __init__(
        self,
        full_text: FullTextSourcePort,
        abstract_lookup: Callable[[str], str | None] | None = None,
        doc_model_reader: DocModelReadPort | None = None,
    ) -> None:
        self._full_text = full_text
        self._abstract_lookup = abstract_lookup
        self._doc_model_reader = doc_model_reader

    def _server_abstract(self, paper_id: str) -> str | None:
        """The canonical abstract for a paper, from the server-side store only.

        A lookup fault degrades to "no abstract" (→ ``source_unavailable``) rather than falling
        back to anything caller-supplied: an unverifiable source is not a source.
        """
        if not self._abstract_lookup:
            return None
        try:
            return self._abstract_lookup(paper_id)
        except Exception:
            return None

    def select(self, request: SummaryRequest) -> SourceText | None:
        if request.task == Task.TRANSLATE and request.scope == Scope.ABSTRACT:
            abstract = self._server_abstract(request.paper_id)
            if abstract:
                return SourceText(kind=SourceKind.ABSTRACT, raw=abstract)
            return None

        # summary, or translate scope=full → full text with abstract fallback (Q1/NFR-R2).
        # (D2) Prefer the structured doc-model; degrade to legacy plain text, then abstract.
        if self._doc_model_reader is not None:
            doc = self._doc_model_reader.get_doc_model(request.paper_id, request.version)
            if doc is not None:
                return SourceText(kind=SourceKind.FULL_TEXT, doc_model=doc)

        raw = self._full_text.get_full_text(request.paper_id, request.version)
        if raw:
            return SourceText(kind=SourceKind.FULL_TEXT, raw=raw)

        abstract = self._server_abstract(request.paper_id)
        if abstract:
            return SourceText(
                kind=SourceKind.ABSTRACT,
                raw=abstract,
                fallback_reason="full_text_unavailable",
            )
        return None
