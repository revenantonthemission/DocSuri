"""Target-side effect executor: one target transaction per planned effect.

The control plane records intent durably as UNKNOWN before dispatch; this adapter performs the
effect and writes its ledger row in a *single* target transaction, under a dedicated physical
connection and a session-level lock, with the operator authority re-checked inside that same
transaction immediately before commit. That is what serializes a concurrent revocation against
the commit: the finalizer holds a short ``FOR SHARE`` lock on the grant row, so a revoker's
UPDATE either commits first and is seen by the finalizer, or waits for the commit to finish.

A lost commit reply is never reported as success. The effect may be durable while the caller
cannot prove it, so the executor raises :class:`TargetOutcomeUnknown` and the only way to resolve
it is :meth:`PostgresTargetExecutor.observe`, which is read-only and never writes.
"""

import time
from contextlib import contextmanager

from ..contracts.codec import canonical, digest
from ..contracts.models import (
    CheckpointReceipt,
    EffectAssurance,
    EffectBinding,
    EffectObservation,
    ExecutionPlan,
    PlannedEffect,
    RunAttempt,
    TargetFence,
)
from .authority import MutationUnavailable

try:  # pragma: no cover - import shape differs only before psycopg is installed
    from psycopg import Error as PsycopgError
    from psycopg import OperationalError
except ImportError:  # pragma: no cover

    class OperationalError(RuntimeError):
        """Placeholder so the module imports without psycopg for pure-domain consumers."""

    class PsycopgError(RuntimeError):
        sqlstate = None


# The scoped command reports a moved precondition with this SQLSTATE, so the adapter can classify
# the refusal by code rather than by matching an error message.
STALE_PRECONDITION = "R1T01"
# Clock-independent source/fence refusal. The guard separately checks identity and trusted time.
AUTHORITY_NOT_CURRENT = "R1T02"


class TargetOutcomeUnknown(RuntimeError):
    """The effect may or may not be durable; only read-only reconciliation may resolve it."""


class TargetStateChanged(MutationUnavailable):
    """The target no longer holds expected_before, so this effect must not be applied."""


