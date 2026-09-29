# DO NOT EDIT. Generated from the JSON Schema SSOT in shared/ by tools/generate.py.
# Change the schema and regenerate (§5-B); never hand-edit.

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, RootModel
from enum import Enum


class ExistingOwnerHttpContractsPromotedToSharedWire(RootModel[Any]):
    root: Any = Field(
        ...,
        description='Existing U2/U7/U8/U9/U10/U11/U12/U14/U15/U16 transport shapes. View projections remain explicit adapters. No new endpoint or behavior is introduced.',
        title='Existing owner HTTP contracts promoted to shared wire',
    )


class GlossaryTermUpsertDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    termFrom: str
    termTo: str
    promptEnforced: bool | None = None


class GlossaryUpsertResultDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Literal['ok']
    glossaryVer: float


class GlossaryTermDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    termFrom: str
    termTo: str
    promptEnforced: bool | None = None


class GlossaryListDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Literal['ok']
    terms: list[GlossaryTermDTO]


class BehaviorEventType(Enum):
    search_executed = 'search_executed'
    paper_opened = 'paper_opened'
    library_added = 'library_added'
    library_removed = 'library_removed'
    summary_translation_requested = 'summary_translation_requested'
    source_anchor_clicked = 'source_anchor_clicked'
    glossary_updated = 'glossary_updated'
    read_completed = 'read_completed'


class Kind(Enum):
    paper = 'paper'
    search = 'search'
    summary = 'summary'
    translation = 'translation'
    source_anchor = 'source_anchor'
    glossary = 'glossary'


