"""
Tool definitions (JSON schemas) for the Fraud Detection Agent.
These are passed to client.messages.create(tools=...) so Claude can
call specific analysis functions during its reasoning process.
"""

# Tool 1 – Analyze a single transaction against all fraud rules
ANALYZE_TRANSACTION_TOOL = {
    "name": "analyze_transaction",
    "description": (
        "Analyze a single banking transaction against all four fraud rules: "
        "high amount, unusual location, rapid succession, and international origin. "
        "Returns risk level (Safe/Suspicious/High Risk) and fraud reasons."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "transaction_id":   {"type": "string",  "description": "Unique ID of the transaction"},
            "customer_id":      {"type": "string",  "description": "ID of the customer"},
            "amount":           {"type": "number",  "description": "Transaction amount in INR"},
            "location":         {"type": "string",  "description": "Location where transaction occurred"},
            "transaction_type": {
                "type": "string",
                "enum": ["purchase", "withdrawal", "transfer", "deposit", "payment", "refund"],
            },
            "time":             {"type": "string",  "description": "ISO-8601 datetime of the transaction"},
        },
        "required": ["transaction_id", "customer_id", "amount",
                     "location", "transaction_type", "time"],
    },
}

# Tool 2 – Check transaction history for a customer
CHECK_CUSTOMER_HISTORY_TOOL = {
    "name": "check_customer_history",
    "description": (
        "Retrieve the recent transaction history for a customer "
        "to detect behavioral patterns like velocity fraud or account takeover."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id":  {"type": "string",  "description": "Customer ID to look up"},
            "hours":        {"type": "integer", "description": "How many hours back to search (default 24)"},
        },
        "required": ["customer_id"],
    },
}

# Tool 3 – Calculate fraud risk score for a transaction
CALCULATE_FRAUD_SCORE_TOOL = {
    "name": "calculate_fraud_score",
    "description": (
        "Calculate a numeric fraud risk score from 0 (no risk) to 100 (highest risk) "
        "based on all fraud indicators present in the transaction."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "high_amount_triggered":      {"type": "boolean"},
            "unusual_location_triggered": {"type": "boolean"},
            "rapid_succession_triggered": {"type": "boolean"},
            "international_triggered":    {"type": "boolean"},
            "amount":                     {"type": "number",  "description": "Transaction amount in INR"},
        },
        "required": [
            "high_amount_triggered", "unusual_location_triggered",
            "rapid_succession_triggered", "international_triggered", "amount",
        ],
    },
}

# Tool 4 – Generate a fraud investigation report
GENERATE_FRAUD_REPORT_TOOL = {
    "name": "generate_fraud_report",
    "description": (
        "Generate a detailed fraud investigation report for a transaction, "
        "including classification, fraud reasons, risk score, and recommended actions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "transaction_id":  {"type": "string"},
            "risk_level":      {"type": "string", "enum": ["Safe", "Suspicious", "High Risk"]},
            "fraud_reasons":   {"type": "array",  "items": {"type": "string"}},
            "risk_score":      {"type": "number", "description": "0–100"},
            "amount":          {"type": "number"},
            "location":        {"type": "string"},
            "customer_id":     {"type": "string"},
            "recommended_action": {
                "type": "string",
                "enum": ["none", "monitor", "alert_customer", "block_transaction", "escalate"],
            },
        },
        "required": ["transaction_id", "risk_level", "fraud_reasons",
                     "risk_score", "amount", "location", "customer_id"],
    },
}

# Pass this to every client.messages.create(tools=ALL_TOOLS)
ALL_TOOLS = [
    ANALYZE_TRANSACTION_TOOL,
    CHECK_CUSTOMER_HISTORY_TOOL,
    CALCULATE_FRAUD_SCORE_TOOL,
    GENERATE_FRAUD_REPORT_TOOL,
]
