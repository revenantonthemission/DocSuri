# Entities — AssetViewer

**Unit:** AssetViewer
**Phase:** Construction — Functional Design
**Date:** 2026-10-02

---

## Entity Definitions

### Asset
**Owner:** AssetViewer
**Identifier:** `assetId` (string)

| Attribute | Type | Description |
|-----------|------|-------------|
| assetId | string | Unique asset identifier |
| paperId | string | Parent paper identifier |
| mimeType | string | MIME type (e.g., 'image/png', 'image/webp') |
| size | number | File size in bytes |
| cacheControl | string | Cache-Control header value (e.g., 'private, max-age=60') |
| width | number | Optional: image width in pixels |
| height | number | Optional: image height in pixels |

**References:**
- Paper (owned by ContentJobApi) — Each Asset belongs to one Paper

---

### Paper (Reference)
**Owner:** ContentJobApi (external)
**Identifier:** `paperId` (string)

| Attribute | Type | Description |
|-----------|------|-------------|
| paperId | string | Unique paper identifier |
| title | string | Paper title |
| version | number | Paper version number |

**References:** Owned by ContentJobApi