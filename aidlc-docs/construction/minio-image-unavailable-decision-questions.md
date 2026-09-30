# MinIO Image Unobtainable — Decision Required

Phase 2 pulled the four digests pinned in `ops/platform-integrity/sbom-targets.json`. **Three
succeeded and are verified locally. MinIO cannot be pulled from any official source.** This is a
decision for you, not something I should work around by swapping in a different image.

## Pull results

| Target | Result |
|---|---|
| `redis@sha256:c6eabf74...` | ✅ pulled, 192 MB, digest verified |
| `softwaremill/elasticmq-native@sha256:e4580abd...` | ✅ pulled, 128 MB, digest verified |
| `opensearchproject/opensearch@sha256:4ee82ecb...` | ✅ pulled, 2 GB, digest verified (1 retry — transient CloudFront TLS timeout, not a bad pin) |
| `quay.io/minio/minio@sha256:14cea493...` | ❌ **not obtainable** |

No pin in `sbom-targets.json` was changed.

## Evidence: MinIO denies anonymous access at the repository level

| Source | Probe | Result |
|---|---|---|
| `quay.io/v2/minio/minio/manifests/<digest>` | `HEAD`, OCI + Docker manifest accept headers | **401** `UNAUTHORIZED` |
| `quay.io/v2/minio/minio/tags/list` | `GET` | **401** |
| `registry-1.docker.io/v2/minio/minio` | `GET` with a valid `auth.docker.io` pull-scope token | **401** |
| `dl.min.io/server/minio/release/linux-amd64/minio` | `HEAD`, vendor server binary | **410 Gone** |

The `tags/list` 401 is the decisive one. It is not that this digest was superseded or garbage
collected — anonymous access to `quay.io/minio/minio` as a whole is no longer granted. The 410 from
the vendor's own binary path is consistent with the community edition being withdrawn from public
distribution.

**I did not pull a mirror or build from source.** That would restore runnability but break the
provenance chain that `sbom-targets.json` exists to protect.

## Why this needs your call

1. **G1 scan target** — G1 requires a CVE scan of the MinIO image. With no obtainable image there is
   nothing to scan, so that sub-item cannot be satisfied from the pinned artifact.
2. **Provenance** — `sbom-targets.json` pins a scannable, reproducible artifact. Substituting a
   different S3 server changes the security baseline every downstream scan result attests to.
3. **The approved design names MinIO** — ten REM-3 design documents reference it, including
   `infrastructure-design/deployment-architecture.md` and `tech-stack-decisions.md`. The design is
   the retained specification, so substituting changes a specification-level decision.
4. **Blast radius is contained** — the live single-Mac smoke test is scoped to real
   Postgres/Redis/OpenSearch. MinIO is **not** in that set. The affected scope is the asset-store
   live path and the MinIO G1 scan.

## Extra defects found in `assets.py` during this diagnosis

Already in the delete-and-regenerate set; found now so the rewrite is complete:

- **L12-13** imports `minio` / `minio.error`; the `minio` SDK is **not declared** in
  `platform_integrity/pyproject.toml` — a third undeclared dependency alongside `jwt` and `redis`.
- **L117-121** `create_minio_client()` hardcodes `endpoint="127.0.0.1:9000"`,
  `access_key="minioadmin"`, `secret_key="minioadmin"`. No environment override; the well-known
  default credentials are the insecure-defaults defect already on record.
- **L91-93** `_minio_presigned_get` hardcodes `bucket_name="docsuri"` instead of using `self.bucket`,
  so the constructor's bucket argument is ignored on the read path.

## Question 1

The pinned MinIO image is unobtainable. How should the S3 asset store be handled?

A) Substitute a different S3-compatible server for the **local Colima stack only** — SeaweedFS or Garage — keep the `minio` Python SDK as the client since it speaks S3, and mark the `sbom-targets.json` MinIO pin as `UNOBTAINABLE` with the 401/410 evidence recorded rather than silently repointed. G1's MinIO scan item stays unsatisfied and is recorded as blocked. The `minio` SDK dependency still gets declared in Phase 3.

B) Keep the pin exactly as-is and mark MinIO unavailable in `sbom-targets.json`, but **exclude the asset store from the Colima stack entirely** for this unit. The live smoke test stays Postgres/Redis/OpenSearch, which is what the gate already specifies. The `assets` adapter still gets rewritten with an environment-driven, Keychain-backed client, but its live path is not exercised this unit.

C) Replace the MinIO pin outright with a substitute S3 server image, update `sbom-targets.json`, and re-baseline the scan baseline on the new image. This unblocks the G1 MinIO scan but changes the recorded security baseline.

D) Vendor MinIO from source or use a third-party mirror for local use only, keeping the original pin as the record of what production is expected to run.

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Substitute a different S3-compatible server for the **local Colima stack only** — SeaweedFS or Garage

## Question 2

Whatever you choose above, how should the G1 MinIO scan sub-item be recorded?

A) Record it as a new explicit blocker under G1 alongside the three existing operator sign-offs, with the 401/410 evidence attached, so G1's remaining-blocked list is accurate

B) Record it in `audit.md` only, and leave the G1 disposition in `cve-disposition.md` unchanged since the CVE data was already gathered when the image was obtainable

C) Mark the G1 MinIO scan as **not applicable** this unit, on the basis that the image is unobtainable and therefore out of scope

X) Other (please describe after [Answer]: tag below)

[Answer]: A) Record it as a new explicit blocker under G1 alongside the three existing operator sign-offs, with the 401/410 evidence attached, so G1's remaining-blocked list is accurate
