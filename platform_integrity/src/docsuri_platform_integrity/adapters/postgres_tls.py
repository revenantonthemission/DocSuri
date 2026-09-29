"""Explicit loopback mTLS transport; credentials are fetched for each physical connection."""

import os
from contextlib import contextmanager
from typing import Annotated

from pydantic import Field

from ..contracts.models import Value


class PostgresTarget(Value):
    database: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,62}$")]
    user: Annotated[str, Field(pattern=r"^r1_[a-z0-9_]{1,59}$")]
    port: Annotated[int, Field(ge=1, le=65535)]


class PostgresTLS:
    def __init__(self, target: PostgresTarget, credentials):
        self.target = target
        self.credentials = credentials

    @contextmanager
    def connect(self, *, readonly=True):
        connection = self.open(readonly=readonly)
        try:
            yield connection
        finally:
            connection.close()

    def open(self, *, readonly=True, autocommit=False):
        """Return an authenticated physical connection; the caller owns closing it.

        Key material is removed before returning, just as for the context-managed read port.
        Explicit autocommit supports native target guards without pooling or ambient DSNs.
        """
        import psycopg

        if any(key.startswith("PG") for key in os.environ):
            raise PermissionError("inherited database configuration is not accepted")
        connection = None
        transaction_policy = (
            "-c default_transaction_read_only=on" if readonly else "-c synchronous_commit=on"
        )
        try:
            with self.credentials.materialize() as material:
                connection = psycopg.connect(
                    host="localhost", hostaddr="127.0.0.1", port=self.target.port,
                    dbname=self.target.database, user=self.target.user,
                    sslmode="verify-full", sslrootcert=str(material.ca),
                    sslcert=str(material.certificate), sslkey=str(material.private_key),
                    ssl_min_protocol_version="TLSv1.2", gssencmode="disable", passfile="/dev/null",
                    connect_timeout=1, application_name="docsuri-rem1",
                    autocommit=autocommit,
                    options="-c statement_timeout=2000 -c lock_timeout=1000 "
                    "-c idle_in_transaction_session_timeout=3000 "
                    + transaction_policy,
                )
            # libpq has completed its TLS handshake; on-disk PEMs are already removed here.
            if connection.pgconn.ssl_in_use is not True:
                raise PermissionError("database TLS was not negotiated")
            row = connection.execute(
                "SELECT session_user,rolsuper,rolcreatedb,rolcreaterole,"
                "rolreplication,rolbypassrls "
                "FROM pg_catalog.pg_roles WHERE rolname=session_user"
            ).fetchone()
            if (
                row is None or row[0] != self.target.user
                or any(flag is not False for flag in row[1:])
            ):
                raise PermissionError("unexpected privileged database identity")
            connection.rollback()
            return connection
        except BaseException:
            if connection is not None:
                connection.close()
            raise
