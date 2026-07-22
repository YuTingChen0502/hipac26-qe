# e002-resource-shape

Status: ready after validation.

With nk=7 fixed, compare:

    r7:
      7 MPI ranks
      7 GPUs
      1 active node
      1 rank per pool

    r14:
      14 MPI ranks
      14 GPUs
      2 active nodes
      2 ranks per pool

This is a resource-shape comparison, not a pure GPU scaling law.

Decision gate:

    r7 clearly wins:
      prefer one rank per pool;
      e003 becomes low priority.

    r14 is competitive or wins:
      continue to e003-pool-placement.

    noisy:
      perform controlled confirmation only;
      do not rerun e001.
