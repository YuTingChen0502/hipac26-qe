# B1 Type B freeze

Status: frozen for the tested `B1-si1000-gamma` case.

## Frozen launch

- Build: `G4X`
- Case: `B1-si1000-gamma`
- `nk`: `1`
- MPI ranks: `8`
- Active GPUs: `8`
- Allocated nodes: `1`
- Ranks per node: `8`
- OpenMP threads: `12`
- Rank/GPU mapping: one MPI rank per active GPU
- Expected rank layout: `8`
- Profiler: disabled

## Evidence chain

- e001: 4/8/16 GPU coarse scaling;
- e002: 6-versus-8 single-node refinement;
- e003: independent 6-versus-8 confirmation;
- e004: independent 8-versus-16 node-boundary confirmation.

## Final evidence

- e004 `r16/r8` median ratio: `1.263007433`;
- e004 r8 latency reduction: `20.824%`;
- e004 paired wins: `5/5`;
- combined e001+e004 `r16/r8` ratio: `1.272039859`.

## Claim boundary

This freeze is valid only for the tested B1 input, G4X build identity,
Nano4 H200 environment and fixed runtime conditions. It is not a
universal Gamma-only GPU-count rule.
