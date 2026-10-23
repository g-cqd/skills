# Cloud and deployment

Use when the target defines or relies on IAM, infrastructure as code, containers, Kubernetes, a service mesh,
serverless or edge runtimes, ingress, cloud events, object storage, or runtime configuration.

## Discipline

- Establish the active configuration first: render the templates, overlays, and values the repository uses for each
  environment. A finding is about the deployed object, not an unused default.
- Name the lower-trust caller or workload, the identity that performs the final operation, the selector the caller
  controls, the resource, and the unauthorized operation or disclosure.
- Cloud IAM and application authorization are separate checks; one does not imply the other.
- Missing network controls alone are not a finding; a reachable sensitive interface is. Attached policies, drift, and
  provider defaults outside the repository make a candidate `needs_validation`.

## Classes

**Workload identity overreach.** A pod, function, node, or edge worker identity can act beyond its role, and request
or job input selects the target.

**Cross-account role confusion.** Role assumption, external ids, token exchange, or workload federation accept claims
not bound to the intended account, audience, repository, namespace, or workload.

**App authorization from cloud metadata.** The application trusts identity headers, tags, labels, or account ids
without proof that the control plane or a trusted proxy set them.

**Management-plane reachability.** An ingress, service, port, security group, or bind address exposes an admin,
debug, metrics, node, or control-plane API to a lower-trust network.

**Proxy and mesh bypass.** A backend accepts forwarded identity or mTLS metadata from peers outside the intended
ingress or sidecar, or a second port or a health path skips the mesh.

**Metadata service reachability.** An untrusted URL reaches instance or container metadata, control-plane sockets, or
internal APIs with the workload's credentials (with SSRF from `attack-classes.md`).

**Host capability exposure.** A less-trusted workload can request privileged mode, capabilities, host namespaces,
host paths, devices, the container runtime socket, or service-account tokens that reach node or cluster authority.

**Admission path inconsistency.** One deployment route enforces image, namespace, secret, or privilege policy and
another (a controller, a job, an upgrade, a restore) does not.

**Label and namespace trust.** Network, admission, secret, or identity policy matches labels, annotations, or
namespaces that a less-trusted principal can set.

**Security-control precedence drift.** Development values, chart defaults, environment variables, flags, or regional
overlays disable authentication, TLS, tenant scoping, or audit in a deployed environment.

**Secret exposure across workloads.** Secrets in logs, crash reports, process arguments, shared environments, broad
volumes, build outputs, or read APIs that another workload or tenant can reach.

**Credential renewal fallback.** A failed mount, refresh, rotation, or revocation leaves stale credentials active or
switches the app to a weaker identity mode.

**Object storage and signed URLs.** Bucket policies, object keys, CDN origins, or signed URLs that do not bind the
principal, operation, object namespace, audience, or expiry; list and version operations and writes as well as reads.

**Event-source identity.** A function trusts fields in the event body as the source without checking the provider's
signed envelope, subscription, account, region, and replay state.

**Edge and origin mismatch.** An edge runtime assumes a secret, isolation, or tenant policy that differs from the
origin, and falling back to the origin changes authority or caching.

## Moves

- Render every maintained environment into a matrix: exposed port, workload identity, network peers, mounted secrets,
  cloud resources. Each difference needs a reason.
- Follow a lower-trust request, object, label, or event into cloud policy, and show which credential performs the
  final operation.
- Compare normal deploy, migration, restore, failover, and emulator paths, and behavior when the mesh, admission,
  identity, or secret service is down.

## Validation rules

1. Use the active source path and the rendered object; if the effective attachment is not visible, use
   `needs_validation` and name it.
2. Check provider and orchestrator defaults for the pinned versions; do not assume a public IP, a reachable metadata
   service, or a missing admission controller.
3. Validate locally only: render templates, evaluate policy, inspect an isolated container, or run an emulator with
   dummy identities. Never probe live endpoints or change shared cloud resources.
