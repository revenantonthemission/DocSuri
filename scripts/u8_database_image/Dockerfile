# U8's database image: PostgreSQL 16.14 with pgvector built from its pinned source.
#
# No published pgvector image carries exactly (16.14, 0.8.7), so the composed realm and
# the CI lane build this one from the `postgres:16.14` digest (decision "The pgvector pin
# and the lane's image"). Every pin is passed in from
# `ops/src/docsuri_ops/arrangement/runtimes.py`; nothing here names a version itself.
# The source is checked against PGXN's published SHA-1 and the recorded SHA-256 before
# it is built, and `migrate` asserts `server_version` and `extversion` afterwards.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG PGVECTOR_VERSION
ARG PGVECTOR_URL
ARG PGVECTOR_SHA1
ARG PGVECTOR_SHA256

RUN set -eux; \
    test -n "${PGVECTOR_VERSION}" && test -n "${PGVECTOR_URL}"; \
    test -n "${PGVECTOR_SHA1}" && test -n "${PGVECTOR_SHA256}"; \
    apt-get update; \
    # Hold the server at the base image's own version: an unpinned development package
    # would pull the newest minor release's server along with it.
    apt-mark hold locales "postgresql-${PG_MAJOR}" "postgresql-client-${PG_MAJOR}"; \
    apt-get install -y --no-install-recommends \
        build-essential "postgresql-server-dev-${PG_MAJOR}=${PG_VERSION}" \
        ca-certificates curl unzip; \
    curl --fail --silent --show-error --location --max-time 120 \
        --output /tmp/pgvector.zip "${PGVECTOR_URL}"; \
    echo "${PGVECTOR_SHA1}  /tmp/pgvector.zip" | sha1sum --check --strict; \
    echo "${PGVECTOR_SHA256}  /tmp/pgvector.zip" | sha256sum --check --strict; \
    unzip -q /tmp/pgvector.zip -d /tmp; \
    cd "/tmp/vector-${PGVECTOR_VERSION}"; \
    make clean; \
    make OPTFLAGS=""; \
    make install; \
    cd /; \
    rm -rf /tmp/pgvector.zip "/tmp/vector-${PGVECTOR_VERSION}"; \
    apt-get remove -y build-essential "postgresql-server-dev-${PG_MAJOR}" curl unzip; \
    apt-get autoremove -y; \
    apt-mark unhold locales "postgresql-${PG_MAJOR}" "postgresql-client-${PG_MAJOR}"; \
    test "$(postgres --version | awk '{print $3}')" = "${PG_VERSION%%-*}"; \
    # The one extension (D14): only plpgsql and pgvector stay installable. Every other
    # contrib extension's control file goes, so no login, not even a database owner that
    # may create trusted extensions, can create a second one; `migrate` asserts the set.
    extensions="/usr/share/postgresql/${PG_MAJOR}/extension"; \
    find "${extensions}" -maxdepth 1 -name '*.control' \
        ! -name 'plpgsql.control' ! -name 'vector.control' -delete; \
    test "$(find "${extensions}" -maxdepth 1 -name '*.control' | sort | xargs -n1 basename | tr '\n' ' ')" \
        = "plpgsql.control vector.control "; \
    rm -rf /var/lib/apt/lists/*
