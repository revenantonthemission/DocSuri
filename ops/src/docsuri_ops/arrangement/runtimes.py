"""The pinned runtimes, held once (decision "The pgvector pin and the lane's image").

PostgreSQL is 16.14 (tech-stack-decisions). pgvector is the newest release that
supports PostgreSQL 16 and iterative index scans (0.8.0 or later): 0.8.7, published
on PGXN on 2026-10-01 with the SHA-1 below, which a download is checked against
together with the SHA-256 recorded from that verified download.

pgvector's official PostgreSQL 16 images for 0.8.7 (and 0.8.6) carry server 16.15,
and the last one carrying 16.14 is 0.8.5's, read from each image's configuration on
2026-10-22. No published digest carries exactly (16.14, 0.8.7), so the composed realm
and the CI lane build their image from the `postgres:16.14` digest and pgvector's
pinned source (`scripts/u8_database_image/Dockerfile`), and the same version
assertion runs either way. This fallback is recorded for approval at the U8
checkpoint. The installer's source builds (Step 37) add their pins here.
"""

from __future__ import annotations

from dataclasses import dataclass

POSTGRESQL_VERSION = "16.14"


@dataclass(frozen=True)
class SourcePin:
    version: str
    url: str
    published_sha1: str
    sha256: str


PGVECTOR = SourcePin(
    version="0.8.7",
    url="https://api.pgxn.org/dist/vector/0.8.7/vector-0.8.7.zip",
    # PGXN's META.json for vector 0.8.7 publishes this SHA-1.
    published_sha1="305575805ca313b5aaeb070098ecfb4a5bd074ca",
    sha256="cf09c09624f7fc9eb31560e48539799ee516030d89b22155c36f3cc2a86fc452",
)
# pgvector's loadable module, relative to the PostgreSQL runtime's folder. PGXS installs
# the module as `vector$(DLSUFFIX)` into `pkglibdir`, the folder `pg_config --pkglibdir`
# reports; PostgreSQL's `Makefile.global` keeps `pkglibdir` at `$(libdir)` when that path
# contains `postgres` or `pgsql`, as `<runtimes>/postgresql-16.14/lib` does (phase 2
# configures with `--prefix=<that folder>`); PostgreSQL 16's macOS template sets DLSUFFIX
# to `.dylib`. Only the installation's first build confirms this reading; phase 2 refuses
# the pin when no regular file is there (`runtime-program-missing:pgvector`).
PGVECTOR_LIBRARY = "lib/vector.dylib"
# pgvector's control file and install script, relative to the same folder. The same
# `Makefile.global` rule keeps `datadir` at `share/`, and PGXS installs an extension's
# control file and install script into `$(datadir)/extension`. `CREATE EXTENSION vector`
# reads the control file, whose `module_pathname` names the library the extension's
# functions load, and then runs the install script; phase 3 runs that statement in
# `template1`. Phase 2 refuses either one missing (`runtime-file-missing:pgvector`).
PGVECTOR_CONTROL = "share/extension/vector.control"
PGVECTOR_SCRIPT = f"share/extension/vector--{PGVECTOR.version}.sql"

# The official `postgres:16.14-bookworm` index digest (Debian 12, as pgvector's own
# PostgreSQL 16 images use), published 2026-08-05.
POSTGRES_BASE_IMAGE = (
    "postgres@sha256:64154d0babcb1741988719e703419af0382b19953706149f9872fbd0f438efa8"
)

# The official pgvector image carrying exactly (16.14, 0.8.7), if one is ever published.
# None: the fallback build is used (see the module docstring).
PGVECTOR_OFFICIAL_IMAGE: str | None = None

# The one extension (D14): the only extensions the instance can install. The image
# keeps only their control files, and `migrate` refuses any other available extension.
DATABASE_EXTENSIONS = ("plpgsql", "vector")

# The tag the realm and the lane give the fallback build, and the labels it carries so
# a container can be traced back to these pins. The tag's last part is the image's own
# build revision: revision 2 keeps only DATABASE_EXTENSIONS installable.
DATABASE_IMAGE_REVISION = 2
DATABASE_IMAGE_TAG = (
    f"docsuri/u8-postgres:{POSTGRESQL_VERSION}-pgvector-{PGVECTOR.version}"
    f"-r{DATABASE_IMAGE_REVISION}"
)
DATABASE_IMAGE_LABELS = {
    "dev.docsuri.u8.postgresql": POSTGRESQL_VERSION,
    "dev.docsuri.u8.pgvector": PGVECTOR.version,
    "dev.docsuri.u8.pgvector.sha256": PGVECTOR.sha256,
    "dev.docsuri.u8.base": POSTGRES_BASE_IMAGE,
    "dev.docsuri.u8.extensions": ",".join(DATABASE_EXTENSIONS),
}


def server_version_matches(reported: str) -> bool:
    """`SHOW server_version` reports e.g. `16.14 (Debian 16.14-1.pgdg120+1)`."""
    return reported.split()[0] == POSTGRESQL_VERSION if reported else False


