# Bad feature flag

## Symptoms
- Errors isolated to one code path (e.g. pricing)
- Error rate jumped right after a flag change
- No deploy in the last hour

## Diagnosis
1. Check `get_recent_deploys` — any deploy recently? If not, suspect a flag.
2. Check `get_service_status` / `GET /ops/flags` — which flags changed?
3. Check `query_logs` for the flag name in error messages.

## Fix
- **toggle_flag** back to the previous value.
- Verify the affected path recovers.

## Notes
- Flag toggles are compensated by toggling back.
