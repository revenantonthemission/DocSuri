# Pinned PostgreSQL runtime image for REM-1.
#
# Why this exists: every upstream `postgres` tag ships /usr/local/bin/gosu, a Go
# binary built with go1.24.6. That toolchain's standard library carries 24
# High/Critical advisories (GO-2026-4337 and 21 others), so the finding set cannot
# be cleared by moving to a newer tag. gosu only exists to drop root to the
# postgres user, so we remove it and run the server as the unprivileged postgres
# uid instead. The image entrypoint skips the gosu branch when it is not uid 0.
#
# Base is pinned by immutable digest. The base OS is Alpine rather than Debian
# trixie: the trixie variant carries 74 additional blocking OS/distro advisories
# (libxml2, util-linux, gnupg, libacl, glibc, libperl) with no upstream fix state.
#
# Effect: 7384 components / 323 findings / 98 blocking -> 865 / 4 / 1.
# The one remaining blocking finding is alpine's zlib 1.3.2-r0
# (CVE-2026-85091, High, no fix state) and needs an alpine base refresh or a
# documented time-boxed exception.
#
# Operator note: because the container no longer starts as root, a bind mount or
# named volume for PGDATA must already be owned by the postgres uid before first
# start, or PostgreSQL cannot initialise the cluster:
#   docker run --rm -u 0 -v <volume>:/var/lib/postgresql/data \
#     --entrypoint sh <image> -c "chown -R 70:70 /var/lib/postgresql/data && chmod 700 /var/lib/postgresql/data"
#
# Build reproducibly. Without SOURCE_DATE_EPOCH and --provenance=false the image
# config digest changes on every build, so it cannot be pinned in compose:
#   SOURCE_DATE_EPOCH=1758800000 docker buildx build --provenance=false --load \
#     -f ops/platform-integrity/images/postgres-alpine-nosu.Dockerfile \
#     -t docsuri/postgres-alpine-16.15-nosu:16.15-alpine3.24-nosu .
# That reproduces image config digest
# sha256:ccbe2a110992a5b602afdd4a28a45f184de67308d4e80284c0b2329a10cb0e2e.

FROM postgres@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea

USER root
RUN rm -f /usr/local/bin/gosu
USER postgres
