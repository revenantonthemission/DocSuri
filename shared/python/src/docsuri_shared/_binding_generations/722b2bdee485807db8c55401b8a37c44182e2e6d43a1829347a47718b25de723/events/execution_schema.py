# DO NOT EDIT. Generated from the JSON Schema SSOT in shared/ by tools/generate.py.
# Change the schema and regenerate (§5-B); never hand-edit.

from __future__ import annotations

from typing import Any, Literal, Optional, Union
from pydantic import AnyUrl, BaseModel, ConfigDict, Field, RootModel
from enum import StrEnum
from ..dtos import workspace_schema


class Model(RootModel[Any]):
    root: Any


class Role(StrEnum):
    user = 'user'
    admin = 'admin'


class JsonValue(
    RootModel[
        Union[
            str | float | bool | None,
            list[Optional["JsonValue"]],
            dict[str, Optional["JsonValue"]],
        ]
    ]
):
    root: Union[
        str | float | bool | None,
        list[Optional["JsonValue"]],
        dict[str, Optional["JsonValue"]],
    ]


class Compatibility(StrEnum):
    compatible = 'compatible'
    incompatible = 'incompatible'
    unknown = 'unknown'


class Outcome(StrEnum):
    pass_ = 'pass'
    fail = 'fail'
    unknown = 'unknown'


class Outcome1(StrEnum):
    accepted = 'accepted'
    running = 'running'
    succeeded = 'succeeded'
    failed = 'failed'
    unknown = 'unknown'


class Outcome2(StrEnum):
    succeeded = 'succeeded'
    rejected = 'rejected'
    retry_later = 'retry_later'
    unknown = 'unknown'


class RetryAfterSeconds(RootModel[int]):
    root: int = Field(..., ge=0)


class Outcome3(StrEnum):
    progress = 'progress'
    succeeded = 'succeeded'
    failed = 'failed'
    cancelled = 'cancelled'
    unknown = 'unknown'


class Disposition(StrEnum):
    committed = 'committed'
    duplicate = 'duplicate'
    rejected = 'rejected'
    retry_later = 'retry_later'


class Provider(StrEnum):
    google = 'google'
    orcid = 'orcid'


class RequestedUse(StrEnum):
    metadata = 'metadata'
    read = 'read'
    model = 'model'
    redistribute = 'redistribute'


class Outcome4(StrEnum):
    complete = 'complete'
    partial = 'partial'
    rejected = 'rejected'


class Disposition1(StrEnum):
    accepted = 'accepted'
    rejected = 'rejected'
    unknown = 'unknown'


class Disposition2(StrEnum):
    committed = 'committed'
    rejected = 'rejected'
    unknown = 'unknown'


class DisplayName(RootModel[str]):
    root: str = Field(..., min_length=1)


class Orcid(RootModel[str]):
    root: str = Field(..., min_length=1)


class Affiliation(RootModel[str]):
    root: str = Field(..., min_length=1)


class Scope(StrEnum):
    papers = 'papers'
    permitted_web = 'permitted_web'


class Disposition3(StrEnum):
    committed = 'committed'
    definitely_not_committed = 'definitely_not_committed'
    unknown = 'unknown'


class Component(StrEnum):
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


class Owner(StrEnum):
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


class State(StrEnum):
    available = 'available'
    degraded = 'degraded'
    unavailable = 'unavailable'
    unknown = 'unknown'


class Intent(StrEnum):
    sign_in = 'sign_in'
    link = 'link'


class FactorKind(StrEnum):
    totp = 'totp'
    recovery_proof = 'recovery_proof'


class Decision(StrEnum):
    granted = 'granted'
    revoked = 'revoked'


class Decision1(StrEnum):
    allow = 'allow'
    deny = 'deny'


class Action(StrEnum):
    withdraw = 'withdraw'
    erase = 'erase'


class Decision2(StrEnum):
    allow = 'allow'
    deny = 'deny'
    requires_reconciliation = 'requires_reconciliation'


class Disposition4(StrEnum):
    recorded = 'recorded'
    duplicate = 'duplicate'
    suppressed_by_clear = 'suppressed_by_clear'
    suppressed_by_lifecycle = 'suppressed_by_lifecycle'


class Appearance(StrEnum):
    light = 'light'
    dark = 'dark'
    system = 'system'


class Action2(StrEnum):
    save_interests = 'save_interests'
    complete = 'complete'
    skip = 'skip'


class Disposition5(StrEnum):
    recorded = 'recorded'
    duplicate = 'duplicate'
    suppressed_by_consent = 'suppressed_by_consent'
    suppressed_by_reset = 'suppressed_by_reset'
    suppressed_by_lifecycle = 'suppressed_by_lifecycle'


class Disposition6(StrEnum):
    ready = 'ready'
    cold_start = 'cold_start'
    disabled = 'disabled'
    unavailable = 'unavailable'


class Action3(StrEnum):
    delete_behavior = 'delete_behavior'
    reset_profile = 'reset_profile'


class View(StrEnum):
    outstanding = 'outstanding'
    history = 'history'


class State1(StrEnum):
    open = 'open'
    accepted = 'accepted'
    closed = 'closed'


class Decision3(StrEnum):
    commit = 'commit'
    release = 'release'
    refund = 'refund'


class Purpose(StrEnum):
    metadata = 'metadata'
    read = 'read'
    assistance = 'assistance'
    research = 'research'
    citation = 'citation'
    saved_reference = 'saved-reference'


class Operation(StrEnum):
    ingest = 'ingest'
    incremental_refresh = 'incremental-refresh'
    rebuild = 'rebuild'
    reprocess = 'reprocess'


class Disposition7(StrEnum):
    eligible = 'eligible'
    withdrawn = 'withdrawn'
    restricted = 'restricted'
    unavailable = 'unavailable'


class Disposition8(StrEnum):
    eligible = 'eligible'
    withdrawn = 'withdrawn'
    restricted = 'restricted'
    unavailable = 'unavailable'
    canonical_alias = 'canonical-alias'


