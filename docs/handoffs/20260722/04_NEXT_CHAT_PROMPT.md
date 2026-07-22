# Prompt for the Next HiPAC 2026 QE Chat

You are taking over the HiPAC 2026 Quantum ESPRESSO optimization mainline.

I will provide:

- the 20260721 full project handoff;
- 00_READ_FIRST.md;
- 01_OPTIMIZATION_MAINLINE.md;
- 02_EXACT_EVIDENCE_MANIFEST.md;
- 03_INCIDENT_AND_VALIDATION_LEDGER.md;
- 04_NEXT_CHAT_PROMPT.md;
- the full evidence package;
- the latest weekly-update deck.

Your first reply must be a comprehension check only.

Answer all of the following precisely:

1. What is the overall project objective and evidence ladder?
2. What are the roles of G1, G1p, G4X and G4Xp?
3. Why do Type A many-k and Type B Gamma-only use different tuning paths?
4. What do e001, e002, e003 and e004 test?
5. What are the exact e002, e003 and e004 trial values, medians, ratios and winners?
6. How must jobs 203322, 203455, 203897 and 203925 be classified?
7. Why does a Slurm FAILED state not necessarily mean QE failed?
8. What are standalone bundles, the execution-only gate and the raw verifier?
9. What Type A configuration is frozen?
10. What is the exact scope and claim boundary of the freeze?
11. What is the next Type B mainline?
12. What claims remain unsupported?
13. Confirm explicitly that you have not modified files, committed, pushed,
    submitted jobs, rebuilt QE or rerun experiments.

Before I approve your comprehension:

- do not modify the repository;
- do not stage, commit or push;
- do not submit Slurm jobs;
- do not rebuild QE;
- do not rerun e001 through e004;
- do not move or delete run artifacts.

After comprehension is approved, the first task is read-only revalidation:

- branch, HEAD and origin;
- classified git status;
- Type A freeze artifacts;
- e002, e003 and e004 retention;
- raw-verification-v2 artifacts;
- Type B Stage 1 evidence inventory;
- partition, disk and excluded-node state;
- discrepancies between handoff and current nano4 state.
