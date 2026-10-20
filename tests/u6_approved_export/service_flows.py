"""Service-level flows: the real `ExportService` over the realm and the real SDK over the
fake Notion, with a research-port double for U4's export read and an injected clock.

The research double stands in only for U4's answers in component tests (absent,
changed, ineligible, unreachable, policy unresolved); the database, owner filters,
compare-and-sets and the session guard are always real. Every token is a synthetic
string only the fake accepts. Policies are smaller than production (a 1 ms pace), so
no test waits in real time.
"""

import copy
import datetime as dt
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import psycopg
from backend.modules.export.errors import ExportError
from backend.modules.export.lane_store import CheckResult, WriteOutcome
from backend.modules.export.notion_session import InteractiveGate
from backend.modules.export.repository import ExportRepository
from backend.modules.export.service import ExportService
from backend.modules.export.store_support import canonical_digest
from backend.modules.export.token_keyring import TokenKeyring
from backend.modules.export.token_vault import TokenVault
from backend.modules.research.errors import ResearchError
from backend.u6_policy import ExportPolicy

from tests.u6_approved_export import notion_flows as nf
from tests.u6_approved_export import store_flows as flows

# The frozen per-operation error lists (C09 2.1.0, including A2 and A3). A foreign or
# absent record is the boundary's NOT_FOUND, which every list holds.
BASE_ERRORS = (
    "INVALID_ARGUMENT",
    "UNAUTHENTICATED",
    "FORBIDDEN",
    "NOT_FOUND",
    "POLICY_UNRESOLVED",
    "DEPENDENCY_UNAVAILABLE",
)
OPERATION_ERRORS = {
    "configure": (*BASE_ERRORS, "INVALID_TOKEN", "CONFLICT", "IDEMPOTENCY_CONFLICT"),
    "read_connection": BASE_ERRORS,
    "disconnect": (*BASE_ERRORS, "CONFLICT", "OUTCOME_UNKNOWN"),
    "list_destinations": BASE_ERRORS,
    "prepare_preview": (*BASE_ERRORS, "SOURCE_INELIGIBLE", "CONFLICT"),
    "approve": (*BASE_ERRORS, "CONFLICT", "SOURCE_INELIGIBLE", "IDEMPOTENCY_CONFLICT"),
    "execute": (
        *BASE_ERRORS,
        "CONFLICT",
        "SOURCE_INELIGIBLE",
        "APPROVAL_REQUIRED",
        "OUTCOME_UNKNOWN",
        "CAPACITY_EXHAUSTED",
    ),
    "read_effect": BASE_ERRORS,
    "cancel": (*BASE_ERRORS, "CONFLICT", "OUTCOME_UNKNOWN"),
    "history": BASE_ERRORS,
    "settle": (*BASE_ERRORS, "CONFLICT", "IDEMPOTENCY_CONFLICT"),
}
WORKSPACE_ID = nf.WORKSPACE_ID


def refusal(call) -> tuple[str, ExportError | None]:
    """Run `call`; return the code the shared boundary would answer, and the domain
    error when there is one. A call that succeeds fails the test."""
    try:
        call()
    except ExportError as error:
        return error.code, error
    except (LookupError, psycopg.errors.InsufficientPrivilege):
        return "NOT_FOUND", None
    raise AssertionError("the operation was expected to refuse")


def refuse(operation: str, call) -> str:
    """The refusal's code, which must lie in the operation's own frozen list."""
    code, _ = refusal(call)
    assert code in OPERATION_ERRORS[operation], (operation, code)
    return code


class Clock:
    """The one injected clock: every due-time decision reads it (decision "One clock")."""

    def __init__(self, start: dt.datetime | None = None):
        self.now = start or dt.datetime.now(dt.UTC)

    def __call__(self) -> dt.datetime:
        return self.now

    def advance(self, seconds: float) -> dt.datetime:
        self.now += dt.timedelta(seconds=seconds)
        return self.now


