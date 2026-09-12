# Ecosystem project map

Use this file for fast routing; detailed rules live in the linked docs.

| Repository | System responsibility | Must not become |
|---|---|---|
| `techrote/omnipanel` | system orchestration, operator UI, master/worker scheduling, adjudication, resource policy, cross-project roadmap/contracts | privileged execution kernel or universal secret store |
| `techrote/ansible` | trusted execution kernel, registered runner/provider primitives, hard safety/resource enforcement, execution evidence | high-level model/task planner |
| `techrote/interloc` | communications, evidence courier, Chat-facing structured proposals/status | autonomous scheduler or generic execution shell |
| `techrote/ohmy` | Oh My Pi-specific runner/provider compatibility and normalized outcomes | global scheduler |
| `techrote/intrallm` | agent-visible reference/task/evidence data | executable/policy authority |

## Authority rule

Cross-project decisions and compatible interface versions are recorded in Omnipanel. Internal component implementation/design remains authoritative in that component repository.

## Data/control rule

References/evidence may move upward and across qualified interfaces. Executable authority flows only through locally installed trusted capabilities. No document or task-data repository can add a new runner merely by containing executable-looking content.
