"""The isolation journeys' own paper asset (U8 plan Step 150; L3-4, L3-5).

J03 reads one paper's asset as two owners and J13 reads it signed out, through both
asset routes: `POST /api/v2/c04/read-asset` and C13's byte route. No v2 code writes
`corpus.asset` rows, and production holds none (`backend/u8_asset_bytes.py:24-25`), so the
realm's fixtures make their own: one paper with an eligible and an ineligible
`local-research` version, each with one PNG whose bytes are generated per run (L1-36) and
published to the realm's `corpus-files` store. The rows are written through the corpus
owner's login. The paper has no projection, so search never finds it.

`paper_asset` is restartable: given the record of an earlier run whose rows and bytes are
still intact, it returns that record; otherwise it makes a new paper under a fresh token,
so no key collides and nothing an earlier run made is rewritten.
"""

from __future__ import annotations

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SOURCE_URL = "https://fixture.example.com/paper"
ALT_TEXT = "합성 그림"


def _content(label: str) -> dict:
    return {"document": {"sections": [{"id": "s1", "title": "Body", "blocks": [
        {"id": "s1.p1", "type": "paragraph", "text": f"Synthetic isolation paper {label}."},
    ]}]}}


def _intact(transactions, files, known: dict | None) -> bool:
    """Whether `known` names both assets, each row holds its hash and each artifact reads
    intact from the store."""
    from uuid import UUID

    from backend.artifacts import Artifact, ArtifactUnavailable

    if not known or not all(isinstance(known.get(kind), dict)
                            for kind in ("eligible", "ineligible")):
        return False
    assets = [known["eligible"], known["ineligible"]]
    try:
        ids = [UUID(str(asset["assetId"])) for asset in assets]
    except (KeyError, ValueError):
        return False
    rows = transactions.run("corpus", lambda conn: {
        row["id"]: row for row in conn.execute(
            "SELECT id, content_hash, byte_length FROM corpus.asset WHERE id = ANY(%s)",
            (ids,)).fetchall()})
    for asset, asset_id in zip(assets, ids, strict=True):
        row = rows.get(asset_id)
        if row is None or row["content_hash"] != asset.get("sha256"):
            return False
        try:
            files.read(Artifact(asset_id.hex + ".blob", row["content_hash"],
                                int(row["byte_length"])))
        except ArtifactUnavailable:
            return False
    return True


def _write_version(conn, paper_id: str, label: str, eligible: bool, artifact) -> dict:
    """One version with one asset row, through the corpus owner's connection."""
    import secrets
    import uuid

    from psycopg.types.json import Jsonb

    from backend.modules.corpus.repository import content_revision

    version_id, revision, content = f"{paper_id}-{label}", uuid.uuid4(), _content(label)
    conn.execute(
        "INSERT INTO corpus.version(id,paper_id,source_url,source_hash,version_label,"
        "private_path,eligible,purpose,eligibility_revision,provenance,content) VALUES"
        "(%s,%s,%s,%s,%s,'fixture',%s,'local-research',%s,'{}',%s)",
        (version_id, paper_id, SOURCE_URL, secrets.token_hex(32), label, eligible, revision,
         Jsonb(content)))
    asset_id = uuid.UUID(artifact.name.removesuffix(".blob"))
    conn.execute(
        "INSERT INTO corpus.asset(id,version_id,section_id,media_type,content_hash,storage,"
        "byte_length,alt_text) VALUES(%s,%s,'s1','image/png',%s,'private',%s,%s)",
        (asset_id, version_id, artifact.sha256, artifact.size, ALT_TEXT))
    return {"paper": {"paperId": paper_id, "versionId": version_id,
                      "eligibilityRevision": str(revision)},
            "contentRevision": content_revision({"content": content}),
            "assetId": str(asset_id), "sha256": artifact.sha256}


def paper_asset(transactions, files, known: dict | None) -> dict:
    """The isolation paper: `{"paperId", "eligible", "ineligible"}`, each version as
    `{"paper", "contentRevision", "assetId", "sha256"}`. Returns `known` when it is
    still intact."""
    import secrets

    if _intact(transactions, files, known):
        return known
    paper_id = "u8-asset-" + secrets.token_hex(6)
    artifacts = {label: files.publish(PNG_SIGNATURE + secrets.token_bytes(64))
                 for label in ("v1", "v2")}

    def write(conn) -> dict:
        conn.execute("INSERT INTO corpus.paper(id,title,authors,metadata) "
                     "VALUES(%s,'Synthetic isolation paper','[]','{}')", (paper_id,))
        return {"paperId": paper_id,
                "eligible": _write_version(conn, paper_id, "v1", True, artifacts["v1"]),
                "ineligible": _write_version(conn, paper_id, "v2", False, artifacts["v2"])}

    return transactions.run("corpus", write)
