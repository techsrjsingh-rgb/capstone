"""
MCP Server 1 – Fraud Transaction Database
Provides tools related to transaction history and fraud blacklists.

Run this server before starting the Streamlit app:
  python fraud_detection/mcp_server_fraud.py

Tools exposed:
  get_transaction_history  – recent transactions for a customer
  get_fraud_blacklist      – list of known fraudulent accounts
  report_fraud_transaction – mark a transaction as confirmed fraud
  get_fraud_statistics     – summary stats for the fraud database
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.server.fastmcp import FastMCP
from shared.config import config

# Create the FastMCP application — "fraud-db" is the server name
app = FastMCP("fraud-db", port=config.FRAUD_MCP_PORT)


# ──────────────────────────────────────────────────────────────────
# Simulated in-memory databases
# ──────────────────────────────────────────────────────────────────

TRANSACTION_HISTORY = {
    "CUST_L": [
        {"txn_id": "TXN012", "amount": 2000,  "time": "2024-06-15T17:00:00", "location": "Mumbai"},
        {"txn_id": "TXN013", "amount": 1800,  "time": "2024-06-15T17:02:00", "location": "Mumbai"},
    ],
    "CUST_M": [
        {"txn_id": "TXN015", "amount": 3000, "time": "2024-06-15T17:10:00", "location": "Delhi"},
        {"txn_id": "TXN016", "amount": 2500, "time": "2024-06-15T17:12:00", "location": "Delhi"},
    ],
}

FRAUD_BLACKLIST = {
    "CUST_BLACKLISTED_001": {"reason": "Card skimming", "date_added": "2024-01-15"},
    "CUST_BLACKLISTED_002": {"reason": "Identity theft", "date_added": "2024-03-20"},
    "CUST_BLACKLISTED_003": {"reason": "Money laundering", "date_added": "2024-05-10"},
}


# ──────────────────────────────────────────────────────────────────
# Tool 1: Recent transaction history
# ──────────────────────────────────────────────────────────────────

@app.tool()
def get_transaction_history(customer_id: str, hours: int = 24) -> dict:
    """
    Retrieve recent transactions for a customer within the given time window.
    Used to detect velocity fraud (many transactions in short time).
    """
    history = TRANSACTION_HISTORY.get(customer_id, [])
    return {
        "customer_id": customer_id,
        "hours_window": hours,
        "transaction_count": len(history),
        "transactions": history,
        "velocity_flag": len(history) >= config.RAPID_TXN_COUNT - 1,
    }


# ──────────────────────────────────────────────────────────────────
# Tool 2: Fraud blacklist check
# ──────────────────────────────────────────────────────────────────

@app.tool()
def get_fraud_blacklist() -> dict:
    """
    Return the complete list of blacklisted customer accounts.
    Agents use this to immediately flag transactions from known fraudsters.
    """
    return {
        "blacklisted_count": len(FRAUD_BLACKLIST),
        "accounts": FRAUD_BLACKLIST,
    }


# ──────────────────────────────────────────────────────────────────
# Tool 3: Report confirmed fraud
# ──────────────────────────────────────────────────────────────────

@app.tool()
def report_fraud_transaction(transaction_id: str, reason: str) -> dict:
    """Mark a transaction as confirmed fraud in the database."""
    return {
        "status": "recorded",
        "transaction_id": transaction_id,
        "reason": reason,
        "message": f"Transaction {transaction_id} flagged as confirmed fraud: {reason}",
    }


# ──────────────────────────────────────────────────────────────────
# Tool 4: Fraud statistics
# ──────────────────────────────────────────────────────────────────

@app.tool()
def get_fraud_statistics() -> dict:
    """Return aggregate fraud statistics for the current period."""
    return {
        "period": "2024-06",
        "total_transactions_processed": 1250,
        "fraud_detected": 47,
        "false_positives": 8,
        "fraud_rate_pct": 3.76,
        "avg_fraud_amount": 85000,
        "top_fraud_locations": ["Lagos, Nigeria", "Unknown", "Panama"],
        "top_fraud_types": ["transfer", "withdrawal"],
    }


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Starting Fraud DB MCP Server on port {config.FRAUD_MCP_PORT}...")
    print("Tools: get_transaction_history, get_fraud_blacklist,")
    print("       report_fraud_transaction, get_fraud_statistics")
    app.run(transport="sse")
