# e004 Placement Confirmation Result

## Execution

- Slurm job: `203925`
- State: `COMPLETED`
- Exit code: `0:0`
- Nodes: `25a-hgpn[074-075]`
- Expected trials: 10
- Actual trials: 10
- Execution failures: 0
- Corrected raw verification: `PASS`
- QE rerun required: no

## Independent confirmation

| Candidate | Raw wall times | Median | Mean | CV |
|---|---|---:|---:|---:|
| map7x7 | 20.80, 20.81, 20.82, 20.88, 20.78 | 20.810 s | 20.818 s | 0.181% |
| map8x6 | 18.72, 18.44, 19.10, 19.52, 18.46 | 18.720 s | 18.848 s | 2.444% |

- e004 map8x6/map7x7 ratio: `0.899567516`
- e004 improvement: `10.043%`
- matched-repeat wins for map8x6: `5/5`

## Combined e003 and e004

- map7x7 combined median: `20.850 s`
- map8x6 combined median: `19.285 s`
- combined ratio: `0.924940048`
- combined improvement: `7.506%`

## Freeze decision

- all ten e004 trials valid: `True`
- independent result has same direction: `True`
- paired wins at least 4/5: `True`
- combined improvement at least 3%: `True`
- candidate CV at most 5%: `True`
- Type A freeze: **PASS**
