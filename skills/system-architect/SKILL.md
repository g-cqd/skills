---
name: system-architect
description: >-
  Language-agnostic: design infrastructure, CI/CD, Terraform, containers, Kubernetes,
  observability, progressive delivery, and disaster recovery. Use for deployment
  pipelines, cloud architecture, reliability, scalability, alerting, or recovery targets.
  For application profiling, use `performance-engineering`; for code security, use
  `secure-coding`; for work planning, use `planner`.
allowed-tools:
  - Read
  - Glob
  - Grep
---

# System Architect

This skill covers **the system around the code**: how it is built, deployed, observed, and
recovered. Application performance belongs to `performance-engineering`. Application security
belongs to `secure-coding`.

## Contract

```
§PRIORITY safety ≻ correctness ≻ reliability ≻ recoverability ≻
          observability ≻ performance ≻ cost ≻ velocity ≻ elegance
          ⇒ lower ¬push higher below its stated target
§ANALYZE  ! emit <analysis> block BEFORE proposing architecture
§EXPLICIT ! define IaC ∧ CI/CD ∧ security ∧ observability strategy ¬implicit
§PROVEN   proven-patterns ≻ novel ∷ immutable-infra · GitOps · progressive-delivery
§RISK     ∀recommendation ! paired-risk + mitigation
§BAN      untested-backup · alert ∅runbook · manual-console-change ·
          vague recovery-goal · security-as-afterthought
```

---

## 1. Decision priority hierarchy

Apply in strict order. **A lower-priority concern must not push a higher item below its stated
target.**

```
1. SAFETY         Human safety, data integrity, legal compliance
2. CORRECTNESS    Behaves as specified under all conditions
3. RELIABILITY    Fault tolerance, graceful degradation, self-healing
4. RECOVERABILITY RTO/RPO met, backup and restore actually tested
5. OBSERVABILITY  Logs, metrics, traces, actionable alerts
6. PERFORMANCE    Latency, throughput, resource efficiency
7. COST           Right-sizing, spot, reserved capacity
8. VELOCITY       Developer experience, deployment frequency
9. ELEGANCE       Clean, minimal — never at the expense of the above
```

When a proposal or an existing design lets a lower item outrank a higher one (for example cost
over recoverability, or velocity over correctness), name the conflict in your answer.

## 2. Pre-implementation analysis

Emit this block before you propose a new architecture or a change to an existing one. A direct
question about one setting or one command does not need the block.

```xml
<analysis>
  <Objective><!-- business or technical goal --></Objective>
  <Requirements>
    <Functional><!-- user-facing capabilities --></Functional>
    <NonFunctional>
      <Scalability><!-- X requests/sec, Y concurrent users --></Scalability>
      <Availability><!-- 99.9%, 99.99% --></Availability>
      <RTO_RPO><!-- recovery time / recovery point objectives --></RTO_RPO>
      <Compliance><!-- SOC2, HIPAA, GDPR, PCI-DSS --></Compliance>
    </NonFunctional>
  </Requirements>
  <CurrentState><!-- existing architecture, infra, processes --></CurrentState>
  <ProposedArchitecture><!-- design, with risks and mitigations --></ProposedArchitecture>
</analysis>
```

**Numbers, not adjectives.** "Highly available" is not a requirement; "99.95% monthly, RTO 15
minutes, RPO 5 minutes" is. Topology, cost, and on-call load follow from these numbers, so get
them first. If the user gives no numbers, state the numbers you assume and label them as
assumptions.

Before finishing, check the proposed design against the same numbers: the topology meets the
availability target, and the backup and failover path meets RTO and RPO.

## 3. Architecture patterns

| Do this | Avoid this |
|---|---|
| **Design for failure** — health checks, retries with backoff, circuit breakers | Assuming components never fail |
| **Loose coupling** — queues, APIs, event buses | A tightly coupled distributed monolith |
| **Horizontal scalability** — stateless services | Relying solely on vertical scaling |
| **Security by design** — defense in depth at every layer | Security as an afterthought |
| **Immutable infrastructure** — replace, do not patch | Mutable servers and configuration drift |
| **GitOps** — declarative state in Git, reconciled by operators | Manual `kubectl apply` and console clicks |

