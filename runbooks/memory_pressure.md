# Memory pressure

## Symptoms
- Heap usage climbing steadily
- p95 latency degrading over time
- Error rate rises slowly, then faster

## Diagnosis
1. Check `query_metrics` — is memory_mb climbing without bound?
2. Check `query_logs` for "heap usage high".
3. Correlate with deploy history (leak in current version).

## Fix
- **restart_service** to clear the heap.
- Verify memory drops and latency recovers.

## Notes
- Restarts are **non-compensable**: the process state is lost.
- If the leak is in the newest deploy, a rollback also works and is preferred.