class BehaviorSubject(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Kind
    paperId: str | None = None
    queryHash: str | None = None
    category: str | None = None
    anchorId: str | None = None


class Source(Enum):
    backend = 'backend'
    frontend_anchor = 'frontend_anchor'


class BehaviorEventCreate(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    eventType: BehaviorEventType
    subject: BehaviorSubject
    occurredAt: str | None = None
    source: Source | None = None
    metadata: dict[str, Any] | None = None
    dedupeKey: str


class Reason(Enum):
    recorded = 'recorded'
    duplicate = 'duplicate'
    disabled = 'disabled'
    degraded = 'degraded'


class EventRecordResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    recorded: bool
    duplicate: bool
    reason: Reason


class PersonalizationSettings(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    userId: str
    enabled: bool
    rawEventsDeletedAt: str | None = None
    profileResetAt: str | None = None
    updatedAt: str


class DeletePersonalizationEventsResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    deletedEvents: float


class ResetPersonalizationProfileResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Literal['reset']


class OnboardingState(Enum):
    pending = 'pending'
    completed = 'completed'
    skipped = 'skipped'


class OnboardingStatusResponse(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: OnboardingState
    categories: list[str]


class Source1(Enum):
    onboarding_picker = 'onboarding_picker'
    orcid_derived = 'orcid_derived'


class InterestSelectionCreate(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    categories: list[str]
    keywords: list[str]
    source: Source1


class InterestsResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: OnboardingState
    eventRecorded: bool
    reason: Reason


class SkipResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: OnboardingState


class Kind1(Enum):
    category = 'category'
    keyword = 'keyword'


class OrcidSuggestion(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Kind1
    value: str


class OrcidSuggestionsResponse(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    suggestions: list[OrcidSuggestion]
    degraded: bool


class LoginProvider(Enum):
    GOOGLE = 'GOOGLE'
    ORCID = 'ORCID'
    EMAIL = 'EMAIL'


class AccountProfileVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    loginProvider: LoginProvider
    createdAt: str


class OrcidWorkVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    title: str
    year: float | None


class OrcidProfileVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    orcidId: str
    name: str
    affiliation: str | None
    works: list[OrcidWorkVM]


class RecentlyViewedItemVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    arxivId: str
    title: str
    viewedAt: str


class ConsentSettingsVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    privacyPolicyAgreed: bool
    termsOfServiceAgreed: bool
    nightlyPushAgreed: bool


class DigestCadence(Enum):
    daily = 'daily'
    weekly = 'weekly'


class FollowedTopicVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: str
    topic: str
    createdAt: str


class FollowListVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    topics: list[FollowedTopicVM]
    maxTopics: float


class DigestSettingsVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    optedIn: bool
    cadence: DigestCadence
    lastSentAt: str | None


class UnsubscribeResultVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    optedIn: bool


class CitationTreeStatus(Enum):
    Success = 'Success'
    Partial = 'Partial'
    Unavailable = 'Unavailable'
    RateLimited = 'RateLimited'


class CitationNode(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    nodeId: str
    title: str
    year: float | None = None
    citationCount: float | None = None
    depth: float
    arxivId: str | None = None
    url: str | None = None
    inCorpus: bool | None = None
    saveable: bool
    alreadyShown: bool


class CitationEdge(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    source: str
    target: str
    depth: float


class UnresolvedCitation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    title: str
    year: float | None = None
    reason: str


class CitationTreeResponse(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: CitationTreeStatus
    rootPaperId: str
    nodes: list[CitationNode]
    edges: list[CitationEdge]
    unresolved: list[UnresolvedCitation]
    depthReturned: float
    truncated: bool
    remainingEstimate: float | None = None
    cacheHit: bool
    providerStatus: str


class CitationTreeQuery(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    expandNodeId: str | None = None
    refresh: bool | None = None


class PlanTier(Enum):
    free = 'free'
    plus = 'plus'


class PlanQuotasVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    evidenceDaily: float
    noveltyDaily: float


class MyPlanVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    tier: PlanTier
    quotas: PlanQuotasVM
    expiresAt: str | None = None


class PaperMetaVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    arxivId: str
    title: str
    authors: list[str]
    year: float | None = None
    abstract: str
    arxivUrl: str | None = None
    sourceName: str | None = None
    sourceUrl: str | None = None


class State(Enum):
    active = 'active'
    completed = 'completed'
    failed = 'failed'
    cancelled = 'cancelled'


class BackendResearchJob(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: str
    title: str
    state: State
    updatedAt: str


class Role(Enum):
    user = 'user'
    assistant = 'assistant'
    system = 'system'


class BackendResearchMessage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    messageId: str
    role: Role
    content: str
    attachments: list[Any] | None = None
    createdAt: str


class BackendNoveltyJob(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: str
    topic: str
    state: str
    updatedAt: str


class BackendNoveltyMessage(RootModel[BackendResearchMessage]):
    root: BackendResearchMessage = Field(..., title='BackendNoveltyMessage')


class BackendNoveltyEvent(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    eventId: str
    state: str
    message: str
    payload: dict[str, Any] | None = None
    createdAt: str


class BackendNoveltyArtifact(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    artifactId: str
    kind: str
    title: str
    payload: dict[str, Any] | None = None
    createdAt: str


class NotionConnectionStatusVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connected: bool
    parentPageId: str | None = None
    updatedAt: str | None = None


class NotionExportVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: str
    notionPageId: str | None = None
    errorMessage: str | None = None


class Artifact(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: str
    title: str


class Preview(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    title: str
    artifacts: list[Artifact]


class NotionExportPreviewVM(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    export: NotionExportVM
    preview: Preview


class SummarizeValidationErrorDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Literal['validation_error']
    field: str | None = None
    message: str


class UnauthorizedDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Literal['unauthorized']


class JobAcceptedDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: str


class AgentJobsDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobs: list[BackendResearchJob | BackendNoveltyJob] | None = None


class ResearchJobDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    job: BackendResearchJob
    messages: list[BackendResearchMessage] | None = None


class NoveltyJobDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    job: BackendNoveltyJob
    events: list[BackendNoveltyEvent] | None = None


class NoveltyMessagesDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    messages: list[BackendNoveltyMessage] | None = None


class NoveltyArtifactsDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    artifacts: list[BackendNoveltyArtifact] | None = None


class RecentlyViewedDTO(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[RecentlyViewedItemVM]
