# e004 Post-processing Recovery

## Incident

Slurm job `203925` completed normally with ten of ten QE trials.
The first offline verification incorrectly returned
`energy_reference_missing` for all ten trials.

## Root cause

The verifier was extended from six-trial experiments to e004,
but its energy-reference guard remained hard-coded to six.

Original condition:

    len(valid_energies) == 6

Corrected condition:

    len(valid_energies) == expected_trials

## Recovery

The preserved e002, e003 and e004 raw outputs were reprocessed.
All three experiments passed regression.
No QE job was resubmitted.
