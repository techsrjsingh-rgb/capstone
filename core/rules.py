"""
rules.py — Fraud Detection Rules Engine
========================================
This file contains the core fraud detection logic written in plain Python.
There are NO AI calls here — these are simple if/else checks that run instantly.

Why separate rules from AI?
  - Rules are fast (no internet needed, no API cost)
  - Rules are easy to test and understand
  - The AI agent later ENRICHES these rule results with deeper explanations

Four Fraud Rules:
  Rule 1 — High Amount:        transaction above ₹1,00,000 is suspicious
  Rule 2 — Unusual Location:   transaction from a known fraud country/city
  Rule 3 — Rapid Succession:   same customer making 3+ transactions in 5 minutes
  Rule 4 — International:      transaction from outside India

How classification works:
  0 rules triggered → SAFE
  1 rule triggered  → SUSPICIOUS
  2+ rules triggered → HIGH RISK
"""

from datetime import datetime   # used to compare transaction times

from config.settings import config   # loads thresholds like ₹1,00,000 from config.py


class FraudDetectionRules:
    """
    This class holds all four fraud rules.

    How to use it:
        rules = FraudDetectionRules()
        result = rules.evaluate(transaction, all_transactions)
        print(result["risk_level"])   # "Safe", "Suspicious", or "High Risk"
    """

    # ──────────────────────────────────────────────────────────────────
    # RULE 1: HIGH TRANSACTION AMOUNT
    # If someone transfers a very large amount of money at once,
    # it could be a fraudster moving stolen funds quickly.
    # Our threshold is ₹1,00,000 (set in shared/config.py).
    # ──────────────────────────────────────────────────────────────────

    def check_high_amount(self, amount: float) -> tuple[bool, str]:
        """
        Check if the transaction amount is suspiciously large.

        Parameters:
            amount (float): the transaction amount in Indian Rupees

        Returns:
            (triggered, message)
            triggered = True if this rule fired, False if not
            message   = a human-readable explanation of what was found
        """
        amount = float(amount)   # make sure it's a number, not a string

        # Extra-large amounts (3x the threshold = ₹3,00,000+) are very dangerous
        if amount >= config.HIGH_AMOUNT_THRESHOLD * 3:
            return True, (
                f"Very high amount: ₹{amount:,.0f} "
                f"(threshold: ₹{config.HIGH_AMOUNT_THRESHOLD:,.0f})"
            )

        # Above ₹1,00,000 is suspicious
        elif amount >= config.HIGH_AMOUNT_THRESHOLD:
            return True, (
                f"High amount: ₹{amount:,.0f} "
                f"(exceeds ₹{config.HIGH_AMOUNT_THRESHOLD:,.0f} limit)"
            )

        # Normal amount — rule does NOT trigger
        return False, f"Normal amount: ₹{amount:,.0f}"

    # ──────────────────────────────────────────────────────────────────
    # RULE 2: UNUSUAL LOCATION
    # Some places in the world are known fraud hotspots.
    # We keep a list of these locations in shared/config.py.
    # If a transaction comes from one of them, we flag it immediately.
    # "Unknown" and "Anonymous" locations are also red flags —
    # legitimate transactions always have a real location.
    # ──────────────────────────────────────────────────────────────────

    def check_unusual_location(self, location: str) -> tuple[bool, str]:
        """
        Check if the transaction location is a known fraud hotspot.

        Parameters:
            location (str): where the transaction happened, e.g. "Lagos, Nigeria"

        Returns:
            (triggered, message)
        """
        # Convert to lowercase so comparison works regardless of capitalisation
        loc_lower = location.lower().strip()

        # Check every entry in our fraud location list
        # config.FRAUD_LOCATIONS = ["nigeria", "lagos", "unknown", "panama", ...]
        for fraud_loc in config.FRAUD_LOCATIONS:
            if fraud_loc in loc_lower:
                # Found a match — this location is on the fraud hotspot list
                return True, f"Unusual/high-risk location: '{location}'"

        # Location is NOT in the fraud list — looks normal
        return False, f"Location appears normal: '{location}'"

    # ──────────────────────────────────────────────────────────────────
    # RULE 3: RAPID SUCCESSION (velocity fraud)
    # If the same customer makes 3 or more transactions within 5 minutes,
    # it looks like someone stole their card and is using it very quickly.
    # This pattern is called "velocity fraud" in the banking industry.
    # ──────────────────────────────────────────────────────────────────

    def check_rapid_succession(
        self, transaction: dict, all_transactions: list[dict]
    ) -> tuple[bool, str]:
        """
        Check if this customer has made too many transactions in a short time.

        Parameters:
            transaction      (dict): the current transaction we're checking
            all_transactions (list): the full list of transactions (used to find recent ones)

        Returns:
            (triggered, message)
        """
        customer_id = transaction["customer_id"]
        # Parse the transaction time into a datetime object so we can do math on it
        txn_time = _parse_time(transaction["time"])

        # Find other transactions from the SAME customer that happened
        # within the time window (default: 5 minutes = 300 seconds)
        recent = [
            t for t in all_transactions
            if t["customer_id"] == customer_id                          # same customer
            and t["transaction_id"] != transaction["transaction_id"]    # not the current one
            and abs((_parse_time(t["time"]) - txn_time).total_seconds())
               <= config.RAPID_TXN_WINDOW_SEC                           # within 5 minutes
        ]

        # Count = other recent transactions + this one
        count = len(recent) + 1

        # If 3 or more transactions within the window → flag it
        if count >= config.RAPID_TXN_COUNT:
            return True, (
                f"Rapid transactions: {count} transactions from customer "
                f"'{customer_id}' within {config.RAPID_TXN_WINDOW_SEC // 60} minutes"
            )

        # Frequency is normal
        return False, f"Normal transaction frequency for customer '{customer_id}'"

    # ──────────────────────────────────────────────────────────────────
    # RULE 4: INTERNATIONAL TRANSACTION
    # Our bank is Indian, so any transaction from outside India
    # could indicate: the customer is travelling (normal), OR
    # someone abroad stole their credentials (fraud).
    # We flag all international transactions for review.
    #
    # How we detect "India": we check if the location string contains
    # "India" or any major Indian city name.
    # ──────────────────────────────────────────────────────────────────

    def check_international(self, location: str) -> tuple[bool, str]:
        """
        Check if the transaction is from outside India.

        Parameters:
            location (str): the transaction location

        Returns:
            (triggered, message)
        """
        loc_lower = location.lower().strip()

        # List of Indian city/country keywords.
        # If ANY of these appear in the location → it's domestic (safe).
        indian_keywords = [
            "india", "mumbai", "delhi", "bangalore", "bengaluru", "chennai",
            "hyderabad", "pune", "ahmedabad", "kolkata", "jaipur", "surat",
            "lucknow", "kanpur", "nagpur", "visakhapatnam", "indore", "bhopal",
        ]

        for kw in indian_keywords:
            if kw in loc_lower:
                # Location contains an Indian city/country name → domestic transaction
                return False, f"Domestic transaction: '{location}'"

        # No Indian keyword found → this is an international transaction
        return True, f"International transaction detected: '{location}'"

    # ──────────────────────────────────────────────────────────────────
    # AGGREGATE: COMBINE ALL FOUR RULES INTO A FINAL DECISION
    # After running all four checks, we combine the results:
    #   0 rules triggered → Safe
    #   1 rule triggered  → Suspicious
    #   2+ rules triggered → High Risk
    # We also compute a numeric "risk score" (0–100) for the dashboard gauge.
    # ──────────────────────────────────────────────────────────────────

    def aggregate_risk(
        self,
        high_amount_result: tuple,
        unusual_location_result: tuple,
        rapid_succession_result: tuple,
        international_result: tuple,
    ) -> tuple[str, list[str], float]:
        """
        Combine four rule results into one final classification.

        Parameters:
            high_amount_result        → output of check_high_amount()
            unusual_location_result   → output of check_unusual_location()
            rapid_succession_result   → output of check_rapid_succession()
            international_result      → output of check_international()

        Returns:
            (risk_level, fraud_reasons, risk_score)
            risk_level    = "Safe", "Suspicious", or "High Risk"
            fraud_reasons = list of human-readable reasons (shown in dashboard)
            risk_score    = a number from 0 to 100 (shown as a gauge in dashboard)
        """
        # Put all four results in a list for easy looping
        all_results = [
            high_amount_result,
            unusual_location_result,
            rapid_succession_result,
            international_result,
        ]

        # Collect only the messages where the rule actually triggered (triggered == True)
        fraud_reasons = [msg for triggered, msg in all_results if triggered]
        trigger_count = len(fraud_reasons)

        # Calculate a risk score 0–100 by adding points per triggered rule.
        # High-amount and unusual-location are weighted more heavily because
        # they are stronger fraud signals.
        risk_score = 0.0
        if high_amount_result[0]:
            risk_score += 35.0      # highest weight — direct financial risk
        if unusual_location_result[0]:
            risk_score += 30.0      # second highest — known fraud area
        if rapid_succession_result[0]:
            risk_score += 25.0      # velocity fraud
        if international_result[0]:
            risk_score += 20.0      # lower weight — might just be travelling
        risk_score = min(100.0, risk_score)   # cap at 100 so gauge doesn't overflow

        # Final classification based on how many rules triggered
        if trigger_count == 0:
            # No rules triggered → the transaction looks completely normal
            return "Safe", [], 0.0

        elif trigger_count == 1:
            # Only one rule triggered → worth watching, but not definitely fraud
            return "Suspicious", fraud_reasons, risk_score

        else:
            # Two or more rules triggered → strong fraud signal, needs immediate action
            return "High Risk", fraud_reasons, risk_score

    # ──────────────────────────────────────────────────────────────────
    # EVALUATE: Run all four rules on one transaction at once
    # This is the main method the agent calls. It runs all four checks
    # and returns everything in a single dictionary.
    # ──────────────────────────────────────────────────────────────────

    def evaluate(self, transaction: dict, all_transactions: list[dict]) -> dict:
        """
        Run all four fraud rules on a single transaction.

        Parameters:
            transaction      (dict): the transaction to check (one row from data.py)
            all_transactions (list): needed for the rapid succession check

        Returns:
            A dictionary with:
              transaction_id  → which transaction we checked
              risk_level      → "Safe", "Suspicious", or "High Risk"
              fraud_reasons   → list of triggered rule messages (shown in dashboard)
              risk_score      → 0–100 number for the gauge chart
              rule_details    → True/False for each of the 4 rules (for debugging)
        """
        # Step 1: Run each rule independently
        amount_res   = self.check_high_amount(transaction["amount"])
        location_res = self.check_unusual_location(transaction["location"])
        rapid_res    = self.check_rapid_succession(transaction, all_transactions)
        intl_res     = self.check_international(transaction["location"])

        # Step 2: Combine results into final risk level
        risk_level, fraud_reasons, risk_score = self.aggregate_risk(
            amount_res, location_res, rapid_res, intl_res
        )

        # Step 3: Return everything as a dictionary
        return {
            "transaction_id": transaction["transaction_id"],
            "risk_level":     risk_level,       # "Safe" / "Suspicious" / "High Risk"
            "fraud_reasons":  fraud_reasons,    # list of reasons shown to the user
            "risk_score":     risk_score,       # 0–100 for the gauge chart
            "rule_details": {
                # Each rule shows triggered (True/False) and the reason message
                "high_amount":      {"triggered": amount_res[0],   "message": amount_res[1]},
                "unusual_location": {"triggered": location_res[0], "message": location_res[1]},
                "rapid_succession": {"triggered": rapid_res[0],    "message": rapid_res[1]},
                "international":    {"triggered": intl_res[0],     "message": intl_res[1]},
            },
        }


# ──────────────────────────────────────────────────────────────────────
# HELPER FUNCTION: Parse a date/time string into a Python datetime object
# We need this to compare transaction times (e.g. "are these 2 transactions
# within 5 minutes of each other?")
# ──────────────────────────────────────────────────────────────────────

def _parse_time(time_str: str) -> datetime:
    """
    Convert a date string like "2024-06-15T17:02:00" into a Python datetime.
    Tries multiple formats in case the string has slight differences.
    Raises ValueError if the string can't be parsed.
    """
    # Try each format until one works
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue   # try the next format
    # None of the formats worked — raise a clear error
    raise ValueError(f"Cannot parse datetime: '{time_str}'")
