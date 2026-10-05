# Dependency down

## Symptoms
- Sudden spike in 5xx across all endpoints
- Logs: `connection refused to <dependency>:<port>`
- The dependency service is unreachable

## Diagnosis
1. Check `query_logs` for "connection refused".
2. Check `get_service_status` for the named dependency.
3. Confirm the dependency process is not running.

## Fix
- **start_service** for the dead dependency (world group only).
- Verify checkout error rate recovers.

## Notes
- If the dependency cannot be started, escalate to a human.