A distributed monolith has the operational cost of microservices and the coupling of a monolith.
Check for one when services must be deployed together.

## 4. CI/CD

- **Stages** — lint and format, build, unit test, integration test, security scan, package,
  deploy, smoke test.
- **Cheapest stages first.** Order stages by cost so that a lint failure does not wait for an
  integration suite.
- **Cache** dependencies and build outputs, keyed on lockfile hashes.
- **Matrix builds** for platform and version coverage.
- **OIDC, not long-lived credentials,** for cloud deploys. A static cloud key in CI secrets is a
  finding.
- **Reusable workflows and composite actions** to share pipeline logic across repositories.
- **A failing pipeline on the main branch blocks other merges until it is fixed.** A pipeline that
  fails routinely no longer signals anything.

## 5. Containers and orchestration

- Use multi-stage builds. Ship the minimal runtime layer, not the build toolchain.
- Pin base images by digest. Run as non-root. Use a read-only root filesystem unless the workload
  must write to it.
- Declare resource requests and limits. A container without limits can starve other workloads on
  the node.
- Liveness and readiness probes answer **different questions**: "must this container restart"
  versus "may this container receive traffic". Using one probe for both causes restart storms
  under load.

## 6. Observability

**Golden signals** — monitor these first: latency (p50, p95, p99), traffic, errors, and
saturation.

**Alert quality** — each alert must:

- **Name the action** the responder takes, in the linked runbook.
- **Indicate user impact** — a symptom users feel, not an internal metric that drifts.
- **Fire early enough** for the responder to act before users feel the impact.
- **Carry context** — what fired, where, and the runbook link.

An alert that fails one of these checks trains people to ignore alerts. Rewrite it so that a
responder knows what to do. If no rewrite can give it an action, recommend deleting it; do not
delete an alert without the user's approval.

## 7. Security, shift-left

Scan in the pipeline, not after deploy: dependency and CVE scanning, secret detection, IaC
misconfiguration scanning, container image scanning. Fail the build on severity thresholds agreed
in advance. Application-level review belongs to `secure-coding`.

## 8. Cost

Right-size from measured utilization, not from the instance type chosen at setup. Recommend
reserved capacity for the predictable baseline; do not buy or commit to reservations without the
user's approval. Use spot capacity only for stateless or batch workloads that tolerate
interruption. Set budget alerts. Cost is priority 7: it must not push recoverability or
reliability below their stated targets.

## 9. Disaster recovery

| Do this | Avoid this |
|---|---|
| **Define and test RTO/RPO** | Vague recovery goals |
| **Automated failover** — health-based DNS or load-balancer routing | Manual intervention required |
| **Regular DR drills** in a production-like environment | Writing the plan and never testing it |
| **Chaos engineering** — proactive failure injection | Waiting for a real outage to learn |
| **Multi-region** — active-active or active-passive | Single-region dependency |

**DR testing checklist**

- [ ] Database restore tested **within RTO**
- [ ] Failover to the secondary region tested
- [ ] Runbooks executed by on-call — **not by their author**, because a runbook is correct only
      if someone who did not write it can follow it
- [ ] Communication plan tested
- [ ] Post-incident review process verified

## Boundaries

| Need | Skill |
|---|---|
| Application profiling, latency percentiles, load-test design | `performance-engineering` |
| Application code security, OWASP, crypto | `secure-coding` |
| Decomposing and sequencing the work | `planner` |
| ADRs and design documents | `work-docs` |
| Commit, branch, and release flow | `engineering-practices` |
| Apple-specific build and CI invocation | `xcode` |

## References

`references/guidelines.md` — full standards: IaC module structure, GitHub Actions examples
(monorepo matrix with caching and services, reusable deployment with OIDC, composite Terraform
action), production Dockerfile and Kubernetes patterns, shell-script template, security scanning
pipeline, and the complete cost and DR sections.
