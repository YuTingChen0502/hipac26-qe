# e004-node-boundary-confirmation

Status: complete; decision `FROZEN_R8_ONE_NODE`.

## Purpose

Confirm whether crossing the node boundary from the confirmed
single-node `r8` configuration to `r16` across two nodes improves or
degrades `B1-si1000-gamma`.

## Fixed conditions

- Build: `G4X`
- Canonical B1 input
- `nk=1`
- OpenMP threads: `12`
- One MPI rank per active GPU
- Two allocated H200 nodes
- Eight GPUs allocated per node
- Node `25a-hgpn144` excluded

## Candidates

| Candidate | MPI ranks | Active GPUs | Active nodes | Layout |
|---|---:|---:|---:|---|
| `r8` | 8 | 8 | 1 | `8` |
| `r16` | 16 | 16 | 2 | `8,8` |

Five paired trials per candidate are executed in one two-node
allocation with alternating candidate order.

This is a case-specific node-boundary confirmation, not a universal
Gamma-only scaling rule.
