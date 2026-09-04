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

This skill owns **the system around the code**: how it is built, deployed, observed, and
recovered. It does not own application performance (`performance-engineering`) or application
security (`secure-coding`).

## Contract

```
§PRIORITY safety ≻ correctness ≻ reliability ≻ recoverability ≻
          observability ≻ performance ≻ cost ≻ velocity ≻ elegance
          ⇒ lower NEVER compromises higher
§ANALYZE  ! emit <analysis> block BEFORE proposing architecture
§EXPLICIT ! define IaC ∧ CI/CD ∧ security ∧ observability strategy ¬implicit
§PROVEN   proven-patterns ≻ novel ∷ immutable-infra · GitOps · progressive-delivery
§RISK     ∀recommendation ! paired-risk + mitigation
§BAN      untested-backup · alert ∅runbook · manual-console-change ·
          vague recovery-goal · security-as-afterthought
```

---

## 1. Decision priority hierarchy

Apply in strict order. **A lower-priority concern never compromises a higher one.**

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

Most bad architecture decisions are a lower item quietly outranking a higher one — cost beating
recoverability, velocity beating correctness. Name it when you see it.

## 2. Pre-implementation analysis

Emit before proposing anything:

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
minutes, RPO 5 minutes" is. Topology, cost, and on-call load all follow from those numbers, so
extracting them is the first real work.

Before finishing, check the proposed design against those same numbers: does the topology
actually meet the availability target, and does the backup and failover path meet RTO and RPO?
A design that never gets compared back to its targets is where the priority hierarchy quietly
inverts.

## 3. Architecture patterns

| Do this | Avoid this |
|---|---|
| **Design for failure** — health checks, retries with backoff, circuit breakers | Assuming components never fail |
| **Loose coupling** — queues, APIs, event buses | A tightly coupled distributed monolith |
| **Horizontal scalability** — stateless services | Relying solely on vertical scaling |
| **Security by design** — defense in depth at every layer | Security as an afterthought |
| **Immutable infrastructure** — replace, do not patch | Mutable servers and configuration drift |
| **GitOps** — declarative state in Git, reconciled by operators | Manual `kubectl apply` and console clicks |

A distributed monolith is the worst outcome available: the operational cost of microservices with
the coupling of a monolith. Check for it whenever services must be deployed together.

## 4. CI/CD

Design the pipeline as a product with its own requirements: fast feedback, reproducibility, and a
trustworthy signal.

- **Stages** — lint and format, build, unit test, integration test, security scan, package,
  deploy, smoke test.
- **Fail fast, cheap first.** Order stages by cost; a lint failure should never wait behind an
  integration suite.
- **Cache deliberately** — dependencies and build outputs keyed on lockfile hashes.
- **Matrix builds** for platform and version coverage.
- **OIDC over long-lived credentials** for cloud deploys. A static cloud key in CI secrets is a
  finding.
- **Reusable workflows and composite actions** keep pipeline logic DRY across repositories.
- **A red pipeline is a stop-the-line event.** A routinely-red pipeline has already stopped being
  a signal.

## 5. Containers and orchestration

- Multi-stage builds; ship the minimal runtime layer, not the build toolchain.
- Pin base images by digest. Run as non-root. Read-only root filesystem where possible.
- Declare resource requests and limits — an unbounded container is a noisy neighbour.
- Liveness and readiness probes answer **different questions**: "should I be restarted" versus
  "should I receive traffic". Conflating them causes restart storms under load.

## 6. Observability

**Golden signals** — monitor these before anything else:

| Signal | Meaning |
|---|---|
| **Latency** | Time to serve requests (p50, p95, p99) |
| **Traffic** | Requests per second |
| **Errors** | Rate of failed requests — 5xx, timeouts |
| **Saturation** | Resource utilization — CPU, memory, I/O |

**Alert quality** — every alert:

- **Names the action** the responder takes, in the alert text or the linked runbook
- **Indicates user impact** — a symptom users feel, not an internal metric drifting
- **Fires early enough** to act before the impact lands
- **Carries context** — what fired, where, and the runbook link

An alert failing any of these trains people to ignore alerts, which is worse than not having it.
Rewrite it so a responder knows what to do, or delete it.

## 7. Security, shift-left

Scan in the pipeline, not after deploy: dependency and CVE scanning, secret detection, IaC
misconfiguration scanning, container image scanning. Fail the build on severity thresholds agreed
in advance rather than argued during an incident. Application-level review is `secure-coding`.

## 8. Cost

Right-size from measured utilization, not from the instance type someone picked once. Spot and
reserved capacity for predictable workloads. Set budget alerts. Cost is priority 7 — it never
justifies weakening recoverability or reliability, but unexamined cost is a real failure of
stewardship.

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
- [ ] Runbooks executed by on-call — **not by their author**
- [ ] Communication plan tested
- [ ] Post-incident review process verified

The author-versus-on-call distinction catches the real gaps: a runbook is only correct if someone
who did not write it can follow it at 3am.

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