# --- The installer's runtimes (U8 plan Step 37; Workflow 20 step 2, BR6.11) ---------------
#
# Each runtime is checked against its publisher's checksum before anything of it is
# used, then with `otool -L`. Where the publisher puts its checksum:
#
# - `sha256-file`: a `<archive>.sha256` file beside the archive (PostgreSQL's source
#   releases);
# - `github-digest`: the `digest` (`sha256:…`) GitHub's release API reports for the
#   publisher's uploaded asset (Ollama, cloudflared, uv);
# - `pinned`: a digest held here, from a verified download (pgvector, above).
#
# The publisher's checksum is read at installation and recorded in the installation log
# beside the downloaded file's own digest (tech-stack-decisions § Verification notes).
#
# pgvector's library is checked like PostgreSQL's own programs, at phase 2 and by the
# isolation check (security-design § 8).


@dataclass(frozen=True)
class RuntimePin:
    name: str
    version: str
    url: str
    checksum: str  # `sha256-file`, `github-digest` or `pinned`
    checksum_url: str | None = None
    sha256: str | None = None
    folder: str = ""
    # The programs and loadable modules that phase 2's `otool -L` and the isolation
    # check's programs item watch, relative to the runtime's folder.
    programs: tuple[str, ...] = ()
    # The files the isolation check's files item watches, relative to the runtime's folder.
    config_files: tuple[str, ...] = ()

    @property
    def archive(self) -> str:
        return self.url.rsplit("/", 1)[-1]


POSTGRESQL = RuntimePin(
    name="postgresql", version=POSTGRESQL_VERSION,
    url=f"https://ftp.postgresql.org/pub/source/v{POSTGRESQL_VERSION}/"
        f"postgresql-{POSTGRESQL_VERSION}.tar.bz2",
    checksum="sha256-file",
    checksum_url=f"https://ftp.postgresql.org/pub/source/v{POSTGRESQL_VERSION}/"
                 f"postgresql-{POSTGRESQL_VERSION}.tar.bz2.sha256",
    folder=f"postgresql-{POSTGRESQL_VERSION}",
    programs=("bin/postgres", "bin/pg_ctl", "bin/initdb", "bin/psql", "bin/pg_dump",
              "bin/pg_restore", "bin/pg_isready"),
)
OLLAMA = RuntimePin(
    name="ollama", version="0.40.7",
    url="https://github.com/ollama/ollama/releases/download/v0.40.7/ollama-darwin.tgz",
    checksum="github-digest",
    checksum_url="https://api.github.com/repos/ollama/ollama/releases/tags/v0.40.7",
    folder="ollama-0.40.7", programs=("ollama",),
)
CLOUDFLARED = RuntimePin(
    name="cloudflared", version="2026.10.3",
    url="https://github.com/cloudflare/cloudflared/releases/download/2026.10.3/"
        "cloudflared-darwin-arm64.tgz",
    checksum="github-digest",
    checksum_url="https://api.github.com/repos/cloudflare/cloudflared/releases/tags/2026.10.3",
    folder="cloudflared-2026.10.3", programs=("cloudflared",),
)
# uv stages each release's environment (decision "The release environment"); CI uses
# the same version (U6's lane, cicd-pipeline § 3.2).
UV = RuntimePin(
    name="uv", version="0.9.0",
    url="https://github.com/astral-sh/uv/releases/download/0.9.0/"
        "uv-aarch64-apple-darwin.tar.gz",
    checksum="github-digest",
    checksum_url="https://api.github.com/repos/astral-sh/uv/releases/tags/0.9.0",
    folder="uv-0.9.0", programs=("uv",),
)
PGVECTOR_RUNTIME = RuntimePin(
    name="pgvector", version=PGVECTOR.version, url=PGVECTOR.url, checksum="pinned",
    sha256=PGVECTOR.sha256, folder=f"postgresql-{POSTGRESQL_VERSION}",
    programs=(PGVECTOR_LIBRARY,), config_files=(PGVECTOR_CONTROL, PGVECTOR_SCRIPT),
)
RUNTIMES = (POSTGRESQL, PGVECTOR_RUNTIME, OLLAMA, CLOUDFLARED, UV)
# PostgreSQL's build: no ICU and no TLS (tech-stack-decisions, Q22 A).
POSTGRESQL_CONFIGURE = ("--without-icu", "--without-openssl", "--without-readline")
PYTHON_VERSION = "3.13.7"


def publisher_checksum(pin: RuntimePin, answer: bytes) -> str:
    """The publisher's SHA-256 for the pinned archive, from its checksum answer: a
    `<digest>  <name>` file, or GitHub's release JSON with each asset's `digest`.
    Anything else refuses (never a pass)."""
    import json
    import re

    if pin.checksum == "pinned":
        if pin.sha256 is None:
            raise ValueError("a pinned runtime needs its digest")
        return pin.sha256
    if pin.checksum == "sha256-file":
        match = re.fullmatch(r"\s*([0-9a-f]{64})\s+\*?(\S+)\s*", answer.decode("ascii", "replace"))
        if match is None or match.group(2) != pin.archive:
            raise ValueError("the publisher's checksum file does not name the archive")
        return match.group(1)
    if pin.checksum == "github-digest":
        value = json.loads(answer)
        if value.get("tag_name", "").lstrip("v") != pin.version:
            raise ValueError("the release answer is for another version")
        for asset in value.get("assets", []):
            if asset.get("name") == pin.archive:
                digest = str(asset.get("digest", ""))
                if re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    return digest.removeprefix("sha256:")
        raise ValueError("the release answer carries no digest for the archive")
    raise ValueError("unknown checksum source")
