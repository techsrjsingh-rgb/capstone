---
tags: [governance, compliance, audit, fairness]
---

# 🛡️ Governance & Compliance

Source: `core/governance.py`, `core/hooks.py` · See also: [[Observability]], [[Architecture]]

---

## Overview

Every transaction passes through the `FraudHookManager` before and after the agent pipeline:

```
pre_process()  → validate → rate limit → sanitize → correlation ID → audit log
                                        ↓
                        FraudDetectionOrchestrator
                                        ↓
post_process() → compliance check → fairness check → audit log → metrics
```

---

## Input Validation (`GovernanceManager.validate_transaction`)

**Required fields:** `transaction_id`, `customer_id`, `amount`, `location`, `transaction_type`, `time`

**Rules:**
- `amount` must be non-negative number
- `transaction_type` must be one of: `purchase`, `withdrawal`, `transfer`, `deposit`, `payment`, `refund`
- `transaction_id` and `customer_id` cannot be empty strings

Returns `(is_valid: bool, errors: list[str])`

---

## Compliance Check (`GovernanceManager.check_compliance`)

Validates the pipeline's output decision:
- Decision must be in `{Safe, Suspicious, High Risk}` (case-insensitive)
- Reasoning must be ≥ 15 characters (meaningful explanation required)

If non-compliant: decision is overridden to `"Suspicious"` and `compliance_override: True` is added to the result.

---

## Fairness Check (`GovernanceManager.check_fairness`)

Detects potential bias: flags any `"High Risk"` decision where `amount < HIGH_AMOUNT_THRESHOLD` (₹1,00,000).

Rationale: *location alone* should not drive a High Risk classification for small transactions.

Returns `{has_flags: bool, flags: list[str]}`

---

## Rate Limiting (`RateLimiter`)

Token bucket algorithm:
- **Max requests:** 20 per minute (configurable via `RATE_LIMIT_REQUESTS`)
- **Window:** 60 seconds (sliding)
- Returns `(allowed: bool, message: str)` — message includes retry-after seconds if denied

---

## Audit Log (`audit.jsonl`)

Append-only JSONL file — one JSON object per line.

```json
{"timestamp": "2024-06-15T09:30:01Z", "correlation_id": "...", "agent": "pre_process", "action": "transaction_entry", "data": "..."}
{"timestamp": "2024-06-15T09:30:02Z", "correlation_id": "...", "agent": "post_process", "action": "decision", "data": "..."}
```

The audit log never crashes the pipeline (write errors are silently swallowed).

---

## Error Hook

If any agent in the pipeline throws an exception, `FraudHookManager.on_error()` returns a safe fallback:

```python
{
    "risk_level":   "Suspicious",
    "risk_score":   50.0,
    "fraud_reasons": ["Automated assessment failed — flagged for manual review"],
    "recommended_action": "monitor",
}
```