def novelty_output(*, evidence_items: int = 2, summary: str | None = None) -> dict:
    """A ready U4 novelty result's `output`, in the shape U4's export read returns."""
    evidence = [
        {
            "evidenceId": str(uuid4()),
            "sourceKind": "public-paper",
            "sourceId": f"paper-{index}",
            "sourceVersion": "1",
            "sourceContentHash": f"{index:064x}",
            "location": f"p.{index}",
            "readCoverage": "partial",
            "quote": "인용된 문장입니다.",
            "claim": f"근거 {index}의 주장입니다.",
            "stance": "supports",
            "sourceUrl": f"https://example.org/paper/{index}",
        }
        for index in range(1, evidence_items + 1)
    ]
    return {
        "summary": summary or "관련 연구 두 건을 확인했습니다. 차이는 학습 방식에 있습니다.",
        "evidence": evidence,
        "coverage": "partial",
        "limitations": ["두 편만 읽었습니다."],
        "methodRevision": "u4-synthetic-extractive-1",
        "assessments": [],
    }


class ResearchDouble:
    """U4's export read (`readNoveltyArtifactForExport`), answering like U4 does."""

    def __init__(self):
        self.results: dict[str, dict] = {}
        self.failure: BaseException | None = None
        self.calls: list = []

    def ready(self, *, output: dict | None = None, eligibility: str = "1") -> dict:
        artifact = str(uuid4())
        output = output or novelty_output()
        reference = {
            "artifactId": artifact,
            "revision": "1",
            "contentHash": canonical_digest(output),
        }
        self.results[artifact] = {
            "availability": "ready",
            "prepared": {
                "artifact": dict(reference),
                "ownerId": str(uuid4()),
                "contextId": str(uuid4()),
                "operationId": str(uuid4()),
                "kind": "novelty-result",
                "output": output,
                "currentEligibilityRevision": eligibility,
                "mediaType": "application/json",
                "policy": {"policyId": "u4-synthetic", "revision": "1"},
            },
        }
        return reference

    def set_eligibility(self, reference: dict, eligibility: str) -> None:
        self.results[reference["artifactId"]]["prepared"]["currentEligibilityRevision"] = (
            eligibility
        )

    def readNoveltyArtifactForExport(self, authority, reference):  # noqa: N802 - U4's name
        self.calls.append((authority, dict(reference)))
        if self.failure is not None:
            raise self.failure
        item = self.results.get(reference["artifactId"])
        if item is None:
            raise ResearchError("NOT_FOUND")
        if item["prepared"]["artifact"] != reference:
            raise ResearchError("CONFLICT")
        return copy.deepcopy(item)


class CountingGate(InteractiveGate):
    """The real gate, recording every key it was asked for."""

    def __init__(self, per_process: int, per_connection: int):
        super().__init__(per_process, per_connection)
        self.asked: list[UUID] = []

    def try_acquire(self, key: UUID) -> bool:
        self.asked.append(key)
        return super().try_acquire(key)


def vault(tmp_path, name: str = "export-keys") -> TokenVault:
    root = tmp_path / name
    root.mkdir(mode=0o700)
    return TokenVault(TokenKeyring(root, "u6-service-test", nf.NoSealedTokens()))


