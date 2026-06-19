# Governance Report
## Fraud Detection AI Agent

**Version:** 1.0  
**Date:** June 2026

---

## 1. Overview

This report describes the governance controls implemented in the Fraud Detection AI Agent to ensure the system is **fair**, **compliant**, **auditable**, and **robust** against misuse.

---

## 2. Input Validation

All transactions are validated by `shared/governance.py → GovernanceManager.validate_transaction()` before entering the agent pipeline.

### Required Fields
| Field | Type | Validation Rule |
|-------|------|----------------|
| transaction_id | string | Non-empty |
| customer_id | string | Non-empty |
| amount | number | ≥ 0 |
| location | string | Non-empty |
| transaction_type | enum | One of: purchase, withdrawal, transfer, deposit, payment, refund |
| time | string | Non-empty |

### Rejection Behavior
- Invalid transactions raise `ValueError` in the pre-process hook
- The hook returns a safe fallback result (`"Suspicious"`) instead of crashing
- All rejections are recorded in the audit log

---

## 3. Rate Limiting

**Class:** `shared/governance.py → RateLimiter`  
**Algorithm:** Token bucket (sliding window)  
**Limit:** 20 requests per 60-second window  

This prevents:
- API abuse / DoS attacks on the agent endpoint
- Runaway Streamlit re-runs consuming excessive tokens
- Unintentional load testing of the Anthropic API

---

## 4. Compliance Checks

Every agent decision passes `GovernanceManager.check_compliance()`:

| Check | Rule | Action on Failure |
|-------|------|------------------|
| Valid decision value | Must be "Safe", "Suspicious", or "High Risk" | Override to "Suspicious" |
| Non-empty explanation | Reasoning must be ≥ 15 characters | Override to "Suspicious" |

Compliance overrides are flagged in the result with `compliance_override: True`.

---

## 5. Fairness and Bias Detection

`GovernanceManager.check_fairness()` flags potentially biased decisions:

**Rule:** If a transaction is classified as "High Risk" but the amount is below the high-amount threshold, and the only trigger appears to be location — a fairness flag is raised for human review.

**Why:** Location-only High Risk decisions could disproportionately affect customers from certain regions without sufficient financial evidence.

**Response:** Flagged transactions appear with `fairness_flags` in the result. The flag does not override the decision — it adds a note for the human reviewer.

---

## 6. Audit Logging

**File:** `audit.jsonl` (append-only)  
**Format:** One JSON object per line (JSONL)  

Every audit record contains:
```json
{
  "timestamp": "2026-06-15T10:30:00Z",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent": "FraudDetectionAgent",
  "action": "decision",
  "data": "{ transaction_id: TXN001, risk_level: Safe, ... }"
}
```

**Audit events logged:**
1. `pre_process` — transaction entered the system
2. `decision` — final classification produced
3. `error` — any exception in the pipeline

**Retention:** Logs are appended indefinitely. Set up external log rotation for production.

---

## 7. Observability

**Module:** `shared/observability.py → ObservabilityManager`

- **Correlation IDs:** Every request gets a UUID that ties together all 4 agent calls
- **Agent Traces:** Duration, input summary, output summary for each agent
- **Decision Log:** Final classification + confidence + reasoning snippet
- **Metrics:** `fraud_classification` (count per risk level), `risk_score`, `agent_error`

All traces are stored in-memory and accessible via `get_audit_trail(correlation_id)`.

---

## 8. Explainability

Every fraud decision includes:
1. **Fraud reasons** — which specific rules triggered and why
2. **Risk score** — numeric 0–100 score explaining the overall risk level
3. **Agent explanation** — human-readable text from the Coordinator Agent
4. **Agent trace** — which agents ran and what they found
5. **Recommended action** — none / monitor / alert_customer / block_transaction / escalate

This satisfies explainable AI (XAI) requirements for financial services regulation.

---

## 9. Data Privacy

- No customer PII beyond transaction fields is stored permanently
- The audit log stores data summaries (truncated to 400 chars), not full records
- The Anthropic API receives only the transaction fields needed for analysis
- No API keys, credentials, or PII appear in any log files

---

## 10. Controls Summary

| Control | Implemented By | Status |
|---------|---------------|--------|
| Input validation | governance.validate_transaction() | ✅ Active |
| Rate limiting | RateLimiter (token bucket) | ✅ Active |
| Compliance check | governance.check_compliance() | ✅ Active |
| Fairness check | governance.check_fairness() | ✅ Active |
| Audit logging | governance.audit_log() → JSONL | ✅ Active |
| Correlation IDs | observability.generate_correlation_id() | ✅ Active |
| Error fallback | hooks.on_error() → Suspicious | ✅ Active |
| Explainability | fraud_reasons + explanation + trace | ✅ Active |
| Data minimization | Truncated audit summaries | ✅ Active |
