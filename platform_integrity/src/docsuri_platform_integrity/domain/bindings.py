"""REM-1's tool-role view of the shared offline schema interpreter."""


def validate_catalog(documents: tuple[dict, ...]) -> dict[str, dict]:
    # Lazy loading keeps the readonly daemon independent of generator/tool dependencies.
    from docsuri_schema import Catalog

    catalog = Catalog(documents)
    return {
        identity: catalog.nodes[location][0] for identity, location in catalog.resources.items()
    }
