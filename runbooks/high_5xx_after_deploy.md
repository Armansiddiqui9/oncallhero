# High 5xx after deploy

## Symptoms
- 5xx error rate above 5% within minutes of a deploy
- Errors correlate with the new version
- Latency may also spike

## Diagnosis
1. Check `get_recent_deploys` — what version was just deployed?
2. Check `query_metrics` — does the error rate track the deploy time?
3. Check `query_logs` for exceptions mentioning the new version.

## Fix
- **rollback_deploy** to the previous known-good version.
- Wait, then verify error rate is back under 2%.

## Notes
- Do NOT restart the service: the bug is in the code, not the process state.
- Do NOT toggle feature flags unless the deploy was a flag change.
