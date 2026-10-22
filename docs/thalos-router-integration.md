# THALOS router integration

Router release 2.1.0 · Internal handoff schema 0.1.0 · October 22, 2026

Status: first integration milestone, advisory only. Based on Quick2 Agent commit
`27bea341fe9608d04f177c52bb43fb4981175e58`. The routing subsystem is a component of
THALOS. This change does not deploy THALOS, enable business execution, implement
subscription billing, or establish production scalability.

## Component ownership

| Component | Owns | Implementation in this change |
|---|---|---|
| Work Context | Reusable user/organization responsibilities, exclusions, assignments and authority references | Version/hash references consumed; onboarding/store remain separate |
| THALOS policy and work decision | Ownership, disposition, permitted processing, per-action automate/augment/human mode | A trusted resolver supplies a pinned decision; no replacement policy engine is invented |
| Classifier | Intent, requirements and uncertainty | Existing keyword/phrase baseline, used independently per action; unknown fallback requests clarification |
| Router | Rank eligible models, endpoints and agents | Hard filters and internal adapter implemented |
| Commercial platform | Caller identity, tenant access, entitlements, quota, billing and durable records | Required resolver boundary specified; production services not implemented |
| Execution runtime | Current authority, exact arguments, spending, retries, model/tool invocation | No dispatch here; every result explicitly denies execution authorization |
| Observatory | Show observed decisions and routing | Event integration mapped below; live streaming remains a subsequent milestone |

SAM/ADAM classifiers can be evaluated behind the classification boundary. Their
accuracy, calibration and routing policies must be evaluated separately before
substitution. A model catalogue is not a classifier, a policy engine, or an
approved deployment inventory.

## Internal contract

Entry point: `services.router.thalos.recommend_for_decision(caller, decision_id, resolver)`.
The machine-readable input schema is [thalos-routing-handoff.schema.json](thalos-routing-handoff.schema.json).
This is an internal resolver-to-router schema, not a public API accepting authorization claims.

1. The application authenticates the caller and resolves permitted tenant, project
   and subject. It checks processing admission before any task upload/inspection.
2. A trusted `DecisionResolver.resolve` access-checks the decision and pins the
   context/profile/policy snapshots, source action digests and eligible resources.
3. The adapter independently checks scope, decision ID, expiry, no-AI status and
   the permitted processor ID before asking for any action text.
4. Held/unknown/forbidden processing returns metadata only: no actions, raw input
   reference, text digest, inferred tasks or used processor.
5. Non-proceed dispositions preserve the action records without loading text or
   recommending resources. Human and authority-bound actions also skip text loading.
6. Other actions load their authorized text lazily. The adapter checks the pinned
   digest and the 100,000-byte per-action limit before feature extraction.
7. It ranks only unexpired deployments supplied by the resolver. Every primary and
   fallback faces the same constraints. The adapter never consults the global
   catalogue for an extra candidate when the supplied set is empty.
8. The result is advisory. A future runtime must recheck current grants, revocation,
   deployment eligibility, exact tool arguments and spending immediately before use.

`CallerScope` must originate from authentication. `ResolvedDecision`, its modes,
its restrictions and its approved resources must originate from trusted services.
Accepting those objects directly from a client would defeat this boundary. Python
types and an `evidence_ref` are not proofs of authority. The resolver is responsible
for validating the evidence, its scope and its validity, and binding the model
metadata to the actual endpoint. There is intentionally no new HTTP endpoint that
accepts a self-asserted authorization envelope.

| Record | Key fields |
|---|---|
| Caller scope | tenant_id, project_id, subject_id |
| Context binding | context_id, profile_version/hash, policy_version/hash, resolver_version |
| Resolved decision | decision_id, valid_until, processing, no_ai, permitted_processors, disposition |
| Action | unique action_id, execution_mode, authority_bound, input_sha256, constraints |
| Approved deployment | deployment_id, evidence_ref, valid_until, endpoint-specific ModelCard |
| Approved agent | evidence_ref, valid_until, AgentCard and its model chain |
| Result | scope/context/version binding, status, observed processors, per-action recommendations, execution_authorized=false |

All action records are retained for authorized decisions, including mixed requests.
An authority-bound action is conservatively normalized to human mode. A human
action never contains model or agent routes. An unmatched intent returns `clarify`;
an empty eligible inventory returns `no_eligible_route`. Neither becomes a generic
successful AI route. Resolver/input errors propagate as errors, never business success.

The adapter has no content logger, cache, network call, persistent store, metering
side effect or execution client. Policy expiry is evaluated at recommendation time;
recommendations are not leases guaranteeing that permission will persist.

## Constraint changes

- Cost and latency caps include equality and reject over-budget estimates. Zero is
  a real limit. Latency no longer permits 50% slack.
- The model must fit estimated input plus output and the estimated output allowance.
- Required compliance labels eliminate agents, instead of applying a score penalty.
- Agent primary/fallback models are filtered against the same model constraints;
  the returned chain is rewritten to contain only eligible IDs.