@dataclass
class Rig:
    service: ExportService
    repo: ExportRepository
    fake: object
    research: ResearchDouble
    gate: CountingGate
    clock: Clock
    authority: object
    policy: ExportPolicy
    token: str
    bot: str
    keys: list = field(default_factory=list)

    # -- connection ----------------------------------------------------------------------

    def configure(self, *, token=None, expected=None, key=None, authority=None) -> dict:
        value = {"token": token or self.token, "credentialPolicy": self.policy.reference()}
        if expected is not None:
            value["expectedRevision"] = str(expected)
        return self.service.configure(authority or self.authority, value, operation=key or uuid4())

    def connection(self, authority=None) -> dict:
        return self.service.read_connection(authority or self.authority, {})

    def new_token(self) -> tuple[str, str]:
        token, bot = nf.synthetic_token(), nf.bot_id()
        self.fake.add_token(
            token, bot_id=bot, workspace_id=WORKSPACE_ID, workspace_name=nf.WORKSPACE_NAME
        )
        return token, bot

    # -- destinations and previews --------------------------------------------------------

    def page(self, title: str | None = "합성 페이지", **kwargs) -> str:
        return self.fake.add_page(title=title, **kwargs)

    def destination(self, page_id: str, connection: dict | None = None) -> dict:
        connection = connection or self.connection()
        return {
            "connectionId": connection["connectionId"],
            "workspaceId": WORKSPACE_ID,
            "parentPageId": page_id,
            "formatRevision": "1",
        }

    def preview_value(self, page_id: str, source: dict | None = None) -> dict:
        return {
            "source": source or self.research.ready(),
            "destination": self.destination(page_id),
            "renderPolicy": self.policy.reference(),
        }

    def preview(self, page_id: str, source: dict | None = None, *, authority=None) -> dict:
        return self.service.prepare_preview(
            authority or self.authority, self.preview_value(page_id, source)
        )

    @staticmethod
    def approval_value(preview: dict, **overrides) -> dict:
        return {
            "previewId": preview["previewId"],
            "previewRevision": preview["revision"],
            "bindingHash": preview["bindingHash"],
            "explicitApproval": True,
            **overrides,
        }

    def approve(self, preview: dict, *, key=None, authority=None) -> dict:
        return self.service.approve(
            authority or self.authority, self.approval_value(preview), operation=key or uuid4()
        )

    def execute(self, approval: dict, *, key=None, authority=None) -> dict:
        value = {"approvalId": approval["approvalId"], "bindingHash": approval["bindingHash"]}
        return self.service.execute(authority or self.authority, value, operation=key or uuid4())

    def press(self, page_id: str, source: dict | None = None) -> dict:
        """One press: approve and execute with the same key (BR3.2)."""
        preview = self.preview(page_id, source)
        key = uuid4()
        approval = self.approve(preview, key=key)
        effect = self.execute(approval, key=key)
        return {"preview": preview, "approval": approval, "effect": effect}

    # -- lane outcomes, recorded through the store's own lane units ----------------------

    @staticmethod
    def row(effect: dict) -> dict:
        return {"id": UUID(effect["effectId"]), "revision": int(effect["revision"])}

    def succeed(self, effect: dict) -> dict:
        return flows.succeed(self.repo, self.row(effect), self.clock.now)

    def claim(self, effect: dict):
        return self.repo.claim(
            UUID(effect["effectId"]), int(effect["revision"]), now=self.clock.now
        )

    def uncertain(self, effect: dict) -> dict:
        return flows.uncertain(self.repo, self.row(effect), self.clock.now)

    def check(self, effect_row: dict, result: str, **facts) -> dict:
        return self.repo.record_check(
            effect_row["id"],
            effect_row["revision"],
            CheckResult(
                result=result,
                window_start=self.clock.now - dt.timedelta(minutes=10),
                evidence_hash=canonical_digest({"check": str(uuid4())}),
                **facts,
            ),
            now=self.clock.now,
        )

    def read_effect(self, effect: dict) -> dict:
        return self.service.read_effect(self.authority, {"effectId": effect["effectId"]})


def build(
    transactions,
    connect,
    authority,
    tmp_path,
    *,
    policy: ExportPolicy | None = None,
    clock: Clock | None = None,
    fresh: bool = True,
    keys: str = "export-keys",
) -> Rig:
    """A service over the realm and a fake Notion that knows one synthetic token."""
    chosen = policy or nf.policy()
    clock = clock or Clock()
    repo = ExportRepository(transactions, chosen)
    opener = vault(tmp_path, keys)
    token, bot = nf.synthetic_token(), nf.bot_id()
    fake = nf.fake_with(token, bot)
    gate = CountingGate(chosen.interactive_per_process, chosen.interactive_per_connection)
    adapter = nf.adapter(repo, opener, fake, chosen, gate=gate, clock=clock)
    research = ResearchDouble()
    service = ExportService(transactions, repo, adapter, opener, research, chosen, clock)
    if fresh:
        flows.fresh(connect, authority.account_id)
    return Rig(service, repo, fake, research, gate, clock, authority, chosen, token, bot)


def outcome_created() -> WriteOutcome:
    reference = uuid4().hex
    return WriteOutcome(
        "created",
        provider_request_id="synthetic-request",
        creator_confirmed=True,
        remote_reference=reference,
        remote_url=f"https://www.notion.so/{reference}",
    )
