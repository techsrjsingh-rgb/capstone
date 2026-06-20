"""
MCP Server 2 – Geolocation & Country Risk Data
Provides geographic context for fraud analysis.

Run this server before starting the Streamlit app:
  python mcp/mcp_server_geo.py

Tools exposed:
  get_country_risk_score    – risk level for a given country
  check_ip_location         – resolve an IP to a location (simulated)
  get_high_risk_regions     – list all high-risk regions
  verify_domestic_location  – confirm if a location is within India
"""

from mcp.server.fastmcp import FastMCP
from config.settings import config

app = FastMCP("geo-risk-db", port=config.GEO_MCP_PORT)


# ──────────────────────────────────────────────────────────────────
# Country risk database (simulated)
# ──────────────────────────────────────────────────────────────────

COUNTRY_RISK = {
    "india":             {"risk_score": 20, "tier": "low",    "international": False},
    "nigeria":           {"risk_score": 85, "tier": "high",   "international": True},
    "ghana":             {"risk_score": 70, "tier": "high",   "international": True},
    "usa":               {"risk_score": 25, "tier": "low",    "international": True},
    "uk":                {"risk_score": 20, "tier": "low",    "international": True},
    "cayman islands":    {"risk_score": 80, "tier": "high",   "international": True},
    "panama":            {"risk_score": 75, "tier": "high",   "international": True},
    "uae":               {"risk_score": 35, "tier": "medium", "international": True},
    "singapore":         {"risk_score": 15, "tier": "low",    "international": True},
    "unknown":           {"risk_score": 95, "tier": "critical","international": True},
    "anonymous":         {"risk_score": 95, "tier": "critical","international": True},
    "offshore":          {"risk_score": 90, "tier": "critical","international": True},
}


# ──────────────────────────────────────────────────────────────────
# Tool 1: Country risk score
# ──────────────────────────────────────────────────────────────────

@app.tool()
def get_country_risk_score(location: str) -> dict:
    """
    Return the fraud risk score (0–100) and tier for a given location string.
    Matches by checking if any known country name appears in the location.
    """
    loc_lower = location.lower().strip()

    for country, data in COUNTRY_RISK.items():
        if country in loc_lower:
            return {
                "location": location,
                "matched_country": country,
                "risk_score": data["risk_score"],
                "risk_tier": data["tier"],
                "is_international": data["international"],
                "recommendation": _risk_recommendation(data["tier"]),
            }

    # Unknown location — treat as medium risk
    return {
        "location": location,
        "matched_country": "unrecognised",
        "risk_score": 50,
        "risk_tier": "medium",
        "is_international": True,
        "recommendation": "Verify location manually",
    }


# ──────────────────────────────────────────────────────────────────
# Tool 2: Check IP location (simulated)
# ──────────────────────────────────────────────────────────────────

@app.tool()
def check_ip_location(ip_address: str) -> dict:
    """
    Resolve an IP address to an approximate location (simulated).
    In production this would call an IP geolocation API.
    """
    # Simulate a few known IPs
    ip_map = {
        "192.168.0.1": {"country": "India",   "city": "Mumbai",  "risk": "low"},
        "41.0.0.1":    {"country": "Nigeria",  "city": "Lagos",   "risk": "high"},
        "0.0.0.0":     {"country": "Unknown",  "city": "Unknown", "risk": "critical"},
    }
    result = ip_map.get(ip_address, {
        "country": "India", "city": "Unknown city", "risk": "medium"
    })
    return {"ip_address": ip_address, **result}


# ──────────────────────────────────────────────────────────────────
# Tool 3: List all high-risk regions
# ──────────────────────────────────────────────────────────────────

@app.tool()
def get_high_risk_regions() -> dict:
    """Return all regions classified as high or critical risk."""
    high_risk = {
        k: v for k, v in COUNTRY_RISK.items()
        if v["tier"] in ("high", "critical")
    }
    return {
        "high_risk_region_count": len(high_risk),
        "regions": high_risk,
    }


# ──────────────────────────────────────────────────────────────────
# Tool 4: Verify domestic location
# ──────────────────────────────────────────────────────────────────

@app.tool()
def verify_domestic_location(location: str) -> dict:
    """
    Confirm whether a location string refers to a domestic (India) location.
    Returns True if domestic, False if international.
    """
    loc_lower = location.lower()
    indian_keywords = [
        "india", "mumbai", "delhi", "bangalore", "bengaluru", "chennai",
        "hyderabad", "pune", "ahmedabad", "kolkata", "jaipur", "surat",
        "lucknow", "nagpur", "indore", "bhopal", "visakhapatnam",
    ]
    is_domestic = any(kw in loc_lower for kw in indian_keywords)
    return {
        "location": location,
        "is_domestic": is_domestic,
        "country": "India" if is_domestic else "International/Unknown",
    }


# ──────────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────────

def _risk_recommendation(tier: str) -> str:
    return {
        "low":      "Allow with standard monitoring",
        "medium":   "Allow with enhanced monitoring",
        "high":     "Flag for manual review",
        "critical": "Block and escalate immediately",
    }.get(tier, "Review manually")


# ──────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Starting Geo Risk MCP Server on port {config.GEO_MCP_PORT}...")
    print("Tools: get_country_risk_score, check_ip_location,")
    print("       get_high_risk_regions, verify_domestic_location")
    app.run(transport="sse")
