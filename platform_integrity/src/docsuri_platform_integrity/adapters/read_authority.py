"""Current certificate/subject grant lookup on the authoritative control connection."""

import re


class PostgresReadAuthority:
    def __init__(self, connection_factory, clock):
        self.connection_factory, self.clock = connection_factory, clock

    def permits(self, fingerprint, subject):
        if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            return False
        if not isinstance(subject, str) or not re.fullmatch(r"[A-Za-z0-9_.:@/-]{1,200}", subject):
            return False
        try:
            with self.connection_factory() as connection:
                row = connection.execute(
                    "SELECT valid_from,valid_until,revoked FROM r1_control.reader_grants "
                    "WHERE fingerprint=%s AND subject=%s", (fingerprint, subject),
                ).fetchone()
            lower, upper = self.clock()
            return (
                row is not None and row[2] is False and type(lower) is int and type(upper) is int
                and 0 <= lower <= upper < 2**64 and int(row[0]) <= lower <= upper < int(row[1])
            )
        except Exception:
            return False
