# How `work` admits jobs, and why

`work` (`scripts/work.py`) admits a job on the cores its command is predicted to use, not on the weight it
declares. This page gives the evidence for that policy, called policy R below, and lists what was tried and dropped.

## The evidence

A trace-driven simulator replayed 1,360 recorded jobs on a model of this machine (8 cores, 16 GiB, processor
sharing among running jobs). Replayed with today's policy, it reproduces the measured waits of the 1,278 jobs
recorded after the idle and memory gates existed:

| | measured | simulated |
|---|---|---|
| mean wait | 69.7 s | 73.8 s |
| p90 wait | 253 s | 253 s |

What the trace showed:

- **Declared weights overstate real use by 2.75 times.** The median job uses about 1 core at every declared weight
  from 1 to 8. A capacity counted in declared cores leaves cores idle while jobs wait.
- **Exclusive jobs cause most of the waiting.** A job as heavy as the CPU count drains the machine before it starts.
  They belong to a task's final timing numbers only, one job per task.

## Policy R against today's policy

Closed loop: each agent's next job asks when its previous one ends, as agents do. The table gives the medians over
6 perturbed copies of the trace; each copy shifts arrivals, think times and CPU work at random.

| policy | mean wait | p90 wait | max wait | total wait | CPU overload | memory overload |
|---|---|---|---|---|---|---|
| today: declared weights, first in first out | 73.0 s | 157 s | 2,386 s | 27.6 h | 0.20 h | 0.24 h |
| R: predicted cores, shortest predicted first, aging 1 | 54.9 s | 86 s | 2,212 s | 20.7 h | 0.25 h | 0.35 h |

The paired change in total wait, copy by copy, has a median of -19%. In open loop, with arrivals replayed as
recorded, R cut total waiting by 59% (unbatched) to 64% (exclusive jobs batched): 97.5 h today, against 41.7 h and
35.9 h (aging 0.25 in that run). Overload stayed small: in closed loop, CPU overload rose by 0.05 h and memory
overload by 0.11 h over the whole trace.

## What R does

1. **Predicted cores.** The median of the average cores (CPU time over run time) of the last 5 runs of the most
   specific signature that has enough runs: the whole command (1 run), then program and flags (2), then program and
   subcommand in this place (3), then program and subcommand anywhere (3). The declared weight caps the prediction,
   and it is the estimate until history exists. Predicted memory is the largest of the last 5 peaks, and predicted
   run time the median of the last 5.
2. **Admission.** A job starts while the running jobs' predicted cores plus its own fit the CPU budget
   (`--cpu-budget`, default the CPU count). The idle gate (10%) and the kernel's memory-pressure gate stay.
3. **Memory on measured use.** No job starts while used memory (active, wired and compressed pages; on Linux
   MemTotal minus MemAvailable) is above the memory budget (`--memory-budget`, default the memory minus 2 GiB).
4. **Order.** Validity first, then the smallest predicted run time minus `--aging` (1) times the seconds waited, then
   the order of asking. Backfill counts predicted cores, and a head that has waited `--backfill-wait` still keeps
   every job behind it.
5. **Exclusive jobs stay exclusive.** A job as heavy as the CPU count holds the whole budget, whatever its history,
   and exclusive jobs waiting together run as one batch.
6. **QoS.** Jobs run at the utility QoS (`--job-qos`), through `taskpolicy -c utility` on macOS, and their children
   inherit it, so the user's own work comes first under contention. Exclusive jobs run at the default QoS, so their
   timings are not distorted.
7. **The capacity** (`--capacity`) remains an optional cap on declared weights, off by default.

## Tried and dropped

| idea | what the simulation showed |
|---|---|
| Booking a share of declared weights | Closed loop, 10 copies: the longest wait grew from 2,397 s to 3,928 s and memory overload from 0.24 h to 0.37 h |
| Admitting while the summed predicted memory peaks fit | Open loop, 6 copies: total wait 148.9 h, against 97.5 h today |
| An AIMD limit on the budget | No slowdown signal at this load. Closed loop, 10 copies: total wait unchanged at 24.8 h |
| EASY backfill on predicted run times | Closed loop, 10 copies: no gain on backfill in cores (18.4 h against 17.8 h), and memory overload 0.84 h |
| Shortest predicted first without aging | One replay, closed loop: one job waited 11,568 s |

## Sources

- Borg's reservations start at the request and decay toward measured use plus a margin, then jump back up on
  overrun: Verma et al., [Large-scale cluster management at Google with Borg](https://doi.org/10.1145/2741948.2741964),
  EuroSys 2015.
- Sizing from usage history instead of requests: Rzadca et al.,
  [Autopilot: workload autoscaling at Google](https://doi.org/10.1145/3342195.3387524), EuroSys 2020; and the
  Kubernetes Vertical Pod Autoscaler's recommender, a usage percentile plus a margin over a history window
  (`--target-cpu-percentile`, `--recommendation-margin-fraction`, `--history-length`,
  [flags](https://github.com/kubernetes/autoscaler/blob/master/vertical-pod-autoscaler/docs/flags.md)).
- Charging measured use keeps the allocation strategy-proof: Ghodsi et al.,
  [Dominant Resource Fairness](https://www.usenix.org/conference/nsdi11/dominant-resource-fairness-fair-allocation-multiple-resource-types),
  NSDI 2011.
- Scheduling on predicted sizes, robust to poor predictions: Purohit, Svitkina and Kumar,
  [Improving Online Algorithms via ML Predictions](https://proceedings.neurips.cc/paper/2018/hash/73a427badebe0e32caa2e1fc7530b7f3-Abstract.html),
  NeurIPS 2018; Mitzenmacher,
  [Scheduling with Predictions and the Price of Misprediction](https://doi.org/10.4230/LIPIcs.ITCS.2020.14), ITCS 2020.
- Small jobs first while keeping servers full: Grosof, Scully, Harchol-Balter and Scheller-Wolf,
  [Optimal Scheduling in the Multiserver-job Model under Heavy Traffic](https://doi.org/10.1145/3570612)
  (ServerFilling-SRPT), POMACS 2022.
- Utility work yields to the user's work: Apple,
  [Prioritize Work with Quality of Service Classes](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/PrioritizeWorkWithQoS.html),
  and [`DispatchQoS.QoSClass.utility`](https://developer.apple.com/documentation/dispatch/dispatchqos/qosclass-swift.enum/utility).
