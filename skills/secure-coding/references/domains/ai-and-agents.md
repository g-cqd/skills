# AI, LLM, and agent systems

Use when the target assembles prompts, retrieves documents (RAG), keeps agent memory, calls tools, acts as or
connects to an MCP server, delegates to sub-agents, or renders or executes model output.

## Discipline

- Prompt injection alone is not a finding. A finding needs a code-level boundary failure: content reaches another
  principal's context, uses authority the requester lacks, discloses data they cannot read, or drives a sink they
  cannot reach directly.
- Model output, memory, tool descriptions, retrieved text, and MCP responses are untrusted input. Point to the code
  that grants authority, trusts output, writes durable state, or feeds a sink.
- A guardrail prompt is not a security boundary. Only deterministic checks count: resource-scoped authorization,
  isolation, argument validation, action binding, constrained credentials.
- Authorization and action binding are separate controls. Content that makes an agent take an action the affected
  principal did not request or approve, under that principal's valid authority, is an action-binding failure. A
  user's own direct request, executed by a model with that user's authority, is not a delegation defect.

## Classes

**Indirect injection through retrieved content.** An attacker can write a document, page, file, email, issue, tool
response, or metadata that enters another principal's model context. Trace who writes each source, how retrieval is
scoped, whose session reads it, and which capability that session holds.

**Cross-session or cross-tenant context bleed.** History, embeddings, retrieval results, or prompt caches keyed too
broadly. The tenant filter must be in the query and in every cache key.

**Persistent memory poisoning.** Attacker content or a model summary is written to memory that later shapes another
user's or a privileged session's task. Check who may create, merge, and delete memory, its provenance and tenant, and
whether observations become durable instructions.

**Role and provenance confusion.** Prompt assembly lets untrusted text pass as a system message, an earlier turn, a
tool result, a policy, or a memory record: string concatenation, untyped history, caller-set role fields,
serialization that drops source labels.

**Tool arguments into a sink.** Model-produced arguments reach SQL, shell, file paths, URL fetches, or privileged
APIs without validation in the handler. A schema narrows shape; it does not authorize.

**Excessive agency and confused deputy.** The agent acts with a service identity or broad credential and the tool
handler does not check that the requesting principal may do this action on this resource.

**Approval binding.** The user approves one described action, and execution uses changed arguments, another resource,
another principal, or a later turn.

**Schema and dispatcher disagreement.** The schema accepts aliases, extra or duplicate keys, coercions, or nested
free-form objects that the dispatcher interprets differently. Validate again where the value is used.

**Unbounded action loops.** One request can queue repeated spend, sends, mutations, or external calls without a
per-request budget, per-action authorization, cancellation, or idempotency.

**Sub-agent and MCP trust inheritance.** A delegated task gets the full session, credentials, or memory instead of the
least authority it needs, or its results are trusted on return.

**MCP identity confusion.** Calls or results are routed by names, tool ids, request ids, or resource URIs that a peer
or the model can influence, rather than by the authenticated connection and the outstanding request. Two servers
claiming one tool name.

**MCP metadata as policy.** Tool descriptions, schemas, prompts, or hints from an MCP peer treated as authorization.
They can guide the model; they cannot grant a capability.

**Insecure output rendering.** Model output reaches HTML, Markdown with auto-loaded images or links, templates, URLs,
or commands without the sink's encoding and policy. A Markdown image that sends data to an attacker URL is
exfiltration.

**Sensitive context extraction.** The assembled context holds credentials, another user's data, private source, or
values that grant access, and user-influenced output can expose them. Revealing generic instructions is not a
finding.

## Moves

- Draw four maps: each execution identity, each capability, each writable context or memory source, each output
  destination. Connect the principal at the start to the authority at the end.
- Start at side-effecting tools and walk backward through dispatcher, schema, confirmation, context, retrieval, and
  ingestion. Start at memory reads and find every writer.
- Compare direct, queued, retried, resumed, batched, and delegated paths to the same action; the strongest gate must
  run after the arguments are final and before every side effect.

## Validation rules

1. Name the attacker, the affected principal or shared resource, the execution identity, the target, and the
   unauthorized or unrequested action or disclosure.
2. A confused-deputy finding shows that the handler lacks requester-and-resource authorization and that the attacker
   cannot do the same action directly. An action-binding finding shows content causing an action the affected
   principal did not request.
3. A memory or retrieval finding cites both the attacker's write and the later cross-principal read or privileged
   decision.
4. Use a local model stub or recorded responses to show the effect; do not run harmful actions for real.
5. External server identity, provider behavior, or renderer behavior that decides the outcome makes the candidate
   `needs_validation`.