class PostgresTargetExecutor:
    """Applies planned effects against a dedicated target connection.

    Exclusion is derived from the physical target scope, never from the run or step. An optional
    configured key must match that derivation. Closing the physical session releases exclusion.
    """

    def __init__(
        self,
        dsn: str | None,
        authority,
        *,
        identity: str,
        session_lock_key: int | None = None,
        connection_factory=None,
        planned_effect: PlannedEffect | None = None,
        require_preparation: bool = False,
    ):
        if not identity or (session_lock_key is not None and (
            type(session_lock_key) is not int or not 0 < session_lock_key < 2**63
        )):
            raise ValueError("executor requires an identity and a non-zero session lock key")
        self.dsn = dsn
        self.authority = authority
        self.identity = identity
        self.session_lock_key = session_lock_key
        if not dsn and connection_factory is None:
            raise ValueError("explicit target connection source required")
        self.planned_effect = planned_effect
        # Legacy 006-009 tests use the old transaction primitive. The deployed scoped profile
        # requires this protocol, and migration 011 removes the legacy database signature.
        self.require_preparation = require_preparation
        self._connect = connection_factory or self._open

    def _open(self):
        import psycopg

        # autocommit keeps the connection IDLE between effects, which the guard requires.
        return psycopg.connect(self.dsn, autocommit=True, connect_timeout=1)

    @staticmethod
    def _configure(connection, timeout_ms: int):
        from psycopg.pq import TransactionStatus

        if (
            not connection.autocommit
            or connection.info.transaction_status != TransactionStatus.IDLE
        ):
            raise MutationUnavailable("dedicated idle autocommit connection required")
        connection.execute(
            "SELECT set_config('statement_timeout',%s,false),"
            "set_config('lock_timeout',%s,false),"
            "set_config('idle_in_transaction_session_timeout','5000',false)",
            (str(timeout_ms), str(timeout_ms)),
        )

    def validate(self, binding: EffectBinding) -> None:
        """Bind the actual effect to the live guard; a guard for another plan is not reusable."""
        if self.planned_effect is not None and (
            binding.step, binding.definition_digest,
            binding.expected_before, binding.expected_after,
        ) != (
            self.planned_effect.step, self.planned_effect.definition_digest,
            self.planned_effect.expected_before, self.planned_effect.expected_after,
        ):
            raise MutationUnavailable("effect differs from frozen helper step")
        if (
            binding.target != self.authority.binding.target
            or binding.target != self.authority.fence.target
            or binding.plan != self.authority.binding.plan
            or binding.attempt_id != self.authority.fence.holder
            or binding.fence_epoch != self.authority.fence.epoch
            or self.authority.definitions.get(self.identity) != binding.definition_digest
        ):
            raise MutationUnavailable("effect differs from operator authority binding")
        if self.session_lock_key not in (None, default_session_lock_key(binding)):
            raise ValueError("session lock key differs from canonical target scope")

    def validate_attempt(
        self, attempt: RunAttempt, plan: ExecutionPlan, fence: TargetFence,
    ) -> None:
        approval = self.authority.binding
        if (
            attempt.approval != approval.approval_id or attempt.actor != approval.actor
            or approval.purpose != "apply" or approval.target != plan.target
            or approval.plan != digest(canonical(plan.model_dump(mode="json")))
            or approval.artifact != plan.artifact_digest or approval.policy != plan.policy_digest
            or fence != self.authority.fence or fence.holder != attempt.attempt_id
        ):
            raise MutationUnavailable("run attempt differs from operator authority binding")

    @staticmethod
    def _lock(connection, key: int):
        # Session level, not transaction level: it must cover the whole effect, and it must be
        # released by closing the connection even if this process dies.
        connection.execute("SELECT pg_advisory_lock(%s)", (key,))

    @staticmethod
    def _unlock(connection, key: int):
        connection.execute("SELECT pg_advisory_unlock(%s)", (key,))

    @contextmanager
    def _transaction(self, connection):
        """The single target transaction. Overridable so tests can inject a lost reply."""
        with connection.transaction():
            yield connection

    def apply(
        self, binding: EffectBinding, *, preparation: CheckpointReceipt | None = None,
        before_commit_hook=None,
    ) -> str:
        """Apply the effect and its ledger row atomically, returning the ledger digest.

        Raises :class:`TargetOutcomeUnknown` when the commit outcome cannot be proven, and
        :class:`TargetStateChanged` when the compare-and-set precondition no longer holds.
        """
        self.validate(binding)
        if self.require_preparation and (
            preparation is None or not preparation.dispatch_token
            or preparation.record.binding != binding
            or preparation.record.checkpoint.assurance != EffectAssurance.UNKNOWN
            or preparation.record_digest != digest(canonical(
                preparation.record.model_dump(mode="json"),
            ))
            or preparation.event_id != digest(canonical([
                "checkpoint", binding.run_id, preparation.record.checkpoint.sequence,
            ]))
        ):
            raise MutationUnavailable("acknowledged preparation required")
        remaining_ms = int((self.authority.deadline - time.monotonic()) * 1000)
        if remaining_ms <= 0:
            raise MutationUnavailable("operator attempt deadline expired")
        key = default_session_lock_key(binding)
        connection = self._connect()
        try:
            self._configure(connection, min(5000, remaining_ms))
            self._lock(connection, key)
            try:
                with self.authority.guard(
                    connection, self.identity, binding.definition_digest
                ) as finalization:
                    with self._transaction(connection):
                        if self.require_preparation:
                            ledger = self._write_prepared(connection, binding, preparation)
                            if before_commit_hook is not None:
                                before_commit_hook()
                        else:
                            ledger = self._write(connection, binding, before_commit_hook)
                        # Re-checks the authority under FOR SHARE while this transaction still
                        # holds the effect. A concurrent revoke cannot slip past this point.
                        window = finalization.before_commit()
                        if self.require_preparation:
                            connection.execute(
                                "SELECT r1_target.attest_effect(%s,%s,%s,%s,%s,%s)",
                                (binding.run_id, binding.step, binding.attempt_id,
                                 preparation.record_digest, str(window[0]), str(window[1])),
                            )
            except OperationalError as error:
                # The connection failed, and the client cannot tell a mid-transaction drop from a
                # lost commit acknowledgement. Both are reported as unproven: saying "failed"
                # could invite a duplicate effect, and saying "succeeded" could be a lie. Only
                # read-only reconciliation may resolve it.
                raise TargetOutcomeUnknown(f"target commit outcome unproven: {error}") from error
            except PsycopgError as error:
                # A custom ERRCODE is not one of psycopg's known classes, so it arrives as the
                # generic database error; the SQLSTATE is the only reliable discriminator.
                if error.sqlstate == STALE_PRECONDITION:
                    # The compare-and-set lost: the server rejected and rolled back, so this is a
                    # provable non-application rather than an unknown outcome.
                    raise TargetStateChanged(
                        "target state no longer matches expected_before"
                    ) from error
                if error.sqlstate == AUTHORITY_NOT_CURRENT:
                    # The database refused because the grant is not current. This is a refusal,
                    # not a failure of the effect, and it is provably not applied.
                    raise MutationUnavailable("operator authority is not current") from error
                if error.sqlstate == "R1T04":
                    raise MutationUnavailable(
                        "native preparation or finalization rejected",
                    ) from error
                # Any other database error is not an outcome we can characterise, so it is
                # reported as itself rather than being guessed into a target-domain verdict.
                raise
            except (MutationUnavailable, ValueError, KeyError):
                # A refusal or a rejected statement: the transaction aborted and rolled back.
                raise
            return ledger
        finally:
            try:
                self._unlock(connection, key)
            except Exception:
                # A session lock is released by closing the connection anyway, so a dead
                # connection here must not mask the real outcome.
                pass
            connection.close()

    def _write_prepared(self, connection, binding: EffectBinding, preparation: CheckpointReceipt):
        return connection.execute(
            "SELECT r1_target.apply_effect(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (binding.target.target_id, binding.target.namespace, binding.target.incarnation,
             binding.run_id, binding.step, binding.attempt_id, binding.definition_digest,
             binding.expected_before, binding.expected_after, int(binding.fence_epoch),
             self.authority.binding.approval_id, binding.plan, preparation.record_digest,
             preparation.dispatch_token),
        ).fetchone()[0]

    def _write(self, connection, binding: EffectBinding, before_commit_hook) -> str:
        """The effect and its ledger row, inside the caller's open transaction.

        There is deliberately no table write here. The target plane is reachable only through the
        scoped ``r1_target.apply_effect`` command, so the process role holds no INSERT or UPDATE
        right on any table and cannot widen its own reach.
        """
        ledger = connection.execute(
            "SELECT r1_target.apply_effect(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                binding.target.target_id,
                binding.target.namespace,
                binding.target.incarnation,
                binding.run_id,
                binding.step,
                binding.attempt_id,
                binding.definition_digest,
                binding.expected_before,
                binding.expected_after,
                int(binding.fence_epoch),
                self.authority.binding.approval_id,
                binding.plan,
            ),
        ).fetchone()[0]
        if before_commit_hook is not None:
            before_commit_hook()
        return ledger

    def observe(self, binding: EffectBinding) -> EffectObservation:
        """Read-only reconciliation. Never writes, never authorizes, never advances anything.

        A matching v2 ledger proves the effect, not historical protected-clock/actor approval.
        Abort requires target exclusion AND a newer native fence preventing delayed dispatch.
        Missing/legacy/mismatched records and busy writers remain UNKNOWN.
        """
        key = default_session_lock_key(binding)
        connection = self._connect()
        try:
            self._configure(connection, 2000)
            if self.require_preparation:
                from psycopg.types.json import Jsonb

                with connection.transaction():
                    connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                    payload = connection.execute(
                        "SELECT r1_target.observe_prepared_effect(%s)",
                        (Jsonb(binding.model_dump(mode="json")),),
                    ).fetchone()[0]
                return EffectObservation.model_validate_json(canonical(payload))
            if not connection.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()[0]:
                return _unknown(binding)
            with connection.transaction():
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                row = connection.execute(
                    "SELECT target_id,namespace,incarnation,plan_digest,definition_digest,"
                    "expected_before,expected_after,fence_epoch,digest,actor_role,"
                    "authorization_revision,approval_id FROM r1_target.effect_ledger "
                    "WHERE run_id=%s AND step=%s AND attempt_id=%s",
                    (binding.run_id, binding.step, binding.attempt_id),
                ).fetchone()
                state = connection.execute(
                    "SELECT digest FROM r1_target.state WHERE target_id=%s AND namespace=%s "
                    "AND incarnation=%s",
                    (
                        binding.target.target_id,
                        binding.target.namespace,
                        binding.target.incarnation,
                    ),
                ).fetchone()
                identity = connection.execute(
                    "SELECT incarnation,epoch FROM r1_control.target_identity "
                    "WHERE target_id=%s AND namespace=%s",
                    (binding.target.target_id, binding.target.namespace),
                ).fetchone()
                # Settings alone do not prove this observed commit was flushed (a direct caller
                # can request async commit). Check a WAL barrier after reading the visible facts.
                durable = connection.execute(
                    "SELECT current_setting('fsync')='on' AND NOT pg_is_in_recovery() "
                    "AND pg_current_wal_insert_lsn() <= pg_current_wal_flush_lsn()"
                ).fetchone()[0]
            observed = state[0] if state is not None else None
            if row is not None:
                expected = (
                    binding.target.target_id, binding.target.namespace, binding.target.incarnation,
                    binding.plan, binding.definition_digest, binding.expected_before,
                    binding.expected_after, int(binding.fence_epoch),
                )
                if row[:8] != expected or row[8] != ledger_digest(binding, *row[9:]):
                    return _unknown(binding, observed)
                return EffectObservation(
                    binding=binding,
                    authoritative=True,
                    receipt=row[8],
                    committed=True,
                    aborted=False,
                    quiescent=True,
                    observed_state=observed,
                    authorization_verified=False,
                    durability_verified=durable,
                )
            if (
                durable and observed == binding.expected_before and identity is not None
                and identity[0] == binding.target.incarnation
                and identity[1] > int(binding.fence_epoch)
            ):
                return EffectObservation(
                    binding=binding,
                    authoritative=True,
                    receipt=digest(canonical({
                        "kind": "rem1.fenced-abort.v1", "binding": binding.model_dump(mode="json"),
                        "observedEpoch": str(identity[1]), "observedState": observed,
                    })),
                    committed=False,
                    aborted=True,
                    quiescent=True,
                    observed_state=observed,
                    authorization_verified=False,
                    durability_verified=True,
                )
            return _unknown(binding, observed)
        finally:
            # Session close releases even a successfully acquired observation lock on error.
            connection.close()