- Agent cost overhead is included when evaluating an explicit cost cap. Required
  tools are checked against agent capabilities.
- Invalid/negative/nonfinite values, string booleans and misspelled HTTP constraint
  keys are rejected instead of being silently ignored or coerced.
- Passing an empty tenant-specific model/agent inventory never restores global defaults.

These are admission checks against estimates. A p50 latency estimate is not a
deadline guarantee, and projected cost uses an input/output heuristic. Real execution
needs output-token limits, per-step accounting, retry budgets and cancellation. An
agent can perform multiple calls; this adapter does not claim to bound its total run cost.

## Catalogue evidence

OpenRouter import no longer infers compliance, US/EU hosting, open-weight licensing
or tool support from provider identity. Missing/invalid pricing and latency remain
unknown internally and serialize as JSON null. An explicit relevant cost/latency cap
excludes unknown estimates. Unknown regions also fail an explicit region requirement.

Curated catalogue labels remain historical, unverified data for the legacy advisory
console. Their default region is now unknown. The THALOS path accepts only approved
endpoint snapshots from its resolver; it does not promote curated labels to evidence.

Offline/failure samples carry `openrouter_sample` provenance and are excluded by the
THALOS adapter. Network failure no longer silently enables sample fallback by default
in the API or UI. Explicit demo use remains available in the development console.

Intent confidence is labeled an uncalibrated heuristic. Existing benchmark numbers
and family fallbacks remain an unverified static snapshot. They provide baseline
ranking signals and do not establish measured accuracy for the requested workload.

## Compatibility and deployment

The existing v2 endpoints remain development/advisory interfaces. Their HTTP paths
are unchanged. Strict constraint semantics, unknown estimates (null), unknown region
defaults and filtered agent chains are intentional behavior changes. Clients must
handle no-candidate responses and null estimates. Service version advances to 2.1.0.

Do not expose the existing v2 service as the commercial THALOS API. It still lacks
production identity/tenant authorization, entitlement/quota controls, durable scoped
storage and billing. Existing process-global catalogue sync and legacy Redis caching
remain outside the internal THALOS adapter and must not become tenant data boundaries.

To test the router slice with Python 3.11+:

```sh
python -m venv .venv
.venv/bin/python -m pip install pytest pytest-asyncio fastapi redis httpx opentelemetry-instrumentation-fastapi
.venv/bin/python -m pytest tests/test_advanced_router.py tests/test_thalos_router.py -q
node --check services/router/static/app.js
```

## Verification and evaluation

The original baseline had **47 passing router tests** before changes. The combined
suite has **108 passing tests** (47 existing and 61 added) covering caps, agent fallback restrictions, unknown metadata,
scope mismatch, processing holds, authority-bound actions, input binding, expired
approvals, explicit sample provenance and HTTP validation. JavaScript syntax and
Git whitespace checks also passed. Tests use synthetic endpoint/authority fixtures and do not verify an
external provider's compliance, region or availability.

The safety tests are not the product evaluation set. A separate evaluation should:

1. Freeze a representative, independently labeled held-out set and an adversarial set.
   Keep profile/policy versions and request-family groups fixed; do not tune on it.
2. Compare the keyword baseline, SAM and ADAM classification independently of
   resource selection. Report compound-action completeness, unknown detection,
   ownership/disposition agreement where implemented, and calibrated uncertainty.
3. Compare routing using the same allowed endpoints, prices, policies and workloads.
   Report task success, actual cost/latency, constraint violations, no-route coverage
   and human review effort. Include fixed economical/strong-model baselines.
4. Keep exact-model measurements separate from family priors and provider estimates.
   A replacement classifier must qualify on the same held-out tasks before promotion.

No held-out quality benchmark, production load test, SAM/ADAM integration or provider
execution was performed as part of this implementation milestone.

## Observatory mapping and remaining milestones

The adapter produces resource recommendations; it cannot truthfully emit upstream
context-resolution/classification events that it did not observe. The future API's
event recorder should map actual service transitions to Observatory's envelope:

| Observed service transition | Observatory event |
|---|---|
| Authorized request intake | request.received |
| Versioned profile/policy resolution | context.resolved |
| Processor admission | processing.authorized |
| Action extraction by the owning classifier | actions.classified |
| Work decision committed | decision.created |
| Resource recommendations committed | route.recommended |
| Pre-processing hold | request.held |

Do not invent classifier events from router guesses or turn a recommendation into
an execution/completion event. A server must filter/redact event payloads and enforce
viewer scope, ordering, replay, retention and backpressure before SSE delivery.

Next milestones: implement the authenticated decision/context API with two isolated
test tenants; provide the trusted resolver and durable usage ledger; benchmark
classifier substitutions; then connect committed decision events to Observatory.
Subscriptions and compute enrollment remain separate platform/runtime deliverables.
