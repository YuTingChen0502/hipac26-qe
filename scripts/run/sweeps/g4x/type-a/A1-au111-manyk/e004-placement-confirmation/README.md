# e004 Placement Confirmation

Independent confirmation of the e003 pool-placement result.

Fixed conditions:

- G4X executable and Type A input identity unchanged
- 2 allocated nodes
- 14 active MPI ranks / GPUs
- OpenMP threads = 12
- nk = 7
- 2 ranks per k-point pool

Candidates:

- map7x7: rank layout 7,7
- map8x6: rank layout 8,6

Protocol:

- five measured repeats per candidate
- balanced interleaved order
- e004 begins with map8x6 because e003 began with map7x7

Freeze gate:

- all ten trials pass raw verification
- e004 median favors map8x6
- at least four of five matched repeats favor map8x6
- candidate CV values do not exceed 5%
- combined e003+e004 median improvement is at least 3%