def default_session_lock_key(binding: EffectBinding) -> int:
    """Canonical physical target scope, shared with SQL and across runs/restored incarnations."""
    raw = digest(canonical([
        "rem1.target-lock.v1", binding.target.target_id, binding.target.namespace,
    ]))
    return int(raw.split(":", 1)[1][:15], 16)


def ledger_digest(binding: EffectBinding, actor: str, revision: int, approval: str) -> str:
    """Independently verify the database's v2 receipt; a digest is integrity, not authority."""
    return digest(canonical({
        "kind": "rem1.target-effect.v2", "actorRole": actor, "approval": approval,
        "attemptId": binding.attempt_id, "authorizationRevision": str(revision),
        "definitionDigest": binding.definition_digest, "expectedAfter": binding.expected_after,
        "expectedBefore": binding.expected_before, "fenceEpoch": binding.fence_epoch,
        "incarnation": binding.target.incarnation, "namespace": binding.target.namespace,
        "plan": binding.plan, "runId": binding.run_id, "step": binding.step,
        "targetId": binding.target.target_id,
    }))


def _unknown(binding: EffectBinding, observed: str | None = None) -> EffectObservation:
    return EffectObservation(
        binding=binding, authoritative=False, receipt=None, committed=False, aborted=False,
        quiescent=False, observed_state=observed, authorization_verified=False,
        durability_verified=False,
    )
