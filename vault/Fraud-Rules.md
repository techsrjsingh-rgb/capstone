---
tags: [rules, fraud-detection, thresholds]
---

# 📋 Fraud Detection Rules

Source: `core/rules.py` · Config: `config/settings.py` · See also: [[Agents/Rules-Agent]]

---

## The Four Rules

| # | Rule | Trigger | Score Weight |
|---|------|---------|--------------|
| 1 | 💸 High Amount | Amount ≥ ₹1,00,000 | +35 pts (up to +50 for ₹3,00,000+) |
| 2 | 📍 Unusual Location | Matches fraud hotspot keyword | +30 pts |
| 3 | ⚡ Rapid Succession | 3+ transactions in 5 minutes (same customer) | +25 pts |
| 4 | 🌍 International | Location is outside India | +20 pts |

**Classification:**
- 0 rules → ✅ **Safe** (score 0)
- 1 rule → ⚠️ **Suspicious** (score 25–35)
- 2+ rules → 🚨 **High Risk** (score 50–100)

---

## Rule Details

### Rule 1: High Amount

```python
HIGH_AMOUNT_THRESHOLD = 100_000  # ₹1,00,000
```

- `amount >= 300_000` → "Very high amount: ₹X exceeds ₹3,00,000" (+50 pts)
- `amount >= 100_000` → "High amount: ₹X exceeds threshold" (+35 pts)

**Test transactions:** TXN006 (₹1,50,000), TXN007 (₹5,00,000), TXN008 (₹1,20,000)

---

### Rule 2: Unusual Location

Matches any of these keywords in the location string (case-insensitive):

```
nigeria · lagos · abuja · unknown · anonymous
offshore · cayman · panama · dark web
```

**Test transactions:** TXN009 (Lagos, Nigeria), TXN010 (Unknown), TXN011 (Panama)

---

### Rule 3: Rapid Succession

```python
RAPID_TXN_WINDOW_SEC = 300   # 5 minutes
RAPID_TXN_COUNT      = 3     # 3+ transactions
```

Counts all transactions by the same `customer_id` within ±5 minutes. If 3 or more exist → triggered.

**Test transactions:** TXN012/013/014 (CUST_L, 17:00/17:02/17:04), TXN015/016/017 (CUST_M, 17:10/17:12/17:13)

---

### Rule 4: International

Marks a transaction as international if the location does not contain any Indian city/country keyword:

```
india · mumbai · delhi · bangalore · bengaluru · chennai
hyderabad · pune · ahmedabad · kolkata · jaipur · surat
lucknow · kanpur · nagpur · visakhapatnam · indore · bhopal
```

**Test transactions:** TXN018 (New York, USA), TXN019 (London, UK)

---

## Score Calculation

```python
score = 0
if high_amount:     score += 35  # up to +50 for very high
if unusual_loc:     score += 30
if rapid_succession: score += 25
if international:   score += 20
score = min(score, 100)
```

Risk bands: 0–39 = Safe · 40–69 = Suspicious · 70–100 = High Risk