class Disposition9(StrEnum):
    recorded = 'recorded'
    duplicate = 'duplicate'
    suppressed_by_clear = 'suppressed-by-clear'
    suppressed_by_lifecycle = 'suppressed-by-lifecycle'


class Direction(StrEnum):
    cited = 'cited'
    citing = 'citing'
    both = 'both'


class Operation1(StrEnum):
    summary = 'summary'
    translation = 'translation'


class Purpose1(StrEnum):
    research = 'research'
    novelty = 'novelty'


class Scope1(StrEnum):
    one_session = 'one-session'
    all_sessions = 'all-sessions'


class MediaType(StrEnum):
    application_pdf = 'application/pdf'
    text_plain = 'text/plain'


class Kind(StrEnum):
    research_question = 'research-question'
    novelty_topic = 'novelty-topic'
    novelty_manuscript = 'novelty-manuscript'
    novelty_discussion = 'novelty-discussion'


class Mode(StrEnum):
    question = 'question'
    compare = 'compare'
    quote = 'quote'


class InputMode(StrEnum):
    topic = 'topic'
    manuscript = 'manuscript'


class Kind1(StrEnum):
    research_turn = 'research-turn'
    novelty_analysis = 'novelty-analysis'
    novelty_discussion = 'novelty-discussion'


