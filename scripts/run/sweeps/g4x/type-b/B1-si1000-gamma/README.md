# B1-si1000-gamma

Canonical Type B Gamma-only case.

Case identity:

    Atoms: 1000
    Actual k-points: 1
    Gamma-only: yes
    nk: 1
    OpenMP threads per rank: 12
    Mapping: 1 MPI rank per GPU

Tuning order:

    intra-node GPU scaling
      -> node-boundary crossover
      -> optional Gamma-only workload-size ladder

This is a project-defined representative case, not an official universal
Quantum ESPRESSO benchmark class.
