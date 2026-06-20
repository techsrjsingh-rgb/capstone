"""
data.py — Sample Banking Transaction Dataset
=============================================
This file contains 22 fake bank transactions that we use to test our
fraud detection agent.

Why fake data?
  In a real bank, we would connect to a live database.
  For learning purposes, we create our own sample data so we can
  run the app without needing any external database.

Each transaction has 6 fields:
  transaction_id   → a unique code like "TXN001" to identify the transaction
  customer_id      → who made the transaction (e.g. "CUST_A")
  amount           → how much money was transferred, in Indian Rupees (₹)
  location         → the city/country where the transaction happened
  transaction_type → what kind of transaction: purchase, transfer, withdrawal, etc.
  time             → when it happened, in the format YYYY-MM-DDTHH:MM:SS

The 22 transactions are grouped into 5 categories so we can test every fraud rule:
  Group 1 — Safe:              small domestic transactions, all rules pass
  Group 2 — High Amount:       very large transfers that trigger the high-amount rule
  Group 3 — Unusual Location:  transactions from known fraud hotspots
  Group 4 — Rapid Succession:  the same customer making many transactions in minutes
  Group 5 — International:     transactions from outside India
  Group 6 — Multi-flag:        transactions that break multiple rules at once (High Risk)
"""

# SAMPLE_TRANSACTIONS is a Python list of dictionaries.
# Each dictionary = one bank transaction.
SAMPLE_TRANSACTIONS = [

    # ──────────────────────────────────────────────────────────────
    # GROUP 1: SAFE TRANSACTIONS
    # These are normal everyday transactions. Small amounts, Indian cities,
    # no back-to-back behavior. All fraud rules should pass → classified as SAFE.
    # ──────────────────────────────────────────────────────────────

    {
        "transaction_id": "TXN001",        # unique ID for this transaction
        "customer_id":    "CUST_A",        # the customer who paid
        "amount":         1500.00,         # ₹1,500 — small grocery/online purchase
        "location":       "Mumbai, India", # domestic city → not suspicious
        "transaction_type": "purchase",    # buying something
        "time":           "2024-06-15T09:30:00",  # morning transaction
    },
    {
        "transaction_id": "TXN002",
        "customer_id":    "CUST_B",
        "amount":         4200.00,         # ₹4,200 — utility bill payment
        "location":       "Delhi, India",
        "transaction_type": "payment",
        "time":           "2024-06-15T10:00:00",
    },
    {
        "transaction_id": "TXN003",
        "customer_id":    "CUST_C",
        "amount":         800.00,          # ₹800 — small purchase, very normal
        "location":       "Bangalore, India",
        "transaction_type": "purchase",
        "time":           "2024-06-15T11:15:00",
    },
    {
        "transaction_id": "TXN004",
        "customer_id":    "CUST_D",
        "amount":         25000.00,        # ₹25,000 — below ₹1,00,000 threshold → Safe
        "location":       "Chennai, India",
        "transaction_type": "transfer",
        "time":           "2024-06-15T12:00:00",
    },
    {
        "transaction_id": "TXN005",
        "customer_id":    "CUST_E",
        "amount":         3500.00,
        "location":       "Hyderabad, India",
        "transaction_type": "withdrawal",
        "time":           "2024-06-15T13:30:00",
    },

    # ──────────────────────────────────────────────────────────────
    # GROUP 2: HIGH AMOUNT TRANSACTIONS
    # Our rule says: any transaction above ₹1,00,000 is suspicious.
    # Why? Because most normal people don't transfer lakhs of rupees
    # in a single transaction. A fraudster might try to quickly move
    # stolen money in one large transfer before the bank catches them.
    # ──────────────────────────────────────────────────────────────

    {
        "transaction_id": "TXN006",
        "customer_id":    "CUST_F",
        "amount":         150000.00,       # ₹1,50,000 — above the ₹1,00,000 limit → Suspicious
        "location":       "Pune, India",
        "transaction_type": "transfer",
        "time":           "2024-06-15T14:00:00",
    },
    {
        "transaction_id": "TXN007",
        "customer_id":    "CUST_G",
        "amount":         500000.00,       # ₹5,00,000 — extremely large → High Risk
        "location":       "Kolkata, India",
        "transaction_type": "withdrawal",  # withdrawing ₹5 lakh at once is a red flag
        "time":           "2024-06-15T14:30:00",
    },
    {
        "transaction_id": "TXN008",
        "customer_id":    "CUST_H",
        "amount":         120000.00,       # ₹1,20,000 — just above threshold → Suspicious
        "location":       "Ahmedabad, India",
        "transaction_type": "purchase",
        "time":           "2024-06-15T15:00:00",
    },

    # ──────────────────────────────────────────────────────────────
    # GROUP 3: UNUSUAL LOCATION TRANSACTIONS
    # Some locations around the world are known to have very high
    # rates of banking fraud. Our agent keeps a list of these places.
    # A transaction from Lagos (Nigeria) or an "Unknown" location
    # is automatically flagged as suspicious.
    # ──────────────────────────────────────────────────────────────

    {
        "transaction_id": "TXN009",
        "customer_id":    "CUST_I",
        "amount":         5000.00,
        "location":       "Lagos, Nigeria",  # Lagos is on our fraud hotspot list → flagged
        "transaction_type": "purchase",
        "time":           "2024-06-15T15:30:00",
    },
    {
        "transaction_id": "TXN010",
        "customer_id":    "CUST_J",
        "amount":         8000.00,
        "location":       "Unknown",          # "Unknown" location means we can't verify it → very dangerous
        "transaction_type": "transfer",
        "time":           "2024-06-15T16:00:00",
    },
    {
        "transaction_id": "TXN011",
        "customer_id":    "CUST_K",
        "amount":         45000.00,
        "location":       "Panama",           # Panama is an offshore tax haven used for money laundering
        "transaction_type": "transfer",
        "time":           "2024-06-15T16:30:00",
    },

    # ──────────────────────────────────────────────────────────────
    # GROUP 4: RAPID SUCCESSION TRANSACTIONS
    # Our rule says: if the same customer makes 3 or more transactions
    # within 5 minutes, something unusual is happening.
    # Why? A fraudster who steals a card tries to use it as fast as
    # possible, before the real owner blocks it. Multiple small charges
    # in a few minutes is a classic fraud pattern.
    #
    # TXN012, TXN013, TXN014 all come from CUST_L within 4 minutes.
    # TXN015, TXN016, TXN017 all come from CUST_M within 3 minutes.
    # ──────────────────────────────────────────────────────────────

    {
        "transaction_id": "TXN012",
        "customer_id":    "CUST_L",          # first transaction from CUST_L
        "amount":         2000.00,
        "location":       "Mumbai, India",
        "transaction_type": "purchase",
        "time":           "2024-06-15T17:00:00",  # 5:00 PM
    },
    {
        "transaction_id": "TXN013",
        "customer_id":    "CUST_L",          # same customer, 2 minutes later
        "amount":         1800.00,
        "location":       "Mumbai, India",
        "transaction_type": "purchase",
        "time":           "2024-06-15T17:02:00",  # 5:02 PM — only 2 minutes after TXN012!
    },
    {
        "transaction_id": "TXN014",
        "customer_id":    "CUST_L",          # same customer again — 3rd transaction in 4 minutes!
        "amount":         1500.00,
        "location":       "Mumbai, India",
        "transaction_type": "purchase",
        "time":           "2024-06-15T17:04:00",  # 5:04 PM → triggers the rapid succession rule
    },
    {
        "transaction_id": "TXN015",
        "customer_id":    "CUST_M",          # first transaction from CUST_M
        "amount":         3000.00,
        "location":       "Delhi, India",
        "transaction_type": "withdrawal",
        "time":           "2024-06-15T17:10:00",
    },
    {
        "transaction_id": "TXN016",
        "customer_id":    "CUST_M",          # second rapid withdrawal
        "amount":         2500.00,
        "location":       "Delhi, India",
        "transaction_type": "withdrawal",
        "time":           "2024-06-15T17:12:00",  # 2 minutes after TXN015
    },
    {
        "transaction_id": "TXN017",
        "customer_id":    "CUST_M",          # third withdrawal in 3 minutes → flagged!
        "amount":         2000.00,
        "location":       "Delhi, India",
        "transaction_type": "withdrawal",
        "time":           "2024-06-15T17:13:00",  # only 3 minutes after first transaction
    },

    # ──────────────────────────────────────────────────────────────
    # GROUP 5: INTERNATIONAL TRANSACTIONS
    # Our bank is Indian, so transactions from outside India are
    # flagged as suspicious. The customer might be travelling, but
    # it's important to flag it for review just in case.
    # ──────────────────────────────────────────────────────────────

    {
        "transaction_id": "TXN018",
        "customer_id":    "CUST_N",
        "amount":         15000.00,
        "location":       "New York, USA",   # outside India → flagged as international
        "transaction_type": "purchase",
        "time":           "2024-06-15T18:00:00",
    },
    {
        "transaction_id": "TXN019",
        "customer_id":    "CUST_O",
        "amount":         7500.00,
        "location":       "London, UK",      # UK is also outside India → flagged
        "transaction_type": "payment",
        "time":           "2024-06-15T18:30:00",
    },

    # ──────────────────────────────────────────────────────────────
    # GROUP 6: MULTI-FLAG (HIGH RISK) COMBINATIONS
    # These transactions break TWO or more rules at the same time.
    # When multiple fraud rules trigger together, the risk is much higher.
    # For example: a huge amount sent to a known fraud country is extremely suspicious.
    # ──────────────────────────────────────────────────────────────

    {
        "transaction_id": "TXN020",
        "customer_id":    "CUST_P",
        "amount":         200000.00,         # Rule 1: very high amount (₹2,00,000)
        "location":       "Lagos, Nigeria",  # Rule 2: known fraud hotspot
        "transaction_type": "transfer",      # transferring money to a fraud country → HIGH RISK
        "time":           "2024-06-15T19:00:00",
    },
    {
        "transaction_id": "TXN021",
        "customer_id":    "CUST_Q",
        "amount":         180000.00,         # Rule 1: high amount (₹1,80,000)
        "location":       "Cayman Islands",  # Rule 2: offshore tax haven used in money laundering
        "transaction_type": "transfer",      # two rules at once → HIGH RISK
        "time":           "2024-06-15T19:30:00",
    },
    {
        "transaction_id": "TXN022",
        "customer_id":    "CUST_R",
        "amount":         50000.00,          # below ₹1,00,000 threshold
        "location":       "Bangalore, India",
        "transaction_type": "deposit",       # depositing money — less suspicious than transfer
        "time":           "2024-06-15T20:00:00",  # Safe — no rules triggered
    },
]
