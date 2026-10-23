# Protocols, RPC, and messaging

Use when the target speaks gRPC, GraphQL over a custom transport, Protobuf, Thrift, Cap'n Proto, a custom binary or
text protocol, or uses queues, brokers, pub/sub, webhooks, or streaming RPC.

## Discipline

- Name the producer or peer, the accepted message, the authenticated channel identity, the affected principal or
  resource, and the unauthorized change or disclosure.
- The channel identity (mTLS, workload identity, broker credentials) and the principal named in the message must be
  bound by deterministic policy; a field the caller sets is not identity.
- Delivery guarantees (at-least-once, ordering per partition) come from the broker's configuration; establish them
  before claiming a replay or ordering defect.

## Classes

**Boundary and canonicalization disagreement.** Two components disagree on length, compression, duplicate or unknown
fields, encoding, numeric width, normalization, or envelope-versus-body precedence.

**Union, enum, and default confusion.** Unknown variants, missing discriminators, zero values, or default privileges
reach code that assumes a validated case; old consumers read new fields differently.

**Envelope and payload mismatch.** Authorization uses routing or envelope metadata while the handler acts on a
different tenant, account, subject, or sender named in the body.

**Interceptor coverage gaps.** An authentication or authorization interceptor covers unary calls but not streams,
reflection, health, gateway-transcoded routes, or each message of a stream.

**Peer identity to principal confusion.** The channel is authenticated, and a caller-controlled field selects the
user or tenant.

**Per-item and streaming authorization.** A stream, subscription, or batch is authorized once, then later items name
other resources or continue after a role change or revocation.

**Reply correlation.** Predictable, reused, or cross-tenant correlation ids let one caller's response, webhook,
cancellation, or acknowledgment satisfy another caller's pending operation.

**Topic and subscription scope.** A publisher or subscriber can choose another tenant's topic, wildcard, consumer
group, partition, reply queue, or dead-letter route.

**Dead-letter and diagnostic disclosure.** Failed messages land in error topics, traces, or operator views that a
lower-trust consumer can read, with secrets or other tenants' data.

**Untrusted producer as control plane.** A message body declares itself an admin event, provider callback,
replication record, or migration instruction without an authenticated producer.

**Duplicate delivery.** Redelivery repeats a side effect because deduplication is missing, runs after the mutation,
or uses a key that collides across tenants.

**Stale and out-of-order messages.** Older state, revoked membership, or canceled work arrives late and overwrites
newer state.

**Acknowledgment ordering.** Ack before durable commit loses security-relevant work; commit before ack duplicates a
mutation.

**Partial multi-consumer transitions.** Several consumers implement one transition and a partial failure leaves only
some committed.

## Moves

- Draw producer → transport → gateway → consumer → storage for each message family, with the authenticated peer, the
  authoritative fields, the validation, and the side effect at each hop.
- Feed the same small fixture to every schema version and language binding in the repository; include duplicate,
  missing, unknown, boundary, replayed, and reordered messages.
- Compare normal, retry, dead-letter, replay, migration, reflection, stream, and transcoded routes.

## Validation rules

1. A disagreement finding cites both parsers or consumers and the divergent decoded value; a safe rejection by
   either side prevents confirmation.
2. A replay or ordering finding establishes the actual delivery guarantee and reproduces the failure with an
   in-memory or local transport.
3. Broker ACLs, gateway routes, or service identities outside the repository make the candidate `needs_validation`.
