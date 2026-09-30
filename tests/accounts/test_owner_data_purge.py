"""BR-PURGE-02 — owner purge must remove stored objects as well as rows, in DB→object order.

The row is the only proof of ownership of an object key, so the keys must be read before the
DELETE and the objects removed after — never a prefix sweep (that would cross owners)."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.modules.accounts.services.owner_data_purge import (
    OwnerScopedTable,
    S3ObjectPurger,
    SqlOwnerDataPurger,
)


class FakeObjectPurger:
    def __init__(self, fail: bool = False):
        self.deleted: list[str] = []
        self._fail = fail

    def delete_objects(self, keys):
        if self._fail:
            raise RuntimeError("object store unavailable")
        keys = [k for k in keys]
        self.deleted.extend(keys)
        return len(keys)


def _session_with_artifacts():
    engine = create_engine("sqlite:///:memory:")
    s = sessionmaker(bind=engine)()
    s.execute(
        text(
            "CREATE TABLE novelty_artifacts ("
            "artifact_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, object_key TEXT NOT NULL)"
        )
    )
    return s


def test_owner_objects_are_deleted_after_rows_using_collected_keys():
    s = _session_with_artifacts()
    s.execute(
        text("INSERT INTO novelty_artifacts VALUES ('a1','owner-1','novelty/owner-1/j1/art.json')")
    )
    s.execute(
        text("INSERT INTO novelty_artifacts VALUES ('a2','owner-1','novelty/owner-1/j2/art.json')")
    )
    s.execute(
        text("INSERT INTO novelty_artifacts VALUES ('b1','owner-2','novelty/owner-2/j1/art.json')")
    )
    s.commit()

    purger = FakeObjectPurger()
    SqlOwnerDataPurger(
        s,
        tables=(OwnerScopedTable("novelty_artifacts", object_column="object_key"),),
        object_purger=purger,
    ).purge("owner-1")

    assert sorted(purger.deleted) == [
        "novelty/owner-1/j1/art.json",
        "novelty/owner-1/j2/art.json",
    ]
    # owner-2's row survives untouched and its object was never handed to the purger.
    assert s.execute(
        text("SELECT COUNT(*) FROM novelty_artifacts WHERE owner_id='owner-2'")
    ).scalar_one() == 1
    assert s.execute(
        text("SELECT COUNT(*) FROM novelty_artifacts WHERE owner_id='owner-1'")
    ).scalar_one() == 0


def test_object_delete_failure_propagates_so_the_transaction_can_roll_back():
    """A store failure must not be swallowed: purge_job rolls back and retries the account, so the
    rows (and the keys) are still present for the retry."""
    s = _session_with_artifacts()
    s.execute(
        text("INSERT INTO novelty_artifacts VALUES ('a1','owner-1','novelty/owner-1/j1/a.json')")
    )
    s.commit()

    import pytest

    with pytest.raises(RuntimeError, match="object store unavailable"):
        SqlOwnerDataPurger(
            s,
            tables=(OwnerScopedTable("novelty_artifacts", object_column="object_key"),),
            object_purger=FakeObjectPurger(fail=True),
        ).purge("owner-1")
    s.rollback()
    assert s.execute(text("SELECT COUNT(*) FROM novelty_artifacts")).scalar_one() == 1


def test_rows_are_still_deleted_when_no_object_purger_is_configured():
    """A deployment without the bucket env still purges DB rows; the gap is only the object."""
    s = _session_with_artifacts()
    s.execute(
        text("INSERT INTO novelty_artifacts VALUES ('a1','owner-1','novelty/owner-1/j1/a.json')")
    )
    s.commit()

    SqlOwnerDataPurger(
        s,
        tables=(OwnerScopedTable("novelty_artifacts", object_column="object_key"),),
        object_purger=None,
    ).purge("owner-1")

    assert s.execute(text("SELECT COUNT(*) FROM novelty_artifacts")).scalar_one() == 0


class _RecordingS3:
    def __init__(self):
        self.buckets: list[str] = []
        self.calls: list[list[dict]] = []

    def delete_objects(self, Bucket, Delete):  # noqa: N803 — boto3 keyword names
        self.buckets.append(Bucket)
        self.calls.append(Delete["Objects"])
        return {"Deleted": Delete["Objects"]}


def test_s3_object_purger_chunks_and_skips_empty_keys():
    client = _RecordingS3()
    purger = S3ObjectPurger("artifacts-bucket", client=client)

    assert purger.delete_objects([]) == 0
    assert client.calls == []

    purger.delete_objects(["k1", "", "k2"])
    assert client.calls == [[{"Key": "k1"}, {"Key": "k2"}]]
    assert client.buckets == ["artifacts-bucket"]


def test_s3_object_purger_requires_a_bucket():
    import pytest

    with pytest.raises(ValueError, match="bucket"):
        S3ObjectPurger("")
