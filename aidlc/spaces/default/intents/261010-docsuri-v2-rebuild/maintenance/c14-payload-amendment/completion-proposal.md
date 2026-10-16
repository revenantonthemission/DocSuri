# Research completion contract correction

Status: additive correction applied to canonical C00/C14, exported schemas and
generated bindings in the U4 working branch. This records the exact correction
within the approved U4 scope. U4 execution remains disabled until the mounted
execution round trip and adversarial checks pass.

## Observed gap

Commit `45413571` adds ResearchAcceptedInput and ResearchExecutionPayload to
C00/C14. Its schema export drift check passes. However, DispatchFact.prepared
still permits only AssistanceResult or null. C07 ResearchCompletion requires a
ResearchArtifact, whose immutable reference uses artifactId; ResultRef instead
uses resultId and additionally requires mediaType. C14's current sentence
`prepared.result must equal resultRef` only describes PaperAssistance's shape.

A research worker can therefore receive a valid payload but cannot send its
actual prepared artifact through the existing completion envelope. Passing null
and retrieving an unstated staging object would introduce an undocumented
protocol. The executable reproduction beside this proposal demonstrates the
schema mismatch without changing any service or contract file.

## Exact change

1. Add ResearchArtifact to DispatchFact.prepared's type alternatives.
2. Constrain that alternative by owner: ResearchWorkspace can carry only a
   ResearchArtifact or null; every other owner retains the existing
   AssistanceResult-or-null alternatives. Preserve the existing
   PaperAssistance success rule unchanged.
3. ResearchWorkspace success requires a ResearchArtifact, ResultRef and
   usageRecordId, and a null error. Its other outcomes carry no prepared result.
4. Specify the immutable reference conversion explicitly:
   - resultRef.resultId = prepared.artifact.artifactId
   - resultRef.revision = prepared.artifact.revision
   - resultRef.contentHash = prepared.artifact.contentHash
   - resultRef.mediaType = prepared.mediaType
5. The owning transaction also verifies operationId, ownerId, contextId,
   operation kind, exact input hash, current claim/fence and unexpired lease,
   job revision and current account/source permission. The existing C07
   completion operation remains the authoritative state transition; C14 maps
   into it and grants no additional authority.
6. Advance C14 from 2.1.0 to 2.2.0, documenting this additive completion
   alternative. Preserve the existing DispatchCommand envelope's 2.0.0
   discriminator for existing consumers; this change does not rewrite it.
7. Regenerate language bindings and schema exports, verify existing
   PaperAssistance consumers, and then prove a mounted U4 claim → payload read
   → completion round trip, including substituted-owner, artifact mismatch,
   stale claim, revoked authority and duplicate completion cases.

## Scope and completion boundary

This correction adds no product capability, provider, deployment or spending.
It completes the shared protocol needed by the already-approved U4 work.
U4's Step 15 remains incomplete until both the coordinated contract change and
the executable round-trip evidence exist. The rest of the approved U4 build can
continue independently. Follow CONVENTIONS.md when the working branch is ready.
