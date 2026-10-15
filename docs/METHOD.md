# Method and limitations

## Evaluation method

The CLI uses 1,000 deterministic routing keys and an intentionally degraded candidate. Stable samples score 0.92 and candidate samples 0.55. A rollback is expected when the observed candidate drop exceeds 0.05. These values test control behavior; they are not evidence of model quality.

Evidence integrity is tested separately: a passing record is bound to a canonical, sorted JSON manifest digest. Mutating each of the four default dependencies must invalidate the record. An explicit narrow scope is tested as a control.

## Assumptions

- The caller supplies trustworthy, comparable metric samples.
- Route keys are stable and non-sensitive before hashing.
- One independent approval is sufficient for this demo.
- Bundle dictionaries contain JSON-serializable data.

## Limitations and risks

- In-memory state disappears at process exit; production use needs transactional durable storage.
- Actor names are not authenticated identities and audit events are not tamper-evident.
- Small canaries can produce noisy estimates; there are no confidence intervals or minimum sample gates yet.
- A single aggregate metric can hide subgroup regressions.
- Narrow dependency scopes reduce retesting but can legitimize stale evidence when chosen incorrectly.
- Rollback compatibility is not checked; restoring an older prompt against a changed tool contract may fail.

## Success criteria for this MVP

- Every promoted version has current passing evidence and independent approval.
- 4/4 scoped configuration mutations invalidate existing evidence.
- A synthetic harmful candidate receives a bounded cohort and is automatically removed.
- The full decision trail exports without external services.