class DigestUnsubscribe(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    signedToken: str = Field(..., min_length=1)
    confirmed: Literal[True]


class ProcessLiveness(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Literal['alive']


class Status(StrEnum):
    ready = 'ready'
    not_ready = 'not_ready'
    unknown = 'unknown'


class Principal1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Literal['anonymous']
    requestScope: workspace_schema.Id


class Principal2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Literal['account']
    accountId: workspace_schema.Id
    authorityRevision: workspace_schema.Revision
    roles: list[Role]
    mfa: bool


class Principal3(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    kind: Literal['operator']
    actorId: workspace_schema.Id
    authorityRef: workspace_schema.Id


class Principal(RootModel[Principal1 | Principal2 | Principal3]):
    root: Principal1 | Principal2 | Principal3


class CommandContext(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    requestId: workspace_schema.Id
    principal: Principal
    idempotencyKey: workspace_schema.Id | None = None
    expectedRevision: workspace_schema.Revision | None = None
    policyRevision: workspace_schema.PolicyRef | None = None


class OperatorEvidenceRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    targetId: workspace_schema.Id
    inputHash: workspace_schema.Hash
    requiredGeneration: workspace_schema.Revision


class Check(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    name: workspace_schema.Id
    outcome: Outcome
    evidenceRef: workspace_schema.Id


class OperatorEvidence(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    evidenceId: workspace_schema.Id
    targetId: workspace_schema.Id
    inputHash: workspace_schema.Hash
    generation: workspace_schema.Revision
    observedAt: workspace_schema.Time
    compatibility: Compatibility
    checks: list[Check]


class OperatorExecuteRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    operation: workspace_schema.Id
    targetId: workspace_schema.Id
    inputHash: workspace_schema.Hash
    evidenceId: workspace_schema.Id
    evidenceGeneration: workspace_schema.Revision
    authorityRef: workspace_schema.Id
    policy: workspace_schema.PolicyRef


class OperatorReceiptRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    operationId: workspace_schema.Id


class OperatorReceipt(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    operationId: workspace_schema.Id
    receiptId: workspace_schema.Id
    targetId: workspace_schema.Id
    inputHash: workspace_schema.Hash
    authorityRef: workspace_schema.Id
    evidenceId: workspace_schema.Id
    revision: workspace_schema.Revision
    outcome: Outcome1
    effectRefs: list[workspace_schema.Id]
    reconciliationEvidence: list[workspace_schema.Id]


class OpsQuery(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest
    capability: workspace_schema.Id | None = None


class OpsRecoveryRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    incidentId: workspace_schema.Id
    ownerComponent: workspace_schema.Id
    operation: workspace_schema.Id
    targetId: workspace_schema.Id
    expectedRevision: workspace_schema.Revision
    evidenceRefs: list[workspace_schema.Id]
    policy: workspace_schema.PolicyRef


class DispatchCommand(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    messageId: workspace_schema.Id
    contractVersion: Literal['2.0.0']
    ownerComponent: workspace_schema.Id
    operationId: workspace_schema.Id
    operationKind: workspace_schema.Id
    ownerId: workspace_schema.Id
    inputRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    authorityRevision: workspace_schema.Revision
    policy: workspace_schema.PolicyRef
    payloadRef: workspace_schema.Id
    acceptedAt: workspace_schema.Time
    attempt: int = Field(..., ge=1)


class DispatchAck(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    messageId: workspace_schema.Id
    operationId: workspace_schema.Id
    disposition: Disposition
    recordedRevision: workspace_schema.Revision


class ProviderIdentityExchange(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    provider: Provider
    authorizationCode: str = Field(..., min_length=1)
    redirectBindingId: workspace_schema.Id
    stateBindingId: workspace_schema.Id
    nonceBindingId: workspace_schema.Id | None


class ProviderIdentityResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    provider: Provider
    subject: workspace_schema.Id
    issuer: str = Field(..., min_length=1)
    credentialRef: workspace_schema.Id
    verifiedClaimsRevision: workspace_schema.Revision
    consentedScopeIds: list[workspace_schema.Id]


class ProviderSourceRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sourceId: workspace_schema.Id
    recordId: workspace_schema.Id
    version: workspace_schema.Revision
    requestedUse: RequestedUse
    permissionPolicy: workspace_schema.PolicyRef


class ProviderSourceResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: workspace_schema.PaperRef
    sourceId: workspace_schema.Id
    contentRef: workspace_schema.Id | None
    permissionDecisionRef: workspace_schema.Id
    observedAt: workspace_schema.Time


class ProviderCitationRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: workspace_schema.PaperRef
    page: workspace_schema.PageRequest


class ProviderCitationResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: workspace_schema.PaperRef
    references: list[workspace_schema.PaperRef]
    page: workspace_schema.PageInfo
    observedAt: workspace_schema.Time
    complete: bool


class ProviderModelRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    operationId: workspace_schema.Id
    modelProfile: workspace_schema.Id
    modelRevision: workspace_schema.Revision
    modeId: workspace_schema.Id
    inputRefs: list[workspace_schema.Id]
    inputHash: workspace_schema.Hash
    languageId: workspace_schema.Id
    outputSchemaId: workspace_schema.Id
    permissionPolicy: workspace_schema.PolicyRef


class ProviderModelResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    operationId: workspace_schema.Id
    result: workspace_schema.ResultRef
    modelRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    groundingEvidenceRefs: list[workspace_schema.Id]


class ProviderExtractionRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    ownerId: workspace_schema.Id
    attachmentId: workspace_schema.Id
    inputHash: workspace_schema.Hash
    mediaType: str = Field(..., min_length=1)
    contentRef: workspace_schema.Id
    policy: workspace_schema.PolicyRef


class ProviderExtractionResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    attachmentId: workspace_schema.Id
    inputHash: workspace_schema.Hash
    textRef: workspace_schema.Id | None
    outcome: Outcome4
    limitations: list[workspace_schema.Id]


class ProviderEmailRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: workspace_schema.Id
    recipientRef: workspace_schema.Id
    templateId: workspace_schema.Id
    templateRevision: workspace_schema.Revision
    variablesRef: workspace_schema.Id
    authorityRevision: workspace_schema.Revision
    policy: workspace_schema.PolicyRef


class ProviderEmailResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: workspace_schema.Id
    providerMessageId: workspace_schema.Id | None
    disposition: Disposition1


class ProviderNotionRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: workspace_schema.Id
    approvalId: workspace_schema.Id
    connectionId: workspace_schema.Id
    destinationId: workspace_schema.Id
    artifact: workspace_schema.ResultRef
    previewHash: workspace_schema.Hash


class ProviderNotionResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: workspace_schema.Id
    remotePageId: workspace_schema.Id | None
    disposition: Disposition2


class ProviderIdentityProfileRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    provider: Provider
    subject: workspace_schema.Id
    credentialRef: workspace_schema.Id
    consentRevision: workspace_schema.Revision


class ProviderIdentityProfileResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    provider: Provider
    subject: workspace_schema.Id
    profileRevision: workspace_schema.Revision
    displayName: DisplayName | None
    orcid: Orcid | None
    affiliations: list[Affiliation]
    observedAt: workspace_schema.Time


class ProviderSourceSearch(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sourceId: workspace_schema.Id
    query: str = Field(..., min_length=1)
    scope: Scope
    page: workspace_schema.PageRequest
    permissionPolicy: workspace_schema.PolicyRef


class Item(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sourceRecordId: workspace_schema.Id
    version: workspace_schema.Revision
    title: str = Field(..., min_length=1)
    url: AnyUrl
    snippet: str = Field(..., min_length=1)
    permissionDecisionRef: workspace_schema.Id
    observedAt: workspace_schema.Time


class ProviderSourceSearchResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    sourceId: workspace_schema.Id
    items: list[Item]
    page: workspace_schema.PageInfo
    complete: bool


class ProviderNotionInspect(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connectionId: workspace_schema.Id
    connectionRevision: workspace_schema.Revision
    page: workspace_schema.PageRequest


class Destination(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    destinationId: workspace_schema.Id
    title: str = Field(..., min_length=1)
    revision: workspace_schema.Revision
    writable: bool


class ProviderNotionInspection(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    connectionId: workspace_schema.Id
    connectionRevision: workspace_schema.Revision
    valid: bool
    destinations: list[Destination]
    page: workspace_schema.PageInfo
    observedAt: workspace_schema.Time


class ProviderEffectReconcile(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: workspace_schema.Id
    providerId: workspace_schema.Id
    credentialRef: workspace_schema.Id
    requestHash: workspace_schema.Hash
    remoteReference: workspace_schema.Id | None


class ProviderEffectEvidence(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    effectId: workspace_schema.Id
    disposition: Disposition3
    remoteReference: workspace_schema.Id | None
    evidenceHash: workspace_schema.Hash | None
    observedAt: workspace_schema.Time


class HostContractBinding(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    contractId: workspace_schema.Id
    revision: workspace_schema.Revision
    schemaDigest: workspace_schema.Hash


class HostRouteContribution(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    routeId: workspace_schema.Id
    pathTemplate: str = Field(
        ...,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    titleKey: workspace_schema.Id
    capabilityId: workspace_schema.Id
    accessRuleId: workspace_schema.Id
    viewFactoryId: workspace_schema.Id


class HostContribution(BaseModel):
    """
    Trusted compiled application contribution, not an externally installable plugin or browser registration request.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    contributionId: workspace_schema.Id
    revision: workspace_schema.Revision
    components: list[Component] = Field(..., max_length=13)
    requires: list[HostContractBinding]
    provides: list[HostContractBinding]
    routes: list[HostRouteContribution]
    capabilityIds: list[workspace_schema.Id]
    lifecycleParticipantIds: list[workspace_schema.Id]


class HostRegisterInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contribution: HostContribution
    expectedManifestRevision: workspace_schema.Revision


class HostManifestResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    manifestRevision: workspace_schema.Revision
    acceptedContributionIds: list[workspace_schema.Id]
    ready: bool
    missingRequiredBindings: list[HostContractBinding]
    missingLifecycleParticipants: list[workspace_schema.Id]


class HostInspectInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    manifestRevision: workspace_schema.Revision


class HostCapability(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    capabilityId: workspace_schema.Id
    owner: Owner
    state: State
    observedAt: workspace_schema.Time
    evidenceRevision: workspace_schema.Revision
    reasonKey: workspace_schema.Id


class HostCapabilitiesInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class HostCapabilitiesPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[HostCapability]
    page: workspace_schema.PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: workspace_schema.PolicyRef


class HostNavigationInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    routeId: workspace_schema.Id
    returnContext: workspace_schema.HostReturnContext | None = None


class HostObservation(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    observationId: workspace_schema.Id
    requestId: workspace_schema.Id
    capabilityId: workspace_schema.Id
    observedAt: workspace_schema.Time
    outcomeCode: workspace_schema.Id
    operationReference: workspace_schema.Id | None = None
    evidenceRevision: workspace_schema.Revision


class HostObservationInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    observation: HostObservation


class AccessSessionInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext


class AccessRegisterInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    email: workspace_schema.AccessEmail
    password: workspace_schema.AccessSecret
    displayName: str | None = Field(
        None,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )
    policyRef: workspace_schema.PolicyRef


class AccessEmailRequestInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    email: workspace_schema.AccessEmail
    policyRef: workspace_schema.PolicyRef


class AccessVerifyEmailInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    verification: workspace_schema.AccessChallengeProof


class AccessLoginInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    email: workspace_schema.AccessEmail
    password: workspace_schema.AccessSecret
    policyRef: workspace_schema.PolicyRef


class AccessLogoutInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext


class AccessPasswordResetInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    verification: workspace_schema.AccessChallengeProof
    newPassword: workspace_schema.AccessSecret


class AccessPasswordChangeInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    currentPassword: workspace_schema.AccessSecret
    newPassword: workspace_schema.AccessSecret


class AccessEmailChangeInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    currentProof: workspace_schema.AccessSecret
    newEmail: workspace_schema.AccessEmail
    policyRef: workspace_schema.PolicyRef


class AccessEmailChangeCompleteInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    verification: workspace_schema.AccessChallengeProof


class AccessBeginIdentityInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    provider: Provider
    intent: Intent
    returnRouteId: workspace_schema.Id
    policyRef: workspace_schema.PolicyRef


class AccessCompleteIdentityInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    flowId: workspace_schema.Id
    callbackState: workspace_schema.AccessSecret
    authorizationCode: workspace_schema.AccessSecret
    callbackBinding: workspace_schema.Id


class AccessIdentitySignedIn(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['signed_in']
    identityLink: workspace_schema.AccessIdentityLink
    session: workspace_schema.AccessPublicSession


class AccessIdentityLinked(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['linked']
    identityLink: workspace_schema.AccessIdentityLink


class AccessIdentityMfa(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    state: Literal['mfa_required']
    mfaChallenge: workspace_schema.AccessMfaContinuation


class AccessIdentityResult(
    RootModel[AccessIdentitySignedIn | AccessIdentityLinked | AccessIdentityMfa]
):
    root: AccessIdentitySignedIn | AccessIdentityLinked | AccessIdentityMfa


class AccessUnlinkIdentityInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    identityLinkId: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class AccessIdentityListInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class AccessOrcidProfileInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    identityLinkId: workspace_schema.Id


class AccessMfaVerifyInput(BaseModel):
    """
    Pre-authentication request: context may contain an anonymous principal. The trusted transport separately validates the protected primary-authentication continuation cookie, binds it to verification.challengeId/flowBinding and the server-owned primary-authentication record, and passes only a verified invocation. The factor proof is untrusted until checked; neither a full session nor a caller-claimed account is required.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    verification: workspace_schema.AccessChallengeProof
    factorKind: FactorKind


class AccessMfaEnrollmentInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    currentProof: workspace_schema.AccessSecret
    policyRef: workspace_schema.PolicyRef


class AccessMfaMaterialInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    enrollmentId: workspace_schema.Id
    deliveryReference: workspace_schema.Id
    currentProof: workspace_schema.AccessSecret


class AccessMfaConfirmInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    enrollmentId: workspace_schema.Id
    verification: workspace_schema.AccessChallengeProof


class AccessMfaRecoveryInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    verification: workspace_schema.AccessChallengeProof
    policyRef: workspace_schema.PolicyRef


class AccessProfileInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext


class AccessProfileUpdateInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    fieldVocabularyRevision: workspace_schema.Revision
    changes: list[workspace_schema.AccessProfileField]
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class AccessConsentListInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class AccessConsentUpdateInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    purposeId: workspace_schema.Id
    decision: Decision
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class AccessAuthorityInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    accountId: workspace_schema.Id
    operationId: workspace_schema.Id
    resourceOwnerId: workspace_schema.Id | None = None
    requiredConsentPurposeIds: list[workspace_schema.Id]


class AccessAuthorityDecision(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: workspace_schema.Id
    operationId: workspace_schema.Id
    decision: Decision1
    authorityRevision: workspace_schema.Revision
    consentRevisions: list[workspace_schema.AccessConsentRecord]
    reasonKey: workspace_schema.Id
    evaluatedAt: workspace_schema.Time


class LifecycleParticipant(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    participantId: workspace_schema.Id
    component: Component
    contractRevision: workspace_schema.Revision
    requiredScopes: list[workspace_schema.LifecycleScope] = Field(..., max_length=7)


class LifecycleManifestInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    manifestRevision: workspace_schema.Revision
    policyRef: workspace_schema.PolicyRef
    participants: list[LifecycleParticipant] = Field(..., max_length=13)


class AccessLifecyclePrepareInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    currentProof: workspace_schema.AccessSecret
    action: Action
    expectedRevision: workspace_schema.Revision
    policyRef: workspace_schema.PolicyRef


class LifecycleRequestInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    action: Action
    policyRef: workspace_schema.PolicyRef
    confirmationRef: workspace_schema.Id


class LifecycleReactivationInput(BaseModel):
    """
    Public pre-authentication envelope; no caller account ID or active session is required. Account and withdrawn lifecycle identity are resolved exclusively from the verified purpose-bound reactivation proof. Trusted transport context may remain anonymous until this limited recovery authority is verified.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    verification: workspace_schema.AccessChallengeProof
    policyRef: workspace_schema.PolicyRef
    confirmationRef: workspace_schema.Id


class LifecycleStatusInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    lifecycleRequestId: workspace_schema.Id


class LifecycleWorkTicket(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    lifecycleRequestId: workspace_schema.Id
    accountId: workspace_schema.Id
    participant: LifecycleParticipant
    action: workspace_schema.LifecycleAction
    requestRevision: workspace_schema.Revision
    authorityRevision: workspace_schema.Revision
    manifestRevision: workspace_schema.Revision
    policyRef: workspace_schema.PolicyRef
    workReference: workspace_schema.Id


class LifecyclePendingInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    participantId: workspace_schema.Id
    page: workspace_schema.PageRequest


class LifecycleWorkPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    items: list[LifecycleWorkTicket]
    page: workspace_schema.PageInfo
    appliedLimit: int = Field(..., ge=1)
    policyRef: workspace_schema.PolicyRef


class LifecycleAcknowledgeInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    work: LifecycleWorkTicket
    disposition: workspace_schema.LifecycleParticipantDisposition
    evidenceDigest: workspace_schema.Hash


class LifecycleRestoreInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    accountId: workspace_schema.Id
    participantId: workspace_schema.Id
    restoreSetReference: workspace_schema.Id
    policyRef: workspace_schema.PolicyRef
    recordedAuthorityRevision: workspace_schema.Revision
    scopes: list[workspace_schema.LifecycleScope] = Field(..., max_length=7)


class LifecycleRestoreDecision(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    decision: Decision2
    authorityRevision: workspace_schema.Revision
    policyRef: workspace_schema.PolicyRef
    reasonKey: workspace_schema.Id
    decisionReference: workspace_schema.Id


class LifecycleApplyInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    work: LifecycleWorkTicket


class LibrarySavePaperInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef
    policyRef: workspace_schema.PolicyRef


class LibrarySavedPaperInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    savedPaperId: workspace_schema.Id


class LibraryPaperListInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class LibrarySaveSearchInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    queryContext: workspace_schema.LibraryQueryContext
    label: str | None = Field(
        None,
        description='Bound by the named approved policy before processing.',
        min_length=1,
    )


class LibrarySavedSearchInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    savedSearchId: workspace_schema.Id


class LibrarySearchListInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class LibraryHistoryListInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class LibraryHistoryInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    historyId: workspace_schema.Id


class LibraryHistoryFactResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    disposition: Disposition4
    historyId: workspace_schema.Id | None = None
    clearBoundary: workspace_schema.Revision
    requestId: workspace_schema.Id


class LibraryClearHistoryInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class SettingsReadInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext


class SettingsUpdateInput1(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    searchDefaults: workspace_schema.SettingsSearchDefaults
    assistanceDefaults: workspace_schema.SettingsAssistanceDefaults | None = None
    appearance: Appearance | None = None
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class SettingsUpdateInput2(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    searchDefaults: workspace_schema.SettingsSearchDefaults | None = None
    assistanceDefaults: workspace_schema.SettingsAssistanceDefaults
    appearance: Appearance | None = None
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class SettingsUpdateInput3(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    searchDefaults: workspace_schema.SettingsSearchDefaults | None = None
    assistanceDefaults: workspace_schema.SettingsAssistanceDefaults | None = None
    appearance: Appearance
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class SettingsUpdateInput(
    RootModel[SettingsUpdateInput1 | SettingsUpdateInput2 | SettingsUpdateInput3]
):
    root: SettingsUpdateInput1 | SettingsUpdateInput2 | SettingsUpdateInput3 = Field(
        ...,
        description='Internal envelope; context is derived by the trusted boundary, never accepted from a public body.',
    )


class SettingsOnboardingInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    action: Action2
    interestIds: list[workspace_schema.Id]
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class SettingsSuggestionInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest
    identityLinkId: workspace_schema.Id | None = None


class SettingsRecentInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class SettingsBehaviorEvent(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    eventId: workspace_schema.Id
    accountId: workspace_schema.Id
    paper: workspace_schema.PaperRef
    activityId: workspace_schema.Id
    occurredAt: workspace_schema.Time
    consentRevision: workspace_schema.Revision
    inputBoundary: workspace_schema.Revision
    authorityRevision: workspace_schema.Revision


class SettingsBehaviorInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    event: SettingsBehaviorEvent


class SettingsBehaviorResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    disposition: Disposition5
    inputBoundary: workspace_schema.Revision
    requestId: workspace_schema.Id


class SettingsProfileProjection(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    accountId: workspace_schema.Id
    profileId: workspace_schema.Id
    revision: workspace_schema.Revision
    inputBoundary: workspace_schema.Revision
    consentRevision: workspace_schema.Revision
    disposition: Disposition6
    interestIds: list[workspace_schema.Id]
    reasonKey: workspace_schema.Id


class SettingsProjectionInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    accountId: workspace_schema.Id
    purposeId: workspace_schema.Id


class SettingsResetPrepareInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    action: Action3
    currentProof: workspace_schema.AccessSecret
    policyRef: workspace_schema.PolicyRef
    expectedRevision: workspace_schema.Revision


class SettingsResetInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    action: Action3
    policyRef: workspace_schema.PolicyRef
    confirmationRef: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class SettingsResetListInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    view: View
    page: workspace_schema.PageRequest


class SettingsResetInspectInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    resetId: workspace_schema.Id


class AdmissionIdentity(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    operation: workspace_schema.UsageOperation
    generation: workspace_schema.Revision
    accountId: workspace_schema.Id
    intentDigest: workspace_schema.Hash
    periodId: workspace_schema.Id
    quantities: list[workspace_schema.UsageQuantity] = Field(
        ..., max_length=16, min_length=1
    )
    policyRef: workspace_schema.PolicyRef


class AdmissionIntent(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    identity: AdmissionIdentity
    state: State1
    revision: workspace_schema.Revision
    acceptedAt: workspace_schema.Time
    reservationId: workspace_schema.Id | None
    effectRef: workspace_schema.Id | None


class AdmissionClosedEvidence(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    identity: AdmissionIdentity
    state: Literal['closed']
    closureRevision: workspace_schema.Revision
    reasonKey: workspace_schema.Id
    closedAt: workspace_schema.Time
    evidenceRef: workspace_schema.Id


class AdmissionAllocateInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    identity: AdmissionIdentity


class AdmissionInspectInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    identity: AdmissionIdentity


class AdmissionAcceptInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    identity: AdmissionIdentity
    reservationId: workspace_schema.Id
    effectRef: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class AdmissionCloseInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    identity: AdmissionIdentity
    reasonKey: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class SettingsConsentBoundaryInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    consent: workspace_schema.AccessConsentRecord


class UsageInspectInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class UsagePlanInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext


class UsageGrantInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    accountId: workspace_schema.Id
    tierId: workspace_schema.Id
    policyRef: workspace_schema.PolicyRef
    reasonKey: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class UsageRevokeInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    accountId: workspace_schema.Id
    entitlementId: workspace_schema.Id
    policyRef: workspace_schema.PolicyRef
    reasonKey: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class UsageReserveInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    operation: workspace_schema.UsageOperation
    quantities: list[workspace_schema.UsageQuantity]
    policyRef: workspace_schema.PolicyRef


class UsageSettleInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    usageRecordId: workspace_schema.Id
    operation: workspace_schema.UsageOperation
    decision: Decision3
    actualQuantities: list[workspace_schema.UsageQuantity]
    effectReference: workspace_schema.Id
    policyRef: workspace_schema.PolicyRef


class UsageReconcileInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    operation: workspace_schema.UsageOperation


class UsageRecordsInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class CorpusRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef
    purpose: Purpose


class CorpusResolve(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    identifier: str = Field(..., min_length=1)
    versionLabel: str | None = Field(None, min_length=1)


class CorpusAssetRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef
    contentRevision: workspace_schema.Revision
    assetId: workspace_schema.Id


class CorpusRunRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    operation: Operation
    sourceScopeIds: list[workspace_schema.Id] = Field(..., min_length=1)
    authoritativeInputRevision: workspace_schema.Revision
    inputManifestHash: workspace_schema.Hash
    sourcePolicy: workspace_schema.PolicyRef
    compatibilityRevision: workspace_schema.Revision


class CorpusRunRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    runId: workspace_schema.Id


class CorpusProjectionEntry(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: workspace_schema.PaperRef
    contentRevision: workspace_schema.Revision
    contentHash: workspace_schema.Hash
    chunkId: workspace_schema.Id
    sectionId: workspace_schema.Id
    text: str = Field(..., min_length=1)
    representationHandle: workspace_schema.Id | None


class CorpusProjectionBatch(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    runId: workspace_schema.Id
    generationId: workspace_schema.Id
    batchId: workspace_schema.Id
    batchHash: workspace_schema.Hash
    compatibilityRevision: workspace_schema.Revision
    entries: list[CorpusProjectionEntry] = Field(..., min_length=1)
    policy: workspace_schema.PolicyRef


class CorpusPublicationRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    runId: workspace_schema.Id
    generationId: workspace_schema.Id
    expectedPublishedGeneration: workspace_schema.Id | None
    inputManifestHash: workspace_schema.Hash
    verifiedBatchIds: list[workspace_schema.Id]
    verificationEvidenceHash: workspace_schema.Hash
    compatibilityRevision: workspace_schema.Revision
    eligibilityRevision: workspace_schema.Revision


class CorpusProjectionRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    requiredCompatibilityRevision: workspace_schema.Revision


class CorpusEligibilityChange(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef
    disposition: Disposition7
    reasonKey: str = Field(..., min_length=1)
    sourceEvidenceHash: workspace_schema.Hash
    policy: workspace_schema.PolicyRef


class CorpusChangeFact(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    factId: workspace_schema.Id
    paper: workspace_schema.PaperRef
    previousEligibilityRevision: workspace_schema.Revision
    eligibilityRevision: workspace_schema.Revision
    disposition: Disposition8
    occurredAt: workspace_schema.Time
    sequence: int = Field(..., ge=0)
    policy: workspace_schema.PolicyRef


class CorpusChangeRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    afterSequence: int = Field(..., ge=0)
    page: workspace_schema.PageRequest


class CorpusChangePage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    facts: list[CorpusChangeFact]
    page: workspace_schema.PageInfo


class SearchRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    query: workspace_schema.LibraryQueryContext
    page: workspace_schema.PageRequest
    snapshotRevision: workspace_schema.Revision | None = None


class SearchHistoryCheckpointRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext


class SearchCompletedFact(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    factId: workspace_schema.Id
    ownerId: workspace_schema.Id
    executionId: workspace_schema.Id
    query: workspace_schema.LibraryQueryContext
    admissionSequence: int = Field(..., ge=0)
    completionSequence: int = Field(..., ge=0)
    completedAt: workspace_schema.Time
    snapshotRevision: workspace_schema.Revision
    authorityRevision: workspace_schema.Revision
    historyPolicy: workspace_schema.PolicyRef


class SearchFactsRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    afterCompletionSequence: int = Field(..., ge=0)
    page: workspace_schema.PageRequest


class SearchFactsPage(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    facts: list[SearchCompletedFact]
    page: workspace_schema.PageInfo


class SearchFactAck(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    factId: workspace_schema.Id
    consumerId: Literal['Library']
    disposition: Disposition9
    consumerEvidenceRevision: workspace_schema.Revision


class CitationRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef
    direction: Direction
    page: workspace_schema.PageRequest
    traversalPolicy: workspace_schema.PolicyRef
    snapshotRevision: workspace_schema.Revision | None = None


class AssistanceOptionsRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef


class AssistanceRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef
    contentRevision: workspace_schema.Revision
    contentHash: workspace_schema.Hash
    operation: Operation1
    optionId: workspace_schema.Id
    optionsRevision: workspace_schema.Revision
    glossaryRevision: workspace_schema.Revision
    processingPolicy: workspace_schema.PolicyRef


class AssistanceJobRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    jobId: workspace_schema.Id


class AssistanceResultRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    jobId: workspace_schema.Id
    result: workspace_schema.ResultRef | None = None


class AssistanceGlossaryRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext


class AssistanceGlossaryWrite(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    expectedRevision: workspace_schema.Revision
    normalizationPolicy: workspace_schema.PolicyRef
    terms: list[workspace_schema.AssistanceGlossaryTerm]


class ResearchContextCreate(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    purpose: Purpose1
    policy: workspace_schema.PolicyRef


class ResearchContextRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contextId: workspace_schema.Id


class ResearchSessionCreate(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    title: str = Field(..., min_length=1)
    scope: workspace_schema.ResearchScope


class ResearchSessionRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    sessionId: workspace_schema.Id


class ResearchSessionList(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class ResearchDelete(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    scope: Scope1
    sessionId: workspace_schema.Id | None = None
    expectedRevision: workspace_schema.Revision
    confirmed: Literal[True]
    policy: workspace_schema.PolicyRef


class ResearchAttachmentStart(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contextId: workspace_schema.Id
    fileName: str = Field(..., min_length=1)
    mediaType: MediaType
    byteLength: int = Field(..., ge=1)
    contentHash: workspace_schema.Hash
    policy: workspace_schema.PolicyRef


class ResearchAttachmentFinish(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    uploadId: workspace_schema.Id
    contextId: workspace_schema.Id
    contentHash: workspace_schema.Hash


class ResearchAttachmentRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contextId: workspace_schema.Id
    attachmentId: workspace_schema.Id


class ResearchPrivateAssetRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contextId: workspace_schema.Id
    attachmentId: workspace_schema.Id
    assetId: workspace_schema.Id


class DraftWrite(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contextId: workspace_schema.Id
    draftId: workspace_schema.Id
    kind: Kind
    baseRevision: workspace_schema.Revision | None
    text: str
    policy: workspace_schema.PolicyRef


class DraftRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contextId: workspace_schema.Id
    draftId: workspace_schema.Id


class DraftDiscard(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    contextId: workspace_schema.Id
    draft: workspace_schema.DraftRef
    confirmed: Literal[True]
    policy: workspace_schema.PolicyRef


class ResearchTurnRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    sessionId: workspace_schema.Id
    scope: workspace_schema.ResearchScope
    mode: Mode
    text: str = Field(..., min_length=1)
    submittedDraft: workspace_schema.DraftRef | None = None
    policy: workspace_schema.PolicyRef


class ResearchNoveltyRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    scope: workspace_schema.ResearchScope
    inputMode: InputMode
    text: str = Field(..., min_length=1)
    submittedDraft: workspace_schema.DraftRef | None = None
    policy: workspace_schema.PolicyRef


class ResearchJobRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    kind: Kind1
    jobId: workspace_schema.Id
    contextId: workspace_schema.Id


class ResearchTurnRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    sessionId: workspace_schema.Id
    turnId: workspace_schema.Id


class ResearchArtifactRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    artifact: workspace_schema.ResearchArtifactRef


class ResearchNoveltyDiscussion(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    source: workspace_schema.ResearchArtifactRef
    text: str = Field(..., min_length=1)
    submittedDraft: workspace_schema.DraftRef | None = None
    policy: workspace_schema.PolicyRef


class DigestSubscriptionWrite(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    topic: str = Field(..., min_length=1)
    enabled: bool
    schedule: workspace_schema.DigestSchedule
    expectedRevision: workspace_schema.Revision | None
    policy: workspace_schema.PolicyRef


class DigestSubscriptionRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    subscriptionId: workspace_schema.Id


class DigestSubscriptionsRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    page: workspace_schema.PageRequest


class DigestPrepare(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    subscriptionId: workspace_schema.Id
    subscriptionRevision: workspace_schema.Revision
    window: workspace_schema.DigestWindow
    consentRevision: workspace_schema.Revision
    policy: workspace_schema.PolicyRef


class DigestDeliveryRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    deliveryId: workspace_schema.Id


class DigestSend(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    deliveryId: workspace_schema.Id
    expectedRevision: workspace_schema.Revision
    effectKey: workspace_schema.Id
    policy: workspace_schema.PolicyRef


class ExportConnectionConfigure(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    token: str = Field(..., min_length=1)
    expectedRevision: workspace_schema.Revision | None
    credentialPolicy: workspace_schema.PolicyRef


class ExportConnectionRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    connectionId: workspace_schema.Id


class ExportPreviewRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    source: workspace_schema.ResearchArtifactRef
    destination: workspace_schema.ExportDestination
    renderPolicy: workspace_schema.PolicyRef


class ExportApprovalRequest(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    previewId: workspace_schema.Id
    previewRevision: workspace_schema.Revision
    bindingHash: workspace_schema.Hash
    explicitApproval: Literal[True]


class ExportExecute(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    approvalId: workspace_schema.Id
    bindingHash: workspace_schema.Hash


class ExportEffectRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    effectId: workspace_schema.Id


class ExportCancel(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    approvalId: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class ControlledReadiness(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    status: Status
    generation: workspace_schema.Revision
    reasonKeys: list[workspace_schema.Id]


class LibraryRemoveSavedPaperInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    savedPaperId: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class LibraryRemoveSavedSearchInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    savedSearchId: workspace_schema.Id
    expectedRevision: workspace_schema.Revision


class UsageAssignmentRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    accountId: workspace_schema.Id


class AssistanceHistoryRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    paper: workspace_schema.PaperRef
    page: workspace_schema.PageRequest


class ExecutionBinding(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    ownerComponent: workspace_schema.Id
    operationId: workspace_schema.Id
    inputRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    payloadRef: workspace_schema.Id


class ExecutionClaim(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    binding: ExecutionBinding
    workerId: workspace_schema.Id
    leaseId: workspace_schema.Id
    fence: int = Field(..., ge=1)
    leaseRevision: workspace_schema.Revision
    expiresAt: workspace_schema.Time


class ExecutionAcquire(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    binding: ExecutionBinding
    deliveryId: workspace_schema.Id


class ExecutionRenew(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    claim: ExecutionClaim
    expectedLeaseRevision: workspace_schema.Revision


class ExecutionReclaim(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    binding: ExecutionBinding
    previousFence: int = Field(..., ge=1)
    deliveryId: workspace_schema.Id


class ExecutionClaimRead(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    claim: ExecutionClaim


class ExecutionClaimResult(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    claim: ExecutionClaim
    jobRevision: workspace_schema.Revision
    acceptedAt: workspace_schema.Time


class AssistanceAcceptedInput(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    paper: workspace_schema.PaperRef
    contentRevision: workspace_schema.Revision
    contentHash: workspace_schema.Hash
    operation: Operation1
    optionId: workspace_schema.Id
    optionsRevision: workspace_schema.Revision
    glossaryRevision: workspace_schema.Revision
    processingPolicy: workspace_schema.PolicyRef
    glossary: workspace_schema.AssistanceGlossary


class AssistanceExecutionPayload(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    binding: ExecutionBinding
    acceptedAt: workspace_schema.Time
    input: AssistanceAcceptedInput
    sections: list[workspace_schema.CorpusSection]
    usageRecordId: workspace_schema.Id


class AssistanceProgress(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    jobId: workspace_schema.Id
    factId: workspace_schema.Id
    claim: ExecutionClaim
    expectedJobRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    progress: workspace_schema.Progress


class AssistanceFailure(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    jobId: workspace_schema.Id
    factId: workspace_schema.Id
    claim: ExecutionClaim
    expectedJobRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    error: workspace_schema.Error
    usageRecordId: workspace_schema.Id


class ProviderRequest1(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['identity.profile']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderIdentityProfileRead']
    validatedPayload: ProviderIdentityProfileRead
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest2(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['source.search']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderSourceSearch']
    validatedPayload: ProviderSourceSearch
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest3(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['notion.inspect']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderNotionInspect']
    validatedPayload: ProviderNotionInspect
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest4(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['effect.reconcile']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderEffectReconcile']
    validatedPayload: ProviderEffectReconcile
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest5(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['identity.exchange']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderIdentityExchange']
    validatedPayload: ProviderIdentityExchange
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest6(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['source.read']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderSourceRead']
    validatedPayload: ProviderSourceRead
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest7(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['citation.read']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderCitationRead']
    validatedPayload: ProviderCitationRead
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest8(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['model.generate']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderModelRequest']
    validatedPayload: ProviderModelRequest
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest9(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['attachment.extract']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderExtractionRequest']
    validatedPayload: ProviderExtractionRequest
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest10(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['email.send']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderEmailRequest']
    validatedPayload: ProviderEmailRequest
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest11(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    adapterId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    operation: Literal['notion.write']
    ownerComponent: workspace_schema.Id
    credentialRef: workspace_schema.Id | None
    requestSchemaId: Literal['ProviderNotionRequest']
    validatedPayload: ProviderNotionRequest
    effectId: workspace_schema.Id | None
    policy: workspace_schema.PolicyRef


class ProviderRequest(
    RootModel[
        ProviderRequest1
        | ProviderRequest2
        | ProviderRequest3
        | ProviderRequest4
        | ProviderRequest5
        | ProviderRequest6
        | ProviderRequest7
        | ProviderRequest8
        | ProviderRequest9
        | ProviderRequest10
        | ProviderRequest11
    ]
):
    root: (
        ProviderRequest1
        | ProviderRequest2
        | ProviderRequest3
        | ProviderRequest4
        | ProviderRequest5
        | ProviderRequest6
        | ProviderRequest7
        | ProviderRequest8
        | ProviderRequest9
        | ProviderRequest10
        | ProviderRequest11
    )


class ProviderOutcome(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    requestId: workspace_schema.Id
    adapterRevision: workspace_schema.Revision
    outcome: Outcome2
    responseSchemaId: workspace_schema.Id
    validatedPayload: (
        ProviderIdentityProfileResult
        | ProviderSourceSearchResult
        | ProviderNotionInspection
        | ProviderEffectEvidence
        | ProviderIdentityResult
        | ProviderSourceResult
        | ProviderCitationResult
        | ProviderModelResult
        | ProviderExtractionResult
        | ProviderEmailResult
        | ProviderNotionResult
        | None
    )
    remoteReference: workspace_schema.Id | None
    retryAfterSeconds: RetryAfterSeconds | None
    evidenceRefs: list[workspace_schema.Id]


class DispatchFact(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    messageId: workspace_schema.Id
    causationId: workspace_schema.Id
    ownerComponent: workspace_schema.Id
    operationId: workspace_schema.Id
    kind: workspace_schema.Id
    outcome: Outcome3
    resultRef: workspace_schema.ResultRef | None
    error: workspace_schema.Error | None
    claim: ExecutionClaim
    expectedJobRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    progress: workspace_schema.Progress | None
    prepared: workspace_schema.AssistanceResult | None
    usageRecordId: workspace_schema.Id | None


class LibraryHistoryFactInput(BaseModel):
    """
    Internal envelope; context is derived by the trusted boundary, never accepted from a public body.
    """

    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    fact: SearchCompletedFact


class AssistanceComplete(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    jobId: workspace_schema.Id
    factId: workspace_schema.Id
    claim: ExecutionClaim
    expectedJobRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    prepared: workspace_schema.AssistanceResult
    usageRecordId: workspace_schema.Id


class ResearchCompletion(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
    context: CommandContext
    kind: Kind1
    jobId: workspace_schema.Id
    contextId: workspace_schema.Id
    leaseId: workspace_schema.Id
    expectedJobRevision: workspace_schema.Revision
    inputHash: workspace_schema.Hash
    prepared: workspace_schema.ResearchArtifact
    usageRecordId: workspace_schema.Id


JsonValue.model_rebuild()
