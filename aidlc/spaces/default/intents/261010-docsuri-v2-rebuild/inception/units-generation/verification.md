# Units Generation verification

Date: 2026-10-11 (Asia/Seoul). These checks concern design-document consistency.
No v2 service implementation, end-to-end acceptance or free/local feasibility
result is claimed by them.

## Executed checks

The read-only [verifier](verify.mjs) completed successfully with:

```text
units: 8
service: 3
library: 5
components: 13
edges: 19
parentRequirements: 20
subrequirements: 50
nfrRows: 10
mermaid: flowchart-v2
checks: passed
```

It checks unique/stable unit IDs and directory names; kinds against the confirmed
plan; exact YAML node shape and known dependencies; no duplicate/self/cyclic
edges; agreement between the confirmed plan, graph table and diagram; retention
of all approved component owners; all source FR IDs in source order and exactly
once in the map/JSON; declared targets and directories in each mapped row; all
units participating; ten NFR rows and nine IB identifiers; local file links and
replacement-character absence; and Mermaid syntax.

The Mermaid diagram was also parsed successfully before being written into the
dependency document. The first combined verifier run reached the NFR check and
rejected descriptive labels because its parser expected ID-only cells. The
parser was corrected to accept the actual `NFR1 — description` label form;
the subsequent complete run passed. No requirement was removed to make it pass.

## Reproduction

From the repository root, with Bun, the frontend's existing JSDOM dependency
and Mermaid 11.12.0 available:

```sh
bun aidlc/spaces/default/intents/261010-docsuri-v2-rebuild/inception/units-generation/verify.mjs /tmp/docsuri-domain-validation/node_modules/mermaid/dist/mermaid.esm.mjs
```

The last argument is the installed Mermaid module path; use the corresponding
path on another machine. The temporary Mermaid installation was already present
from Domain Design validation; application dependencies and CI configuration
were not changed for this check. The verifier reads artifacts and does not write
them. It does not execute application jobs, publish content or access user data.

## Limits and further evidence

- IDs and edges can be internally consistent while a boundary is semantically
  incomplete. An independent architecture review follows these checks.
- `OK` traceability means assigned responsibility. It does not mean implemented,
  tested, accepted or complete. U1 contributes real partial coverage; parent FR
  closure still needs every child and applicable cross-boundary check.
- No runtime composition, actual provider path, owner isolation, interruption
  recovery, accessibility conformance or performance target is proven here.
  Construction and integrated acceptance must supply those results.
- The approved dependency topology does not select an economic build sequence,
  hosting/technology, migration, retention policy, numeric targets or schedule.
  The approved evidence obligations still constrain those choices.
