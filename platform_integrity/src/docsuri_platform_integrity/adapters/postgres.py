"""Control/evidence persistence. No bootstrap DDL is issued from a read method."""

from contextlib import contextmanager

from pydantic import TypeAdapter

from ..contracts.codec import canonical, digest
from ..contracts.models import (
    U64,
    BoundCheckpoint,
    CheckpointReceipt,
    CommandContext,
    EffectAssurance,
    EffectObservation,
    EvidenceHeadSelection,
    EvidencePublication,
    ExecutionPlan,
    Ref,
    RunAttempt,
    RunIntent,
    RunRecord,
    SubjectSnapshot,
    TargetFence,
    VerificationAttestation,
    VerificationRequest,
    VerificationReservation,
)
from ..domain.gate import pending_selection, reserve_selection, resolve_selection
from ..domain.run import make_intent, prepare_checkpoint, reconcile_checkpoint


class PostgresEvidenceReader:
    def __init__(self, dsn: str | None = None, *, connection_factory=None):
        if (dsn is None) == (connection_factory is None):
            raise ValueError("exactly one database connection source required")
        self._dsn = dsn
        self._connection_factory = connection_factory

    @contextmanager
    def _connect(self):
        import psycopg

        if self._connection_factory is not None:
            with self._connection_factory() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                yield conn
            return
        with psycopg.connect(
            self._dsn,
            connect_timeout=1,
            options="-c statement_timeout=2000 -c default_transaction_read_only=on",
        ) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            yield conn

    def healthy(self) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("SELECT binding, verification_id FROM r1_control.heads LIMIT 0")
                conn.execute("SELECT verification_id FROM r1_control.evidence LIMIT 0")
                return True
        except Exception:
            return False

    def snapshot(self, subject: str):
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT h.slot, h.revision, h.state, h.evidence_id, h.binding, h.verification_id,
                    e.payload, e.digest FROM r1_control.heads h
                    LEFT JOIN r1_control.evidence e ON h.evidence_id=e.evidence_id
                    WHERE h.subject=%s ORDER BY h.slot LIMIT 101""",
                (subject,),
            ).fetchall()
            if len(rows) > 100:
                raise ValueError("evidence snapshot limit")
            heads, evidence = [], []
            for *head_values, payload, expected_digest in rows:
                head = _decode_head(head_values)
                if head.subject is not None and head.subject.subject != subject:
                    raise ValueError("evidence subject binding mismatch")
                heads.append(head)
                if payload is not None:
                    data = canonical(payload)
                    if digest(data) != expected_digest:
                        raise ValueError("evidence integrity mismatch")
                    evidence.append(VerificationAttestation.model_validate_json(data))
            return tuple(heads), tuple(evidence)


def _decode_head(row) -> EvidenceHeadSelection:
    slot, revision, state, identity, binding, verification = row
    return EvidenceHeadSelection(
        slot=slot, revision=str(revision), state=state, evidence_id=identity,
        subject=SubjectSnapshot.model_validate_json(canonical(binding)) if binding else None,
        verification_id=verification,
    )


class ControlUnavailable(RuntimeError):
    """No write acknowledgement was obtained. The caller must observe, never blindly replay."""


_REF = TypeAdapter(Ref)
_SEQUENCE = TypeAdapter(U64)


class _ControlConnection:
    """Internal control port with one acknowledged transaction per command.

    Protected composition owns authentication and current-purpose authorization. No method
    dispatches target I/O or issues a native commit guard. Checkpoint receipts prove control
    persistence only; possession of a serialized receipt cannot authorize execution.
    """

    def __init__(self, dsn: str):
        self._dsn = dsn

    @contextmanager
    def _transaction(self):
        import psycopg

        try:
            with psycopg.connect(
                self._dsn, connect_timeout=1,
                options=(
                    "-c statement_timeout=2000 -c lock_timeout=1000 "
                    "-c idle_in_transaction_session_timeout=3000 -c synchronous_commit=on"
                ),
            ) as conn:
                durability = conn.execute(
                    "SELECT current_setting('fsync'), current_setting('synchronous_commit'), "
                    "pg_is_in_recovery()"
                ).fetchone()
                if durability != ("on", "on", False):
                    raise ControlUnavailable("control durability unavailable")
                yield conn
            # Leaving this context, not executing INSERT, is the commit acknowledgement.
        except psycopg.Error:
            raise ControlUnavailable("control transaction outcome unconfirmed") from None

    @contextmanager
    def _readonly(self):
        import psycopg

        try:
            with psycopg.connect(
                self._dsn, connect_timeout=1,
                options="-c statement_timeout=2000 -c default_transaction_read_only=on",
            ) as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                yield conn
        except psycopg.Error:
            raise ControlUnavailable("control observation unavailable") from None

    @staticmethod
    def _context(context: CommandContext, purpose: str):
        if context.purpose != purpose:
            raise PermissionError("control command purpose mismatch")

    @staticmethod
    def _audit(conn, event_id: str, payload: dict) -> None:
        from psycopg.types.json import Jsonb

        conn.execute(
            "INSERT INTO r1_audit.events(event_id,payload,digest) VALUES (%s,%s,%s)",
            (event_id, Jsonb(payload), digest(canonical(payload))),
        )
        conn.execute("INSERT INTO r1_control.outbox(event_id) VALUES (%s)", (event_id,))


class PostgresRunStore(_ControlConnection):
    """Run coordination, separate from evidence publication and the readonly facade."""

    @staticmethod
    def _run(conn, run_id: str, *, lock: bool = False) -> RunRecord:
        _REF.validate_python(run_id, strict=True)
        row = conn.execute(
            "SELECT plan_payload,intent_payload,intent_digest,state,checkpoint_revision,"
            "current_attempt,semantic_key,plan_digest FROM r1_control.runs WHERE run_id=%s"
            + (" FOR UPDATE" if lock else ""),
            (run_id,),
        ).fetchone()
        if row is None:
            raise ValueError("run not found")
        plan = ExecutionPlan.model_validate_json(canonical(row[0]))
        intent_bytes = canonical(row[1])
        intent = RunIntent.model_validate_json(intent_bytes)
        if (
            digest(intent_bytes) != row[2] or intent != make_intent(plan, run_id)
            or (intent.semantic_key, intent.plan) != (row[6], row[7])
        ):
            raise ValueError("run integrity mismatch")
        return RunRecord(
            intent=intent, plan=plan, state=row[3], revision=str(row[4]), attempt_id=row[5]
        )

    @staticmethod
    def _latest(conn, run_id: str, step: str) -> BoundCheckpoint | None:
        _REF.validate_python(run_id, strict=True)
        _REF.validate_python(step, strict=True)
        row = conn.execute(
            "SELECT payload,digest,sequence,attempt_id,assurance FROM r1_control.checkpoints "
            "WHERE run_id=%s AND step=%s ORDER BY sequence DESC LIMIT 1", (run_id, step),
        ).fetchone()
        if row is None:
            return None
        return PostgresRunStore._checkpoint(row, run_id, step)

    @staticmethod
    def _checkpoint(row, run_id: str, step: str) -> BoundCheckpoint:
        payload = canonical(row[0])
        record = BoundCheckpoint.model_validate_json(payload)
        if digest(payload) != row[1] or (
            record.binding.run_id, record.binding.step, record.checkpoint.sequence,
            record.binding.attempt_id, record.checkpoint.assurance.value,
        ) != (run_id, step, str(row[2]), row[3], row[4]):
            raise ValueError("checkpoint integrity mismatch")
        return record

    @staticmethod
    def _effects(conn, run: RunRecord) -> dict[str, BoundCheckpoint]:
        """One bounded history snapshot, not a new database round-trip for each planned step."""
        count, latest = conn.execute(
            "SELECT count(*),COALESCE(MAX(sequence),0) FROM r1_control.checkpoints WHERE run_id=%s",
            (run.intent.run_id,),
        ).fetchone()
        if count != int(run.revision) or latest != int(run.revision):
            raise ValueError("checkpoint history gap")
        rows = conn.execute(
            "SELECT DISTINCT ON (step) step,payload,digest,sequence,attempt_id,assurance "
            "FROM r1_control.checkpoints WHERE run_id=%s ORDER BY step,sequence DESC LIMIT 2001",
            (run.intent.run_id,),
        ).fetchall()
        if len(rows) > 2000:
            raise ValueError("effect history limit")
        effects = {}
        planned = {effect.step: effect for effect in run.plan.steps}
        for step, *row in rows:
            record = PostgresRunStore._checkpoint(row, run.intent.run_id, step)
            expected = planned.get(step)
            if (
                expected is None or record.binding.target != run.plan.target
                or record.binding.plan != run.intent.plan
                or record.binding.definition_digest != expected.definition_digest
                or record.binding.expected_before != expected.expected_before
                or record.binding.expected_after != expected.expected_after
                or int(record.checkpoint.sequence) > int(run.revision)
            ):
                raise ValueError("effect history differs from frozen plan")
            effects[step] = record
        return effects

    @staticmethod
    def _attempt(conn, run_id: str, attempt_id: str) -> RunAttempt | None:
        _REF.validate_python(attempt_id, strict=True)
        row = conn.execute(
            "SELECT payload,digest,ordinal,invocation FROM r1_control.attempts "
            "WHERE run_id=%s AND attempt_id=%s", (run_id, attempt_id),
        ).fetchone()
        if row is None:
            return None
        payload = canonical(row[0])
        record = RunAttempt.model_validate_json(payload)
        if digest(payload) != row[1] or (
            record.run_id, record.attempt_id, record.ordinal, record.invocation
        ) != (run_id, attempt_id, row[2], row[3]):
            raise ValueError("attempt integrity mismatch")
        return record

    @staticmethod
    def _next(run: RunRecord, expected: str) -> str:
        _SEQUENCE.validate_python(expected, strict=True)
        if run.revision != expected:
            raise ValueError("checkpoint revision conflict")
        if int(expected) == 2**64 - 1:
            raise ValueError("checkpoint sequence exhausted")
        return str(int(expected) + 1)

    def read(self, run_id: str) -> RunRecord:
        with self._readonly() as conn:
            return self._run(conn, run_id)

    def latest(self, run_id: str, step: str) -> BoundCheckpoint | None:
        with self._readonly() as conn:
            return self._latest(conn, run_id, step)

    def attempt(self, run_id: str, attempt_id: str) -> RunAttempt:
        with self._readonly() as conn:
            self._run(conn, run_id)
            record = self._attempt(conn, run_id, attempt_id)
            if record is None:
                raise ValueError("attempt not found")
            return record

    def register(
        self, plan: ExecutionPlan, *, run_id: str, submission_key: str, context: CommandContext
    ) -> RunIntent:
        from psycopg.types.json import Jsonb

        self._context(context, "plan")
        _REF.validate_python(submission_key, strict=True)
        proposed = make_intent(plan, run_id)
        with self._transaction() as conn:
            # Serializes short submission/semantic-key registration only, not target execution.
            conn.execute("SELECT pg_advisory_xact_lock(1380798032, 2)")
            existing = conn.execute(
                "SELECT run_id FROM r1_control.submissions WHERE submission_key=%s",
                (submission_key,),
            ).fetchone()
            if existing:
                intent = self._run(conn, existing[0]).intent
                if intent.semantic_key != proposed.semantic_key:
                    raise ValueError("submission key changed meaning")
            else:
                existing = conn.execute(
                    "SELECT run_id FROM r1_control.runs WHERE semantic_key=%s",
                    (proposed.semantic_key,),
                ).fetchone()
                if existing:
                    intent = self._run(conn, existing[0]).intent
                else:
                    if conn.execute(
                        "SELECT 1 FROM r1_control.runs WHERE run_id=%s", (run_id,)
                    ).fetchone():
                        raise ValueError("run ID already belongs to another intent")
                    intent = proposed
                    payload = intent.model_dump(mode="json")
                    conn.execute(
                        "INSERT INTO r1_control.runs(run_id,semantic_key,plan_digest,state,"
                        "plan_payload,intent_payload,intent_digest) "
                        "VALUES (%s,%s,%s,'PLANNED',%s,%s,%s)",
                        (intent.run_id, intent.semantic_key, intent.plan,
                         Jsonb(plan.model_dump(mode="json")), Jsonb(payload),
                         digest(canonical(payload))),
                    )
                conn.execute(
                    "INSERT INTO r1_control.submissions(submission_key,run_id) VALUES (%s,%s)",
                    (submission_key, intent.run_id),
                )
                self._audit(
                    conn, digest(canonical(["submission", submission_key])),
                    {"code": "run_registered", "intent": intent.model_dump(mode="json"),
                     "context": context.model_dump(mode="json")},
                )
        return intent

    def begin_attempt(
        self, run_id: str, *, attempt_id: str, approval: str, invocation: str,
        context: CommandContext,
    ) -> RunAttempt:
        from psycopg.types.json import Jsonb

        self._context(context, "run")
        with self._transaction() as conn:
            run = self._run(conn, run_id, lock=True)
            record = self._attempt(conn, run_id, attempt_id)
            if record is not None:
                if (record.actor, record.approval, record.invocation) != (
                    context.actor, approval, invocation
                ):
                    raise ValueError("attempt identity conflict")
            else:
                effects = self._effects(conn, run)
                if run.state not in {"PLANNED", "PAUSED"} or any(
                    record.checkpoint.assurance == EffectAssurance.UNKNOWN
                    for record in effects.values()
                ):
                    raise ValueError("run requires reconciliation or is already active/complete")
                ordinal = conn.execute(
                    "SELECT COALESCE(MAX(ordinal),0)+1 FROM r1_control.attempts WHERE run_id=%s",
                    (run_id,),
                ).fetchone()[0]
                record = RunAttempt(
                    run_id=run_id, attempt_id=attempt_id, ordinal=ordinal, outcome="RUNNING",
                    actor=context.actor, approval=approval, invocation=invocation,
                    started_at=context.recorded_at,
                )
                payload = record.model_dump(mode="json")
                conn.execute(
                    "INSERT INTO r1_control.attempts(run_id,attempt_id,ordinal,invocation,"
                    "payload,digest) VALUES (%s,%s,%s,%s,%s,%s)",
                    (run_id, attempt_id, ordinal, invocation, Jsonb(payload),
                     digest(canonical(payload))),
                )
                conn.execute(
                    "UPDATE r1_control.runs SET state='RUNNING',current_attempt=%s WHERE run_id=%s",
                    (attempt_id, run_id),
                )
                self._audit(
                    conn, digest(canonical(["attempt", run_id, attempt_id])),
                    {"code": "attempt_started", "attempt": payload,
                     "context": context.model_dump(mode="json")},
                )
        return record

    @staticmethod
    def _receipt(record: BoundCheckpoint) -> CheckpointReceipt:
        return CheckpointReceipt(
            record=record, record_digest=digest(canonical(record.model_dump(mode="json"))),
            event_id=digest(canonical([
                "checkpoint", record.binding.run_id, record.checkpoint.sequence
            ])),
        )

    def _append(
        self, conn, record: BoundCheckpoint, context: CommandContext,
        observation: EffectObservation | None = None,
    ) -> CheckpointReceipt:
        from psycopg.types.json import Jsonb

        receipt = self._receipt(record)
        conn.execute(
            "INSERT INTO r1_control.checkpoints(run_id,sequence,payload,digest,step,attempt_id,"
            "assurance) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (record.binding.run_id, record.checkpoint.sequence,
             Jsonb(record.model_dump(mode="json")), receipt.record_digest, record.binding.step,
             record.binding.attempt_id, record.checkpoint.assurance.value),
        )
        self._audit(
            conn, receipt.event_id,
            {"code": "effect_checkpoint", "checkpoint": receipt.record_digest,
             "binding": record.binding.model_dump(mode="json"),
             "assurance": record.checkpoint.assurance.value,
             "context": context.model_dump(mode="json"),
             "observation": observation.model_dump(mode="json") if observation else None},
        )
        return receipt


    def prepare(
        self, run_id: str, *, attempt_id: str, step: str, fence: TargetFence,
        expected_revision: str, context: CommandContext,
    ) -> CheckpointReceipt:
        self._context(context, "run")
        with self._transaction() as conn:
            run = self._run(conn, run_id, lock=True)
            sequence = self._next(run, expected_revision)
            if run.state != "RUNNING" or run.attempt_id != attempt_id:
                raise ValueError("run/attempt is not dispatchable")
            attempt = self._attempt(conn, run_id, attempt_id)
            if attempt is None or attempt.actor != context.actor:
                raise PermissionError("attempt actor mismatch")
            effects = self._effects(conn, run)
            if any(
                record.checkpoint.assurance == EffectAssurance.UNKNOWN
                for record in effects.values()
            ):
                raise ValueError("run has an unresolved effect")
            for effect in run.plan.steps:
                if effect.step == step:
                    break
                predecessor = effects.get(effect.step)
                if predecessor is None or not predecessor.completion_verified:
                    raise ValueError("planned predecessor is not verified")
            record = prepare_checkpoint(
                run.plan, run.intent, attempt, fence, step,
                current=effects.get(step), sequence=sequence,
                recorded_at=context.recorded_at,
            )
            receipt = self._append(conn, record, context)
            conn.execute(
                "UPDATE r1_control.runs SET state='RECONCILE_REQUIRED',checkpoint_revision=%s "
                "WHERE run_id=%s", (sequence, run_id),
            )
        return receipt

    def reconcile(
        self, run_id: str, *, step: str, observation: EffectObservation,
        expected_revision: str, context: CommandContext,
    ) -> CheckpointReceipt:
        self._context(context, "reconcile")
        with self._transaction() as conn:
            run = self._run(conn, run_id, lock=True)
            sequence = self._next(run, expected_revision)
            effects = self._effects(conn, run)
            current = effects.get(step)
            if current is None:
                raise ValueError("effect checkpoint not found")
            record = reconcile_checkpoint(
                current, observation, sequence=sequence, recorded_at=context.recorded_at
            )
            if record == current:
                receipt = self._receipt(current)
            else:
                receipt = self._append(conn, record, context, observation)
                effects[step] = record
                if record.checkpoint.assurance == EffectAssurance.UNKNOWN:
                    state = "RECONCILE_REQUIRED"
                elif not record.completion_verified:
                    state = "PAUSED"
                else:
                    complete = all(
                        (item := effects.get(effect.step)) is not None
                        and item.completion_verified for effect in run.plan.steps
                    )
                    state = "SUCCEEDED" if complete else "RUNNING"
                conn.execute(
                    "UPDATE r1_control.runs SET state=%s,checkpoint_revision=%s WHERE run_id=%s",
                    (state, sequence, run_id),
                )
        return receipt


class PostgresEvidenceStore(_ControlConnection):
    """Explicit protected verification commands; never instantiated by the reader facade.

    Each command owns its commit/audit/outbox transaction. Record authenticity and current
    publishing authority belong to protected composition; persisted records alone are not PASS.
    """

    @staticmethod
    def _reservation(conn, verification_id: str) -> VerificationReservation | None:
        _REF.validate_python(verification_id, strict=True)
        row = conn.execute(
            "SELECT request,digest,subject,slot,revision,previous_revision "
            "FROM r1_control.verifications WHERE verification_id=%s", (verification_id,),
        ).fetchone()
        if row is None:
            return None
        payload = canonical(row[0])
        request = VerificationRequest.model_validate_json(payload)
        if digest(payload) != row[1] or (
            request.verification_id, request.subject.subject, request.slot
        ) != (verification_id, row[2], row[3]):
            raise ValueError("verification reservation integrity mismatch")
        return VerificationReservation(
            request=request, revision=str(row[4]), previous_revision=str(row[5])
        )

    @staticmethod
    def _head(conn, subject: str, slot: str) -> EvidenceHeadSelection | None:
        row = conn.execute(
            "SELECT slot,revision,state,evidence_id,binding,verification_id FROM r1_control.heads "
            "WHERE subject=%s AND slot=%s FOR UPDATE", (subject, slot),
        ).fetchone()
        return _decode_head(row) if row else None

    def reserve(
        self, request: VerificationRequest, *, expected_revision: str, context: CommandContext
    ) -> VerificationReservation:
        from psycopg.types.json import Jsonb

        self._context(context, "verify")
        _SEQUENCE.validate_python(expected_revision, strict=True)
        with self._transaction() as conn:
            # Also serializes absent heads and duplicate verification IDs without orphan rows.
            conn.execute("SELECT pg_advisory_xact_lock(1380798032, 3)")
            reservation = self._reservation(conn, request.verification_id)
            if reservation:
                if (
                    reservation.request != request
                    or reservation.previous_revision != expected_revision
                ):
                    raise ValueError("verification identity changed meaning")
            else:
                current = self._head(conn, request.subject.subject, request.slot)
                reservation = reserve_selection(
                    request, current, expected_revision=expected_revision
                )
                if current is None and conn.execute(
                    "SELECT count(*) FROM r1_control.heads WHERE subject=%s",
                    (request.subject.subject,),
                ).fetchone()[0] >= 100:
                    raise ValueError("verification slot limit")
                payload = request.model_dump(mode="json")
                conn.execute(
                    "INSERT INTO r1_control.verifications(verification_id,subject,slot,revision,"
                    "previous_revision,request,digest) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (request.verification_id, request.subject.subject, request.slot,
                     reservation.revision, reservation.previous_revision, Jsonb(payload),
                     digest(canonical(payload))),
                )
                head = pending_selection(reservation)
                binding = Jsonb(request.subject.model_dump(mode="json"))
                if current is None:
                    conn.execute(
                        "INSERT INTO r1_control.heads(subject,slot,revision,state,evidence_id,"
                        "binding,verification_id) VALUES (%s,%s,%s,'PENDING',NULL,%s,%s)",
                        (request.subject.subject, request.slot, head.revision,
                         binding, request.verification_id),
                    )
                else:
                    conn.execute(
                        "UPDATE r1_control.heads SET revision=%s,state='PENDING',evidence_id=NULL,"
                        "binding=%s,verification_id=%s WHERE subject=%s AND slot=%s",
                        (head.revision, binding, request.verification_id,
                         request.subject.subject, request.slot),
                    )
                self._audit(
                    conn, digest(canonical(["verification_reserved", request.verification_id])),
                    {"code": "verification_reserved", "request": payload,
                     "revision": head.revision, "context": context.model_dump(mode="json")},
                )
        return reservation

    def resolve(
        self, record: VerificationAttestation, *, context: CommandContext
    ) -> EvidencePublication:
        from psycopg.types.json import Jsonb

        self._context(context, "verify")
        if record.verification_id is None:
            raise ValueError("unbound verification result")
        payload = record.model_dump(mode="json")
        record_digest = digest(canonical(payload))
        with self._transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(1380798032, 3)")
            reservation = self._reservation(conn, record.verification_id)
            if reservation is None:
                raise ValueError("verification reservation not found")
            current = self._head(
                conn, reservation.request.subject.subject, reservation.request.slot
            )
            if current is None:
                raise ValueError("verification head missing")
            existing = conn.execute(
                "SELECT evidence_id,payload,digest FROM r1_control.evidence "
                "WHERE verification_id=%s OR evidence_id=%s",
                (record.verification_id, record.evidence_id),
            ).fetchall()
            if existing:
                if len(existing) != 1 or existing[0] != (
                    record.evidence_id, payload, record_digest
                ):
                    raise ValueError("verification result conflict")
            prior = VerificationAttestation.model_validate_json(
                canonical(existing[0][1])
            ) if existing else None
            selected = resolve_selection(reservation, current, record, existing=prior)
            if existing:
                if selected != current:
                    raise ValueError("published evidence has inconsistent selection")
            else:
                conn.execute(
                    "INSERT INTO r1_control.evidence(evidence_id,subject,payload,digest,"
                    "verification_id,slot,selection_revision) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (record.evidence_id, record.subject.subject, Jsonb(payload), record_digest,
                     record.verification_id, record.slot, record.revision),
                )
                if selected != current:
                    conn.execute(
                        "UPDATE r1_control.heads SET state='RESOLVED',evidence_id=%s "
                        "WHERE subject=%s AND slot=%s", (record.evidence_id, record.subject.subject,
                                                       record.slot),
                    )
                self._audit(
                    conn, digest(canonical(["verification_result", record.verification_id])),
                    {"code": "verification_result", "evidence": record.evidence_id,
                     "digest": record_digest, "verification": record.verification_id,
                     "selected_on_arrival": selected.evidence_id == record.evidence_id,
                     "context": context.model_dump(mode="json")},
                )
            result = EvidencePublication(
                evidence_id=record.evidence_id, record_digest=record_digest,
                selected=selected.evidence_id == record.evidence_id,
                head_revision=selected.revision,
            )
        return result
