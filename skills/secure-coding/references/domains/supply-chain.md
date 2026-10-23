# Supply chain, CI, and release

Use when the target resolves dependencies, generates code, runs CI workflows, builds, signs, publishes, updates
itself, or loads plugins and extensions.

## Discipline

- A finding names a lower-trust actor (a fork, a contributor, a public registry, a less-trusted job), the input it
  controls (a package name, a branch, a cache entry, an artifact, metadata), the trusted consumer, and the result:
  unauthorized publication, code in a release, a disclosed secret, or privileged execution.
- Artifact identity must hold across every handoff: build, test, sign, promote, publish. A mutable name or an unbound
  digest between two steps is the usual defect.
- Hosted controls (branch protection, environment approvals, registry settings, signing service policy) may be
  invisible in the repository; when decisive, use `needs_validation`.
- Missing least privilege alone is hardening; a reachable privileged action is a finding.

## Classes

**Dependency source confusion.** The resolver can pick an unintended public or private namespace, a fallback
registry, a mirror, or a source URL. Check package names, source priority, lockfile and checksum use, alternate build
files, and platform-specific resolution.

**Mutable build inputs.** The build uses branches, tags, unpinned submodules, downloaded tools, remote includes,
floating CI actions (`uses: org/action@main`), or container tags that can change without review.

**Generated content without provenance.** Schemas, vendored archives, generated clients, or binary blobs produce
shipped content without the review and integrity gate source gets. Regenerate locally and compare.

**Build-context inclusion.** Secrets, local configuration, `.git` metadata, or developer artifacts enter a package or
image because the build context exceeds the release inputs.

**Untrusted code in a privileged workflow.** A pull request from a fork, an issue comment, or a dependency update runs
contributor code with secrets, write tokens, deployment rights, or a trusted runner (`pull_request_target` with a
checkout of the head ref is the classic case).

**Workflow injection.** Branch names, commit messages, issue titles, artifact names, or matrix values reach shell
commands, `${{ }}` expressions, or paths without validation.

**Cache, artifact, and workspace mixing.** A lower-trust job populates a cache, artifact, or workspace that a
higher-trust job later restores and runs or releases.

**Automation identity overreach.** A CI token has more permission, repository, environment, or lifetime than the job
needs, and untrusted input can choose what it acts on.

**Build-to-promotion substitution.** Test, review, signature, and publication refer to mutable tags, file names, or
artifact ids rather than one immutable digest.

**Release authorization and signing.** A release or signature is accepted from the wrong workflow, repository,
branch, environment, key, or threshold; the consumer checks that a signature is valid, not whose it is.

**Update metadata and rollback.** An updater authenticates the payload but not the version, product, platform,
channel, target path, expiry, or rollback state, or mixes metadata and payload from different releases.

**Plugin trust expansion.** A plugin gains host authority beyond its declared scope, a publisher can replace another
publisher's identity, or install hooks run before authenticity and capability checks.

## Moves

- Walk backward from a released digest or an installed update to every source, generated input, credential, runner,
  cache, test result, and approval.
- Put untrusted and protected workflow triggers side by side and mark every persisted channel between them.
- Read the failure paths: revoked key, failed download, missing attestation, partial release, rollback, registry
  outage.

## Validation rules

1. Name the actor, the controllable input, the trusted consumer, and the result.
2. Show artifact identity breaking across one handoff that a real consumer uses.
3. Check the package manager, host, registry, and signing defaults for the pinned versions.
4. Validate with a throwaway local repository, a dummy credential marker, a local registry, and a non-production
   namespace. Never publish or change a real release.
