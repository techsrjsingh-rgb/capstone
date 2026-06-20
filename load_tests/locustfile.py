"""
locustfile.py — Load Tests for Fraud Detection System
=======================================================
Tests the MCP server HTTP endpoints under concurrent load.

Run with:
    locust -f load_tests/locustfile.py --host=http://localhost:8002

Then open http://localhost:8089 to configure and start the swarm.

Targets:
  - Fraud DB MCP server (port 8002)
  - Geo Risk MCP server (port 8003)
"""

from locust import HttpUser, task, between


class FraudMCPUser(HttpUser):
    """Simulates concurrent requests to the Fraud DB MCP server (port 8002)."""

    wait_time = between(0.5, 2.0)   # random wait between tasks
    host = "http://localhost:8002"

    @task(3)
    def get_transaction_history(self):
        """Most frequent operation — fetch transaction history for a customer."""
        self.client.post(
            "/tools/get_transaction_history",
            json={"customer_id": "CUST_L", "hours": 24},
            name="/tools/get_transaction_history",
        )

    @task(2)
    def get_fraud_blacklist(self):
        """Check the fraud blacklist."""
        self.client.post(
            "/tools/get_fraud_blacklist",
            json={},
            name="/tools/get_fraud_blacklist",
        )

    @task(1)
    def get_fraud_statistics(self):
        """Fetch aggregate statistics — least frequent."""
        self.client.post(
            "/tools/get_fraud_statistics",
            json={},
            name="/tools/get_fraud_statistics",
        )

    @task(1)
    def report_fraud_transaction(self):
        """Report a transaction as confirmed fraud."""
        self.client.post(
            "/tools/report_fraud_transaction",
            json={"transaction_id": "TXN_LOAD_TEST", "reason": "load test"},
            name="/tools/report_fraud_transaction",
        )


class GeoMCPUser(HttpUser):
    """Simulates concurrent requests to the Geo Risk MCP server (port 8003)."""

    wait_time = between(0.5, 2.0)
    host = "http://localhost:8003"

    @task(3)
    def get_country_risk_score(self):
        """Look up country risk for various locations."""
        locations = ["Lagos, Nigeria", "Mumbai, India", "London, UK", "Unknown"]
        for loc in locations:
            self.client.post(
                "/tools/get_country_risk_score",
                json={"location": loc},
                name="/tools/get_country_risk_score",
            )

    @task(2)
    def verify_domestic_location(self):
        """Verify domestic vs international location."""
        self.client.post(
            "/tools/verify_domestic_location",
            json={"location": "Mumbai, India"},
            name="/tools/verify_domestic_location",
        )

    @task(1)
    def get_high_risk_regions(self):
        """Fetch all high-risk regions."""
        self.client.post(
            "/tools/get_high_risk_regions",
            json={},
            name="/tools/get_high_risk_regions",
        )
