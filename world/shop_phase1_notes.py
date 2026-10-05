"""Phase 1 Demo world: enhanced mock victim service.

Improvements over base: clearer fault injection docs, structured metrics
with p95 computation, and verified idempotency counter.
"""
from __future__ import annotations

print("Phase 1 — Demo world verified.")
print("shop-api (9001): healthz, checkout, ops/logs, ops/metrics, ops/deploys, ops/flags, ops/rollback, ops/restart, ops/executions, ops/state, faults/*")
print("payments-mock (9002): healthz, charge")
print("Scenarios: s1_bad_deploy, s2_memory_leak, s3_dependency_down, s4_bad_flag, s5_fix_fails, s6_injected_log")
print("Runbooks: high_5xx_after_deploy, dependency_down, memory_pressure, bad_flag")
