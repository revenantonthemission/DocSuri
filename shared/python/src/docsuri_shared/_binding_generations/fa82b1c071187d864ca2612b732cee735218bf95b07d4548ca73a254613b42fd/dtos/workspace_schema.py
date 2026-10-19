# DO NOT EDIT. Generated from the JSON Schema SSOT in shared/ by tools/generate.py.
# Change the schema and regenerate (§5-B); never hand-edit.

from __future__ import annotations

from typing import Any, Literal
from pydantic import (
    AnyUrl,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    RootModel,
)
from enum import Enum, StrEnum


class Model(RootModel[Any]):
    root: Any


class Id(RootModel[str]):
    root: str = Field(..., max_length=128, min_length=1)


class Revision(RootModel[str]):
    root: str = Field(..., max_length=128, min_length=1)


class Time(RootModel[AwareDatetime]):
    root: AwareDatetime


class Hash(RootModel[str]):
    root: str = Field(..., pattern='^[a-f0-9]{64}$')


class PolicyRef(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    policyId: Id
    revision: Revision


class Code(StrEnum):
    APPROVAL_REQUIRED = 'APPROVAL_REQUIRED'
    CANCELLED = 'CANCELLED'
    CAPACITY_EXHAUSTED = 'CAPACITY_EXHAUSTED'
    CONFLICT = 'CONFLICT'
    CONSENT_REVOKED = 'CONSENT_REVOKED'
    DEADLINE_EXCEEDED = 'DEADLINE_EXCEEDED'
    DEPENDENCY_UNAVAILABLE = 'DEPENDENCY_UNAVAILABLE'
    EXPIRED = 'EXPIRED'
    FORBIDDEN = 'FORBIDDEN'
    IDEMPOTENCY_CONFLICT = 'IDEMPOTENCY_CONFLICT'
    INCOMPATIBLE = 'INCOMPATIBLE'
    INCOMPATIBLE_VERSION = 'INCOMPATIBLE_VERSION'
    INTERNAL_ERROR = 'INTERNAL_ERROR'
    INVALID_ARGUMENT = 'INVALID_ARGUMENT'
    INVALID_CONTENT = 'INVALID_CONTENT'
    INVALID_INPUT = 'INVALID_INPUT'
    INVALID_TOKEN = 'INVALID_TOKEN'
    MFA_REQUIRED = 'MFA_REQUIRED'
    NOT_FOUND = 'NOT_FOUND'
    NOT_READY = 'NOT_READY'
    OUTCOME_UNKNOWN = 'OUTCOME_UNKNOWN'
    POLICY_DENIED = 'POLICY_DENIED'
    POLICY_UNRESOLVED = 'POLICY_UNRESOLVED'
    QUOTA_EXCEEDED = 'QUOTA_EXCEEDED'
    RATE_LIMITED = 'RATE_LIMITED'
    SNAPSHOT_EXPIRED = 'SNAPSHOT_EXPIRED'
    SOURCE_INELIGIBLE = 'SOURCE_INELIGIBLE'
    STALE_REVISION = 'STALE_REVISION'
    UNAUTHENTICATED = 'UNAUTHENTICATED'
    UNKNOWN_OUTCOME = 'UNKNOWN_OUTCOME'


class Details(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    fieldNames: list[Id]


class Error(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    code: Code
    requestId: Id
    retryable: bool
    messageKey: Id
    retryAfterSeconds: int | None = Field(None, ge=0)
    details: Details | None = None


class PaperRef(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paperId: Id
    versionId: Id
    eligibilityRevision: Revision


class ResultRef(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    resultId: Id
    revision: Revision
    contentHash: Hash
    mediaType: str = Field(..., min_length=1)


class Cursor(RootModel[str]):
    root: str = Field(..., min_length=1)


class PageRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    cursor: Cursor | None = None
    limit: int | None = Field(None, ge=1)


class NextCursor(RootModel[str]):
    root: str = Field(..., min_length=1)


class PageInfo(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    nextCursor: NextCursor | None
    snapshotRevision: Revision


class Ack(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    resourceId: Id
    revision: Revision
    requestId: Id


class Progress1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    mode: Literal['indeterminate']


class Progress2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    mode: Literal['determinate']
    current: int = Field(..., ge=0)
    total: int = Field(..., ge=1)


class Progress(RootModel[Progress1 | Progress2]):
    root: Progress1 | Progress2


class State(StrEnum):
    accepted = 'accepted'
    running = 'running'
    cancel_requested = 'cancel_requested'
    succeeded = 'succeeded'
    failed = 'failed'
    cancelled = 'cancelled'


class JobReceipt(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: Id
    revision: Revision
    seq: int = Field(..., ge=0)
    state: State
    requestId: Id
    acceptedAt: Time


class JobSnapshot(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: Id
    kind: Id
    state: State
    revision: Revision
    seq: int = Field(..., ge=0)
    ownerId: Id
    progress: Progress
    result: ResultRef | None
    error: Error | None
    acceptedAt: Time


class Status(StrEnum):
    available = 'available'
    degraded = 'degraded'
    unavailable = 'unavailable'
    unknown = 'unknown'


class OpsObservation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    observationId: Id
    capability: Id
    component: Id
    observedAt: Time
    revision: Revision
    status: Status
    evidenceRef: Id
    limitations: list[Id]


class OpsObservationPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[OpsObservation]
    page: PageInfo


class State5(StrEnum):
    open = 'open'
    investigating = 'investigating'
    recovering = 'recovering'
    resolved = 'resolved'


class OpsIncident(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    incidentId: Id
    revision: Revision
    capabilities: list[Id]
    correlationIds: list[Id]
    state: State5
    evidenceRefs: list[Id]


class OpsIncidentPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[OpsIncident]
    page: PageInfo


class LibraryFilter(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    filterId: Id
    operatorId: Id
    values: list[str | int | bool]


class LibraryQueryContext(BaseModel):
    """
    Canonical submitted query/refinement context shared by search, saved queries and history. Unknown or unsupported vocabulary IDs are rejected; no arbitrary query-engine syntax is accepted through filters.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    query: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    modeId: Id
    orderId: Id
    filters: list[LibraryFilter]
    vocabularyRevision: Revision
    policyRef: PolicyRef


class HostPaperReturnContext(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Literal['paper']
    paper: PaperRef
    anchorId: Id | None = None


class HostSearchReturnContext(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Literal['search']
    queryContext: LibraryQueryContext
    resultWindowId: Id
    resultPosition: int | None = Field(None, ge=0)


class HostRouteReturnContext(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Literal['route']
    routeId: Id


class HostReturnContext(
    RootModel[HostPaperReturnContext | HostSearchReturnContext | HostRouteReturnContext]
):
    root: HostPaperReturnContext | HostSearchReturnContext | HostRouteReturnContext


class HostNavigationItem(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    routeId: Id
    titleKey: Id
    path: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    capabilityId: Id
    available: bool
    reasonKey: Id | None = None


class HostNavigationResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    manifestRevision: Revision
    authorityRevision: Revision
    items: list[HostNavigationItem]
    resolvedRouteId: Id
    returnContext: HostReturnContext | None = None
    clearPriorOwnerState: bool


class AccessSecret(RootModel[str]):
    root: str = Field(
        ...,
        description='Sensitive proof/credential; never logged, reflected or placed in a URL.',
        min_length=1,
    )


class AccessEmail(RootModel[EmailStr]):
    root: EmailStr


class AuthenticationLevel(StrEnum):
    primary = 'primary'
    mfa = 'mfa'


class AccessPublicSession(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sessionId: Id
    accountId: Id
    authorityRevision: Revision
    verified: bool
    authenticationLevel: AuthenticationLevel
    expiresAt: Time | None = None


class AccessAnonymousSession(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['anonymous']
    requestId: Id


class AccessKnownSession(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['authenticated']
    session: AccessPublicSession


class AccessChallengeDelivery(BaseModel):
    """
    Existence-neutral public acknowledgement. It does not expose account existence, challenge secrets or recipient-specific delivery facts.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    requestId: Id
    acknowledgement: Literal['accepted']
    messageKey: Id


class AccessChallengeProof(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    challengeId: Id
    proof: AccessSecret
    flowBinding: Id


class AccessMfaContinuation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['mfa_required']
    challengeId: Id
    flowBinding: Id
    expiresAt: Time


class AccessLoginResult(RootModel[AccessKnownSession | AccessMfaContinuation]):
    root: AccessKnownSession | AccessMfaContinuation


class Provider(StrEnum):
    google = 'google'
    orcid = 'orcid'


class AccessProviderRedirect(BaseModel):
    """
    URL generated from configured provider and registered callback binding; never copied from a caller-controlled destination.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    flowId: Id
    provider: Provider
    authorizationUrl: AnyUrl
    expiresAt: Time


class AccessIdentityLink(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    identityLinkId: Id
    provider: Provider
    providerSubject: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    revision: Revision
    profileAvailable: bool


class AccessIdentityPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[AccessIdentityLink]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class ExternalIdentifier(RootModel[str]):
    root: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )


class AccessOrcidWork(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sourceId: Id
    title: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    externalIdentifiers: list[ExternalIdentifier]
    sourceUrl: AnyUrl | None = None


class Coverage(StrEnum):
    complete = 'complete'
    partial = 'partial'
    unavailable = 'unavailable'


class AccessOrcidProfile(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    identityLinkId: Id
    subject: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    revision: Revision
    provenance: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    displayName: str | None = Field(
        None,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    works: list[AccessOrcidWork]
    coverage: Coverage


class AccessMfaEnrollment(BaseModel):
    """
    Protected one-time enrollment delivery is separate from ordinary JSON/log output; no factor seed or recovery code is returned here.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    enrollmentId: Id
    deliveryReference: Id
    expiresAt: Time
    nextAction: Literal['confirm_factor']


class AccessEnrollmentSecret(RootModel[str]):
    root: str = Field(
        ...,
        description='Secret output permitted only by the protected single-use enrollment-material response; redact entirely from diagnostics and do not cache or persist in the client.',
        min_length=1,
    )


class AccessMfaMaterial(BaseModel):
    """
    Dedicated protected response only. provisioningUri encodes this enrollment's seed and account/issuer binding and may be rendered as a QR locally, without an external QR service. Recovery codes remain unusable before successful enrollment confirmation. The trusted HTTP adapter applies Cache-Control: no-store and excludes the response from logging, tracing, generic result caches and persisted client storage.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    enrollmentId: Id
    seed: AccessEnrollmentSecret
    provisioningUri: AccessEnrollmentSecret
    recoveryCodes: list[AccessEnrollmentSecret]
    expiresAt: Time


class AccessProfileValue1(RootModel[list[Id]]):
    root: list[Id]


class AccessProfileValue(RootModel[str | bool | AccessProfileValue1 | None]):
    root: str | bool | AccessProfileValue1 | None


class ValueKind(StrEnum):
    text = 'text'
    boolean = 'boolean'
    single_choice = 'single_choice'
    multi_choice = 'multi_choice'


class AccessProfileFieldDefinition(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    fieldId: Id
    labelKey: Id
    valueKind: ValueKind
    mutable: bool
    nullable: bool
    choiceIds: list[Id]
    policyRef: PolicyRef


class AccessProfileField(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    fieldId: Id
    value: AccessProfileValue | None


class AccessProfile(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: Id
    revision: Revision
    lifecycleRevision: Revision
    email: AccessEmail
    emailVerified: bool
    fieldVocabularyRevision: Revision
    definitions: list[AccessProfileFieldDefinition]
    fields: list[AccessProfileField]


class Decision(StrEnum):
    granted = 'granted'
    revoked = 'revoked'


class AccessConsentRecord(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    consentId: Id
    accountId: Id
    purposeId: Id
    decision: Decision
    revision: Revision
    effectiveAt: Time
    policyRef: PolicyRef


class AccessConsentPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[AccessConsentRecord]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class LifecycleAction(StrEnum):
    withdraw = 'withdraw'
    reactivate = 'reactivate'
    erase = 'erase'


class LifecycleScope(StrEnum):
    live_records = 'live_records'
    derived_artifacts = 'derived_artifacts'
    pending_work = 'pending_work'
    caches = 'caches'
    backups = 'backups'
    restore_enforcement = 'restore_enforcement'
    external_copies = 'external_copies'


class Action(StrEnum):
    withdraw = 'withdraw'
    erase = 'erase'


class AccessLifecyclePrepareInputHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    currentProof: AccessSecret
    action: Action
    expectedRevision: Revision
    policyRef: PolicyRef


class AccessLifecycleConfirmation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    confirmationRef: Id
    action: Action
    revision: Revision
    expiresAt: Time


class State6(StrEnum):
    accepted = 'accepted'
    running = 'running'
    complete = 'complete'
    blocked = 'blocked'
    failed = 'failed'


class Access(StrEnum):
    reactivation_pending = 'reactivation_pending'
    sign_in_required = 'sign_in_required'


class LifecycleReactivationResult(BaseModel):
    """
    Safe status after valid reactivation proof; never a full session or a promise that erased data was restored. A protected limited recovery binding, issued through trusted cookie transport, permits lifecycle.inspect for this request alone while normal account authority remains unavailable.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    lifecycleRequestId: Id
    revision: Revision
    state: State6
    access: Access
    policyRef: PolicyRef
    requestId: Id
    reasonKey: Id


class Disposition(StrEnum):
    erased = 'erased'
    retained_by_policy = 'retained_by_policy'
    revoked = 'revoked'
    not_applicable = 'not_applicable'
    pending = 'pending'
    blocked = 'blocked'


class LifecycleScopeDisposition(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    scope: LifecycleScope
    disposition: Disposition
    evidenceReference: Id | None = None
    reasonKey: Id


class State7(StrEnum):
    pending = 'pending'
    running = 'running'
    acknowledged = 'acknowledged'
    failed = 'failed'
    blocked = 'blocked'


class LifecycleParticipantDisposition(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    participantId: Id
    revision: Revision
    state: State7
    scopes: list[LifecycleScopeDisposition] = Field(..., max_length=7)
    observedAt: Time


class Revocation(StrEnum):
    not_required = 'not_required'
    pending = 'pending'
    effective = 'effective'


class State8(StrEnum):
    accepted = 'accepted'
    running = 'running'
    complete = 'complete'
    blocked = 'blocked'
    failed = 'failed'


class LifecycleRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    lifecycleRequestId: Id
    accountId: Id
    action: LifecycleAction
    revision: Revision
    policyRef: PolicyRef
    manifestRevision: Revision
    authorityRevision: Revision
    revocation: Revocation
    state: State8
    participants: list[LifecycleParticipantDisposition] = Field(..., max_length=13)
    completionEvidenceRef: Id | None = None


class SourceDisposition(StrEnum):
    available = 'available'
    source_only = 'source_only'
    canonicalized = 'canonicalized'
    withdrawn = 'withdrawn'
    unavailable = 'unavailable'
    restricted = 'restricted'


class LibrarySavedPaper(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    savedPaperId: Id
    accountId: Id
    revision: Revision
    savedPaper: PaperRef
    resolvedPaper: PaperRef | None = None
    savedTitle: str | None = Field(
        None,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    sourceDisposition: SourceDisposition
    reasonKey: Id


class LibraryPaperPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[LibrarySavedPaper]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class LibrarySavedSearch(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    savedSearchId: Id
    accountId: Id
    revision: Revision
    queryContext: LibraryQueryContext
    label: str | None = Field(
        None,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )


class LibrarySearchPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[LibrarySavedSearch]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class LibraryHistoryRecord(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    historyId: Id
    accountId: Id
    searchExecutionId: Id
    queryContext: LibraryQueryContext
    recordedAt: Time
    admissionSequence: int = Field(..., ge=0)
    completionSequence: int = Field(..., ge=0)
    clearBoundary: Revision


class LibraryHistoryPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[LibraryHistoryRecord]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef
    clearBoundary: Revision


class SettingsSearchDefaults(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    modeId: Id
    orderId: Id
    filters: list[LibraryFilter]
    vocabularyRevision: Revision


class SettingsAssistanceDefaults(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    actionId: Id
    languageId: Id
    presentationLevelId: Id
    vocabularyRevision: Revision


class Appearance(StrEnum):
    light = 'light'
    dark = 'dark'
    system = 'system'


class Onboarding(StrEnum):
    not_started = 'not_started'
    in_progress = 'in_progress'
    completed = 'completed'
    skipped = 'skipped'


class SettingsSnapshot(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    timeZone: str | None = Field(
        None,
        description='Explicit owner IANA timezone; null means not configured.',
        max_length=100,
        min_length=1,
    )
    accountId: Id
    settingsId: Id
    revision: Revision
    searchDefaults: SettingsSearchDefaults
    assistanceDefaults: SettingsAssistanceDefaults
    appearance: Appearance
    onboarding: Onboarding
    interestIds: list[Id]
    policyRef: PolicyRef


class Source(StrEnum):
    orcid = 'orcid'
    retained_manual_vocabulary = 'retained_manual_vocabulary'


class SettingsSuggestion(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    interestId: Id
    labelKey: Id
    source: Source
    sourceRevision: Revision
    reasonKey: Id


class SettingsSuggestionPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[SettingsSuggestion]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class SourceDisposition1(StrEnum):
    available = 'available'
    source_only = 'source_only'
    withdrawn = 'withdrawn'
    unavailable = 'unavailable'
    restricted = 'restricted'


class SettingsRecentPaper(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    lastActivityAt: Time
    activityReference: Id
    sourceDisposition: SourceDisposition1


class SettingsRecentPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[SettingsRecentPaper]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class Action7(StrEnum):
    delete_behavior = 'delete_behavior'
    reset_profile = 'reset_profile'


class SettingsResetConfirmation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    confirmationRef: Id
    action: Action7
    revision: Revision
    expiresAt: Time


class Disposition11(StrEnum):
    complete = 'complete'
    pending = 'pending'
    blocked = 'blocked'


class SettingsResetResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    resetId: Id
    ack: Ack
    inputBoundary: Revision
    consentRevision: Revision
    disposition: Disposition11
    remainingScopeReasonKey: Id | None = None


class Disposition12(StrEnum):
    pending = 'pending'
    blocked = 'blocked'
    complete = 'complete'


class SettingsResetSummary(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    resetId: Id
    action: Action7
    acceptedAt: Time
    acceptedSettingsRevision: Revision
    inputBoundary: Revision
    policyRef: PolicyRef
    manifestRevision: Revision
    statusRevision: Revision
    observedAt: Time
    disposition: Disposition12
    reasonKey: Id


class SettingsResetScopeStatus(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    participantId: Id
    scopeId: Id
    manifestRevision: Revision
    workGeneration: Revision
    disposition: Disposition12
    reasonKey: Id
    evidenceRef: Id | None
    updatedAt: Time


class SettingsResetStatus(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    reset: SettingsResetSummary
    scopes: list[SettingsResetScopeStatus] = Field(..., max_length=32, min_length=1)


class SettingsResetPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[SettingsResetSummary] = Field(..., max_length=50)
    page: PageInfo
    appliedLimit: int = Field(..., ge=1, le=50)
    policyRef: PolicyRef


class OperationOwner(StrEnum):
    AccountAccess = 'AccountAccess'
    CorpusContent = 'CorpusContent'
    Discovery = 'Discovery'
    Library = 'Library'
    PaperAssistance = 'PaperAssistance'
    ResearchWorkspace = 'ResearchWorkspace'
    Personalization = 'Personalization'
    TopicsDigests = 'TopicsDigests'
    ApprovedExport = 'ApprovedExport'
    UsageEntitlements = 'UsageEntitlements'
    ServiceOperations = 'ServiceOperations'
    PlatformControl = 'PlatformControl'
    WebWorkspace = 'WebWorkspace'


class UsageOperation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    operationOwner: OperationOwner
    operationId: Id
    inputRevision: Revision


class UsageQuantity(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    metricId: Id
    quantity: int = Field(..., ge=0)


class UsageKnownMeasure(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['known']
    metricId: Id
    allocated: int = Field(..., ge=0)
    used: int = Field(..., ge=0)
    reserved: int = Field(..., ge=0)
    remaining: int = Field(..., ge=0)
    periodId: Id
    periodStart: Time
    periodEnd: Time
    policyRef: PolicyRef


class UsageUnknownMeasure(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['unknown']
    metricId: Id
    reasonKey: Id


class UsageMeasure(RootModel[UsageKnownMeasure | UsageUnknownMeasure]):
    root: UsageKnownMeasure | UsageUnknownMeasure


class UsageMeasurePage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[UsageMeasure]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class Source3(StrEnum):
    mock = 'mock'
    administrative_assignment = 'administrative_assignment'


class UsagePlanPresentation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: Id
    tierId: Id
    labelKey: Id
    source: Source3
    revision: Revision
    policyRef: PolicyRef
    paymentOccurred: Literal[False]


class AssignmentSource(StrEnum):
    mock = 'mock'
    administrative_assignment = 'administrative_assignment'


class Disposition14(StrEnum):
    active = 'active'
    revoked = 'revoked'


class UsageEntitlement(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    entitlementId: Id
    accountId: Id
    tierId: Id
    revision: Revision
    assignmentSource: AssignmentSource
    policyRef: PolicyRef
    effectiveAt: Time
    disposition: Disposition14


class Disposition15(StrEnum):
    reserved = 'reserved'
    committed = 'committed'
    released = 'released'
    refunded = 'refunded'
    unknown = 'unknown'


class UsageRecord(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    usageRecordId: Id
    accountId: Id
    operation: UsageOperation
    revision: Revision
    periodId: Id
    policyRef: PolicyRef
    disposition: Disposition15
    quantities: list[UsageQuantity]
    effectReference: Id | None = None
    reasonKey: Id


class UsageRecordsPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[UsageRecord]
    page: PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: PolicyRef


class CanonicalDisposition(StrEnum):
    same = 'same'
    alias = 'alias'
    withdrawn = 'withdrawn'
    unavailable = 'unavailable'
    restricted = 'restricted'


class SourceUrl(RootModel[AnyUrl]):
    root: AnyUrl


class CorpusIdentity(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    requestedIdentifier: str = Field(..., min_length=1)
    canonicalDisposition: CanonicalDisposition
    metadataRevision: Revision
    title: str = Field(..., min_length=1)
    sourceUrls: list[SourceUrl]
    policy: PolicyRef


class CorpusSection(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sectionId: Id
    heading: str
    text: str
    anchor: Id


class CorpusAssetRef(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    assetId: Id
    mediaType: str = Field(..., min_length=1)
    contentHash: Hash
    altText: str
    sectionId: Id | None = None


class Coverage1(StrEnum):
    complete = 'complete'
    partial = 'partial'


class Limitation(RootModel[str]):
    root: str = Field(..., min_length=1)


class CorpusContent(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    contentRevision: Revision
    contentHash: Hash
    sections: list[CorpusSection]
    assets: list[CorpusAssetRef]
    sourceUrls: list[SourceUrl]
    coverage: Coverage1
    limitations: list[Limitation]
    policy: PolicyRef


class CorpusContentRead1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    availability: Literal['ready']
    content: CorpusContent


class Availability(StrEnum):
    absent = 'absent'
    building = 'building'
    unsupported = 'unsupported'
    failed = 'failed'
    withdrawn = 'withdrawn'
    restricted = 'restricted'


class CorpusContentRead2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    availability: Availability
    paper: PaperRef
    reasonKey: str = Field(..., min_length=1)
    retryable: bool


class CorpusContentRead(RootModel[CorpusContentRead1 | CorpusContentRead2]):
    root: CorpusContentRead1 | CorpusContentRead2


class CorpusAsset(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    asset: CorpusAssetRef
    readHandle: Id
    policy: PolicyRef


class Stage(StrEnum):
    source = 'source'
    control = 'control'
    content = 'content'
    projection = 'projection'
    publication = 'publication'


class State9(StrEnum):
    pending = 'pending'
    committed = 'committed'
    failed = 'failed'
    unknown = 'unknown'


class CorpusEffectDisposition(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: Id
    stage: Stage
    state: State9
    evidenceHash: Hash | None
    error: Error | None


class CommittedWatermark(RootModel[str]):
    root: str = Field(..., min_length=1)


class CorpusRun(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    runId: Id
    revision: Revision
    job: JobSnapshot
    inputManifestHash: Hash
    effects: list[CorpusEffectDisposition]
    committedWatermark: CommittedWatermark | None
    publicationGeneration: Id | None


class CorpusPublication(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    generationId: Id
    publicationRevision: Revision
    manifestHash: Hash
    compatibilityRevision: Revision
    eligibilityRevision: Revision
    publishedAt: Time
    complete: Literal[True]


class Author(RootModel[str]):
    root: str = Field(..., min_length=1)


class Availability1(StrEnum):
    readable = 'readable'
    source_only = 'source-only'
    building = 'building'
    unavailable = 'unavailable'
    restricted = 'restricted'


class SearchHit(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    title: str = Field(..., min_length=1)
    authors: list[Author]
    publishedAt: Time | None
    snippet: str
    sourceUrl: AnyUrl
    availability: Availability1
    matchExplanation: str


class Outcome(StrEnum):
    complete = 'complete'
    partial = 'partial'
    degraded = 'degraded'


class SearchResponse(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    executionId: Id
    query: LibraryQueryContext
    hits: list[SearchHit]
    page: PageInfo
    publication: CorpusPublication
    outcome: Outcome
    effectiveModeId: Id
    limitations: list[Limitation]


class SearchHistoryCheckpoint(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    ownerId: Id
    admissionSequence: int = Field(..., ge=0)
    revision: Revision


class Title(RootModel[str]):
    root: str = Field(..., min_length=1)


class Disposition16(StrEnum):
    eligible = 'eligible'
    unknown = 'unknown'
    incomplete = 'incomplete'
    restricted = 'restricted'
    withdrawn = 'withdrawn'


class CitationNode(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    nodeId: Id
    paper: PaperRef | None
    title: Title | None
    sourceUrl: SourceUrl | None
    disposition: Disposition16


class CitationEdge(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    fromNodeId: Id
    toNodeId: Id
    sourceUrl: AnyUrl
    observedAt: Time


class Freshness(StrEnum):
    current = 'current'
    stale = 'stale'
    unknown = 'unknown'


class CitationResponse(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    snapshotId: Id
    revision: Revision
    root: PaperRef
    nodes: list[CitationNode]
    edges: list[CitationEdge]
    freshness: Freshness
    coverage: Coverage1
    limitations: list[Limitation]
    page: PageInfo


class Operation(StrEnum):
    summary = 'summary'
    translation = 'translation'


class AssistanceOption(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    optionId: Id
    operation: Operation
    sourceLanguageId: Id
    targetLanguageId: Id
    presentationLevelId: Id
    labelKey: str = Field(..., min_length=1)


class AssistanceOptions(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    revision: Revision
    options: list[AssistanceOption]
    policy: PolicyRef
    limitations: list[Limitation]


class Coverage3(StrEnum):
    complete = 'complete'
    partial = 'partial'
    abstained = 'abstained'


class AssistanceResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    result: ResultRef
    ownerId: Id
    jobId: Id
    paper: PaperRef
    sourceContentHash: Hash
    operation: Operation
    optionId: Id
    glossaryRevision: Revision
    sections: list[CorpusSection]
    coverage: Coverage3
    limitations: list[Limitation]
    methodRevision: Revision


class AssistanceResultRead1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    availability: Literal['ready']
    prepared: AssistanceResult


class Availability2(StrEnum):
    pending = 'pending'
    failed = 'failed'
    expired = 'expired'
    withdrawn = 'withdrawn'
    restricted = 'restricted'


class AssistanceResultRead2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    availability: Availability2
    jobId: Id
    reasonKey: str = Field(..., min_length=1)


class AssistanceResultRead(RootModel[AssistanceResultRead1 | AssistanceResultRead2]):
    root: AssistanceResultRead1 | AssistanceResultRead2


class AssistanceGlossaryTerm(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    termId: Id
    source: str = Field(..., min_length=1)
    preferred: str = Field(..., min_length=1)
    languageId: Id


class AssistanceGlossary(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    ownerId: Id
    revision: Revision
    normalizationPolicy: PolicyRef
    terms: list[AssistanceGlossaryTerm]


class WebReference(RootModel[AnyUrl]):
    root: AnyUrl


class ResearchScope(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    publicPapers: list[PaperRef]
    attachmentIds: list[Id]
    webReferences: list[WebReference]
    scopePolicy: PolicyRef


class Purpose(StrEnum):
    research = 'research'
    novelty = 'novelty'


class Lifecycle(StrEnum):
    active = 'active'
    deleting = 'deleting'
    deleted = 'deleted'


class ResearchContext(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    ownerId: Id
    revision: Revision
    purpose: Purpose
    lifecycle: Lifecycle


class ResearchSession(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sessionId: Id
    ownerId: Id
    revision: Revision
    scope: ResearchScope
    lifecycle: Lifecycle
    turnIds: list[Id]
    pendingJobIds: list[Id]
    deletionBoundary: Revision | None


class ResearchSessions(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sessions: list[ResearchSession]
    page: PageInfo


class State10(StrEnum):
    accepted = 'accepted'
    in_progress = 'in-progress'
    complete = 'complete'
    limited = 'limited'
    failed = 'failed'


class ResearchDeletion(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    requestId: Id
    revision: Revision
    state: State10
    tombstoneBoundary: Revision
    policy: PolicyRef
    remainingJobIds: list[Id]
    limitations: list[Limitation]


class ResearchUploadPermit(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    uploadId: Id
    ownerId: Id
    contextId: Id
    contentHash: Hash
    writeHandle: Id
    expiresAt: Time
    policy: PolicyRef


class State11(StrEnum):
    processing = 'processing'
    ready = 'ready'
    partial = 'partial'
    unsupported = 'unsupported'
    failed = 'failed'
    deleted = 'deleted'


class ResearchAttachment(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    attachmentId: Id
    ownerId: Id
    contextId: Id
    revision: Revision
    contentHash: Hash
    state: State11
    assetIds: list[Id]
    limitations: list[Limitation]


class ResearchPrivateAsset(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    attachmentId: Id
    contextId: Id
    assetId: Id
    mediaType: str = Field(..., min_length=1)
    contentHash: Hash
    readHandle: Id
    policy: PolicyRef


class DraftRef(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    draftId: Id
    revision: Revision
    contentHash: Hash


class Kind(StrEnum):
    research_question = 'research-question'
    novelty_topic = 'novelty-topic'
    novelty_manuscript = 'novelty-manuscript'
    novelty_discussion = 'novelty-discussion'


class DraftRevision(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    draft: DraftRef
    ownerId: Id
    contextId: Id
    kind: Kind
    parentRevision: Revision | None
    text: str
    acknowledgedAt: Time
    policy: PolicyRef


class DraftWriteResult1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    outcome: Literal['saved']
    acknowledged: DraftRevision


class DraftWriteResult2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    outcome: Literal['conflict']
    current: DraftRevision
    proposedText: str
    proposedBaseRevision: Revision | None


class DraftWriteResult(RootModel[DraftWriteResult1 | DraftWriteResult2]):
    root: DraftWriteResult1 | DraftWriteResult2


class DraftRecovery1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['recoverable']
    acknowledged: DraftRevision


class State12(StrEnum):
    missing = 'missing'
    consumed = 'consumed'
    discarded = 'discarded'
    expired = 'expired'
    deleted = 'deleted'


class DraftRecovery2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: State12
    draftId: Id
    reasonKey: str = Field(..., min_length=1)


class DraftRecovery(RootModel[DraftRecovery1 | DraftRecovery2]):
    root: DraftRecovery1 | DraftRecovery2


class InputMode(StrEnum):
    question = 'question'
    compare = 'compare'
    quote = 'quote'


class ResearchArtifactRef(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    artifactId: Id
    revision: Revision
    contentHash: Hash


class SourceKind(StrEnum):
    public_paper = 'public-paper'
    private_attachment = 'private-attachment'
    retrieved_web = 'retrieved-web'
    unread_reference = 'unread-reference'


class ReadCoverage(StrEnum):
    read = 'read'
    partial = 'partial'
    not_read = 'not-read'


class Quote(RootModel[str]):
    root: str = Field(..., min_length=1)


class Stance(StrEnum):
    supports = 'supports'
    contradicts = 'contradicts'
    uncertain = 'uncertain'


class ResearchEvidence(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    evidenceId: Id
    sourceKind: SourceKind
    sourceId: Id
    sourceVersion: Revision
    sourceContentHash: Hash | None
    location: str = Field(..., min_length=1)
    readCoverage: ReadCoverage
    quote: Quote | None
    claim: str = Field(..., min_length=1)
    stance: Stance
    sourceUrl: SourceUrl | None


class ResearchAssessment(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    criterionId: Id
    label: str = Field(..., min_length=1)
    score: float | None = None
    scaleMinimum: float | None = None
    scaleMaximum: float | None = None
    evidenceIds: list[Id]
    limitations: list[Limitation]


class Kind7(StrEnum):
    research_answer = 'research-answer'
    novelty_result = 'novelty-result'
    novelty_discussion = 'novelty-discussion'


class Availability3(StrEnum):
    pending = 'pending'
    failed = 'failed'
    expired = 'expired'
    deleted = 'deleted'
    restricted = 'restricted'


class ResearchArtifactResponse2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    availability: Availability3
    artifactId: Id
    reasonKey: str = Field(..., min_length=1)


class DigestSchedule(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    cadenceId: Id
    timeZone: str = Field(..., min_length=1)
    windowPolicy: PolicyRef


class DigestSubscription(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    subscriptionId: Id
    ownerId: Id
    topic: str = Field(..., min_length=1)
    revision: Revision
    enabled: bool
    schedule: DigestSchedule
    unsubscribeBoundary: Revision | None


class DigestSubscriptions(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    subscriptions: list[DigestSubscription]
    page: PageInfo


class DigestWindow(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    startInclusive: Time
    endExclusive: Time
    timeZone: str = Field(..., min_length=1)
    windowPolicy: PolicyRef


class State13(StrEnum):
    prepared = 'prepared'
    no_content = 'no-content'
    queued = 'queued'
    sending = 'sending'
    sent = 'sent'
    failed = 'failed'
    unknown = 'unknown'
    suppressed = 'suppressed'


class DigestDelivery(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    deliveryId: Id
    ownerId: Id
    subscriptionId: Id
    revision: Revision
    window: DigestWindow
    papers: list[PaperRef]
    state: State13
    effectKey: Id
    remoteReference: Id | None
    limitations: list[Limitation]


class DigestUnsubscribeResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    outcome: Literal['acknowledged']
    requestId: Id


class State14(StrEnum):
    connected = 'connected'
    disconnected = 'disconnected'
    revoked = 'revoked'
    unavailable = 'unavailable'


class ExportConnection(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connectionId: Id
    ownerId: Id
    revision: Revision
    provider: Literal['notion']
    state: State14
    destinationScopeIds: list[Id]
    limitations: list[Limitation]


class ExportDestination(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connectionId: Id
    workspaceId: Id
    parentPageId: Id
    formatRevision: Revision


class ExportDestinations(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connectionId: Id
    connectionRevision: Revision
    destinations: list[ExportDestination]


class ExportPreview(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    previewId: Id
    ownerId: Id
    revision: Revision
    source: ResearchArtifactRef
    sourceEligibilityRevision: Revision
    connectionRevision: Revision
    destination: ExportDestination
    renderedText: str
    renderedContentHash: Hash
    bindingHash: Hash
    renderPolicy: PolicyRef


class State15(StrEnum):
    approved = 'approved'
    invalidated = 'invalidated'
    consumed = 'consumed'
    cancelled = 'cancelled'
    expired = 'expired'


class ExportApproval(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    approvalId: Id
    ownerId: Id
    previewId: Id
    previewRevision: Revision
    bindingHash: Hash
    approvedAt: Time
    expiresAt: Time | None
    state: State15
    policy: PolicyRef


class State16(StrEnum):
    accepted = 'accepted'
    executing = 'executing'
    succeeded = 'succeeded'
    failed = 'failed'
    unknown = 'unknown'
    cancelled = 'cancelled'
    invalidated = 'invalidated'


class RemoteUrl(RootModel[AnyUrl]):
    root: AnyUrl


class ExportEffect(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: Id
    approvalId: Id
    ownerId: Id
    revision: Revision
    bindingHash: Hash
    state: State16
    remoteReference: Id | None
    remoteUrl: RemoteUrl | None
    reconciliationEvidenceHash: Hash | None
    limitations: list[Limitation]


class SessionBootstrap(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    signedIn: bool
    accountId: Id | None
    authorityRevision: Revision | None
    csrfToken: str = Field(..., min_length=1)


class State17(StrEnum):
    available = 'available'
    degraded = 'degraded'
    unavailable = 'unavailable'
    policy_pending = 'policy_pending'


class Capability(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    id: Id
    state: State17
    modeIds: list[Id]
    languageIds: list[Id]
    levelIds: list[Id]
    formatIds: list[Id]
    policy: PolicyRef


class CapabilityCatalog(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    revision: Revision
    capabilities: list[Capability]


class UploadAck(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    uploadId: Id
    contentHash: Hash
    receivedBytes: int = Field(..., ge=0)
    revision: Revision


class HostNavigationInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    routeId: Id
    returnContext: HostReturnContext | None = None


class AccessSessionInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )


class AccessRegisterInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    email: AccessEmail
    password: AccessSecret
    displayName: str | None = Field(
        None,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    policyRef: PolicyRef


class AccessEmailRequestInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    email: AccessEmail
    policyRef: PolicyRef


class AccessVerifyEmailInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    verification: AccessChallengeProof


class AccessLoginInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    email: AccessEmail
    password: AccessSecret
    policyRef: PolicyRef


class AccessLogoutInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )


class AccessPasswordResetInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    verification: AccessChallengeProof
    newPassword: AccessSecret


class AccessPasswordChangeInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    currentPassword: AccessSecret
    newPassword: AccessSecret


class AccessEmailChangeInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    currentProof: AccessSecret
    newEmail: AccessEmail
    policyRef: PolicyRef


class AccessEmailChangeCompleteInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    verification: AccessChallengeProof


class Intent(StrEnum):
    sign_in = 'sign_in'
    link = 'link'


class AccessBeginIdentityInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    provider: Provider
    intent: Intent
    returnRouteId: Id
    policyRef: PolicyRef


class AccessIdentityListInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class AccessUnlinkIdentityInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    identityLinkId: Id
    expectedRevision: Revision


class AccessOrcidProfileInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    identityLinkId: Id


class AccessMfaEnrollmentInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    currentProof: AccessSecret
    policyRef: PolicyRef


class AccessMfaMaterialInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    enrollmentId: Id
    deliveryReference: Id
    currentProof: AccessSecret


class AccessMfaConfirmInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    enrollmentId: Id
    verification: AccessChallengeProof


class FactorKind(StrEnum):
    totp = 'totp'
    recovery_proof = 'recovery_proof'


class AccessMfaVerifyInputHttp(BaseModel):
    """
    Pre-authentication request: context may contain an anonymous principal. The trusted transport separately validates the protected primary-authentication continuation cookie, binds it to verification.challengeId/flowBinding and the server-owned primary-authentication record, and passes only a verified invocation. The factor proof is untrusted until checked; neither a full session nor a caller-claimed account is required.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    verification: AccessChallengeProof
    factorKind: FactorKind


class AccessMfaRecoveryInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    verification: AccessChallengeProof
    policyRef: PolicyRef


class AccessProfileInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )


class AccessProfileUpdateInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    fieldVocabularyRevision: Revision
    changes: list[AccessProfileField]
    policyRef: PolicyRef
    expectedRevision: Revision


class AccessConsentListInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class AccessConsentUpdateInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    purposeId: Id
    decision: Decision
    policyRef: PolicyRef
    expectedRevision: Revision


class Action9(StrEnum):
    withdraw = 'withdraw'
    erase = 'erase'


class LifecycleRequestInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: Action9
    policyRef: PolicyRef
    confirmationRef: Id


class LifecycleReactivationInputHttp(BaseModel):
    """
    Public pre-authentication envelope; no caller account ID or active session is required. Account and withdrawn lifecycle identity are resolved exclusively from the verified purpose-bound reactivation proof. Trusted transport context may remain anonymous until this limited recovery authority is verified.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    verification: AccessChallengeProof
    policyRef: PolicyRef
    confirmationRef: Id


class LifecycleStatusInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    lifecycleRequestId: Id


class LibrarySavePaperInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    policyRef: PolicyRef


class LibrarySavedPaperInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    savedPaperId: Id


class LibraryPaperListInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class LibrarySaveSearchInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    queryContext: LibraryQueryContext
    label: str | None = Field(
        None,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )


class LibrarySavedSearchInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    savedSearchId: Id


class LibrarySearchListInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class LibraryHistoryListInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class LibraryHistoryInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    historyId: Id


class LibraryClearHistoryInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    policyRef: PolicyRef
    expectedRevision: Revision


class SettingsReadInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )


class SettingsUpdateInputHttp1(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    timeZone: str = Field(
        ...,
        description='Validated against the installed timezone database.',
        max_length=100,
        min_length=1,
    )
    searchDefaults: SettingsSearchDefaults | None = None
    assistanceDefaults: SettingsAssistanceDefaults | None = None
    appearance: Appearance | None = None
    policyRef: PolicyRef
    expectedRevision: Revision


class SettingsUpdateInputHttp2(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    timeZone: str | None = Field(
        None,
        description='Validated against the installed timezone database.',
        max_length=100,
        min_length=1,
    )
    searchDefaults: SettingsSearchDefaults
    assistanceDefaults: SettingsAssistanceDefaults | None = None
    appearance: Appearance | None = None
    policyRef: PolicyRef
    expectedRevision: Revision


class SettingsUpdateInputHttp3(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    timeZone: str | None = Field(
        None,
        description='Validated against the installed timezone database.',
        max_length=100,
        min_length=1,
    )
    searchDefaults: SettingsSearchDefaults | None = None
    assistanceDefaults: SettingsAssistanceDefaults
    appearance: Appearance | None = None
    policyRef: PolicyRef
    expectedRevision: Revision


class SettingsUpdateInputHttp4(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    timeZone: str | None = Field(
        None,
        description='Validated against the installed timezone database.',
        max_length=100,
        min_length=1,
    )
    searchDefaults: SettingsSearchDefaults | None = None
    assistanceDefaults: SettingsAssistanceDefaults | None = None
    appearance: Appearance
    policyRef: PolicyRef
    expectedRevision: Revision


class SettingsUpdateInputHttp(
    RootModel[
        SettingsUpdateInputHttp1
        | SettingsUpdateInputHttp2
        | SettingsUpdateInputHttp3
        | SettingsUpdateInputHttp4
    ]
):
    root: (
        SettingsUpdateInputHttp1
        | SettingsUpdateInputHttp2
        | SettingsUpdateInputHttp3
        | SettingsUpdateInputHttp4
    ) = Field(
        ...,
        description='Internal envelope; context is derived by the trusted boundary, never accepted from a public body.',
    )


class Action10(StrEnum):
    save_interests = 'save_interests'
    complete = 'complete'
    skip = 'skip'


class SettingsOnboardingInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: Action10
    interestIds: list[Id]
    policyRef: PolicyRef
    expectedRevision: Revision


class SettingsSuggestionInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest
    identityLinkId: Id | None = None


class SettingsRecentInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class Action11(StrEnum):
    delete_behavior = 'delete_behavior'
    reset_profile = 'reset_profile'


class SettingsResetPrepareInputHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    action: Action11
    currentProof: AccessSecret
    policyRef: PolicyRef
    expectedRevision: Revision


class SettingsResetInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    action: Action11
    policyRef: PolicyRef
    confirmationRef: Id
    expectedRevision: Revision


class UsageInspectInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class UsagePlanInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )


class UsageGrantInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: Id
    tierId: Id
    policyRef: PolicyRef
    reasonKey: Id
    expectedRevision: Revision


class UsageRevokeInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: Id
    entitlementId: Id
    policyRef: PolicyRef
    reasonKey: Id
    expectedRevision: Revision


class UsageRecordsInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class CorpusResolveHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    identifier: str = Field(..., min_length=1)
    versionLabel: str | None = Field(None, min_length=1)


class Purpose3(StrEnum):
    metadata = 'metadata'
    read = 'read'
    assistance = 'assistance'
    research = 'research'
    citation = 'citation'
    saved_reference = 'saved-reference'


class CorpusReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    purpose: Purpose3


class CorpusAssetReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    contentRevision: Revision
    assetId: Id


class Operation5(StrEnum):
    ingest = 'ingest'
    incremental_refresh = 'incremental-refresh'
    rebuild = 'rebuild'
    reprocess = 'reprocess'


class CorpusRunRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    operation: Operation5
    sourceScopeIds: list[Id] = Field(..., min_length=1)
    authoritativeInputRevision: Revision
    inputManifestHash: Hash
    sourcePolicy: PolicyRef
    compatibilityRevision: Revision


class CorpusRunReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    runId: Id


class Disposition17(StrEnum):
    eligible = 'eligible'
    withdrawn = 'withdrawn'
    restricted = 'restricted'
    unavailable = 'unavailable'


class CorpusEligibilityChangeHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    disposition: Disposition17
    reasonKey: str = Field(..., min_length=1)
    sourceEvidenceHash: Hash
    policy: PolicyRef


class SearchRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    query: LibraryQueryContext
    page: PageRequest
    snapshotRevision: Revision | None = None


class Direction(StrEnum):
    cited = 'cited'
    citing = 'citing'
    both = 'both'


class CitationRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    direction: Direction
    page: PageRequest
    traversalPolicy: PolicyRef
    snapshotRevision: Revision | None = None


class AssistanceOptionsReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef


class Operation6(StrEnum):
    summary = 'summary'
    translation = 'translation'


class AssistanceRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    contentRevision: Revision
    contentHash: Hash
    operation: Operation6
    optionId: Id
    optionsRevision: Revision
    glossaryRevision: Revision
    processingPolicy: PolicyRef


class AssistanceJobReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: Id


class AssistanceResultRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: Id
    result: ResultRef | None = None


class AssistanceGlossaryReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )


class AssistanceGlossaryWriteHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    expectedRevision: Revision
    normalizationPolicy: PolicyRef
    terms: list[AssistanceGlossaryTerm]


class Purpose4(StrEnum):
    research = 'research'
    novelty = 'novelty'


class ResearchContextCreateHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    purpose: Purpose4
    policy: PolicyRef


class ResearchSessionCreateHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    title: str = Field(..., min_length=1)
    scope: ResearchScope


class ResearchSessionReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sessionId: Id


class ResearchSessionListHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class Scope(StrEnum):
    one_session = 'one-session'
    all_sessions = 'all-sessions'


class ResearchDeleteHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    scope: Scope
    sessionId: Id | None = None
    expectedRevision: Revision
    confirmed: Literal[True]
    policy: PolicyRef


class MediaType(StrEnum):
    application_pdf = 'application/pdf'
    text_plain = 'text/plain'


class ResearchAttachmentStartHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    fileName: str = Field(..., min_length=1)
    mediaType: MediaType
    byteLength: int = Field(..., ge=1)
    contentHash: Hash
    policy: PolicyRef


class ResearchAttachmentFinishHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    uploadId: Id
    contextId: Id
    contentHash: Hash


class ResearchAttachmentReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    attachmentId: Id


class ResearchPrivateAssetReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    attachmentId: Id
    assetId: Id


class Kind8(StrEnum):
    research_question = 'research-question'
    novelty_topic = 'novelty-topic'
    novelty_manuscript = 'novelty-manuscript'
    novelty_discussion = 'novelty-discussion'


class DraftWriteHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    draftId: Id
    kind: Kind8
    baseRevision: Revision | None
    text: str
    policy: PolicyRef


class DraftReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    draftId: Id


class DraftDiscardHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contextId: Id
    draft: DraftRef
    confirmed: Literal[True]
    policy: PolicyRef


class Mode(StrEnum):
    question = 'question'
    compare = 'compare'
    quote = 'quote'


class ResearchTurnRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sessionId: Id
    scope: ResearchScope
    mode: Mode
    text: str = Field(..., min_length=1)
    submittedDraft: DraftRef | None = None
    policy: PolicyRef


class ResearchTurnReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sessionId: Id
    turnId: Id


class InputMode2(StrEnum):
    topic = 'topic'
    manuscript = 'manuscript'


class ResearchNoveltyRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    scope: ResearchScope
    inputMode: InputMode2
    text: str = Field(..., min_length=1)
    submittedDraft: DraftRef | None = None
    policy: PolicyRef


class ResearchNoveltyDiscussionHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    source: ResearchArtifactRef
    text: str = Field(..., min_length=1)
    submittedDraft: DraftRef | None = None
    policy: PolicyRef


class Kind9(StrEnum):
    research_turn = 'research-turn'
    novelty_analysis = 'novelty-analysis'
    novelty_discussion = 'novelty-discussion'


class ResearchJobReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Kind9
    jobId: Id
    contextId: Id


class ResearchArtifactReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    artifact: ResearchArtifactRef


class DigestSubscriptionWriteHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    topic: str = Field(..., min_length=1)
    enabled: bool
    schedule: DigestSchedule
    expectedRevision: Revision | None
    policy: PolicyRef


class DigestSubscriptionsReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest


class DigestSubscriptionReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    subscriptionId: Id


class DigestDeliveryReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    deliveryId: Id


class DigestUnsubscribeHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    signedToken: str = Field(..., min_length=1)
    confirmed: Literal[True]


class ExportConnectionConfigureHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    token: str = Field(..., min_length=1)
    expectedRevision: Revision | None
    credentialPolicy: PolicyRef


class ExportConnectionReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connectionId: Id


class ExportPreviewRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    source: ResearchArtifactRef
    destination: ExportDestination
    renderPolicy: PolicyRef


class ExportApprovalRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    previewId: Id
    previewRevision: Revision
    bindingHash: Hash
    explicitApproval: Literal[True]


class ExportExecuteHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    approvalId: Id
    bindingHash: Hash


class ExportEffectReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: Id


class ExportCancelHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    approvalId: Id
    expectedRevision: Revision


class OpsQueryHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    page: PageRequest
    capability: Id | None = None


class OpsRecoveryRequestHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    incidentId: Id
    ownerComponent: Id
    operation: Id
    targetId: Id
    expectedRevision: Revision
    evidenceRefs: list[Id]
    policy: PolicyRef


class LibraryRemoveSavedPaperInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    savedPaperId: Id
    expectedRevision: Revision


class LibraryRemoveSavedSearchInputHttp(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    savedSearchId: Id
    expectedRevision: Revision


class UsageAssignmentReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: Id


class UsageAssignmentSnapshot(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: Id
    revision: Revision
    entitlement: UsageEntitlement | None


class AssistanceHistoryReadHttp(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: PaperRef
    page: PageRequest


class Operation7(Enum):
    summary = 'summary'
    translation = 'translation'


class State18(Enum):
    accepted = 'accepted'
    running = 'running'
    succeeded = 'succeeded'
    failed = 'failed'


class Availability4(Enum):
    ready = 'ready'
    pending = 'pending'
    failed = 'failed'
    expired = 'expired'
    withdrawn = 'withdrawn'
    restricted = 'restricted'


class AssistanceHistoryRow(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    jobId: Id
    paper: PaperRef
    contentRevision: Revision
    contentHash: Hash
    operation: Operation7
    optionId: Id
    optionsRevision: Revision
    glossaryRevision: Revision
    state: State18
    revision: Revision
    seq: int = Field(..., ge=0)
    createdAt: Time
    availability: Availability4
    result: ResultRef | None


class AssistanceHistoryPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[AssistanceHistoryRow]
    page: PageInfo


class AccessSessionStatus(
    RootModel[AccessAnonymousSession | AccessKnownSession | AccessMfaContinuation]
):
    root: AccessAnonymousSession | AccessKnownSession | AccessMfaContinuation


class LibraryClearHistoryResult(BaseModel):
    """
    Server-captured Discovery admission checkpoint, not a caller-selected cutoff. Facts admitted at/before the cutoff remain suppressed even if they finish after clear.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    ack: Ack
    checkpoint: SearchHistoryCheckpoint
    clearBoundary: Revision


class ResearchTurn(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    turnId: Id
    sessionId: Id
    ownerId: Id
    revision: Revision
    inputMode: InputMode
    committedText: str = Field(..., min_length=1)
    submittedDraft: DraftRef | None
    job: JobSnapshot
    artifact: ResearchArtifactRef | None


class ResearchOutput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    summary: str
    evidence: list[ResearchEvidence]
    coverage: Coverage3
    limitations: list[Limitation]
    methodRevision: Revision
    assessments: list[ResearchAssessment] | None = None


class ResearchArtifact(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    artifact: ResearchArtifactRef
    ownerId: Id
    contextId: Id
    operationId: Id
    kind: Kind7
    output: ResearchOutput
    currentEligibilityRevision: Revision
    mediaType: Literal['application/json']
    policy: PolicyRef


class ResearchArtifactResponse1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    availability: Literal['ready']
    prepared: ResearchArtifact


class ResearchArtifactResponse(
    RootModel[ResearchArtifactResponse1 | ResearchArtifactResponse2]
):
    root: ResearchArtifactResponse1 | ResearchArtifactResponse2


class PreparedJobRead(RootModel[AssistanceResultRead | ResearchArtifactResponse]):
    root: AssistanceResultRead | ResearchArtifactResponse
